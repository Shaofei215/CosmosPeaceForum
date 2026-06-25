# 认证路由控制器
# 处理用户注册、登录、获取当前用户信息等认证相关 API 请求

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from social_platform.app.api.deps import get_access_payload, get_db, get_current_user, security
from social_platform.app.core.security import (
    get_password_hash,
    verify_password,
    verify_admin_key,
)
from social_platform.app.domains.identity import application as identity_service
from social_platform.app.domains.identity import sessions as session_service
from social_platform.app.domains.identity import verification as verification_service
from social_platform.app.domains.identity.models import UserSession
from social_platform.app.domains.invitation import application as invitation_service
from social_platform.app.domains.invitation.schemas import InvitationRegistrationConfigResponse
from social_platform.app.domains.identity.schemas import (
    EmailCodeSendRequest,
    EmailCodeSendResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
)
from social_platform.app.domains.email.application import verification_email_sender
from social_platform.app.domains.user.models import User
from social_platform.app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
    RegisterResponse,
    AILoginRequest,
    RefreshTokenRequest,
    SessionResponse,
)
from social_platform.app.domains.search import application as search_service


router = APIRouter()


def _request_session_context(request: Request, client_type: str | None = None) -> tuple[str, str | None, str | None]:
    """收集创建/刷新 session 所需的端类型、User-Agent 和 IP。"""
    user_agent = request.headers.get("user-agent")
    client_host = request.client.host if request.client else None
    return (
        client_type or session_service.detect_client_type(user_agent),
        user_agent,
        session_service.extract_client_ip(request.headers, client_host),
    )


def _session_response(session: UserSession, current_session_id: str | None = None) -> SessionResponse:
    """把数据库 session 转成前端可展示的会话响应对象。"""
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


def _current_user_payload(credentials: HTTPAuthorizationCredentials, db: Session) -> dict:
    """复用统一鉴权逻辑，取得当前 user scope access token 的 payload。"""
    return get_access_payload(credentials.credentials, db, "user")


def _raise_send_code_http_error(exc: Exception) -> NoReturn:
    """把 identity 验证码发送异常映射成 HTTP 错误。"""
    if isinstance(exc, verification_service.VerificationCodeFrequencyError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.wait_seconds)},
        ) from exc
    if isinstance(exc, verification_service.VerificationCodeDailyLimitError):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    if isinstance(exc, verification_service.EmailDeliveryError):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ========== 邮箱验证码发送 ==========


@router.get(
    "/register/invitation-config",
    response_model=InvitationRegistrationConfigResponse,
    status_code=status.HTTP_200_OK,
)
def get_register_invitation_config() -> InvitationRegistrationConfigResponse:
    """读取公开注册页的邀请码开关配置。

    Returns:
        InvitationRegistrationConfigResponse: 是否开启邀请制注册。
    """

    return InvitationRegistrationConfigResponse(
        enabled=invitation_service.is_invitation_registration_enabled()
    )


@router.post(
    "/register/send-code",
    response_model=EmailCodeSendResponse,
    status_code=status.HTTP_200_OK
)
def send_register_verification_code(
    request: EmailCodeSendRequest,
    db: Session = Depends(get_db)
) -> EmailCodeSendResponse:
    """
    发送注册邮箱验证码

    - **无需认证**
    - 用于真人用户注册前的验证码发送
    - 同一邮箱发送间隔内只能发送一次
    - 同一邮箱每日最多发送指定次数

    Args:
        request: 包含邮箱地址的请求体
        db: 数据库会话

    Returns:
        EmailCodeSendResponse: 发送结果信息

    Raises:
        HTTPException 400: 该邮箱已被注册
        HTTPException 429: 发送过于频繁或已达每日上限
        HTTPException 500: 邮件发送失败
    """
    try:
        return verification_service.send_register_verification_code(
            db,
            request.email,
            verification_email_sender,
            invitation_code=request.invitation_code,
        )
    except (
        verification_service.EmailAlreadyRegisteredError,
        invitation_service.InvitationRequiredError,
        invitation_service.InvitationInvalidError,
        verification_service.VerifiedHumanUserNotFoundError,
        verification_service.VerificationCodeFrequencyError,
        verification_service.VerificationCodeDailyLimitError,
        verification_service.EmailDeliveryError,
    ) as exc:
        _raise_send_code_http_error(exc)


@router.post(
    "/login/send-code",
    response_model=EmailCodeSendResponse,
    status_code=status.HTTP_200_OK
)
def send_login_verification_code(
    request: EmailCodeSendRequest,
    db: Session = Depends(get_db)
) -> EmailCodeSendResponse:
    """
    发送登录邮箱验证码

    - **无需认证**
    - 用于真人用户验证码登录
    - 同一邮箱发送间隔内只能发送一次
    - 同一邮箱每日最多发送指定次数

    Args:
        request: 包含邮箱地址的请求体
        db: 数据库会话

    Returns:
        EmailCodeSendResponse: 发送结果信息

    Raises:
        HTTPException 400: 该邮箱未绑定任何已验证账号
        HTTPException 429: 发送过于频繁或已达每日上限
        HTTPException 500: 邮件发送失败
    """
    try:
        return verification_service.send_login_verification_code(
            db,
            request.email,
            verification_email_sender,
        )
    except (
        verification_service.EmailAlreadyRegisteredError,
        verification_service.VerifiedHumanUserNotFoundError,
        verification_service.VerificationCodeFrequencyError,
        verification_service.VerificationCodeDailyLimitError,
        verification_service.EmailDeliveryError,
    ) as exc:
        _raise_send_code_http_error(exc)


# ========== 用户注册（AI 用户直接注册） ==========


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    user_data: UserRegister,
    x_admin_key: str = Header(None, description="管理员密钥（AI 注册时必填）"),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    用户注册（AI 用户专用）

    AI 用户使用此接口直接注册，无需邮箱验证

    Args:
        user_data: 用户注册信息
        x_admin_key: 管理员密钥（AI 注册时需要）
        db: 数据库会话

    Returns:
        UserResponse: 创建的用户信息

    Raises:
        HTTPException 400: 用户名已存在
        HTTPException 400: AI 注册但未提供管理员密钥
        HTTPException 401: 管理员密钥无效
        HTTPException 400: AI 注册但未提供 ai_config_id
    """
    # AI 用户注册
    if user_data.is_ai_agent:
        if x_admin_key is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI 注册需要提供管理员密钥"
            )
        if not verify_admin_key(x_admin_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="管理员密钥无效"
            )
        if user_data.ai_config_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI 注册需要提供 ai_config_id"
            )
        if not user_data.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI 注册需要提供用户名"
            )

        # 检查用户名是否已存在
        existing_user = db.query(User).filter(
            User.username == user_data.username
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )

        password_hash = get_password_hash(user_data.password)

        db_user = User(
            username=user_data.username,
            password_hash=password_hash,
            is_ai_agent=True,
            ai_config_id=user_data.ai_config_id,
            email=None,
            email_verified=False,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        search_service.index_user(db_user)

        return UserResponse.model_validate(db_user)

    # 真人用户应使用 /register/verify 接口
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="真人用户注册请使用 /auth/register/verify 接口"
    )


# ========== 用户注册并验证邮箱（真人用户两步注册第二步） ==========


@router.post(
    "/register/verify",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED
)
def verify_and_register(
    user_data: UserRegister,
    request: Request,
    code: str = Query(..., description="邮箱验证码"),
    db: Session = Depends(get_db)
) -> RegisterResponse:
    """
    验证邮箱验证码并创建用户（真人用户注册两步流程第一步）

    - **真人用户专用**：验证邮箱验证码后创建用户
    - AI 用户请使用 POST /auth/register
    - 注册成功后需要调用 /users/{user_id} 接口完善用户名等信息

    Args:
        user_data: 用户注册信息（包含邮箱和密码）
        code: 邮箱验证码（Query 参数）
        db: 数据库会话

    Returns:
        RegisterResponse: 包含用户ID和注册成功消息

    Raises:
        HTTPException 400: AI 用户请使用其他接口
        HTTPException 400: 真人用户必须提供邮箱地址
        HTTPException 400: 该邮箱已被注册
        HTTPException 400: 验证码无效、已过期或尝试次数过多
        HTTPException 400: 验证码错误
    """
    # 不允许 AI 用户使用此接口
    if user_data.is_ai_agent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI 用户请使用 POST /auth/register"
        )

    # 真人用户必须提供邮箱
    if not user_data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="真人用户注册必须提供邮箱地址"
        )

    try:
        db_user = identity_service.register_human_user_with_code(
            db,
            user_data.email,
            user_data.password,
            code,
            invitation_code=user_data.invitation_code,
        )
    except (
        verification_service.EmailAlreadyRegisteredError,
        invitation_service.InvitationRequiredError,
        invitation_service.InvitationInvalidError,
        verification_service.VerificationCodeNotFoundError,
        verification_service.VerificationCodeAttemptsExceededError,
        verification_service.VerificationCodeMismatchError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    client_type, user_agent, ip_address = _request_session_context(request)
    token_pair = session_service.create_session_token_pair(
        db=db,
        account_id=db_user.id,
        scope="user",
        client_type=client_type,
        remember_me=user_data.remember_me,
        user_agent=user_agent,
        ip_address=ip_address,
        revoke_same_client=True,
    )

    return RegisterResponse(
        id=db_user.id,
        username=db_user.username,
        message="注册成功，请完善您的个人资料",
        **token_pair,
    )


# ========== 用户登录 ==========


@router.post("/login", response_model=TokenResponse)
def login(
    user_data: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    用户登录

    使用邮箱+密码或邮箱+验证码登录，返回 JWT Token
    两种登录方式二选一：
    - 密码登录：提供 email 和 password
    - 验证码登录：提供 email 和 code

    Args:
        user_data: 用户登录信息（email + password 或 email + code）
        db: 数据库会话

    Returns:
        TokenResponse: 包含 access_token 的响应

    Raises:
        HTTPException 400: 请求参数错误
        HTTPException 401: 邮箱或密码/验证码错误
    """
    # 验证登录方式
    if user_data.password is None and user_data.code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须提供密码或验证码"
        )
    if user_data.password is not None and user_data.code is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能同时提供密码和验证码"
        )

    if user_data.email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="真人用户登录必须提供邮箱"
        )

    email = user_data.email.lower()

    user = db.query(User).filter(
        User.email == email,
        User.email_verified.is_(True),
        User.is_ai_agent.is_(False),
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )

    # 密码登录方式
    if user_data.password is not None:
        if user.password_hash is None or not verify_password(
            user_data.password, user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="邮箱或密码错误"
            )

    else:
        try:
            identity_service.validate_login_verification_code(
                db,
                user,
                email,
                user_data.code or "",
            )
        except verification_service.VerificationCodeInvalidError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

    client_type, user_agent, ip_address = _request_session_context(request)
    token_pair = session_service.create_session_token_pair(
        db=db,
        account_id=user.id,
        scope="user",
        client_type=client_type,
        remember_me=user_data.remember_me,
        user_agent=user_agent,
        ip_address=ip_address,
        revoke_same_client=True,
    )

    return TokenResponse(**token_pair)


# ========== AI 用户登录 ==========


@router.post("/ai-login", response_model=TokenResponse)
def ai_login(
    login_data: AILoginRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    AI 用户登录

    AI 用户通过用户名或 ai_config_id + 密码登录，返回 JWT Token

    Args:
        login_data: AI 用户登录信息（username 或 ai_config_id + password）
        db: 数据库会话

    Returns:
        TokenResponse: 包含 access_token 的响应

    Raises:
        HTTPException 400: 参数错误（未提供 username 或 ai_config_id）
        HTTPException 401: 用户名或密码错误
    """
    if login_data.username is None and login_data.ai_config_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须提供 username 或 ai_config_id"
        )

    if login_data.username is not None and login_data.ai_config_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只需提供 username 或 ai_config_id 其中一个"
        )

    query = db.query(User).filter(User.is_ai_agent == True)

    if login_data.username is not None:
        query = query.filter(User.username == login_data.username)
    else:
        query = query.filter(User.ai_config_id == login_data.ai_config_id)

    user = query.first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    if user.password_hash is None or not verify_password(
        login_data.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    client_type, user_agent, ip_address = _request_session_context(request, client_type="agent")
    token_pair = session_service.create_session_token_pair(
        db=db,
        account_id=user.id,
        scope="user",
        client_type=client_type,
        remember_me=False,
        user_agent=user_agent,
        ip_address=ip_address,
        revoke_same_client=False,
    )

    return TokenResponse(**token_pair)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """使用 refresh token 换取新的 access/refresh token 对。

    refresh token 会在 session_service 中被轮换；旧 refresh token 成功使用后立即失效。
    """
    _, user_agent, ip_address = _request_session_context(request)
    try:
        token_pair = session_service.refresh_token_pair(
            db=db,
            refresh_token=payload.refresh_token,
            expected_scope="user",
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except session_service.RefreshTokenInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenResponse(**token_pair)


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """撤销当前 sid 对应的 user session。

    因为 access token 每次鉴权都会回查 session，撤销后当前 access token 也会失效。
    """
    payload = _current_user_payload(credentials, db)
    session = session_service.get_active_session(db, payload["sid"], "user")
    if session is not None:
        session_service.revoke_session(db, session)
    return {"message": "登出成功"}


@router.post("/logout-all")
def logout_all(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """撤销当前用户除本 session 外的其他 active sessions。"""
    payload = _current_user_payload(credentials, db)
    count = session_service.revoke_other_sessions(db, int(payload["sub"]), "user", payload["sid"])
    return {"message": "其他会话已撤销", "revoked_count": count}


@router.get("/sessions", response_model=list[SessionResponse])
def sessions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> list[SessionResponse]:
    """列出当前用户可管理的 active sessions。"""
    payload = _current_user_payload(credentials, db)
    items = session_service.list_sessions(db, int(payload["sub"]), "user")
    return [_session_response(item, payload["sid"]) for item in items]


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """撤销当前用户的某个非当前 session。

    当前 session 必须通过 logout 撤销，避免前端误删自己后仍以为请求成功可继续操作。
    """
    payload = _current_user_payload(credentials, db)
    if session_id == payload["sid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能通过该接口撤销当前会话，请使用 logout")
    revoked = session_service.revoke_session_id(db, int(payload["sub"]), "user", session_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在或已失效")
    return {"message": "会话已撤销"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    获取当前登录用户信息

    需要在请求头中携带有效的 Bearer Token

    Args:
        current_user: 当前登录用户（通过 Token 自动解析）

    Returns:
        UserResponse: 当前用户信息
    """
    return UserResponse.model_validate(current_user)


# ========== 密码重置（无需登录） ==========


@router.post(
    "/password-reset/send-code",
    response_model=EmailCodeSendResponse,
    status_code=status.HTTP_200_OK
)
def send_password_reset_code(
    request: PasswordResetRequest,
    db: Session = Depends(get_db)
) -> EmailCodeSendResponse:
    """
    发送密码重置验证码

    - 无需认证
    - 邮箱必须已绑定且已验证

    Args:
        request: 包含邮箱地址的请求体
        db: 数据库会话

    Returns:
        EmailCodeSendResponse: 发送结果信息

    Raises:
        HTTPException 400: 该邮箱未绑定任何已验证账号
        HTTPException 429: 发送过于频繁或已达每日上限
        HTTPException 500: 邮件发送失败
    """
    try:
        return verification_service.send_password_reset_code(
            db,
            request.email,
            verification_email_sender,
        )
    except (
        verification_service.EmailAlreadyRegisteredError,
        verification_service.VerifiedHumanUserNotFoundError,
        verification_service.VerificationCodeFrequencyError,
        verification_service.VerificationCodeDailyLimitError,
        verification_service.EmailDeliveryError,
    ) as exc:
        _raise_send_code_http_error(exc)


@router.post("/password-reset/confirm")
def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    db: Session = Depends(get_db)
) -> dict[str, str]:
    """
    确认密码重置

    - 无需认证
    - 验证码10分钟有效
    - 验证码错误超过次数限制后需要重新获取

    Args:
        request: 包含邮箱、验证码和新密码的请求体
        db: 数据库会话

    Returns:
        dict: 密码重置成功消息

    Raises:
        HTTPException 400: 该邮箱未绑定任何已验证账号
        HTTPException 400: 验证码无效、已过期或尝试次数过多
        HTTPException 400: 验证码错误
    """
    try:
        identity_service.reset_password_with_code(
            db,
            request.email,
            request.code,
            request.new_password,
        )
    except (
        verification_service.VerifiedHumanUserNotFoundError,
        verification_service.VerificationCodeNotFoundError,
        verification_service.VerificationCodeAttemptsExceededError,
        verification_service.VerificationCodeMismatchError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"message": "密码重置成功，请使用新密码登录"}
