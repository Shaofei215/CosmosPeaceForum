"""Management 管理员服务端会话与 refresh token 轮换逻辑。

管理端允许同一管理员保留多个可撤销会话，但 access token 仍然必须携带 sid，
并在每次鉴权时回查 admin_sessions，避免撤销后旧 access token 继续可用。
"""

from datetime import datetime, timedelta
from agents.management.backend.core.timezone import local_now
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlmodel import Session, select

from agents.management.backend.core.config import get_config
from agents.management.backend.core.security import create_access_token, create_refresh_token, hash_refresh_token
from agents.management.backend.models.admin_session import AdminSession


def detect_client_type(user_agent: str | None) -> str:
    """记录管理员会话来源端类型，便于会话列表展示与审计。"""
    ua = (user_agent or "").lower()
    mobile_markers = ("mobile", "android", "iphone", "ipad", "ipod", "windows phone")
    return "mobile" if any(marker in ua for marker in mobile_markers) else "desktop"


def get_request_ip(request) -> Optional[str]:
    """提取管理员登录 IP，优先使用代理转发的客户端地址。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def _access_delta() -> timedelta:
    """返回 management admin 的短期 access token 生命周期。"""
    return timedelta(minutes=get_config().jwt_access_token_expire_minutes)


def _refresh_delta(remember_me: bool) -> timedelta:
    """根据 remember_me 选择 management admin session 生命周期。"""
    config = get_config()
    if remember_me:
        return timedelta(days=config.remember_me_refresh_token_expire_days)
    return timedelta(hours=config.refresh_token_expire_hours)


def _active_statement():
    """构造未撤销且未过期 admin session 的 SQLModel 查询。"""
    now = local_now()
    return select(AdminSession).where(AdminSession.revoked_at.is_(None), AdminSession.expires_at > now)


def _issue_access_token(session: AdminSession) -> tuple[str, int]:
    """为指定 admin session 签发带 sid/scope 的短期 access token。"""
    delta = _access_delta()
    token = create_access_token(
        data={
            "sub": str(session.admin_id),
            "username": None,
            "scope": session.scope,
            "sid": session.session_id,
        },
        expires_delta=delta,
    )
    return token, int(delta.total_seconds())


def create_session_token_pair(
    db: Session,
    admin_id: int,
    client_type: str,
    remember_me: bool,
    user_agent: str | None,
    ip_address: str | None,
) -> dict[str, object]:
    """创建新的管理员 session，并返回 access/refresh token 对。"""
    now = local_now()
    refresh_token = create_refresh_token()
    refresh_delta = _refresh_delta(remember_me)
    session = AdminSession(
        session_id=uuid4().hex,
        admin_id=admin_id,
        scope="management_admin",
        client_type=client_type,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=now + refresh_delta,
        last_seen_at=now,
        user_agent=user_agent,
        ip_address=ip_address,
        remember_me=remember_me,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    access_token, expires_in = _issue_access_token(session)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "refresh_expires_in": int(refresh_delta.total_seconds()),
        "session_id": session.session_id,
    }


def refresh_token_pair(
    db: Session,
    refresh_token: str,
    user_agent: str | None,
    ip_address: str | None,
) -> dict[str, object]:
    """校验并轮换 management admin refresh token。

    成功刷新时保留同一个 session_id，替换 refresh token 哈希，让旧 refresh token
    立即失效，同时更新 last_seen/user_agent/ip 供会话列表展示。
    """
    session = db.exec(
        _active_statement().where(AdminSession.refresh_token_hash == hash_refresh_token(refresh_token))
    ).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token 无效或已过期")

    now = local_now()
    next_refresh_token = create_refresh_token()
    session.refresh_token_hash = hash_refresh_token(next_refresh_token)
    session.last_seen_at = now
    session.user_agent = user_agent or session.user_agent
    session.ip_address = ip_address or session.ip_address
    db.add(session)
    db.commit()
    db.refresh(session)
    access_token, expires_in = _issue_access_token(session)
    return {
        "access_token": access_token,
        "refresh_token": next_refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "refresh_expires_in": max(0, int((session.expires_at - now).total_seconds())),
        "session_id": session.session_id,
    }


def get_active_session(db: Session, session_id: str) -> Optional[AdminSession]:
    """查找仍可用于 management access token 鉴权的 admin session。"""
    return db.exec(_active_statement().where(AdminSession.session_id == session_id)).first()


def revoke_session(db: Session, session: AdminSession) -> None:
    """撤销单个 admin session，使其 access/refresh token 同时失效。"""
    if session.revoked_at is None:
        session.revoked_at = local_now()
        db.add(session)
        db.commit()


def revoke_session_id(db: Session, admin_id: int, session_id: str) -> bool:
    """撤销指定管理员名下的某个 active session。"""
    session = db.exec(
        _active_statement().where(AdminSession.admin_id == admin_id, AdminSession.session_id == session_id)
    ).first()
    if session is None:
        return False
    revoke_session(db, session)
    return True


def list_sessions(db: Session, admin_id: int) -> list[AdminSession]:
    """列出管理员当前所有 active sessions，按最近使用时间排序。"""
    return list(
        db.exec(
            _active_statement()
            .where(AdminSession.admin_id == admin_id)
            .order_by(AdminSession.last_seen_at.desc())
        ).all()
    )
