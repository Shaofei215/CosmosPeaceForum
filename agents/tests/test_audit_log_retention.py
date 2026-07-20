"""Management 审计日志上下文与保留期限测试。"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlmodel import Session

from agents.management.backend.api import auth as auth_api
from agents.logging_config import logging_context
from agents.management.backend.core.timezone import local_now
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.models.operation_log import OperationLog
from agents.management.backend.schemas import LoginRequest
from agents.management.backend.services import log_service
from agents.management.backend.services.log_service import cleanup_expired_logs, create_log


def test_audit_context_and_thirty_day_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """审计清理应删除早于 30 天的记录，并保留恰好位于边界的记录。"""

    reference_time = local_now()
    monkeypatch.setattr(log_service, "local_now", lambda: reference_time)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    OperationLog.__table__.create(engine)
    with Session(engine) as db:
        with logging_context(request_id="audit-request", client_ip="203.0.113.8"):
            current = create_log(db, None, "current_action", "system")
        old = OperationLog(
            action="old_action",
            target_type="system",
            details="{}",
            created_at=reference_time - timedelta(days=31),
        )
        boundary = OperationLog(
            action="boundary_action",
            target_type="system",
            details="{}",
            created_at=reference_time - timedelta(days=30),
        )
        db.add(old)
        db.add(boundary)
        db.commit()

        deleted = cleanup_expired_logs(db, 30)

        assert deleted == 1
        assert db.get(OperationLog, current.id) is not None
        assert db.get(OperationLog, boundary.id) is not None
        details = json.loads(db.get(OperationLog, current.id).details)
        assert details["request_id"] == "audit-request"
        assert details["client_ip"] == "203.0.113.8"


def test_management_login_audits_success_once_and_not_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Management 登录成功只写一次审计，认证失败不写成功审计。"""

    admin = AdminUser(id=1, username="admin", password_hash="unused", permissions="[]")
    token_pair = {
        "access_token": "access",
        "refresh_token": "r" * 32,
        "expires_in": 900,
        "refresh_expires_in": 3600,
        "session_id": "session-1",
    }
    audit = MagicMock()
    db = MagicMock()
    http_request = Request({"type": "http", "headers": [], "client": None})
    monkeypatch.setattr(auth_api, "authenticate_admin", MagicMock(return_value=admin))
    monkeypatch.setattr(auth_api, "update_last_login", MagicMock())
    monkeypatch.setattr(auth_api.session_service, "create_session_token_pair", MagicMock(return_value=token_pair))
    monkeypatch.setattr(auth_api, "create_log", audit)

    auth_api.login(LoginRequest(username="admin", password="correct"), http_request, db)

    audit.assert_called_once()
    assert audit.call_args.args[2] == "admin_login"

    audit.reset_mock()
    monkeypatch.setattr(auth_api, "authenticate_admin", MagicMock(return_value=None))
    with pytest.raises(HTTPException) as exc_info:
        auth_api.login(LoginRequest(username="admin", password="wrong"), http_request, db)
    assert exc_info.value.status_code == 401
    audit.assert_not_called()
