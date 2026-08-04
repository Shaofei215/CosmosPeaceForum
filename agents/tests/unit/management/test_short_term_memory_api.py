"""Management 短期记忆 API 契约单测。"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from agents.management.backend.api.short_term_memories import (
    read_short_term_memory,
    replace_short_term_memory,
)
from agents.management.backend.schemas import (
    ShortTermMemoryResponse,
    ShortTermMemoryUpdateRequest,
)


def test_read_short_term_memory_returns_explicit_empty_state() -> None:
    """尚未建立快照的角色仍应得到可编辑的空状态，而不是 404。"""

    memory = ShortTermMemoryResponse(agent_id=7, content="")
    with patch(
        "agents.management.backend.api.short_term_memories.get_short_term_memory",
        return_value=memory,
    ):
        response = read_short_term_memory(7, MagicMock(), MagicMock())

    assert response.revision == 0
    assert response.content == ""


def test_replace_short_term_memory_allows_clear_and_audits_metadata_only() -> None:
    """人类可清空完整快照，审计日志不应复制私有 Markdown 正文。"""

    memory = ShortTermMemoryResponse(
        agent_id=7,
        content="",
        revision=3,
        updated_at=500.0,
        updated_login_count=2,
    )
    db = MagicMock()
    admin = MagicMock()
    with (
        patch(
            "agents.management.backend.api.short_term_memories.update_short_term_memory",
            return_value=memory,
        ) as update_memory,
        patch(
            "agents.management.backend.api.short_term_memories.create_log"
        ) as create_log,
    ):
        response = replace_short_term_memory(
            7,
            ShortTermMemoryUpdateRequest(content=""),
            db,
            admin,
        )

    assert response.revision == 3
    update_memory.assert_called_once_with(db, 7, "")
    assert create_log.call_args.kwargs["details"] == {
        "revision": 3,
        "cleared": True,
    }


def test_short_term_memory_api_rejects_unknown_agent() -> None:
    """Management API 不允许为不存在的内部角色创建游离快照。"""

    with patch(
        "agents.management.backend.api.short_term_memories.get_short_term_memory",
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            read_short_term_memory(999, MagicMock(), MagicMock())

    assert exc_info.value.status_code == 404
