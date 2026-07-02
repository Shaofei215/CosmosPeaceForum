"""共享平台工具执行上下文。

上下文由内部 LangGraph adapter 或外部 HTTP adapter 构造。共享核心不读取
Scheduler 线程状态，也不处理 Bearer Token 解析，只使用显式传入的数据执行工具。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from agents.platform_access import PlatformClient


class RelationExpander(Protocol):
    """内部 Agent 关系名映射服务协议。"""

    def expand_author(self, username: str, user_id: int | None, owner_id: int | None) -> str:
        """按当前 Agent 关系映射扩展作者名。"""

    def expand_content_mentions(self, content: str, owner_id: int | None) -> str:
        """按当前 Agent 关系映射扩展正文中的 @mention。"""


@dataclass
class PlatformToolContext:
    """单次共享平台工具调用上下文。

    Args:
        client: 显式 Token 平台客户端。
        access_token: 当前公开平台 Access Token；外部网关必须传入有效 Token。
        current_user: 当前账号信息，通常来自 `/auth/me`。
        cursor: 内部滚动状态；外部由网关解码签名游标后传入。
        relation_expander: 内部 Agent 可选关系名映射服务。
        profile_sync: 内部 Agent 可选的资料同步回调；外部 Agent 不提供。
    """

    client: PlatformClient
    access_token: str | None
    current_user: dict[str, Any] | None = None
    cursor: dict[str, Any] | None = None
    relation_expander: RelationExpander | None = None
    profile_sync: Callable[[dict[str, Any]], bool] | None = None

    @property
    def current_user_id(self) -> int | None:
        """返回当前用户 ID。"""

        if not self.current_user:
            return None
        value = self.current_user.get("id")
        return int(value) if value is not None else None

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """使用当前上下文调用公开平台。"""

        return self.client.request(
            method,
            endpoint,
            access_token=self.access_token,
            json_data=json_data,
            params=params,
        )
