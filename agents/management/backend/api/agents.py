"""
Management Backend - Agent 管理路由
"""

import json
import logging
import os
import tempfile
import time
import zipfile
import asyncio
from pathlib import Path
from typing import Optional

from datetime import datetime, time as datetime_time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlmodel import func, select
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.api.deps import get_current_admin
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.models.agent_config import AgentConfig
from agents.management.backend.schemas import (
    AgentCreate, AgentUpdate, AgentResponse, AgentListResponse,
    AgentRelationUpdate, DashboardStatsResponse, MessageResponse,
    PromptInjectionRequest,
)
from agents.management.backend.services import agent_service
from agents.management.backend.services.log_service import create_log
from agents.management.backend.services.registrar import (
    register_agent,
    find_avatar_file,
    get_scheduler_status,
    notify_scheduler_reload,
    notify_scheduler_session_injection,
)

logger = logging.getLogger(__name__)

router = APIRouter()
_last_cpu_snapshot: tuple[int, int] | None = None


def _read_cpu_usage_percent() -> float:
    """读取 Linux /proc/stat 计算 CPU 使用率，首次调用用 load average 兜底。"""
    global _last_cpu_snapshot
    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            fields = f.readline().split()[1:]
        values = [int(v) for v in fields[:8]]
        idle = values[3] + values[4]
        total = sum(values)

        if _last_cpu_snapshot is None:
            _last_cpu_snapshot = (idle, total)
            load_1m = os.getloadavg()[0]
            cpu_count = os.cpu_count() or 1
            return round(min(load_1m / cpu_count * 100, 100), 1)

        last_idle, last_total = _last_cpu_snapshot
        _last_cpu_snapshot = (idle, total)
        total_delta = total - last_total
        idle_delta = idle - last_idle
        if total_delta <= 0:
            return 0.0
        return round(max(0, min((1 - idle_delta / total_delta) * 100, 100)), 1)
    except OSError:
        return 0.0


def _read_memory_usage_percent() -> float:
    """读取 Linux /proc/meminfo 计算内存使用率。"""
    try:
        meminfo: dict[str, int] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                key, value = line.split(":", 1)
                meminfo[key] = int(value.strip().split()[0])

        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        if total <= 0:
            return 0.0
        return round(max(0, min((1 - available / total) * 100, 100)), 1)
    except (OSError, ValueError):
        return 0.0


def _find_avatar_in_zip(tmp_dir: str, avatar_filename: str) -> Optional[str]:
    """在解压后的目录中查找头像文件"""
    logger.debug("查找头像: 目标文件名=%r, 搜索目录=%s", avatar_filename, tmp_dir)
    
    all_files = []
    for root, dirs, files in os.walk(tmp_dir):
        for f in files:
            all_files.append(os.path.join(root, f))
            if f.lower() == avatar_filename.lower():
                found = os.path.join(root, f)
                logger.debug("查找头像: 找到=%s", found)
                return found
    
    logger.debug("查找头像: 未找到, 目录下文件数=%d", len(all_files))
    
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
    
    logger.info("共解压 %d 个文件", len(extracted_files))
    
    return extracted_files


def _get_avatar_dir() -> str:
    """获取头像目录路径"""
    agents_dir = Path(__file__).parent.parent.parent.parent
    return str(agents_dir / 'avatar')


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


@router.get("/dashboard-stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取管理仪表盘统计。"""
    today_start = datetime.combine(datetime.utcnow().date(), datetime_time.min)

    total_roles = db.exec(select(func.count()).select_from(AgentConfig)).one()
    enabled_roles = db.exec(
        select(func.count()).select_from(AgentConfig).where(AgentConfig.is_active == True)  # noqa: E712
    ).one()
    daily_active_roles = db.exec(
        select(func.count())
        .select_from(AgentConfig)
        .where(AgentConfig.last_login_at >= today_start)
    ).one()

    return DashboardStatsResponse(
        total_roles=total_roles,
        enabled_roles=enabled_roles,
        daily_active_roles=daily_active_roles,
        cpu_usage_percent=_read_cpu_usage_percent(),
        memory_usage_percent=_read_memory_usage_percent(),
    )


@router.get("/runtime-status")
def get_agents_runtime_status(
    current_admin: AdminUser = Depends(get_current_admin),
):
    """获取 scheduler 中 Agent 线程运行状态。"""
    status_data = get_scheduler_status()
    if status_data is None:
        return {"agents": [], "scheduler_online": False}

    return {**status_data, "scheduler_online": True}


@router.get("/status-stream")
def stream_agents_runtime_status(
    current_admin: AdminUser = Depends(get_current_admin),
):
    """SSE 推送 Agent 线程运行状态。"""

    async def event_stream():
        yield f"event: init\ndata: {json.dumps({'scheduler_online': True}, ensure_ascii=False)}\n\n"

        last_payload = None
        heartbeat_ticks = 0
        while True:
            status_data = await asyncio.to_thread(get_scheduler_status)
            if status_data is None:
                payload = {"agents": [], "scheduler_online": False}
            else:
                payload = {**status_data, "scheduler_online": True}

            payload_text = json.dumps(payload, ensure_ascii=False)
            if payload_text != last_payload:
                yield f"event: status\ndata: {payload_text}\n\n"
                last_payload = payload_text
                heartbeat_ticks = 0
            else:
                heartbeat_ticks += 1
                if heartbeat_ticks >= 15:
                    yield f"event: ping\ndata: {json.dumps({'ok': True}, ensure_ascii=False)}\n\n"
                    heartbeat_ticks = 0

            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/prompt-injections", response_model=MessageResponse)
def inject_prompt_for_next_session(
    request: PromptInjectionRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """为选中的 Agent 设置下一次登录会话的一次性提示词注入。"""
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="提示词注入内容不能为空")

    valid_ids = []
    for agent_id in dict.fromkeys(request.agent_ids):
        agent = agent_service.get_agent(db, agent_id)
        if agent:
            valid_ids.append(agent_id)

    if not valid_ids:
        raise HTTPException(status_code=404, detail="未找到可注入的 Agent")

    success = notify_scheduler_session_injection(
        agent_ids=valid_ids,
        injection_type="prompt",
        content=content,
        source="management",
        metadata={"admin_id": current_admin.id},
    )
    if not success:
        raise HTTPException(status_code=502, detail="无法连接 scheduler 服务或注入失败")

    create_log(
        db,
        current_admin.id,
        "inject_prompt",
        "agent",
        details=json.dumps({"count": len(valid_ids), "agent_ids": valid_ids}, ensure_ascii=False),
    )

    return MessageResponse(message=f"已为 {len(valid_ids)} 个 Agent 设置提示词注入，将在下一次登录会话生效")


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
        logger.error("创建 Agent: 注册到 app_platform 失败: %s，回滚数据库记录", error)
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


@router.post("/{agent_id}/start", response_model=MessageResponse)
def start_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """启动单个 Agent"""
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    agent_service.update_agent(db, agent_id, AgentUpdate(is_active=True))
    notify_scheduler_reload("agent", agent_id, action="start")

    create_log(db, current_admin.id, "start_agent", "agent", agent_id)

    return MessageResponse(message="Agent 启动请求已发送")


@router.post("/{agent_id}/stop", response_model=MessageResponse)
def stop_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """停止单个 Agent"""
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    agent_service.update_agent(db, agent_id, AgentUpdate(is_active=False))
    notify_scheduler_reload("agent", agent_id, action="stop")

    create_log(db, current_admin.id, "stop_agent", "agent", agent_id)

    return MessageResponse(message="Agent 停止请求已发送")


@router.post("/batch-start", response_model=MessageResponse)
def batch_start_agents(
    agent_ids: list[int],
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """批量启动 Agent"""
    started = 0
    valid_ids = []
    for agent_id in agent_ids:
        agent = agent_service.get_agent(db, agent_id)
        if not agent:
            continue

        agent_service.update_agent(db, agent_id, AgentUpdate(is_active=True))
        valid_ids.append(agent_id)
        started += 1

    if valid_ids:
        notify_scheduler_reload("agents", valid_ids, action="start")

    create_log(db, current_admin.id, "batch_start_agents", "agent", details=json.dumps({"count": started}))

    return MessageResponse(message=f"已批量启动 {started} 个 Agent")


@router.post("/batch-stop", response_model=MessageResponse)
def batch_stop_agents(
    agent_ids: list[int],
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """批量停止 Agent"""
    stopped = 0
    valid_ids = []
    for agent_id in agent_ids:
        agent = agent_service.get_agent(db, agent_id)
        if not agent:
            continue

        agent_service.update_agent(db, agent_id, AgentUpdate(is_active=False))
        valid_ids.append(agent_id)
        stopped += 1

    if valid_ids:
        notify_scheduler_reload("agents", valid_ids, action="stop")

    create_log(db, current_admin.id, "batch_stop_agents", "agent", details=json.dumps({"count": stopped}))

    return MessageResponse(message=f"已批量停止 {stopped} 个 Agent")


@router.post("/batch-delete", response_model=MessageResponse)
def batch_delete_agents(
    agent_ids: list[int],
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """批量删除 Agent"""
    deleted = 0
    for agent_id in agent_ids:
        agent = agent_service.get_agent(db, agent_id)
        if not agent:
            continue

        notify_scheduler_reload("agent", agent_id, action="stop")
        agent_service.delete_agent(db, agent_id)
        deleted += 1

    create_log(db, current_admin.id, "batch_delete_agents", "agent", details=json.dumps({"count": deleted}))

    return MessageResponse(message=f"已批量删除 {deleted} 个 Agent")


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
        logger.debug("解压: 临时目录=%s, ZIP路径=%s", tmp_dir, tmp_path)
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
                logger.info("导入: 跳过已存在的用户: %s", username)
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
                    logger.warning("导入: 未找到 %s 的头像文件: %s", username, avatar_filename)
            
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
                logger.error("导入: 注册 %s 失败: %s，回滚数据库记录", username, error)
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
                            logger.warning("导入: 未找到 %s 的头像文件: %s", username, avatar_filename)
                    
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
    from agents.management.backend.services.registrar import (
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
