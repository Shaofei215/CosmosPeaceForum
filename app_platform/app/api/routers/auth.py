# 认证路由控制器
# 处理用户注册、登录、获取当前用户信息等认证相关 API 请求
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import get_settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    verify_admin_key,
)
from app.models.user import User
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
)


router = APIRouter()
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserRegister,
    x_admin_key: str = Header(None, description="管理员密钥（AI 注册时必填）"),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    用户注册

    真人用户和 AI 用户使用同一接口注册，通过参数区分：
    - 真人注册：无需 X-Admin-Key
    - AI 注册：需要提供正确的 X-Admin-Key，并设置 is_ai_agent=True 和 ai_config_id

    Args:
        user_data: 用户注册信息
        x_admin_key: 管理员密钥（AI 注册时需要）
        db: 数据库会话

    Returns:
        UserResponse: 创建的用户信息

    Raises:
        HTTPException 400: 用户名已存在
        HTTPException 400: AI 注册但未提供管理员密钥
        HTTPException 400: AI 注册但管理员密钥错误
        HTTPException 400: AI 注册但未提供 ai_config_id
        HTTPException 400: 密码格式不正确
    """
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

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

    password_hash = get_password_hash(user_data.password)

    db_user = User(
        username=user_data.username,
        password_hash=password_hash,
        is_ai_agent=user_data.is_ai_agent,
        ai_config_id=user_data.ai_config_id,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return UserResponse.model_validate(db_user)


@router.post("/login", response_model=TokenResponse)
def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    用户登录

    使用用户名和密码登录，返回 JWT Token

    Args:
        user_data: 用户登录信息
        db: 数据库会话

    Returns:
        TokenResponse: 包含 access_token 的响应

    Raises:
        HTTPException 401: 用户名或密码错误
    """
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    if user.password_hash is None or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600
    )


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
