# 会话执行器模块
# 提供 LangGraph 会话的执行器，负责运行单个登录会话的完整生命周期
import logging
import threading
import uuid
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime
from dataclasses import dataclass, field
import traceback

from agents.agents_scheduler.langgraph.state import SessionState, SessionSummary, ExitReason
from agents.agents_scheduler.langgraph.config import SessionConfig, AgentConfig, get_default_config
from agents.agents_scheduler.langgraph.session_graph import build_session_graph
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


def create_llm_invoker(
    config: SessionConfig,
    tools: Optional[List] = None,
) -> Callable[[str, str], AIMessage]:
    """
    根据 SessionConfig 创建 LLM 调用器

    Args:
        config: 会话配置，包含 LLM 相关的所有配置
        tools: LangChain 工具列表，用于绑定到 LLM

    Returns:
        Callable[[str, str], AIMessage]: LLM 调用函数，返回 AIMessage
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        try:
            from langchain_anthropic import ChatAnthropic
            use_anthropic = True
            use_openai = False
        except ImportError:
            raise ImportError(
                "请安装 langchain-openai 或 langchain-anthropic"
            )
    else:
        use_openai = True
        use_anthropic = False

    if config.llm_provider.lower() == "anthropic":
        model_name = config.anthropic_model_name or config.model_name
        if not model_name:
            raise ValueError("Anthropic 模型名称未配置，请在 model_configs 中设置第一个活跃模型")
        if not config.anthropic_api_key:
            raise ValueError("Anthropic API Key 未配置，请在 model_configs 中添加一个 is_active=1 的 Anthropic 模型")
        temperature = config.temperature

        if not use_anthropic:
            from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model=model_name, temperature=temperature, api_key=config.anthropic_api_key)
    else:
        model_name = config.openai_model_name or config.model_name
        if not model_name:
            raise ValueError("OpenAI 模型名称未配置，请在 model_configs 中设置第一个活跃模型")
        if not config.openai_api_key:
            raise ValueError("OpenAI API Key 未配置，请在 model_configs 中添加一个 is_active=1 的 OpenAI 模型")
        temperature = config.temperature
        api_key = config.openai_api_key
        base_url = config.openai_base_url or None

        llm_kwargs = {"model": model_name, "temperature": temperature, "api_key": api_key}
        if base_url:
            llm_kwargs["base_url"] = base_url

        llm = ChatOpenAI(**llm_kwargs)

    if tools:
        llm = llm.bind_tools(tools)

    def invoke(system_prompt: str, user_prompt: str) -> AIMessage:
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        return response

    return invoke


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
        agent_id=1,
        personality_prompt="...",
        personal_signature="..."
    )

    # 从配置创建 LLM 调用器
    llm_invoker = create_llm_invoker(executor.config)

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
        agent_id: int,
        personality_prompt: str,
        personal_signature: str,
        config: Optional[SessionConfig] = None,
        name: Optional[str] = None,
        session_prompt_injection: str = "",
    ):
        """
        初始化会话执行器

        Args:
            user_id: 用户 ID
            username: 用户名
            agent_id: AI 配置 ID
            personality_prompt: 角色性格描述
            personal_signature: 个性签名
            config: 会话配置，默认为 SessionConfig()
            name: 昵称（显示用），默认为 username
            session_prompt_injection: 本次登录会话的一次性提示词注入
        """
        self.session_id = str(uuid.uuid4())
        self.start_time = datetime.now()
        self.config = config or get_default_config()
        self.username = username
        self.name = name or username

        logger.info("初始化会话: 用户=%s, 会话ID=%s..., 最大步数=%d", username, self.session_id[:8], self.config.max_steps)

        self.initial_state: SessionState = {
            "user_id": user_id,
            "username": username,
            "name": self.name,
            "agent_id": agent_id,
            "personality_prompt": personality_prompt,
            "personal_signature": personal_signature,
            "session_prompt_injection": session_prompt_injection,
            "step_count": 0,
            "max_steps": self.config.max_steps,
            "exit_reason": None,
            "action_history": [],
            "current_location": "主页（信息流）",
            "last_tool_result": None,
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
            "summary": None,
            "recalled_memories": "",
        }

    def run(
        self,
        llm_invoker: Callable[[str, str], AIMessage],
        thread_id: Optional[str] = None,
        summarize_llm_invoker: Optional[Callable[[str, str], AIMessage]] = None
    ) -> ExecutionResult:
        """
        执行完整会话

        Args:
            llm_invoker: LLM 调用函数，签名为 (system_prompt: str, user_prompt: str) -> AIMessage
            thread_id: 线程 ID，用于检查点保存
            summarize_llm_invoker: 总结节点的 LLM 调用函数，只绑定 write_memory 工具

        Returns:
            ExecutionResult: 包含执行结果的 ExecutionResult 对象
        """
        if thread_id is None:
            thread_id = f"session_{self.session_id}"

        logger.info("开始执行会话: 用户=%s, 会话ID=%s...", self.username, self.session_id[:8])

        try:
            logger.info("构建LangGraph图结构")
            graph = build_session_graph(
                config=self.config,
                llm_invoker=llm_invoker,
                summarize_llm_invoker=summarize_llm_invoker
            )

            logger.info("开始执行图")
            final_state = graph.invoke(
                self.initial_state,
                config={"recursion_limit": 100}
            )

            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()

            logger.info("图执行完成: 步数=%d, 耗时=%.2f秒", final_state.get('step_count', 0), duration)

            summary = self._build_summary(final_state)
            logger.info("生成总结: 退出原因=%s", summary.get('exit_reason', 'N/A'))

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
            logger.error("会话执行异常: %s", error_msg)
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
            agent_id=state.get("agent_id", 0),
            start_time=self.start_time.isoformat(),
            end_time=self.end_time.isoformat(),
            duration_seconds=(self.end_time - self.start_time).total_seconds(),
            step_count=state.get("step_count", 0),
            exit_reason=exit_reason_str,
            actions=actions,
            narrative=summary_text,
        )

    def __repr__(self) -> str:
        return (
            f"SessionExecutor("
            f"session_id={self.session_id[:8]}..., "
            f"username={self.username}, "
            f"max_steps={self.config.max_steps}"
            f")"
        )


class LLMRegistry:
    """
    LLM 调用器注册表

    提供 LLM 调用器的缓存和热更新功能。
    缓存基于 SessionConfig 的模型参数与绑定工具。
    """
    _cache = {}
    _lock = threading.Lock()

    @classmethod
    def get_invoker(cls, config: SessionConfig, tools: Optional[List] = None) -> Callable:
        """
        获取 LLM 调用器（带参数缓存）

        Args:
            config: 会话配置
            tools: 工具列表

        Returns:
            Callable: LLM 调用器
        """
        cache_key = (
            config.model_config_id,
            config.llm_provider,
            config.openai_api_key,
            config.openai_base_url,
            config.openai_model_name,
            config.model_name,
            config.anthropic_api_key,
            config.anthropic_model_name,
            config.temperature,
            config.web_search_enabled,
            bool(config.tavily_api_key),
            tuple(t.name for t in tools or []),
        )

        with cls._lock:
            if cache_key in cls._cache:
                return cls._cache[cache_key]

            invoker = create_llm_invoker(config, tools=tools)
            cls._cache[cache_key] = invoker
            return invoker

    @classmethod
    def clear_cache(cls):
        """清除所有缓存（热更新时调用）"""
        with cls._lock:
            cls._cache.clear()


def reload_llm_registry():
    """
    重载 LLM 注册表（热更新）
    """
    LLMRegistry.clear_cache()


def run_session(
    agent_config: AgentConfig,
    relation_map=None,
    config: Optional[SessionConfig] = None,
) -> ExecutionResult:
    """
    运行会话的便捷函数

    封装会话执行的完整流程：
    1. 加载配置（如未提供）
    2. 获取社交工具列表
    3. 创建 LLM 调用器（绑定社交工具）
    4. 创建总结节点专用的 LLM 调用器（只绑定 write_memory）
    5. 创建执行器
    6. 执行会话

    Args:
        agent_config: Agent 配置
        relation_map: 关系映射服务（可选）
        config: 会话配置，默认使用环境变量/数据库配置

    Returns:
        ExecutionResult: 包含执行结果的 ExecutionResult 对象
    """
    if config is None:
        config = get_default_config()

    from agents.agents_scheduler.langgraph.tools import get_social_tools
    from agents.agents_scheduler.langgraph.tools.support.registry import get_all_tools_for_summarize

    social_tools = get_social_tools(relation_map=relation_map)
    llm_invoker = LLMRegistry.get_invoker(config, tools=social_tools)

    summarize_tools = get_all_tools_for_summarize()
    summarize_llm_invoker = create_llm_invoker(config, tools=summarize_tools)

    executor = SessionExecutor(
        user_id=agent_config.user_id,
        username=agent_config.username,
        name=agent_config.name,
        agent_id=agent_config.agent_id,
        personality_prompt=agent_config.personality_prompt,
        personal_signature=agent_config.personal_signature,
        session_prompt_injection=agent_config.session_prompt_injection,
        config=config,
    )

    return executor.run(llm_invoker, summarize_llm_invoker=summarize_llm_invoker)
