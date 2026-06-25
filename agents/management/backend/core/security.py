"""
Management Backend - 安全认证模块。

负责管理员密码哈希、短期 access JWT 签发/解析，以及 opaque refresh token
生成与哈希。access token 会携带 typ=access 与 jti，sid/scope 由 session service 写入。
"""

from datetime import datetime, timedelta
from agents.management.backend.core.timezone import local_now
from hashlib import sha256
from secrets import token_urlsafe
from typing import Optional
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from agents.management.backend.core.config import get_config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否匹配 passlib 哈希。"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成用于存储的管理员密码哈希。"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建短期 management access token。

    Args:
        data: 要编码的数据；session 化调用应包含 sub、scope、sid。
        expires_delta: 过期时间增量，默认使用 management 分钟级配置。

    Returns:
        str: JWT token。

    Notes:
        函数会强制补充 typ=access 与 jti，实际可用性还要由 admin_sessions 回查决定。
    """
    to_encode = data.copy()
    if expires_delta:
        expire = local_now() + expires_delta
    else:
        config = get_config()
        expire = local_now() + timedelta(minutes=config.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire, "typ": "access", "jti": to_encode.get("jti") or str(uuid4())})
    config = get_config()
    encoded_jwt = jwt.encode(to_encode, config.jwt_secret_key, algorithm=config.jwt_algorithm)
    return encoded_jwt


def create_refresh_token() -> str:
    """生成 management admin refresh token 明文，只在响应中返回给客户端。"""
    return token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """返回 refresh token 哈希，admin_sessions 只保存该值。"""
    return sha256(token.encode("utf-8")).hexdigest()


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码 JWT token。

    Args:
        token: JWT Token

    Returns:
        Optional[dict]: Token 中的数据，解码失败返回 None
    """
    try:
        config = get_config()
        payload = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
        return payload
    except JWTError:
        return None
