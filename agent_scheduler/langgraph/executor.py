# 会话执行器模块
# 提供 LangGraph 会话的执行器，负责运行单个登录会话的完整生命周期
import uuid
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
import traceback

from .state import SessionState, SessionSummary, ExitReason
from .config import SessionConfig, AgentConfig, get_default_config
from .session_graph import build_session_graph


def _create_openai_llm_invoker(
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> Callable[[str, str], str]:
    """
    创建 OpenAI LLM 调用器

    Args:
        model_name: 模型名称
        temperature: 温度参数
        api_key: API 密钥
        base_url: API 基础 URL

    Returns:
        Callable[[str, str], str]: LLM 调用函数
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ImportError(
            "请安装 langchain-openai: pip install langchain-openai"
        )

    # 创建 LLM 实例
    llm_kwargs = {
        "model": model_name,
        "temperature": temperature,
    }

    if api_key:
        llm_kwargs["api_key"] = api_key

    if base_url:
        llm_kwargs["base_url"] = base_url

    llm = ChatOpenAI(**llm_kwargs)

    def invoke(system_prompt: str, user_prompt: str) -> str:
        """执行 LLM 调用"""
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        return response.content

    return invoke


def _create_anthropic_llm_invoker(
    model_name: str = "claude-sonnet-4-20250514",
    temperature: float = 0.7,
    api_key: Optional[str] = None,
) -> Callable[[str, str], str]:
    """
    创建 Anthropic Claude LLM 调用器

    Args:
        model_name: 模型名称
        temperature: 温度参数
        api_key: API 密钥

    Returns:
        Callable[[str, str], str]: LLM 调用函数
    """
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ImportError(
            "请安装 langchain-anthropic: pip install langchain-anthropic"
        )

    llm_kwargs = {
        "model": model_name,
        "temperature": temperature,
    }

    if api_key:
        llm_kwargs["api_key"] = api_key

    llm = ChatAnthropic(**llm_kwargs)

    def invoke(system_prompt: str, user_prompt: str) -> str:
        """执行 LLM 调用"""
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        return response.content

    return invoke


def create_llm_invoker(
    provider: str = "openai",
    **kwargs
) -> Callable[[str, str], str]:
    """
    创建 LLM 调用器的工厂函数

    Args:
        provider: LLM 提供者，可选 "openai" 或 "anthropic"
        **kwargs: 传递给具体 LLM 实现的其他参数

    Returns:
        Callable[[str, str], str]: LLM 调用函数

    Raises:
        ValueError: 不支持的 provider
    """
    provider = provider.lower()

    if provider == "openai":
        return _create_openai_llm_invoker(**kwargs)
    elif provider == "anthropic":
        return _create_anthropic_llm_invoker(**kwargs)
    else:
        raise ValueError(f"不支持的 LLM 提供者: {provider}")


@dataclass
class ExecutionResult:
    """
    会话执行结果

    包含执行后的状态和各种统计数据。
    """
    session_id: str                                      # 会话 ID
    success: bool                                        # 是否成功完成
    final_state: SessionState                             # 最终状态
    summary: Optional[SessionSummary]                     # 会话总结
    error_message: Optional[str]                         # 错误信息（如果有）
    start_time: datetime                                  # 开始时间
    end_time: datetime                                   # 结束时间
    duration_seconds: float                              # 持续时长

    @property
    def step_count(self) -> int:
        """获取执行的步数"""
        return self.final_state.get("step_count", 0)

    @property
    def exit_reason(self) -> Optional[str]:
        """获取退出原因"""
        exit_reason = self.final_state.get("exit_reason")
        if exit_reason:
            return exit_reason.value if isinstance(exit_reason, ExitReason) else str(exit_reason)
        return None


class SessionExecutor:
    """
    会话执行器

    负责运行单个登录会话的完整生命周期：
    1. 初始化会话状态
    2. 构建带 LLM 的图结构
    3. 执行会话
    4. 生成总结
    5. 返回执行结果

    使用示例：
    ```python
    # 创建执行器
    executor = SessionExecutor(
        user_id=42,
        username="帕姆",
        ai_config_id=0,
        personality_prompt="...",
        personal_signature="..."
    )

    # 创建 LLM 调用器
    llm_invoker = create_llm_invoker("openai", api_key="sk-...")

    # 执行会话
    result = executor.run(llm_invoker)

    # 查看结果
    print(f"执行步数: {result.step_count}")
    print(f"退出原因: {result.exit_reason}")
    print(f"总结: {result.summary}")
    ```
    """

    def __init__(
        self,
        user_id: int,
        username: str,
        ai_config_id: int,
        personality_prompt: str,
        personal_signature: str,
        config: Optional[SessionConfig] = None,
    ):
        """
        初始化会话执行器

        Args:
            user_id: 用户 ID
            username: 用户名
            ai_config_id: AI 配置 ID
            personality_prompt: 角色性格描述
            personal_signature: 个性签名
            config: 会话配置，默认为 SessionConfig()
        """
        self.session_id = str(uuid.uuid4())
        self.start_time = datetime.now()
        self.config = config or get_default_config()
        self.username = username

        print(f"[会话执行器] 初始化会话: 用户={username}, 会话ID={self.session_id[:8]}..., 最大步数={self.config.max_steps}")

        self.initial_state: SessionState = {
            "user_id": user_id,
            "username": username,
            "ai_config_id": ai_config_id,
            "personality_prompt": personality_prompt,
            "personal_signature": personal_signature,
            "step_count": 0,
            "max_steps": self.config.max_steps,
            "exit_reason": None,
            "action_history": [],
            "environment": None,
            "pending_tool": None,
            "last_error": None,
            "summary": None,
        }

    def run(
        self,
        llm_invoker: Callable[[str, str], str],
        thread_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        执行完整会话

        Args:
            llm_invoker: LLM 调用函数，签名为 (system_prompt: str, user_prompt: str) -> str
            thread_id: 线程 ID，用于检查点保存

        Returns:
            ExecutionResult: 包含执行结果的 ExecutionResult 对象
        """
        if thread_id is None:
            thread_id = f"session_{self.session_id}"

        print(f"[会话执行器] 开始执行会话: 用户={self.username}, 会话ID={self.session_id[:8]}...")

        try:
            print(f"[会话执行器] 构建LangGraph图结构")
            graph = build_session_graph(
                config=self.config,
                llm_invoker=llm_invoker
            )

            print(f"[会话执行器] 开始执行图")
            final_state = graph.invoke(self.initial_state)

            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()

            print(f"[会话执行器] 图执行完成: 步数={final_state.get('step_count', 0)}, 耗时={duration:.2f}秒")

            summary = self._build_summary(final_state)
            print(f"[会话执行器] 生成总结: 退出原因={summary.get('exit_reason', 'N/A')}")

            return ExecutionResult(
                session_id=self.session_id,
                success=True,
                final_state=final_state,
                summary=summary,
                error_message=None,
                start_time=self.start_time,
                end_time=self.end_time,
                duration_seconds=duration
            )

        except Exception as e:
            self.end_time = datetime.now()
            error_msg = f"会话执行异常: {str(e)}"
            print(f"[会话执行器] 会话执行异常: {error_msg}")
            traceback.print_exc()

            return ExecutionResult(
                session_id=self.session_id,
                success=False,
                final_state=self.initial_state,
                summary=None,
                error_message=error_msg,
                start_time=self.start_time,
                end_time=self.end_time,
                duration_seconds=(self.end_time - self.start_time).total_seconds()
            )

    def _build_summary(self, state: SessionState) -> SessionSummary:
        """
        构建会话总结

        Args:
            state: 最终状态

        Returns:
            SessionSummary: 会话总结
        """
        # 格式化操作记录
        actions = []
        for record in state.get("action_history", []):
            actions.append({
                "step": record.get("step", 0),
                "tool_name": record.get("tool_name", ""),
                "reason": record.get("reason", ""),
                "result_summary": record.get("result_summary", ""),
            })

        # 获取退出原因
        exit_reason = state.get("exit_reason")
        if exit_reason is None:
            # 如果没有显式退出，检查是否达到最大步数
            if state.get("step_count", 0) >= state.get("max_steps", 10):
                exit_reason = ExitReason.MAX_STEPS_REACHED
            else:
                exit_reason = ExitReason.USER_CHOICE

        if isinstance(exit_reason, ExitReason):
            exit_reason_str = exit_reason.value
        else:
            exit_reason_str = str(exit_reason)

        # 构建总结
        summary_text = state.get("summary", "")
        if not summary_text:
            summary_text = f"用户 {state.get('username', '未知')} 执行了 {len(actions)} 个操作。"

        return SessionSummary(
            session_id=self.session_id,
            user_id=state.get("user_id", 0),
            username=state.get("username", ""),
            ai_config_id=state.get("ai_config_id", 0),
            start_time=self.start_time.isoformat(),
            end_time=self.end_time.isoformat(),
            duration_seconds=(self.end_time - self.start_time).total_seconds(),
            step_count=state.get("step_count", 0),
            exit_reason=exit_reason_str,
            actions=actions,
            narrative=summary_text,
        )

    def __repr__(self) -> str:
        """返回执行器的字符串表示"""
        return (
            f"SessionExecutor("
            f"session_id={self.session_id[:8]}..., "
            f"username={self.config}, "
            f"max_steps={self.config.max_steps}"
            f")"
        )


def run_session(
    agent_config: AgentConfig,
    llm_invoker: Callable[[str, str], str],
    config: Optional[SessionConfig] = None,
) -> ExecutionResult:
    """
    运行会话的便捷函数

    这是一个一键执行会话的函数，适用于简单的使用场景。

    Args:
        agent_config: Agent 配置
        llm_invoker: LLM 调用函数
        config: 会话配置

    Returns:
        ExecutionResult: 包含执行结果的 ExecutionResult 对象
    """
    executor = SessionExecutor(
        user_id=agent_config.user_id,
        username=agent_config.username,
        ai_config_id=agent_config.ai_config_id,
        personality_prompt=agent_config.personality_prompt,
        personal_signature=agent_config.personal_signature,
        config=config,
    )

    return executor.run(llm_invoker)
