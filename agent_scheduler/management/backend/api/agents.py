"""
Management Backend - Agent 管理路由
"""

import json
import os
import tempfile
import time
import zipfile
import asyncio

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from agent_scheduler.management.backend.core.database import get_db
from agent_scheduler.management.backend.api.deps import get_current_admin
from agent_scheduler.management.backend.models.admin_user import AdminUser
from agent_scheduler.management.backend.models.agent_config import AgentConfig
from agent_scheduler.management.backend.schemas import (
    AgentCreate, AgentUpdate, AgentResponse, AgentListResponse,
    AgentRelationUpdate, MessageResponse
)
from agent_scheduler.management.backend.services import agent_service
from agent_scheduler.management.backend.services.log_service import create_log
from agent_scheduler.management.backend.services.registrar import (
    register_agent,
    find_avatar_file,
    notify_scheduler_reload,
)

router = APIRouter()


def _find_avatar_in_zip(tmp_dir: str, avatar_filename: str) -> Optional[str]:
    """在解压后的目录中查找头像文件"""
    print(f"[查找头像] 目标文件名: {avatar_filename!r}")
    print(f"[查找头像] 搜索目录: {tmp_dir}")
    
    all_files = []
    for root, dirs, files in os.walk(tmp_dir):
        for f in files:
            all_files.append(os.path.join(root, f))
            if f.lower() == avatar_filename.lower():
                found = os.path.join(root, f)
                print(f"[查找头像] 找到: {found}")
                return found
    
    print(f"[查找头像] 未找到。目录下所有文件:")
    for fp in all_files:
        print(f"  - {fp}")
    
    return None


def _extract_zip_with_encoding(zip_path: str, extract_dir: str) -> list[str]:
    """解压 ZIP 文件，处理中文文件名编码问题（GBK/UTF-8）
    
    Returns:
        解压后的文件名列表
    """
    import shutil
    extracted_files = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            # flag_bits 第 11 位表示是否使用 UTF-8 编码
            is_utf8 = (info.flag_bits & 0x800) != 0
            
            if is_utf8:
                filename = info.filename
            else:
                # 未使用 UTF-8 标记，需要用 GBK 解码
                try:
                    raw_bytes = info.filename.encode('latin-1')
                    filename = raw_bytes.decode('gbk')
                except (UnicodeDecodeError, UnicodeEncodeError):
                    filename = info.filename
            
            target_path = os.path.join(extract_dir, filename)
            
            if info.is_dir():
                os.makedirs(target_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(info) as src, open(target_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                extracted_files.append(filename)
    
    print(f"[解压] 共解压 {len(extracted_files)} 个文件:")
    for f in extracted_files:
        print(f"  - {f}")
    
    return extracted_files


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
        ai_config_id=agent.id,
    )

    if success and platform_id:
        agent.app_platform_user_id = platform_id
        db.add(agent)
        db.commit()
        db.refresh(agent)
    else:
        print(f"[创建 Agent] 注册到 app_platform 失败: {error}，回滚数据库记录")
        agent_service.delete_agent(db, agent.id)
        raise HTTPException(status_code=502, detail=f"Agent 注册到 app_platform 失败: {error}")

    if agent.is_active:
        notify_scheduler_reload("agent", agent.id, action="start")

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

    old_is_active = agent.is_active
    updated = agent_service.update_agent(db, agent_id, agent_in)

    if agent_in.is_active is not None and agent_in.is_active != old_is_active:
        if agent_in.is_active:
            notify_scheduler_reload("agent", agent_id, action="start")
        else:
            notify_scheduler_reload("agent", agent_id, action="stop")
    else:
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

    notify_scheduler_reload("agent", agent_id, action="stop")

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
        print(f"[解压] 临时目录: {tmp_dir}")
        print(f"[解压] ZIP 路径: {tmp_path}")
        _extract_zip_with_encoding(tmp_path, tmp_dir)

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
            )
            agent = agent_service.create_agent(db, agent_in)

            avatar_filename = user_data.get('avatar')
            avatar_path = None
            if avatar_filename:
                avatar_path = _find_avatar_in_zip(tmp_dir, avatar_filename)
                if not avatar_path:
                    print(f"[导入] 未找到 {username} 的头像文件: {avatar_filename}")
            
            if not avatar_path:
                avatar_path = find_avatar_file(avatar_dir, agent.name, agent.username)

            success, platform_id, error = register_agent(
                db=db,
                username=agent.username,
                avatar_path=avatar_path,
                personal_signature=agent.personal_signature if agent.personal_signature else None,
                ai_config_id=agent.id,
            )

            if success and platform_id:
                agent.app_platform_user_id = platform_id
                db.add(agent)
                db.commit()
                db.refresh(agent)
                imported.append(agent)
            else:
                print(f"[导入] 注册 {username} 失败: {error}，回滚数据库记录")
                agent_service.delete_agent(db, agent.id)

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


@router.post("/import-stream")
async def import_agents_stream(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """批量导入 Agent（SSE 流式推送）"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="仅支持 zip 格式压缩包")

    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    tmp_dir = tempfile.mkdtemp()
    _extract_zip_with_encoding(tmp_path, tmp_dir)

    json_path = None
    for root, dirs, files in os.walk(tmp_dir):
        for f in files:
            if f.endswith('.json') and 'ai_users_config' in f.lower():
                json_path = os.path.join(root, f)
                break
        if json_path:
            break

    if not json_path:
        import shutil
        os.remove(tmp_path)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="压缩包中未找到 ai_users_config.json")

    with open(json_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)

    ai_users = config_data.get('ai_users', [])
    if not ai_users:
        import shutil
        os.remove(tmp_path)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="JSON 中未找到 ai_users 配置")

    avatar_dir = os.path.join(tmp_dir, 'avatar')
    if not os.path.exists(avatar_dir):
        avatar_dir = _get_avatar_dir()

    def event_stream():
        import shutil as _shutil
        total = len(ai_users)
        success_count = 0
        exists_count = 0
        failed_count = 0

        try:
            yield f"event: start\ndata: {json.dumps({'total': total}, ensure_ascii=False)}\n\n"

            for user_data in ai_users:
                username = user_data.get('username', '')

                try:
                    existing = agent_service.get_agent_by_username(db, username)
                    if existing:
                        exists_count += 1
                        event_data = {
                            'event': 'exists',
                            'username': username,
                            'id': existing.id,
                            'app_platform_user_id': existing.app_platform_user_id,
                        }
                        yield f"event: progress\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                        continue

                    agent_in = AgentCreate(
                        name=user_data.get('name', ''),
                        username=username,
                        monthly_logins=user_data.get('monthly_logins', 30),
                        personal_signature=user_data.get('personal_signature', ''),
                        personality_prompt=user_data.get('personality_prompt', ''),
                    )
                    agent = agent_service.create_agent(db, agent_in)

                    avatar_filename = user_data.get('avatar')
                    avatar_path = None
                    if avatar_filename:
                        avatar_path = _find_avatar_in_zip(tmp_dir, avatar_filename)
                        if not avatar_path:
                            print(f"[导入] 未找到 {username} 的头像文件: {avatar_filename}")
                    
                    if not avatar_path:
                        avatar_path = find_avatar_file(avatar_dir, agent.name, agent.username)

                    success, platform_id, error = register_agent(
                        db=db,
                        username=agent.username,
                        avatar_path=avatar_path,
                        personal_signature=agent.personal_signature if agent.personal_signature else None,
                        ai_config_id=agent.id,
                    )

                    if success and platform_id:
                        agent.app_platform_user_id = platform_id
                        db.add(agent)
                        db.commit()
                        db.refresh(agent)
                        success_count += 1
                        event_data = {
                            'event': 'success',
                            'username': username,
                            'id': agent.id,
                            'app_platform_user_id': platform_id,
                        }
                    else:
                        failed_count += 1
                        agent_service.delete_agent(db, agent.id)
                        event_data = {
                            'event': 'error',
                            'username': username,
                            'message': error or '未知错误',
                        }

                    yield f"event: progress\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

                except Exception as e:
                    failed_count += 1
                    event_data = {
                        'event': 'error',
                        'username': username,
                        'message': str(e),
                    }
                    yield f"event: progress\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

                time.sleep(0.5)

            notify_scheduler_reload("all")
            create_log(db, current_admin.id, "import_agents", "agent", details=json.dumps({
                "total": total, "success": success_count, "exists": exists_count, "failed": failed_count
            }))

            done_data = {
                'total': total,
                'success': success_count,
                'exists': exists_count,
                'failed': failed_count,
            }
            yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if tmp_dir and os.path.exists(tmp_dir):
                _shutil.rmtree(tmp_dir, ignore_errors=True)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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


@router.put("/{agent_id}/relation", response_model=AgentResponse)
def update_agent_relation(
    agent_id: int,
    relation_in: AgentRelationUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """更新 Agent 相识关系"""
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    updated = agent_service.update_agent_knows(db, agent_id, relation_in.knows_ids, relation_in.bidirectional)

    notify_scheduler_reload("all")

    create_log(db, current_admin.id, "update_agent_relation", "agent", agent_id)

    return agent_service.agent_to_response(updated)
