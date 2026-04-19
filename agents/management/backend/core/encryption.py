"""
Management Backend - 加密模块

已废弃：API Key 改为明文存储，不再使用加密。
保留此文件仅为避免 ImportError。
"""


def encrypt_value(plaintext: str) -> str:
    """已废弃：返回明文"""
    return plaintext


def decrypt_value(ciphertext: str) -> str:
    """已废弃：返回明文"""
    return ciphertext
