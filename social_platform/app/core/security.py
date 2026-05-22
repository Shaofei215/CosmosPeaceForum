# 安全工具模块
# 提供密码哈希、JWT Token 生成和验证等功能
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import bcrypt
from jose import JWTError, jwt

from social_platform.app.core.config import get_settings


settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希密码是否匹配

    Args:
        plain_password: 明文密码
        hashed_password: 数据库中存储的哈希密码

    Returns:
        bool: 密码匹配返回 True，否则返回 False
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """
    对明文密码进行 BCrypt 哈希

    Args:
        password: 明文密码

    Returns:
        str: 哈希后的密码字符串
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT Access Token

    Args:
        data: 要编码到 Token 中的数据字典
        expires_delta: Token 过期时间增量，如果为 None 则使用默认配置

    Returns:
        str: 编码后的 JWT Token 字符串
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解码并验证 JWT Token

    Args:
        token: JWT Token 字符串

    Returns:
        Optional[Dict[str, Any]]: 解码成功返回数据字典，失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_admin_key(admin_key: str) -> bool:
    """
    验证 Admin Key 是否正确

    Args:
        admin_key: 待验证的管理员密钥

    Returns:
        bool: 密钥匹配返回 True，否则返回 False
    """
    return admin_key == settings.ADMIN_KEY
