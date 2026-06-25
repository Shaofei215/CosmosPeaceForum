"""
运行期会话注入队列。

该模块提供 Scheduler 内部的公共注入接口。注入内容只保存在内存中，
由目标 Agent 的下一次登录会话消费，不会写回角色配置。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from agents.agents_scheduler.scheduler.timezone import local_now
from typing import Any, Iterable, Optional


SESSION_INJECTION_TYPE_PROMPT = "prompt"


@dataclass(frozen=True)
class SessionInjection:
    """一次性会话注入项。"""

    injection_type: str
    content: str
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=local_now)


class SessionInjectionQueue:
    """按 Agent 维度保存待消费的一次性会话注入。"""

    def __init__(self):
        self._pending: dict[int, list[SessionInjection]] = {}
        self._lock = threading.RLock()

    def enqueue(
        self,
        agent_ids: Iterable[int],
        injection_type: str,
        content: str,
        source: str = "unknown",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[int, int]:
        """为多个 Agent 加入一次性注入，返回每个 Agent 的待消费数量。"""
        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("注入内容不能为空")

        injection = SessionInjection(
            injection_type=injection_type,
            content=normalized_content,
            source=source,
            metadata=metadata or {},
        )

        results: dict[int, int] = {}
        with self._lock:
            for agent_id in dict.fromkeys(int(item) for item in agent_ids):
                items = self._pending.setdefault(agent_id, [])
                items.append(injection)
                results[agent_id] = len(items)

        return results

    def consume(
        self,
        agent_id: int,
        injection_type: Optional[str] = None,
    ) -> list[SessionInjection]:
        """消费指定 Agent 的注入项。传入 injection_type 时仅消费该类型。"""
        with self._lock:
            items = self._pending.get(agent_id, [])
            if not items:
                return []

            if injection_type is None:
                self._pending.pop(agent_id, None)
                return items

            matched = [item for item in items if item.injection_type == injection_type]
            remaining = [item for item in items if item.injection_type != injection_type]
            if remaining:
                self._pending[agent_id] = remaining
            else:
                self._pending.pop(agent_id, None)

            return matched

    def count(self, agent_id: int, injection_type: Optional[str] = None) -> int:
        """查询指定 Agent 的待消费注入数量。"""
        with self._lock:
            items = self._pending.get(agent_id, [])
            if injection_type is None:
                return len(items)
            return sum(1 for item in items if item.injection_type == injection_type)


_session_injection_queue = SessionInjectionQueue()


def enqueue_session_injection(
    agent_ids: Iterable[int],
    injection_type: str,
    content: str,
    source: str = "unknown",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[int, int]:
    """公共入口：为目标 Agent 的下一次登录会话加入一次性注入。"""
    return _session_injection_queue.enqueue(
        agent_ids=agent_ids,
        injection_type=injection_type,
        content=content,
        source=source,
        metadata=metadata,
    )


def enqueue_prompt_injection(
    agent_ids: Iterable[int],
    content: str,
    source: str = "unknown",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[int, int]:
    """便捷入口：加入下一次登录会话使用的提示词注入。"""
    return enqueue_session_injection(
        agent_ids=agent_ids,
        injection_type=SESSION_INJECTION_TYPE_PROMPT,
        content=content,
        source=source,
        metadata=metadata,
    )


def consume_prompt_injection_text(agent_id: int) -> str:
    """消费并合并指定 Agent 的提示词注入文本。"""
    injections = _session_injection_queue.consume(
        agent_id=agent_id,
        injection_type=SESSION_INJECTION_TYPE_PROMPT,
    )
    if not injections:
        return ""

    return "\n\n".join(item.content for item in injections if item.content.strip())
