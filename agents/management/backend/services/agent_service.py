"""
Management Backend - Agent 配置服务
"""

import json
import logging
import mimetypes
import os
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from sqlmodel import Session, col, select

from agents.logging_config import get_outbound_request_headers
from agents.management.backend.core.timezone import local_now
from agents.management.backend.models.agent_config import AgentConfig
from agents.management.backend.schemas import AgentCreate, AgentResponse, AgentUpdate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentExportArchive:
    """角色配置导出压缩包及其统计信息。"""

    path: str
    agent_count: int
    avatar_count: int


def list_agents(db: Session, skip: int = 0, limit: int = 100) -> tuple[List[AgentConfig], int]:
    """获取 Agent 列表"""
    count_stmt = select(AgentConfig)
    total = len(db.exec(count_stmt).all())

    stmt = select(AgentConfig).offset(skip).limit(limit).order_by(col(AgentConfig.id))
    items = db.exec(stmt).all()
    return list(items), total


def get_agent(db: Session, agent_id: int) -> Optional[AgentConfig]:
    """获取单个 Agent"""
    return db.get(AgentConfig, agent_id)


def get_agent_by_username(db: Session, username: str) -> Optional[AgentConfig]:
    """根据用户名获取 Agent"""
    stmt = select(AgentConfig).where(AgentConfig.username == username)
    return db.exec(stmt).first()


def create_agent(db: Session, agent_in: AgentCreate) -> AgentConfig:
    """创建 Agent"""
    db_agent = AgentConfig(
        name=agent_in.name,
        username=agent_in.username,
        monthly_logins=agent_in.monthly_logins,
        personal_signature=agent_in.personal_signature,
        personality_prompt=agent_in.personality_prompt,
        is_active=agent_in.is_active,
        model_config_id=agent_in.model_config_id,
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent


def update_agent(db: Session, agent_id: int, agent_in: AgentUpdate) -> Optional[AgentConfig]:
    """更新 Agent"""
    db_agent = db.get(AgentConfig, agent_id)
    if not db_agent:
        return None

    update_data = agent_in.model_dump(exclude_unset=True)
    update_data["updated_at"] = local_now()

    for key, value in update_data.items():
        setattr(db_agent, key, value)

    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent


def update_agent_last_login(db: Session, agent_id: int, login_at: Optional[datetime] = None) -> bool:
    """记录 Agent 最近一次成功登录时间。"""
    db_agent = db.get(AgentConfig, agent_id)
    if not db_agent:
        return False

    db_agent.last_login_at = login_at or local_now()
    db_agent.total_login_count = (db_agent.total_login_count or 0) + 1
    db_agent.updated_at = local_now()
    db.add(db_agent)
    db.commit()
    return True


def delete_agent(db: Session, agent_id: int) -> bool:
    """删除 Agent"""
    db_agent = db.get(AgentConfig, agent_id)
    if not db_agent:
        return False
    from agents.management.backend.services.short_term_memory_service import (
        delete_short_term_memory,
    )

    delete_short_term_memory(db, agent_id)
    db.delete(db_agent)
    db.commit()
    return True


def parse_knows_ids(agent: AgentConfig) -> List[int]:
    """解析 knows_ids 字段"""
    if not agent.knows_ids:
        return []
    try:
        return json.loads(agent.knows_ids)
    except (json.JSONDecodeError, TypeError):
        return []


def update_agent_knows(db: Session, agent_id: int, knows_ids: List[int], bidirectional: bool = False) -> Optional[AgentConfig]:
    """更新 Agent 的相识关系"""
    db_agent = db.get(AgentConfig, agent_id)
    if not db_agent:
        return None

    db_agent.knows_ids = json.dumps(knows_ids)
    db_agent.updated_at = local_now()
    db.add(db_agent)

    if bidirectional:
        all_agents = db.exec(select(AgentConfig)).all()
        for other in all_agents:
            if other.id == agent_id:
                continue

            other_knows = parse_knows_ids(other)
            should_have_relation = other.id in knows_ids
            has_relation = agent_id in other_knows

            if should_have_relation and not has_relation:
                other_knows.append(agent_id)
                other.knows_ids = json.dumps(other_knows)
                other.updated_at = local_now()
                db.add(other)
            elif not should_have_relation and has_relation:
                other_knows.remove(agent_id)
                other.knows_ids = json.dumps(other_knows)
                other.updated_at = local_now()
                db.add(other)

    db.commit()
    db.refresh(db_agent)
    return db_agent


def agent_to_response(agent: AgentConfig) -> AgentResponse:
    """将 Agent 配置转换为响应模型。

    Args:
        agent: 已持久化的 Agent 配置。

    Returns:
        AgentResponse: 可直接用于 API 响应的 Agent 数据。

    Raises:
        ValueError: Agent 尚未生成数据库主键。
    """
    if agent.id is None:
        raise ValueError("无法序列化尚未持久化的 Agent")

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        username=agent.username,
        monthly_logins=agent.monthly_logins,
        personal_signature=agent.personal_signature,
        personality_prompt=agent.personality_prompt,
        knows_ids=parse_knows_ids(agent),
        is_active=agent.is_active,
        model_config_id=agent.model_config_id,
        social_platform_user_id=agent.social_platform_user_id,
        last_login_at=agent.last_login_at,
        last_login_timestamp=agent.last_login_timestamp,
        total_login_count=agent.total_login_count,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _resolve_avatar_download_url(api_base_url: str, avatar_url: str) -> Optional[str]:
    """将公开平台返回的头像地址解析为可下载的 HTTP(S) URL。"""
    parsed_avatar = urlsplit(avatar_url)
    if parsed_avatar.scheme:
        return avatar_url if parsed_avatar.scheme in {"http", "https"} else None
    if parsed_avatar.netloc:
        return None

    parsed_api = urlsplit(api_base_url)
    platform_root = urlunsplit((parsed_api.scheme, parsed_api.netloc, "/", "", ""))
    return urljoin(platform_root, avatar_url.lstrip("/"))


def _avatar_filename(avatar_url: str, user_id: int, content_type: str) -> str:
    """根据头像 URL 和响应类型生成安全的归档文件名。"""
    decoded_path = unquote(urlsplit(avatar_url).path).replace("\\", "/")
    filename = decoded_path.rsplit("/", 1)[-1]
    if not filename or filename in {".", ".."}:
        filename = f"avatar_{user_id}"

    if "." not in filename:
        mime_type = content_type.split(";", 1)[0].strip().lower()
        extension = mimetypes.guess_extension(mime_type) if mime_type else None
        filename = f"{filename}{extension or '.bin'}"
    return filename


def _unique_avatar_filename(
    filename: str,
    user_id: int,
    source_url: str,
    archived_sources: dict[str, str],
) -> str:
    """避免不同远程头像在 ZIP 中因同名而相互覆盖。"""
    if filename not in archived_sources or archived_sources[filename] == source_url:
        return filename

    stem, extension = os.path.splitext(filename)
    candidate = f"{stem}_{user_id}{extension}"
    suffix = 2
    while candidate in archived_sources and archived_sources[candidate] != source_url:
        candidate = f"{stem}_{user_id}_{suffix}{extension}"
        suffix += 1
    return candidate


def _fetch_agent_avatar(
    api_base_url: str,
    agent: AgentConfig,
) -> Optional[tuple[str, bytes, str]]:
    """从 social_platform 获取角色当前头像。

    Args:
        api_base_url: social_platform API 根地址。
        agent: 待导出角色配置。

    Returns:
        Optional[tuple[str, bytes, str]]: 头像文件名、内容和来源 URL；角色没有
        公开平台映射、没有头像或下载失败时返回 ``None``。
    """
    user_id = agent.social_platform_user_id
    if user_id is None:
        return None

    try:
        profile_response = requests.get(
            f"{api_base_url}/users/{user_id}",
            headers=get_outbound_request_headers(),
            timeout=10,
        )
        if profile_response.status_code != 200:
            logger.warning(
                "导出角色头像: 获取 %s 的公开平台资料失败: HTTP %d",
                agent.username,
                profile_response.status_code,
            )
            return None

        profile_data = profile_response.json()
        if not isinstance(profile_data, dict):
            logger.warning("导出角色头像: %s 的公开平台资料格式无效", agent.username)
            return None
        avatar_url = profile_data.get("avatar_url")
        if not isinstance(avatar_url, str) or not avatar_url.strip():
            return None
        avatar_url = avatar_url.strip()
        download_url = _resolve_avatar_download_url(api_base_url, avatar_url)
        if download_url is None:
            logger.warning("导出角色头像: %s 的头像 URL 协议不受支持", agent.username)
            return None

        avatar_response = requests.get(download_url, timeout=30)
        if avatar_response.status_code != 200:
            logger.warning(
                "导出角色头像: 下载 %s 的头像失败: HTTP %d",
                agent.username,
                avatar_response.status_code,
            )
            return None

        filename = _avatar_filename(
            avatar_url,
            user_id,
            avatar_response.headers.get("content-type", ""),
        )
        return filename, avatar_response.content, download_url
    except (requests.RequestException, ValueError) as exc:
        logger.warning("导出角色头像: 获取 %s 的头像失败: %s", agent.username, exc)
        return None


def export_agents_to_zip(
    db: Session,
    api_base_url: str,
    agent_ids: Optional[List[int]] = None,
) -> AgentExportArchive:
    """将全部或指定角色导出为批量导入兼容的 ZIP 压缩包。

    Args:
        db: Management 数据库会话。
        api_base_url: social_platform API 根地址。
        agent_ids: 需要导出的角色 ID；省略时导出全部角色。

    Returns:
        AgentExportArchive: 临时 ZIP 路径及导出统计信息。调用方负责删除文件。

    Raises:
        ValueError: 数据库中没有符合范围的可导出角色。
        OSError: 创建压缩包或读取头像失败。
    """
    stmt = select(AgentConfig).order_by(col(AgentConfig.id))
    if agent_ids is not None:
        unique_ids = list(dict.fromkeys(agent_ids))
        if not unique_ids:
            raise ValueError("请选择要导出的角色")
        stmt = stmt.where(col(AgentConfig.id).in_(unique_ids))

    agents = list(db.exec(stmt).all())
    if not agents:
        if agent_ids is None:
            raise ValueError("当前数据库中没有可导出的角色")
        raise ValueError("选中的角色不存在或已被删除")

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = tmp.name

        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            export_users: list[dict[str, object]] = []
            archived_sources: dict[str, str] = {}
            avatar_count = 0
            for agent in agents:
                user_config: dict[str, object] = {
                    "name": agent.name,
                    "username": agent.username,
                    "monthly_logins": agent.monthly_logins,
                    "personal_signature": agent.personal_signature,
                    "personality_prompt": agent.personality_prompt,
                }

                avatar = _fetch_agent_avatar(api_base_url, agent)
                if avatar is not None:
                    avatar_filename, avatar_content, source_url = avatar
                    avatar_filename = _unique_avatar_filename(
                        avatar_filename,
                        agent.social_platform_user_id or 0,
                        source_url,
                        archived_sources,
                    )
                    user_config["avatar"] = avatar_filename
                    if avatar_filename not in archived_sources:
                        archive.writestr(f"avatar/{avatar_filename}", avatar_content)
                        archived_sources[avatar_filename] = source_url
                        avatar_count += 1

                export_users.append(user_config)

            config_json = json.dumps(
                {"ai_users": export_users},
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            archive.writestr("ai_users_config.json", config_json)
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return AgentExportArchive(
        path=tmp_path,
        agent_count=len(export_users),
        avatar_count=avatar_count,
    )


def import_agents_from_zip(db: Session, zip_path: str) -> List[AgentConfig]:
    """
    从压缩包批量导入 Agent
    压缩包需包含 ai_users_config.json 和可选的 avatar/ 目录
    """
    imported = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # 查找 JSON 配置文件
        json_name = None
        for name in zf.namelist():
            if name.endswith('.json') and 'ai_users_config' in name.lower():
                json_name = name
                break

        if not json_name:
            raise ValueError("压缩包中未找到 ai_users_config.json")

        # 读取并解析 JSON
        with zf.open(json_name) as f:
            import json as _json
            config_data = _json.load(f)

        ai_users = config_data.get('ai_users', [])
        for user_data in ai_users:
            # 检查是否已存在
            username = user_data.get('username', '')
            existing = get_agent_by_username(db, username)
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
            agent = create_agent(db, agent_in)
            imported.append(agent)

    return imported
