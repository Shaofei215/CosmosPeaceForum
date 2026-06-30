"""外部滚动游标签名工具。

游标只保存工具名、查询条件、偏移量和过期时间，不包含账号密码、Token、Prompt、
对话历史或长期记忆。签名用于防止客户端篡改分页条件。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any


class CursorError(Exception):
    """滚动游标无效、过期或签名不匹配。"""


def _b64url_encode(data: bytes) -> str:
    """编码为无填充 URL 安全 Base64。"""

    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    """解码无填充 URL 安全 Base64。"""

    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}".encode("ascii"))


def encode_cursor(payload: dict[str, Any], secret: str, ttl_seconds: int = 1800) -> str:
    """生成签名滚动游标。

    Args:
        payload: 可滚动页面的上下文。
        secret: HMAC 签名密钥。
        ttl_seconds: 游标有效期秒数。

    Returns:
        str: 可返回给外部 Agent 的签名游标。
    """

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    body = {**payload, "exp": int(expires_at.timestamp()), "v": 1}
    body_bytes = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    encoded_body = _b64url_encode(body_bytes)
    signature = hmac.new(secret.encode(), encoded_body.encode(), hashlib.sha256).digest()
    return f"{encoded_body}.{_b64url_encode(signature)}"


def decode_cursor(cursor: str, secret: str) -> dict[str, Any]:
    """验证并解码滚动游标。

    Args:
        cursor: 客户端提交的游标。
        secret: HMAC 签名密钥。

    Returns:
        dict[str, Any]: 游标载荷。

    Raises:
        CursorError: 游标结构、签名或有效期不合法。
    """

    try:
        encoded_body, encoded_signature = cursor.split(".", 1)
    except ValueError as exc:
        raise CursorError("scroll_cursor 格式无效") from exc

    expected = hmac.new(secret.encode(), encoded_body.encode(), hashlib.sha256).digest()
    try:
        actual = _b64url_decode(encoded_signature)
    except ValueError as exc:
        raise CursorError("scroll_cursor 编码无效") from exc
    if not hmac.compare_digest(expected, actual):
        raise CursorError("scroll_cursor 签名无效")

    try:
        payload = json.loads(_b64url_decode(encoded_body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise CursorError("scroll_cursor 内容无效") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(datetime.now(timezone.utc).timestamp()):
        raise CursorError("scroll_cursor 已过期")
    return payload
