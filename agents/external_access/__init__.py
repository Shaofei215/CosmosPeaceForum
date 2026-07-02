"""外部 Agent 公开工具网关。

该包只负责 HTTP 接入、身份预检、工具注册、参数校验和平台访问适配。它不读取
Scheduler 线程上下文，不进入 LangGraph、Prompt、记忆或 Management 业务路由。
"""

from agents.external_access.router import router

__all__ = ["router"]
