# 线程局部存储模块
# 用于在多线程环境中存储每个 Agent 的上下文信息
import threading
from typing import Any, Callable, Dict, Optional


class AgentContext:
    """
    Agent 执行上下文

    用于在当前线程中存储 Agent 的执行状态和认证信息。
    每个 Agent 调度器运行在独立线程中，通过此模块实现线程安全的上下文管理。

    Attributes:
        user_id: 当前 Agent 的用户 ID
        username: 当前 Agent 的用户名
        agent_id: 当前 Agent 的配置 ID
        token: 当前 Agent 的访问令牌（JWT Token）
        user_config: 当前 Agent 的配置信息字典

    Thread Safety:
        使用 threading.local() 确保每个线程有独立的上下文实例，
        不同线程之间互不干扰。
    """

    def __init__(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        agent_id: Optional[int] = None,
        token: Optional[str] = None,
        user_config: Optional[Dict[str, Any]] = None,
        stop_event: Optional[threading.Event] = None,
        personal_signature: Optional[str] = None,
        profile_sync: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ):
        """初始化当前调度线程的 Agent 上下文。

        Args:
            user_id: 当前公开平台用户 ID。
            username: 当前用户名。
            agent_id: management 中的 Agent 配置 ID。
            token: 当前公开平台访问令牌。
            user_config: 当前登录统计等会话配置。
            stop_event: 调度线程停止事件。
            personal_signature: 当前公开平台个人签名。
            profile_sync: 资料更新成功后的内部同步回调。
        """

        self.user_id = user_id
        self.username = username
        self.agent_id = agent_id
        self.token = token
        self.user_config = user_config or {}
        self.stop_event = stop_event
        self.personal_signature = personal_signature
        self.profile_sync = profile_sync


_thread_local = threading.local()


def get_current_context() -> Optional[AgentContext]:
    """
    获取当前线程的 Agent 上下文

    Returns:
        Optional[AgentContext]: 当前线程的上下文对象，如果未设置则返回 None
    """
    return getattr(_thread_local, 'context', None)


def set_current_context(context: AgentContext) -> None:
    """
    设置当前线程的 Agent 上下文

    Args:
        context: Agent 上下文对象
    """
    _thread_local.context = context


def clear_current_context() -> None:
    """
    清除当前线程的 Agent 上下文

    在 Agent 完成执行或调度器停止时调用，清理线程本地存储。
    """
    if hasattr(_thread_local, 'context'):
        del _thread_local.context


def get_current_token() -> Optional[str]:
    """
    获取当前线程的访问令牌

    这是获取当前 Agent 认证令牌的标准方式。
    工具函数应使用此方法获取 Token，而不是让 Agent 传入。

    Returns:
        Optional[str]: 当前线程的 JWT Token，如果未设置则返回 None
    """
    context = get_current_context()
    if context:
        return context.token
    return None


def get_current_user_id() -> Optional[int]:
    """
    获取当前线程的用户 ID

    Returns:
        Optional[int]: 当前 Agent 的用户 ID，如果未设置则返回 None
    """
    context = get_current_context()
    if context:
        return context.user_id
    return None


def get_current_username() -> Optional[str]:
    """
    获取当前线程的用户名

    Returns:
        Optional[str]: 当前 Agent 的用户名，如果未设置则返回 None
    """
    context = get_current_context()
    if context:
        return context.username
    return None


def get_current_agent_id() -> Optional[int]:
    """
    获取当前线程的 AI 配置 ID

    Returns:
        Optional[int]: 当前 Agent 的配置 ID，如果未设置则返回 None
    """
    context = get_current_context()
    if context:
        return context.agent_id
    return None


def is_stop_requested() -> bool:
    """当前 Agent 线程是否已收到停止请求。"""
    context = get_current_context()
    return bool(context and context.stop_event and context.stop_event.is_set())
