"""Management Backend - 认证路由"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    SessionResponse,
    AdminUserResponse,
    AdminProfileUpdateRequest,
)
from agents.management.backend.models.admin_session import AdminSession
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.services.auth_service import (
    authenticate_admin,
    admin_to_response,
    update_last_login,
    get_admin_by_id,
    update_profile as update_admin_profile,
)
from agents.management.backend.services import session_service
from agents.management.backend.services.log_service import create_log
from agents.management.backend.api.deps import get_current_admin, get_management_access_payload, security

router = APIRouter()
logger = logging.getLogger(__name__)


def _request_session_context(request: Request) -> tuple[str, str | None, str | None]:
    """收集 management admin session 的端类型、User-Agent 和 IP。"""
    user_agent = request.headers.get("user-agent")
    return session_service.detect_client_type(user_agent), user_agent, session_service.get_request_ip(request)


def _session_response(session: AdminSession, current_session_id: str | None = None) -> SessionResponse:
    """把 admin_sessions 记录转成前端会话列表响应。"""
    return SessionResponse(
        session_id=session.session_id,
        scope=session.scope,
        client_type=session.client_type,
        remember_me=session.remember_me,
        expires_at=session.expires_at,
        last_seen_at=session.last_seen_at,
        user_agent=session.user_agent,
        ip_address=session.ip_address,
        is_current=session.session_id == current_session_id,
    )


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    """Management 管理员登录，创建可撤销 session 并返回 access/refresh token。"""
    admin = authenticate_admin(db, request.username, request.password)
    if not admin:
        logger.warning(
            "Management 管理员登录失败: username=%s",
            request.username,
            extra={"event": "security.admin_login_failed", "component": "management"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    update_last_login(db, admin.id)
    db.refresh(admin)
    client_type, user_agent, ip_address = _request_session_context(http_request)
    token_pair = session_service.create_session_token_pair(
        db=db,
        admin_id=admin.id,
        client_type=client_type,
        remember_me=request.remember_me,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    create_log(
        db,
        admin,
        "admin_login",
        "admin_session",
        details={"session_id": token_pair["session_id"]},
    )

    return LoginResponse(admin=admin_to_response(admin), **token_pair)


@router.post("/refresh", response_model=LoginResponse)
def refresh(request: RefreshTokenRequest, http_request: Request, db: Session = Depends(get_db)):
    """轮换 management admin refresh token，并返回新的短期 access token。"""
    _, user_agent, ip_address = _request_session_context(http_request)
    token_pair = session_service.refresh_token_pair(
        db=db,
        refresh_token=request.refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    payload = get_management_access_payload(str(token_pair["access_token"]), db)
    admin = get_admin_by_id(db, int(payload["sub"]))
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员不存在或已停用")
    return LoginResponse(admin=admin_to_response(admin), **token_pair)


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """撤销当前 management admin session。"""
    payload = get_management_access_payload(credentials.credentials, db)
    admin = get_admin_by_id(db, int(payload["sub"]))
    session = session_service.get_active_session(db, payload["sid"])
    if session is not None:
        session_service.revoke_session(db, session)
    create_log(
        db,
        admin,
        "admin_logout",
        "admin_session",
        details={"session_id": payload["sid"]},
    )
    return {"message": "登出成功"}


@router.get("/sessions", response_model=list[SessionResponse])
def sessions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> list[SessionResponse]:
    """列出当前 management admin 的 active sessions。"""
    payload = get_management_access_payload(credentials.credentials, db)
    items = session_service.list_sessions(db, int(payload["sub"]))
    return [_session_response(item, payload["sid"]) for item in items]


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """撤销当前 management admin 名下的某个非当前 session。"""
    payload = get_management_access_payload(credentials.credentials, db)
    if session_id == payload["sid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能通过该接口撤销当前会话，请使用 logout")
    revoked = session_service.revoke_session_id(db, int(payload["sub"]), session_id)
    if not revoked:
        logger.warning(
            "Management 管理员会话撤销失败: session_id=%s",
            session_id,
            extra={"event": "security.session_revoke_failed", "component": "management"},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在或已失效")
    admin = get_admin_by_id(db, int(payload["sub"]))
    create_log(
        db,
        admin,
        "revoke_admin_session",
        "admin_session",
        details={"session_id": session_id},
    )
    return {"message": "会话已撤销"}


@router.get("/me", response_model=AdminUserResponse)
def get_me(current_admin: AdminUser = Depends(get_current_admin)):
    """获取当前 management 管理员信息。"""
    return admin_to_response(current_admin)


@router.put("/profile", response_model=AdminUserResponse)
def update_profile(
    request: AdminProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """更新当前 management 管理员自己的登录资料。"""
    try:
        admin = update_admin_profile(db, current_admin, request)
    except ValueError as exc:
        logger.warning(
            "Management 管理员凭据或资料变更失败: admin_id=%s reason=%s",
            current_admin.id,
            exc,
            extra={"event": "security.admin_profile_update_failed", "component": "management"},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    create_log(
        db,
        admin,
        "update_admin_profile",
        "admin",
        admin.id,
        details={"password_changed": bool(request.new_password)},
    )
    return admin_to_response(admin)
