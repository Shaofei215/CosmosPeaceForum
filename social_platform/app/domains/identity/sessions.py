"""身份安全领域的 session 与 refresh token 应用服务。

本模块负责服务端可撤销 session、access token 签发和 refresh token 单次轮换；
调用方只需要提供适配层提取出的 User-Agent 与 IP 字符串。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from social_platform.app.core.timezone import local_now
from typing import Mapping, TypedDict
from uuid import uuid4

from sqlalchemy.orm import Query, Session

from social_platform.app.core.config import get_settings
from social_platform.app.core.security import create_access_token, create_refresh_token, hash_refresh_token
from social_platform.app.domains.identity.models import UserSession


settings = get_settings()


class TokenPair(TypedDict):
    """创建或轮换 session 后返回的认证令牌对。"""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_expires_in: int
    session_id: str


class RefreshTokenInvalidError(Exception):
    """refresh token 无效或已过期异常。"""

    def __init__(self) -> None:
        """初始化 refresh token 无效异常。"""

        super().__init__("refresh token 无效或已过期")


def detect_client_type(user_agent: str | None) -> str:
    """把 User-Agent 粗分为 mobile/desktop，用于真人同端互斥策略。

    Args:
        user_agent: HTTP User-Agent 头内容。

    Returns:
        str: ``mobile`` 或 ``desktop``。
    """

    ua = (user_agent or "").lower()
    mobile_markers = ("mobile", "android", "iphone", "ipad", "ipod", "windows phone")
    return "mobile" if any(marker in ua for marker in mobile_markers) else "desktop"


def extract_client_ip(headers: Mapping[str, str], client_host: str | None) -> str | None:
    """从适配层提供的请求信息中提取客户端 IP。

    Args:
        headers: 请求头映射。
        client_host: ASGI 连接对象上的客户端主机地址。

    Returns:
        str | None: 优先返回 ``X-Forwarded-For`` 首段，否则返回客户端主机地址。
    """

    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return client_host


def access_delta_for(scope: str, client_type: str) -> timedelta:
    """根据账号 scope 与 client_type 选择短期 access token 有效期。

    Args:
        scope: 身份作用域，例如 ``user`` 或 ``platform_admin``。
        client_type: 客户端类型，例如 ``desktop``、``mobile`` 或 ``agent``。

    Returns:
        timedelta: access token 有效期。
    """

    if client_type == "agent":
        return timedelta(hours=settings.AI_ACCESS_TOKEN_EXPIRE_HOURS)
    if scope == "platform_admin":
        return timedelta(minutes=settings.ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES)
    return timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def refresh_delta_for(scope: str, client_type: str, remember_me: bool) -> timedelta:
    """计算服务端 session/refresh token 生命周期。

    Args:
        scope: 身份作用域。
        client_type: 客户端类型。
        remember_me: 是否启用更长 refresh 窗口。

    Returns:
        timedelta: refresh token 与 session 的有效期。
    """

    if client_type == "agent":
        return timedelta(hours=settings.AI_REFRESH_TOKEN_EXPIRE_HOURS)
    if scope == "platform_admin":
        if remember_me:
            return timedelta(days=settings.ADMIN_REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS)
        return timedelta(hours=settings.ADMIN_REFRESH_TOKEN_EXPIRE_HOURS)
    if remember_me:
        return timedelta(days=settings.REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS)
    return timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)


def _active_query(db: Session) -> Query[UserSession]:
    """返回只包含未撤销且未过期 session 的基础查询。

    Args:
        db: 当前数据库会话。

    Returns:
        Query[UserSession]: 可继续追加过滤条件的 SQLAlchemy 查询。
    """

    now = local_now()
    return db.query(UserSession).filter(UserSession.revoked_at.is_(None), UserSession.expires_at > now)


def _issue_access_token(session: UserSession) -> tuple[str, int]:
    """为指定 session 签发带 sid/scope 的短期 access token。

    Args:
        session: 已创建且未撤销的会话记录。

    Returns:
        tuple[str, int]: access token 与有效秒数。
    """

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
) -> TokenPair:
    """创建服务端 session，并返回初始 access/refresh token 对。

    Args:
        db: 当前数据库会话。
        account_id: 账号 ID，真人/AI 用户和平台管理员各自在自己的 scope 下解释。
        scope: 身份作用域。
        client_type: 客户端类型。
        remember_me: 是否启用更长 refresh 窗口。
        user_agent: 创建会话时的 User-Agent。
        ip_address: 创建会话时的客户端 IP。
        revoke_same_client: 是否撤销同账号同端类型的旧 active session。

    Returns:
        dict[str, object]: access/refresh token、过期秒数和 session_id。
    """

    now = local_now()
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
) -> TokenPair:
    """校验 refresh token 并轮换为新的 refresh token。

    Args:
        db: 当前数据库会话。
        refresh_token: 客户端提交的 opaque refresh token。
        expected_scope: 期望的身份作用域。
        user_agent: 本次刷新请求的 User-Agent。
        ip_address: 本次刷新请求的客户端 IP。

    Returns:
        dict[str, object]: 新 access/refresh token、过期秒数和 session_id。

    Raises:
        RefreshTokenInvalidError: refresh token 不存在、已过期或 scope 不匹配。
    """

    session = _active_query(db).filter(
        UserSession.refresh_token_hash == hash_refresh_token(refresh_token),
        UserSession.scope == expected_scope,
    ).first()
    if session is None:
        raise RefreshTokenInvalidError()

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
    refresh_expires_in = max(0, int((session.expires_at - now).total_seconds()))
    return {
        "access_token": access_token,
        "refresh_token": next_refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "refresh_expires_in": refresh_expires_in,
        "session_id": session.session_id,
    }


def get_active_session(db: Session, session_id: str, scope: str) -> UserSession | None:
    """按 sid 和 scope 查找仍可用于 access token 鉴权的 session。

    Args:
        db: 当前数据库会话。
        session_id: access token payload 中的 sid。
        scope: 期望的身份作用域。

    Returns:
        UserSession | None: active session；不存在则返回 None。
    """

    return _active_query(db).filter(
        UserSession.session_id == session_id,
        UserSession.scope == scope,
    ).first()


def revoke_session(db: Session, session: UserSession) -> None:
    """撤销单个 session，使其 access token 与 refresh token 同时失效。

    Args:
        db: 当前数据库会话。
        session: 待撤销的 active session。
    """

    if session.revoked_at is None:
        session.revoked_at = local_now()
        db.add(session)
        db.commit()


def revoke_session_id(db: Session, account_id: int, scope: str, session_id: str) -> bool:
    """撤销当前账号名下指定 session_id 的 active session。

    Args:
        db: 当前数据库会话。
        account_id: 账号 ID。
        scope: 身份作用域。
        session_id: 待撤销的 session_id。

    Returns:
        bool: 成功撤销返回 True；不存在或已失效返回 False。
    """

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
    """撤销当前账号除 current_session_id 外的其他 active sessions。

    Args:
        db: 当前数据库会话。
        account_id: 账号 ID。
        scope: 身份作用域。
        current_session_id: 需要保留的当前 session_id。

    Returns:
        int: 被撤销的会话数量。
    """

    now = local_now()
    count = _active_query(db).filter(
        UserSession.account_id == account_id,
        UserSession.scope == scope,
        UserSession.session_id != current_session_id,
    ).update({"revoked_at": now}, synchronize_session=False)
    db.commit()
    return count


def revoke_all_sessions(
    db: Session,
    account_id: int,
    scope: str,
    *,
    commit: bool = True,
) -> int:
    """撤销指定账号和作用域下的全部 active session。

    Args:
        db: 当前数据库会话。
        account_id: 账号 ID。
        scope: 身份作用域，避免不同账号表的相同整数 ID 相互影响。
        commit: 是否立即提交；密码重置传入 ``False`` 以加入同一事务。

    Returns:
        int: 被撤销的 active session 数量。
    """

    count = _active_query(db).filter(
        UserSession.account_id == account_id,
        UserSession.scope == scope,
    ).update({"revoked_at": local_now()}, synchronize_session=False)
    if commit:
        db.commit()
    return count


def list_sessions(db: Session, account_id: int, scope: str) -> list[UserSession]:
    """列出当前账号可管理的 active sessions，最近使用的排在前面。

    Args:
        db: 当前数据库会话。
        account_id: 账号 ID。
        scope: 身份作用域。

    Returns:
        list[UserSession]: active session 列表。
    """

    return _active_query(db).filter(
        UserSession.account_id == account_id,
        UserSession.scope == scope,
    ).order_by(UserSession.last_seen_at.desc()).all()
