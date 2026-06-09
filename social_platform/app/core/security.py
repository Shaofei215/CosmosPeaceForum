"""公开平台安全工具。

负责密码哈希、短期 access JWT 签发/解析，以及 refresh token 的生成和哈希。
access token 会自动补充 typ=access 与 jti；sid/scope 由调用方传入并在依赖层回查 session。
"""
from datetime import datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Optional, Dict, Any
from uuid import uuid4

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
    创建短期 JWT access token。

    Args:
        data: 要编码到 token 中的数据；session 化调用应包含 sub、scope、sid。
        expires_delta: token 过期时间增量；兼容旧调用时可为空。

    Returns:
        str: 编码后的 JWT token 字符串。

    Notes:
        函数会强制补充 typ=access 与 jti，旧版无 typ/sid 的 JWT 将在依赖层被拒绝。
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "typ": "access", "jti": to_encode.get("jti") or str(uuid4())})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token() -> str:
    """生成只返回给客户端的高熵 opaque refresh token。

    refresh token 不使用 JWT，避免它脱离服务端 session 独立长期有效。
    """
    return token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """返回 refresh token 的 SHA-256 哈希，数据库永不保存明文 token。"""
    return sha256(token.encode("utf-8")).hexdigest()


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
