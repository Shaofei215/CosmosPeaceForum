"""公开平台管理员审计日志上下文与保留期限测试。"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from social_platform.app.admin.api import auth as auth_api
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.models.operation_log import PlatformAdminOperationLog
from social_platform.app.admin.schemas import AdminLoginRequest
from social_platform.app.admin.services import log_service
from social_platform.app.admin.services.log_service import (
    cleanup_expired_operation_logs,
    create_operation_log,
)
from social_platform.app.core.logging import logging_context
from social_platform.app.core.timezone import local_now


def test_audit_context_and_thirty_day_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """审计清理应删除早于 30 天的记录，并保留恰好位于边界的记录。"""

    reference_time = local_now()
    monkeypatch.setattr(log_service, "local_now", lambda: reference_time)
    engine = create_engine("sqlite://")
    PlatformAdminOperationLog.__table__.create(engine)
    with Session(engine) as db:
        with logging_context(request_id="audit-request", client_ip="198.51.100.9"):
            current = create_operation_log(db, None, "current_action", "system")
            db.commit()
            db.refresh(current)
        old = PlatformAdminOperationLog(
            action="old_action",
            target_type="system",
            details="{}",
            created_at=reference_time - timedelta(days=31),
        )
        boundary = PlatformAdminOperationLog(
            action="boundary_action",
            target_type="system",
            details="{}",
            created_at=reference_time - timedelta(days=30),
        )
        db.add(old)
        db.add(boundary)
        db.commit()

        deleted = cleanup_expired_operation_logs(db, 30)

        assert deleted == 1
        persisted = db.get(PlatformAdminOperationLog, current.id)
        assert persisted is not None
        assert db.get(PlatformAdminOperationLog, boundary.id) is not None
        details = json.loads(persisted.details)
        assert details["request_id"] == "audit-request"
        assert details["client_ip"] == "198.51.100.9"


@pytest.mark.asyncio
async def test_platform_login_audits_success_once_and_not_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """平台管理员登录成功只写一次审计，认证失败不写成功审计。"""

    now = local_now()
    admin = PlatformAdminUser(
        id=1,
        username="admin",
        password_hash="unused",
        permissions="[]",
        is_active=True,
        is_super_admin=True,
        must_change_credentials=False,
        created_at=now,
        updated_at=now,
    )
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
    monkeypatch.setattr(auth_api.auth_service, "authenticate_admin", MagicMock(return_value=admin))
    monkeypatch.setattr(auth_api.auth_service, "update_last_login", MagicMock())
    monkeypatch.setattr(auth_api.session_service, "create_session_token_pair", MagicMock(return_value=token_pair))
    monkeypatch.setattr(auth_api, "create_operation_log", audit)

    await auth_api.login(AdminLoginRequest(username="admin", password="correct"), http_request, db)

    audit.assert_called_once()
    assert audit.call_args.args[2] == "admin_login"

    audit.reset_mock()
    monkeypatch.setattr(auth_api.auth_service, "authenticate_admin", MagicMock(return_value=None))
    with pytest.raises(HTTPException) as exc_info:
        await auth_api.login(AdminLoginRequest(username="admin", password="wrong"), http_request, db)
    assert exc_info.value.status_code == 401
    audit.assert_not_called()
