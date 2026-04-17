"""
Management Backend - 加密模块
使用 Fernet (AES) 对 API Key 等敏感信息进行加密存储
"""

from cryptography.fernet import Fernet, InvalidToken

from agent_scheduler.management.backend.core.config import get_config

_fernet = None


def _get_fernet() -> Fernet:
    """获取 Fernet 实例（单例）"""
    global _fernet
    if _fernet is None:
        config = get_config()
        key = config.encryption_key
        if isinstance(key, str):
            key = key.encode()
        _fernet = Fernet(key)
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """
    加密敏感值

    Args:
        plaintext: 明文值

    Returns:
        str: Base64 编码的密文
    """
    if not plaintext:
        return ""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """
    解密敏感值

    Args:
        ciphertext: 密文

    Returns:
        str: 明文值

    Raises:
        ValueError: 解密失败
    """
    if not ciphertext:
        return ""
    try:
        fernet = _get_fernet()
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise ValueError(f"解密失败: {e}")
