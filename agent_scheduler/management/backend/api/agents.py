"""
Management Backend - Agent 管理路由
"""

import json
import os
import tempfile
import zipfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlmodel import Session

from agent_scheduler.management.backend.core.database import get_db
from agent_scheduler.management.backend.api.deps import get_current_admin
from agent_scheduler.management.backend.models.admin_user import AdminUser
from agent_scheduler.management.backend.models.agent_config import AgentConfig
from agent_scheduler.management.backend.schemas import (
    AgentCreate, AgentUpdate, AgentResponse, AgentListResponse, MessageResponse
)
from agent_scheduler.management.backend.services import agent_service
from agent_scheduler.management.backend.services.log_service import create_log
from agent_scheduler.management.backend.services.registrar import (
    register_agent,
    find_avatar_file,
    notify_scheduler_reload,
)

router = APIRouter()


def _get_avatar_dir() -> str:
    """获取头像目录路径"""
    scheduler_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(scheduler_dir, 'avatar')


@router.get("/", response_model=AgentListResponse)
def list_agents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取 Agent 列表"""
    items, total = agent_service.list_agents(db, skip, limit)
    responses = [agent_service.agent_to_response(a) for a in items]
    return AgentListResponse(items=responses, total=total)


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    agent_in: AgentCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """创建单个 Agent"""
    existing = agent_service.get_agent_by_username(db, agent_in.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    agent = agent_service.create_agent(db, agent_in)

    avatar_path = find_avatar_file(_get_avatar_dir(), agent.name, agent.username)

    success, platform_id, error = register_agent(
        db=db,
        username=agent.username,
        avatar_path=avatar_path,
        personal_signature=agent.personal_signature if agent.personal_signature else None,
    )

    if success and platform_id:
        agent.app_platform_user_id = platform_id
        db.add(agent)
        db.commit()
        db.refresh(agent)
    else:
        print(f"[创建 Agent] 注册到 app_platform 失败: {error}")

    create_log(db, current_admin.id, "create_agent", "agent", agent.id)

    return agent_service.agent_to_response(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取 Agent 详情"""
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return agent_service.agent_to_response(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int,
    agent_in: AgentUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """更新 Agent"""
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    updated = agent_service.update_agent(db, agent_id, agent_in)

    notify_scheduler_reload("agent", agent_id)

    create_log(db, current_admin.id, "update_agent", "agent", agent_id)

    return agent_service.agent_to_response(updated)


@router.delete("/{agent_id}", response_model=MessageResponse)
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """删除 Agent"""
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    agent_service.delete_agent(db, agent_id)

    create_log(db, current_admin.id, "delete_agent", "agent", agent_id)

    return MessageResponse(message="Agent 已删除")


@router.post("/{agent_id}/restart", response_model=MessageResponse)
def restart_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """重启单个 Agent"""
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    success = notify_scheduler_reload("agent", agent_id)
    if not success:
        raise HTTPException(status_code=502, detail="无法连接 scheduler 服务")

    create_log(db, current_admin.id, "restart_agent", "agent", agent_id)

    return MessageResponse(message="Agent 重启请求已发送")


@router.post("/import", response_model=AgentListResponse)
async def import_agents(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """批量导入 Agent（上传压缩包）"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="仅支持 zip 格式压缩包")

    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            zf.extractall(tmp_dir)

        json_path = None
        for root, dirs, files in os.walk(tmp_dir):
            for f in files:
                if f.endswith('.json') and 'ai_users_config' in f.lower():
                    json_path = os.path.join(root, f)
                    break
            if json_path:
                break

        if not json_path:
            raise HTTPException(status_code=400, detail="压缩包中未找到 ai_users_config.json")

        with open(json_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        ai_users = config_data.get('ai_users', [])
        if not ai_users:
            raise HTTPException(status_code=400, detail="JSON 中未找到 ai_users 配置")

        avatar_dir = os.path.join(tmp_dir, 'avatar')
        if not os.path.exists(avatar_dir):
            avatar_dir = _get_avatar_dir()

        imported = []
        for user_data in ai_users:
            username = user_data.get('username', '')
            existing = agent_service.get_agent_by_username(db, username)
            if existing:
                print(f"[导入] 跳过已存在的用户: {username}")
                continue

            agent_in = AgentCreate(
                name=user_data.get('name', ''),
                username=username,
                monthly_logins=user_data.get('monthly_logins', 30),
                personal_signature=user_data.get('personal_signature', ''),
                personality_prompt=user_data.get('personality_prompt', ''),
                knows_ids=user_data.get('knows_ids', []),
            )
            agent = agent_service.create_agent(db, agent_in)

            avatar_path = find_avatar_file(avatar_dir, agent.name, agent.username)

            success, platform_id, error = register_agent(
                db=db,
                username=agent.username,
                avatar_path=avatar_path,
                personal_signature=agent.personal_signature if agent.personal_signature else None,
            )

            if success and platform_id:
                agent.app_platform_user_id = platform_id
                db.add(agent)
                db.commit()
                db.refresh(agent)

            imported.append(agent)

        notify_scheduler_reload("all")

        create_log(db, current_admin.id, "import_agents", "agent", details=json.dumps({"count": len(imported)}))

        responses = [agent_service.agent_to_response(a) for a in imported]
        return AgentListResponse(items=responses, total=len(imported))

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if tmp_dir and os.path.exists(tmp_dir):
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/{agent_id}/avatar", response_model=MessageResponse)
async def upload_agent_avatar(
    agent_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """上传 Agent 头像"""
    from agent_scheduler.management.backend.services.registrar import (
        _get_api_base_url,
        _get_ai_user_password,
        _login_user,
    )

    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    if not agent.app_platform_user_id:
        raise HTTPException(status_code=400, detail="Agent 尚未注册到 app_platform")

    avatar_dir = _get_avatar_dir()
    os.makedirs(avatar_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1] if file.filename else '.png'
    avatar_filename = f"{agent.name}{ext}"
    avatar_path = os.path.join(avatar_dir, avatar_filename)

    with open(avatar_path, 'wb') as f:
        content = await file.read()
        f.write(content)

    api_base_url = _get_api_base_url(db)
    password = _get_ai_user_password(db)

    import mimetypes
    token = _login_user(api_base_url, agent.username, password)
    if not token:
        raise HTTPException(status_code=502, detail="无法登录 app_platform")

    avatar_url = f"{api_base_url}/users/avatar"
    mime_type, _ = mimetypes.guess_type(avatar_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'

    with open(avatar_path, 'rb') as f:
        files = {'file': (os.path.basename(avatar_path), f, mime_type)}
        import requests
        response = requests.post(
            avatar_url,
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            timeout=30,
        )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"头像上传失败: HTTP {response.status_code}")

    create_log(db, current_admin.id, "upload_avatar", "agent", agent_id)

    return MessageResponse(message="头像上传成功")
