"""服务端会话与 refresh token 轮换逻辑。

这个模块是公开平台认证升级的中心：access token 只表达短期身份，
是否仍然有效由这里维护的 UserSession 决定；refresh token 明文只交给客户端，
数据库只保存哈希并在每次刷新时轮换。
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from social_platform.app.core.config import get_settings
from social_platform.app.core.security import create_access_token, create_refresh_token, hash_refresh_token
from social_platform.app.models.session import UserSession


settings = get_settings()


def detect_client_type(user_agent: str | None) -> str:
    """把 User-Agent 粗分为 mobile/desktop，用于真人同端互斥策略。"""
    ua = (user_agent or "").lower()
    mobile_markers = ("mobile", "android", "iphone", "ipad", "ipod", "windows phone")
    return "mobile" if any(marker in ua for marker in mobile_markers) else "desktop"


def get_request_ip(request) -> Optional[str]:
    """提取客户端 IP，优先信任反向代理传入的 X-Forwarded-For 首段。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def access_delta_for(scope: str, client_type: str) -> timedelta:
    """根据账号 scope 与 client_type 选择短期 access token 有效期。"""
    if client_type == "agent":
        return timedelta(hours=settings.AI_ACCESS_TOKEN_EXPIRE_HOURS)
    if scope == "platform_admin":
        return timedelta(minutes=settings.ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES)
    return timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def refresh_delta_for(scope: str, client_type: str, remember_me: bool) -> timedelta:
    """计算服务端 session/refresh token 生命周期，remember_me 只影响 refresh 窗口。"""
    if client_type == "agent":
        return timedelta(hours=settings.AI_REFRESH_TOKEN_EXPIRE_HOURS)
    if scope == "platform_admin":
        if remember_me:
            return timedelta(days=settings.ADMIN_REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS)
        return timedelta(hours=settings.ADMIN_REFRESH_TOKEN_EXPIRE_HOURS)
    if remember_me:
        return timedelta(days=settings.REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS)
    return timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)


def _active_query(db: Session):
    """返回只包含未撤销且未过期 session 的基础查询。"""
    now = datetime.utcnow()
    return db.query(UserSession).filter(UserSession.revoked_at.is_(None), UserSession.expires_at > now)


def _issue_access_token(session: UserSession) -> tuple[str, int]:
    """为指定 session 签发带 sid/scope 的短期 access token。"""
    delta = access_delta_for(session.scope, session.client_type)
    token = create_access_token(
        data={
            "sub": str(session.account_id),
            "scope": session.scope,
            "sid": session.session_id,
        },
        expires_delta=delta,
    )
    return token, int(delta.total_seconds())


def create_session_token_pair(
    db: Session,
    account_id: int,
    scope: str,
    client_type: str,
    remember_me: bool,
    user_agent: str | None,
    ip_address: str | None,
    revoke_same_client: bool = False,
) -> dict[str, object]:
    """创建服务端 session，并返回初始 access/refresh token 对。

    revoke_same_client 只给真人公开平台登录使用，用来保证同一用户同一端类型
    只有一个 active session；AI Agent 和管理员会话不会走这个互斥策略。
    """
    now = datetime.utcnow()
    if revoke_same_client:
        _active_query(db).filter(
            UserSession.account_id == account_id,
            UserSession.scope == scope,
            UserSession.client_type == client_type,
        ).update({"revoked_at": now}, synchronize_session=False)

    refresh_token = create_refresh_token()
    refresh_delta = refresh_delta_for(scope, client_type, remember_me)
    session = UserSession(
        session_id=uuid4().hex,
        account_id=account_id,
        scope=scope,
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
    expected_scope: str,
    user_agent: str | None,
    ip_address: str | None,
) -> dict[str, object]:
    """校验 refresh token 并轮换为新的 refresh token。

    refresh token 只能使用一次；成功刷新后同一 session 保持不变，但数据库中的
    refresh_token_hash 会被替换，旧 refresh token 随即失效。
    """
    session = _active_query(db).filter(
        UserSession.refresh_token_hash == hash_refresh_token(refresh_token),
        UserSession.scope == expected_scope,
    ).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token 无效或已过期")

    now = datetime.utcnow()
    next_refresh_token = create_refresh_token()
    session.refresh_token_hash = hash_refresh_token(next_refresh_token)
    session.last_seen_at = now
    session.user_agent = user_agent or session.user_agent
    session.ip_address = ip_address or session.ip_address
    db.add(session)
    db.commit()
    db.refresh(session)

    access_token, expires_in = _issue_access_token(session)
    refresh_expires_in = max(0, int((session.expires_at - now).total_seconds()))
    return {
        "access_token": access_token,
        "refresh_token": next_refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "refresh_expires_in": refresh_expires_in,
        "session_id": session.session_id,
    }


def get_active_session(db: Session, session_id: str, scope: str) -> Optional[UserSession]:
    """按 sid 和 scope 查找仍可用于 access token 鉴权的 session。"""
    return _active_query(db).filter(
        UserSession.session_id == session_id,
        UserSession.scope == scope,
    ).first()


def revoke_session(db: Session, session: UserSession) -> None:
    """撤销单个 session，使其 access token 与 refresh token 同时失效。"""
    if session.revoked_at is None:
        session.revoked_at = datetime.utcnow()
        db.add(session)
        db.commit()


def revoke_session_id(db: Session, account_id: int, scope: str, session_id: str) -> bool:
    """撤销当前账号名下指定 session_id 的 active session。"""
    session = _active_query(db).filter(
        UserSession.account_id == account_id,
        UserSession.scope == scope,
        UserSession.session_id == session_id,
    ).first()
    if session is None:
        return False
    revoke_session(db, session)
    return True


def revoke_other_sessions(db: Session, account_id: int, scope: str, current_session_id: str) -> int:
    """撤销当前账号除 current_session_id 外的其他 active session。"""
    now = datetime.utcnow()
    count = _active_query(db).filter(
        UserSession.account_id == account_id,
        UserSession.scope == scope,
        UserSession.session_id != current_session_id,
    ).update({"revoked_at": now}, synchronize_session=False)
    db.commit()
    return count


def list_sessions(db: Session, account_id: int, scope: str) -> list[UserSession]:
    """列出当前账号可管理的 active sessions，最近使用的排在前面。"""
    return _active_query(db).filter(
        UserSession.account_id == account_id,
        UserSession.scope == scope,
    ).order_by(UserSession.last_seen_at.desc()).all()
