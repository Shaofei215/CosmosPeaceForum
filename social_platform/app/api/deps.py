# 依赖注入模块
# 提供 API 路由所需的公共依赖
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from social_platform.app.core.security import decode_access_token
from social_platform.app.db.session import SessionLocal
from social_platform.app.domains.identity import sessions as session_service
from social_platform.app.domains.user.models import User


security = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """
    数据库会话依赖注入

    创建数据库会话，使用完毕后自动关闭

    Yields:
        Session: 数据库会话对象

    Note:
        使用 try-finally 确保会话总是被关闭
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _unauthorized(detail: str = "无效的认证凭证") -> HTTPException:
    """构造统一的 Bearer 认证失败响应。"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_access_payload(token: str, db: Session, expected_scope: str) -> dict:
    """解码 access token，并确认它仍绑定一个 active server-side session。

    只验证 JWT 签名不足以支持立即撤销；因此这里还强制检查 typ=access、
    scope、sid，以及 sid 对应的 UserSession 是否未撤销且未过期。
    """
    payload = decode_access_token(token)
    if payload is None or payload.get("typ") != "access" or payload.get("scope") != expected_scope:
        raise _unauthorized()

    session_id = payload.get("sid")
    if not session_id:
        raise _unauthorized()

    session = session_service.get_active_session(db, session_id, expected_scope)
    if session is None:
        raise _unauthorized("会话已失效，请重新登录")

    user_id_str = payload.get("sub")
    try:
        account_id = int(user_id_str)
    except (ValueError, TypeError):
        raise _unauthorized()

    if session.account_id != account_id:
        raise _unauthorized()

    return payload


def _get_user_from_payload(db: Session, payload: dict, include_banned: bool = False) -> User:
    """根据已验证 payload 加载用户。

    include_banned 参数保留给既有调用点兼容；账号封禁不再阻止读取类接口，
    写操作由具体业务入口调用处罚守卫拦截。
    """
    try:
        user_id = int(payload.get("sub"))
    except (ValueError, TypeError):
        raise _unauthorized()

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _unauthorized("用户不存在")

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前登录用户；access token 必须属于 active user session。"""
    payload = get_access_payload(credentials.credentials, db, "user")
    return _get_user_from_payload(db, payload)


def get_current_user_including_banned(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """加载当前用户但跳过封禁态拦截，供账号状态相关内部接口使用。"""
    payload = get_access_payload(credentials.credentials, db, "user")
    return _get_user_from_payload(db, payload, include_banned=True)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """可选读取当前用户；无 token 或 session 失效时都按匿名访问处理。"""
    if credentials is None:
        return None

    try:
        payload = get_access_payload(credentials.credentials, db, "user")
        return _get_user_from_payload(db, payload)
    except HTTPException:
        return None
