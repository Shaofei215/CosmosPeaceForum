import pytest

from agents.agents_scheduler.scheduler.session_injections import (
    SESSION_INJECTION_TYPE_PROMPT,
    SessionInjectionQueue,
)


def test_session_injection_queue_consumes_once():
    queue = SessionInjectionQueue()

    queue.enqueue(
        agent_ids=[1],
        injection_type=SESSION_INJECTION_TYPE_PROMPT,
        content="临时关注黑塔空间站",
        source="test",
    )

    first = queue.consume(1, SESSION_INJECTION_TYPE_PROMPT)
    second = queue.consume(1, SESSION_INJECTION_TYPE_PROMPT)

    assert [item.content for item in first] == ["临时关注黑塔空间站"]
    assert second == []


def test_session_injection_queue_deduplicates_agent_ids():
    queue = SessionInjectionQueue()

    result = queue.enqueue(
        agent_ids=[1, 1, 2],
        injection_type=SESSION_INJECTION_TYPE_PROMPT,
        content="测试注入",
    )

    assert result == {1: 1, 2: 1}
    assert queue.count(1, SESSION_INJECTION_TYPE_PROMPT) == 1
    assert queue.count(2, SESSION_INJECTION_TYPE_PROMPT) == 1


def test_session_injection_queue_rejects_empty_content():
    queue = SessionInjectionQueue()

    with pytest.raises(ValueError):
        queue.enqueue(
            agent_ids=[1],
            injection_type=SESSION_INJECTION_TYPE_PROMPT,
            content="   ",
        )
