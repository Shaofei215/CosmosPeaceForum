# 认证路由控制器
# 处理用户注册、登录、获取当前用户信息等认证相关 API 请求
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from social_platform.app.admin.services.moderation_guard import ensure_account_available
from social_platform.app.api.deps import get_access_payload, get_db, get_current_user, security
from social_platform.app.core.config import get_settings
from social_platform.app.core.security import (
    get_password_hash,
    verify_password,
    verify_admin_key,
)
from social_platform.app.domains.user.models import User
from social_platform.app.models.email_verification import EmailVerificationCode
from social_platform.app.models.session import UserSession
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
from social_platform.app.schemas.email_verification import (
    EmailCodeSendRequest,
    EmailCodeSendResponse,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
)
from social_platform.app.services.email_service import email_service
from social_platform.app.domains.search import application as search_service
from social_platform.app.services import session_service


router = APIRouter()
settings = get_settings()


def _request_session_context(request: Request, client_type: str | None = None) -> tuple[str, str | None, str | None]:
    """收集创建/刷新 session 所需的端类型、User-Agent 和 IP。"""
    user_agent = request.headers.get("user-agent")
    return (client_type or session_service.detect_client_type(user_agent), user_agent, session_service.get_request_ip(request))


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


def generate_verification_code(length: int = 6) -> str:
    """
    生成随机数字验证码

    Args:
        length: 验证码长度，默认6位

    Returns:
        str: 随机数字验证码字符串
    """
    return ''.join(random.choices(string.digits, k=length))


def check_send_frequency_by_email(
    db: Session,
    email: str,
    purpose: str
) -> Optional[int]:
    """
    检查发送频率限制

    检查同一邮箱在指定时间间隔内是否已发送过同类验证码

    Args:
        db: 数据库会话
        email: 邮箱地址
        purpose: 验证码用途，用于区分注册和密码重置

    Returns:
        Optional[int]: 如果发送过于频繁，返回还需等待的秒数；否则返回 None
    """
    interval = timedelta(minutes=settings.EMAIL_CODE_SEND_INTERVAL_MINUTES)

    latest_code = db.query(EmailVerificationCode).filter(
        and_(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == purpose
        )
    ).order_by(EmailVerificationCode.created_at.desc()).first()

    if latest_code:
        time_since_last = datetime.utcnow() - latest_code.created_at
        if time_since_last < interval:
            return int((interval - time_since_last).total_seconds())

    return None


def check_daily_limit_by_email(db: Session, email: str) -> bool:
    """
    检查每日发送次数限制

    检查同一邮箱今日已发送验证码次数是否达到上限

    Args:
        db: 数据库会话
        email: 邮箱地址

    Returns:
        bool: 未达上限返回 True，已达上限返回 False
    """
    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    count = db.query(func.count(EmailVerificationCode.id)).filter(
        and_(
            EmailVerificationCode.email == email,
            EmailVerificationCode.created_at >= today_start
        )
    ).scalar()

    return count < settings.EMAIL_CODE_DAILY_LIMIT


# ========== 邮箱验证码发送 ==========


@router.post(
    "/register/send-code",
    response_model=EmailCodeSendResponse,
    status_code=status.HTTP_200_OK
)
def send_register_verification_code(
    request: EmailCodeSendRequest,
    db: Session = Depends(get_db)
):
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
    email = request.email.lower()

    # 检查邮箱是否已被注册
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )

    # 检查发送频率限制
    remaining = check_send_frequency_by_email(db, email, "register")
    if remaining:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"发送过于频繁，请 {remaining} 秒后再试",
            headers={"Retry-After": str(remaining)}
        )

    # 检查每日发送次数限制
    if not check_daily_limit_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日发送次数已达上限，请明天再试"
        )

    # 生成验证码
    code = generate_verification_code()

    # 创建验证码记录
    expires_at = datetime.utcnow() + timedelta(
        minutes=settings.EMAIL_CODE_EXPIRE_MINUTES
    )
    verification = EmailVerificationCode(
        user_id=None,  # 注册阶段用户尚未创建
        email=email,
        code=code,
        purpose="register",
        expires_at=expires_at
    )

    db.add(verification)
    db.commit()

    # 发送邮件
    success = email_service.send_verification_email(email, code, "register")

    if not success:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="邮件发送失败，请稍后重试"
        )

    return EmailCodeSendResponse(
        message="验证码已发送至您的邮箱",
        email=email,
        expires_in=settings.EMAIL_CODE_EXPIRE_MINUTES * 60
    )


@router.post(
    "/login/send-code",
    response_model=EmailCodeSendResponse,
    status_code=status.HTTP_200_OK
)
def send_login_verification_code(
    request: EmailCodeSendRequest,
    db: Session = Depends(get_db)
):
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
    email = request.email.lower()

    # 查找已验证的真人用户
    user = db.query(User).filter(
        and_(
            User.email == email,
            User.email_verified == True,
            User.is_ai_agent == False
        )
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱未绑定任何已验证账号"
        )

    # 检查发送频率限制
    remaining = check_send_frequency_by_email(db, email, "login")
    if remaining:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"发送过于频繁，请 {remaining} 秒后再试",
            headers={"Retry-After": str(remaining)}
        )

    # 检查每日发送次数限制
    if not check_daily_limit_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日发送次数已达上限，请明天再试"
        )

    # 生成验证码
    code = generate_verification_code()

    # 创建验证码记录
    expires_at = datetime.utcnow() + timedelta(
        minutes=settings.EMAIL_CODE_EXPIRE_MINUTES
    )
    verification = EmailVerificationCode(
        user_id=user.id,
        email=email,
        code=code,
        purpose="login",
        expires_at=expires_at
    )

    db.add(verification)
    db.commit()

    # 发送邮件
    success = email_service.send_verification_email(email, code, "login")

    if not success:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="邮件发送失败，请稍后重试"
        )

    return EmailCodeSendResponse(
        message="验证码已发送至您的邮箱",
        email=email,
        expires_in=settings.EMAIL_CODE_EXPIRE_MINUTES * 60
    )


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

    email = user_data.email.lower()

    # 检查邮箱是否已被注册
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )

    # 查询最新的有效验证码（未使用且未过期）
    verification = db.query(EmailVerificationCode).filter(
        and_(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == "register",
            EmailVerificationCode.used == False,
            EmailVerificationCode.expires_at > datetime.utcnow()
        )
    ).order_by(EmailVerificationCode.created_at.desc()).first()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="注册信息无效，请重新获取验证码"
        )

    if not verification.can_attempt(settings.EMAIL_CODE_MAX_ATTEMPTS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证失败次数过多，请重新获取验证码"
        )

    # 验证验证码
    if verification.code != code:
        verification.attempt_count += 1
        db.commit()
        remaining = settings.EMAIL_CODE_MAX_ATTEMPTS - verification.attempt_count
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"验证码错误，还剩 {remaining} 次尝试机会"
        )

    # 验证码验证成功，标记为已使用
    verification.used = True
    verification.used_at = datetime.utcnow()

    # 创建用户（暂时使用临时用户名，后续在资料完善页面更新）
    password_hash = get_password_hash(user_data.password)

    db_user = User(
        username=f"用户_{verification.id}",  # 临时用户名，后续需在资料完善页面更新
        password_hash=password_hash,
        is_ai_agent=False,
        ai_config_id=None,
        email=email,
        email_verified=True,
        email_verified_at=datetime.utcnow(),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # 建立验证码与用户的关联
    verification.user_id = db_user.id
    db.commit()

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

    # 查找已验证的真人用户
    user = db.query(User).filter(
        and_(
            User.email == email,
            User.email_verified == True,
            User.is_ai_agent == False
        )
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

    # 验证码登录方式
    else:
        # 查询最新的有效登录验证码
        verification = db.query(EmailVerificationCode).filter(
            and_(
                EmailVerificationCode.user_id == user.id,
                EmailVerificationCode.email == email,
                EmailVerificationCode.purpose == "login",
                EmailVerificationCode.used == False
            )
        ).order_by(EmailVerificationCode.created_at.desc()).first()

        # 统一错误信息，避免泄露验证码状态（无效、过期、尝试次数过多）
        INVALID_CODE_MESSAGE = "验证码错误"

        # 检查验证码是否存在、是否过期、是否超过尝试次数
        if not verification:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_CODE_MESSAGE
            )

        if verification.is_expired():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_CODE_MESSAGE
            )

        if not verification.can_attempt(settings.EMAIL_CODE_MAX_ATTEMPTS):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_CODE_MESSAGE
            )

        if verification.code != user_data.code:
            verification.attempt_count += 1
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_CODE_MESSAGE
            )

        # 验证成功，标记验证码已使用
        verification.used = True
        verification.used_at = datetime.utcnow()
        db.commit()

    ensure_account_available(db, user)
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

    ensure_account_available(db, user)
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
    token_pair = session_service.refresh_token_pair(
        db=db,
        refresh_token=payload.refresh_token,
        expected_scope="user",
        user_agent=user_agent,
        ip_address=ip_address,
    )
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
):
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
    email = request.email.lower()

    # 查找已验证的真人用户
    user = db.query(User).filter(
        and_(
            User.email == email,
            User.email_verified == True,
            User.is_ai_agent == False
        )
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱未绑定任何已验证账号"
        )

    # 检查发送频率
    remaining = check_send_frequency_by_email(db, email, "reset_password")
    if remaining:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"发送过于频繁，请 {remaining} 秒后再试",
            headers={"Retry-After": str(remaining)}
        )

    # 检查每日限制
    if not check_daily_limit_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日发送次数已达上限，请明天再试"
        )

    # 生成验证码
    code = generate_verification_code()

    # 创建验证码记录
    expires_at = datetime.utcnow() + timedelta(
        minutes=settings.EMAIL_CODE_EXPIRE_MINUTES
    )
    verification = EmailVerificationCode(
        user_id=user.id,
        email=email,
        code=code,
        purpose="reset_password",
        expires_at=expires_at
    )

    db.add(verification)
    db.commit()

    # 发送邮件
    success = email_service.send_verification_email(email, code, "reset_password")

    if not success:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="邮件发送失败，请稍后重试"
        )

    return EmailCodeSendResponse(
        message="验证码已发送至您的邮箱",
        email=email,
        expires_in=settings.EMAIL_CODE_EXPIRE_MINUTES * 60
    )


@router.post("/password-reset/confirm")
def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    db: Session = Depends(get_db)
):
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
    email = request.email.lower()

    # 查找已验证的真人用户
    user = db.query(User).filter(
        and_(
            User.email == email,
            User.email_verified == True,
            User.is_ai_agent == False
        )
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱未绑定任何已验证账号"
        )

    # 查询最新未使用的重置验证码（未使用且未过期）
    verification = db.query(EmailVerificationCode).filter(
        and_(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == "reset_password",
            EmailVerificationCode.used == False,
            EmailVerificationCode.expires_at > datetime.utcnow()
        )
    ).order_by(EmailVerificationCode.created_at.desc()).first()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码无效，请重新获取"
        )

    if not verification.can_attempt(settings.EMAIL_CODE_MAX_ATTEMPTS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证失败次数过多，请重新获取验证码"
        )

    if verification.code != request.code:
        verification.attempt_count += 1
        db.commit()
        remaining = settings.EMAIL_CODE_MAX_ATTEMPTS - verification.attempt_count
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"验证码错误，还剩 {remaining} 次尝试机会"
        )

    # 验证成功，标记验证码已使用
    verification.used = True
    verification.used_at = datetime.utcnow()

    # 更新密码
    user.password_hash = get_password_hash(request.new_password)

    db.commit()

    return {"message": "密码重置成功，请使用新密码登录"}
