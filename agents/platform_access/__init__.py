"""agents 访问公开社交平台的共享边界。

内建 LangChain adapter 和后续外部网关都通过这里使用显式 Access Token 与可信
服务身份，避免业务请求函数读取 Scheduler 的线程局部状态。
"""

from agents.platform_access.client import (
    PlatformAccessError,
    PlatformAuthenticationError,
    PlatformClient,
    PlatformConnectionError,
    PlatformNotFoundError,
    PlatformTimeoutError,
    build_agent_service_headers,
)

__all__ = [
    "PlatformAccessError",
    "PlatformAuthenticationError",
    "PlatformClient",
    "PlatformConnectionError",
    "PlatformNotFoundError",
    "PlatformTimeoutError",
    "build_agent_service_headers",
]
