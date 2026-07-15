# Prompt 模板模块
# 定义 LangGraph 会话中使用的各种 Prompt 模板
import json
from collections.abc import Mapping
from typing import Dict, Any, List

from agents.prompt_templates import (
    AGENT_SYSTEM_PROMPT_KEY,
    SUMMARIZE_MEMORY_PROMPT_KEY,
    get_default_prompt_template,
    render_prompt_template,
)


def _get_configured_prompt_template(key: str) -> str:
    default = get_default_prompt_template(key)
    try:
        from agents.management.backend.db_client import get_db_client
        return get_db_client().get_prompt_config(key, default)
    except Exception:
        return default


def _build_login_stats_summary() -> Dict[str, Any]:
    try:
        from agents.agents_scheduler.scheduler.context import get_current_context
        context = get_current_context()
        if context and context.user_config:
            return {
                "total_login_count": context.user_config.get("total_login_count", 0),
                "last_login_timestamp": context.user_config.get(
                    "previous_last_login_timestamp",
                    context.user_config.get("last_login_timestamp"),
                ),
            }

        if context and context.agent_id:
            from agents.management.backend.db_client import get_db_client
            return get_db_client().get_agent_login_stats(context.agent_id)
    except Exception:
        pass

    return {"total_login_count": 0, "last_login_timestamp": None}


def _get_platform_display_name() -> str:
    """读取 Agent 侧配置的平台展示名，失败时回退到默认项目名。"""
    try:
        from agents.management.backend.core.config import get_config
        return get_config().platform_display_name
    except Exception:
        return "[get platform_display_name failed]"


def _format_last_login_time(timestamp: Any) -> str:
    if timestamp is None:
        return "No record available"

    try:
        from agents.agents_scheduler.memory.utils import calculate_time_description
        return calculate_time_description(float(timestamp))
    except Exception:
        return "No record available"


def _build_agent_context_json() -> str:
    """构建系统 Prompt 状态 JSON。

    程序状态使用英文字段名；热榜和话题使用与人类前端一致的产品名称。

    Returns:
        str: 包含账号计数、社区热点和可选登录统计的 JSON。
    """

    try:
        from agents.agents_scheduler.langgraph.tools.support.platform import _get_notification_summary
        summary = _get_notification_summary()
    except Exception:
        summary = {"following_count": 0, "followers_count": 0, "unread_count": 0}

    login_stats = _build_login_stats_summary()
    total_login_count = login_stats.get("total_login_count", 0) or 0
    last_login_time = _format_last_login_time(login_stats.get("last_login_timestamp"))
    hot_topic_titles = _get_hot_topic_titles()
    topic_titles = _get_topic_titles()
    try:
        from agents.agents_scheduler.scheduler.context import get_current_user_id
        platform_user_id = get_current_user_id() or "unknown"
    except Exception:
        platform_user_id = "unknown"
    account_context: Dict[str, Any] = {
        "platform_user_id": platform_user_id,
        "following_count": summary.get("following_count", 0),
        "followers_count": summary.get("followers_count", 0),
        "unread_count": summary.get("unread_count", 0),
        "大家都在聊": hot_topic_titles,
        "话题": topic_titles,
    }
    has_login_stats = bool(total_login_count or login_stats.get("last_login_timestamp"))
    if has_login_stats:
        account_context["login_stats"] = {
            "total_login_count": total_login_count,
            "last_login_time": last_login_time,
        }

    return _serialize_prompt_json(account_context)


def _get_hot_topic_titles() -> List[str]:
    try:
        from agents.agents_scheduler.langgraph.tools.support.platform import _get_hot_topics
        topics = _get_hot_topics(limit=8)
    except Exception:
        topics = []

    titles = [
        str(topic.get("title", "")).strip()
        for topic in topics
        if isinstance(topic, dict) and str(topic.get("title", "")).strip()
    ][:8]
    return titles


def _get_topic_titles() -> List[str]:
    try:
        from agents.agents_scheduler.langgraph.tools.support.platform import _get_trending_topics
        topics = _get_trending_topics(limit=8)
    except Exception:
        topics = []

    titles = [
        str(topic.get("name", "")).strip()
        for topic in topics
        if isinstance(topic, dict) and str(topic.get("name", "")).strip()
    ][:8]
    return titles


def _serialize_prompt_json(value: Any) -> str:
    """把内部状态序列化为保留产品文案的易读 JSON。

    Args:
        value: 准备注入 Prompt 的结构化状态。

    Returns:
        str: UTF-8 文本不转义、带缩进的 JSON 文本。
    """

    return json.dumps(value, ensure_ascii=False, default=str, indent=2)


def build_system_prompt(
    username: str,
    name: str,
    personality_prompt: str,
    personal_signature: str,
    session_prompt_injection: str = "",
) -> str:
    """
    构建系统提示词

    系统提示词定义了 AI Agent 的角色设定和行为准则。
    注意：工具描述由 LangChain 从 @tool 装饰器自动注入到 LLM。

    Args:
        username: 用户名
        name: 昵称
        personality_prompt: 角色性格描述
        personal_signature: 个性签名
        session_prompt_injection: 本次登录会话的一次性提示词注入

    Returns:
        str: 格式化后的系统提示词
    """
    template = _get_configured_prompt_template(AGENT_SYSTEM_PROMPT_KEY)
    values = {
        "agent_context_json": _build_agent_context_json(),
        "platform_name": _get_platform_display_name(),
        "username": username,
        "name": name,
        "personality_prompt": personality_prompt,
        "personal_signature": personal_signature,
        "session_prompt_injection": session_prompt_injection.strip(),
    }
    return render_prompt_template(
        template,
        values,
    )


def build_decision_prompt(state: Mapping[str, Any]) -> str:
    """
    构建决策 Prompt

    LLM 决策时依赖三大核心信息：
    1. 当前位置 (current_location)
    2. 工作记忆 (action_history)
    3. 上一次工具调用的返回值 (last_tool_result)

    Args:
        state: 当前会话状态

    Returns:
        str: 格式化的决策 prompt
    """
    current_step = state.get("step_count", 0)
    max_steps = state.get("max_steps", 10)
    current_location = state.get("current_location", "主页（信息流）")
    action_history = state.get("action_history", [])
    is_first_decision = len(action_history) == 0
    session_context = {
        "current_location": current_location,
        "step_count": current_step,
        "max_steps": max_steps,
        "remaining_steps": max(0, max_steps - current_step),
        "action_history": _build_action_history_data(action_history),
    }
    session_context_text = _serialize_prompt_json(session_context)

    # 构建上一次工具调用的返回值
    last_result_text = ""
    if not is_first_decision:
        last_result = state.get("last_tool_result")
        if last_result is not None:
            last_result_text = (
                "\n [Platform content obtained after last tool call] \n"
                f"{_format_tool_result(last_result)}\n"
            )

    # 仅在首次决策时提示 LLM 获取信息流
    initial_environment_text = ""
    if is_first_decision:
        initial_environment_text = (
            "\n [This is first decision in this session] \n"
            " [Suggest calling a tool first to retrieve some content] \n"
        )

    # 构建召回的记忆注入文本
    recalled_memories = state.get("recalled_memories", "")
    recalled_memory_text = recalled_memories if recalled_memories else ""

    prompt = f"""## Current session context
{session_context_text}
{last_result_text}
{initial_environment_text}
{recalled_memory_text}

Please do your next decision."""

    return prompt


def _build_action_history_data(
    action_history: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """构建供决策和总结 Prompt 共用的工作记忆。

    时间戳不参与模型决策；步骤已经表达顺序，省略时间戳可以减少上下文噪声。

    Args:
        action_history: 会话状态中保存的原始操作记录。

    Returns:
        List[Dict[str, Any]]: 保留 step、summary、action 和 reason 的记录列表。
    """

    return [
        {
            "step": record.get("step", "?"),
            "summary": record.get("summary", ""),
            "action": record.get("action", ""),
            "reason": record.get("reason", ""),
        }
        for record in action_history
    ]


def _format_tool_result(result: Any) -> str:
    """把共享工具结果无损序列化为供 LLM 读取的 JSON。

    内部与外部 Agent 共用 ``agents.platform_tools`` 构建的结构化数据。这里不再
    按帖子、评论或通知类型二次改写，避免新字段需要同步维护 Prompt presenter，
    也避免嵌套结构和真实资源 ID 在自然语言转换中丢失。

    Args:
        result: 共享工具写入会话状态的原始结果。

    Returns:
        str: 保留中文和全部结构的紧凑 JSON 字符串。

    Raises:
        TypeError: 结果包含无法由默认字符串回退处理的对象时抛出。
    """

    return json.dumps(
        result,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


def build_summarize_system_prompt(
    username: str,
    name: str,
    personality_prompt: str,
    personal_signature: str
) -> str:
    """
    构建总结节点的系统提示词

    复用 build_system_prompt 的角色设定，保持一致性。

    Args:
        username: 用户名
        name: 昵称
        personality_prompt: 角色性格描述
        personal_signature: 个性签名

    Returns:
        str: 格式化后的系统提示词
    """
    return build_system_prompt(username, name, personality_prompt, personal_signature)


def build_summarize_prompt(state: Mapping[str, Any]) -> str:
    """
    构建总结节点的用户提示词

    在登出后，根据 action_history（工作记忆）生成会话总结。
    同时提示 LLM 调用 write_memory 工具将重要经历写入长期记忆库。

    Args:
        state: 当前会话状态

    Returns:
        str: 格式化的总结 prompt
    """
    if not state.get("action_history"):
        return f"""用户 {state.get('username', 'unknown')} 的本次会话未执行任何操作。"""

    history_text = _serialize_prompt_json(
        _build_action_history_data(state["action_history"]),
    )

    template = _get_configured_prompt_template(SUMMARIZE_MEMORY_PROMPT_KEY)
    return render_prompt_template(
        template,
        {
            "username": state.get("username", "unknown"),
            "history_text": history_text,
            "platform_name": _get_platform_display_name(),
        },
    )
