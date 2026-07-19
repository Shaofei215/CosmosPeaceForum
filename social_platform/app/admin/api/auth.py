"""平台内管理员认证与可撤销 session 路由。"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import admin_security, get_current_admin
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminProfileUpdateRequest,
    AdminRefreshTokenRequest,
    AdminResponse,
    AdminSessionResponse,
)
from social_platform.app.admin.services import auth_service
from social_platform.app.api.deps import get_access_payload, get_db
from social_platform.app.domains.identity import sessions as session_service
from social_platform.app.domains.identity.models import UserSession

router = APIRouter(prefix="/auth", tags=["platform-admin-auth"])


def _request_session_context(request: Request) -> tuple[str, str | None, str | None]:
    """收集平台管理员 session 的端类型、User-Agent 和 IP。"""
    user_agent = request.headers.get("user-agent")
    client_host = request.client.host if request.client else None
    return (
        session_service.detect_client_type(user_agent),
        user_agent,
        session_service.extract_client_ip(request.headers, client_host),
    )


def _session_response(session: UserSession, current_session_id: str | None = None) -> AdminSessionResponse:
    """把 user_sessions 中的 platform_admin session 转成管理端响应。"""
    return AdminSessionResponse(
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


def _current_admin_payload(credentials: HTTPAuthorizationCredentials, db: Session) -> dict:
    """校验当前平台管理员 access token 并返回 payload。"""
    return get_access_payload(credentials.credentials, db, "platform_admin")


@router.post("/login", response_model=AdminLoginResponse)
async def login(request: AdminLoginRequest, http_request: Request, db: Session = Depends(get_db)):
    """平台管理员登录，创建可撤销 session 并返回 access/refresh token。"""
    admin = auth_service.authenticate_admin(db, request.username, request.password)
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    auth_service.update_last_login(db, admin)
    db.refresh(admin)
    client_type, user_agent, ip_address = _request_session_context(http_request)
    token_pair = session_service.create_session_token_pair(
        db=db,
        account_id=admin.id,
        scope="platform_admin",
        client_type=client_type,
        remember_me=request.remember_me,
        user_agent=user_agent,
        ip_address=ip_address,
        revoke_same_client=False,
    )
    return AdminLoginResponse(admin=auth_service.admin_to_response(admin), **token_pair)


@router.post("/refresh", response_model=AdminLoginResponse)
async def refresh(request: AdminRefreshTokenRequest, http_request: Request, db: Session = Depends(get_db)):
    """轮换平台管理员 refresh token，并返回新的短期 access token。"""
    _, user_agent, ip_address = _request_session_context(http_request)
    try:
        token_pair = session_service.refresh_token_pair(
            db=db,
            refresh_token=request.refresh_token,
            expected_scope="platform_admin",
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except session_service.RefreshTokenInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    admin = auth_service.get_admin_by_id(db, int(get_access_payload(token_pair["access_token"], db, "platform_admin")["sub"]))
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员不存在或已停用")
    return AdminLoginResponse(admin=auth_service.admin_to_response(admin), **token_pair)


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(admin_security),
    db: Session = Depends(get_db),
):
    """撤销当前平台管理员 session。"""
    payload = _current_admin_payload(credentials, db)
    session = session_service.get_active_session(db, payload["sid"], "platform_admin")
    if session is not None:
        session_service.revoke_session(db, session)
    return {"message": "登出成功"}


@router.get("/sessions", response_model=list[AdminSessionResponse])
async def sessions(
    credentials: HTTPAuthorizationCredentials = Depends(admin_security),
    db: Session = Depends(get_db),
) -> list[AdminSessionResponse]:
    """列出当前平台管理员的 active sessions。"""
    payload = _current_admin_payload(credentials, db)
    items = session_service.list_sessions(db, int(payload["sub"]), "platform_admin")
    return [_session_response(item, payload["sid"]) for item in items]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(admin_security),
    db: Session = Depends(get_db),
):
    """撤销当前平台管理员名下的某个非当前 session。"""
    payload = _current_admin_payload(credentials, db)
    if session_id == payload["sid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能通过该接口撤销当前会话，请使用 logout")
    revoked = session_service.revoke_session_id(db, int(payload["sub"]), "platform_admin", session_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在或已失效")
    return {"message": "会话已撤销"}


@router.get("/me", response_model=AdminResponse)
async def me(current_admin: PlatformAdminUser = Depends(get_current_admin)):
    """返回当前平台管理员资料。"""
    return auth_service.admin_to_response(current_admin)


@router.put("/profile", response_model=AdminResponse)
async def update_profile(
    request: AdminProfileUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(admin_security),
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(get_current_admin),
):
    """更新平台管理员自己的登录资料。"""
    password_changed = bool(request.new_password)
    try:
        admin = auth_service.update_profile(db, current_admin, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if password_changed:
        payload = _current_admin_payload(credentials, db)
        session_service.revoke_other_sessions(
            db,
            int(payload["sub"]),
            "platform_admin",
            str(payload["sid"]),
        )
    return auth_service.admin_to_response(admin)
