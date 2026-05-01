import pytest
from unittest.mock import patch, MagicMock

from agents.management.backend.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)


class TestSecurity:
    def test_verify_password_correct(self):
        hashed = get_password_hash("test_password")
        assert verify_password("test_password", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = get_password_hash("test_password")
        assert verify_password("wrong_password", hashed) is False

    def test_get_password_hash_different(self):
        hash1 = get_password_hash("password1")
        hash2 = get_password_hash("password2")
        assert hash1 != hash2

    def test_get_password_hash_same_input(self):
        hash1 = get_password_hash("same_password")
        hash2 = get_password_hash("same_password")
        assert hash1 != hash2

    def test_create_and_decode_token(self):
        data = {"user_id": 1, "username": "test_user"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["user_id"] == 1
        assert decoded["username"] == "test_user"

    def test_decode_invalid_token(self):
        result = decode_access_token("invalid.token.here")
        assert result is None

    def test_decode_expired_token(self):
        from datetime import timedelta
        data = {"user_id": 1}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        decoded = decode_access_token(token)
        assert decoded is None

    def test_create_access_token_with_expiry(self):
        from datetime import timedelta
        data = {"user_id": 1}
        token = create_access_token(data, expires_delta=timedelta(hours=1))
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["user_id"] == 1
