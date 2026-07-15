# 节点定义模块
# 定义 LangGraph 图结构中的各个节点，包括LLM决策、工具执行、总结等
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import AIMessage

from agents.agents_scheduler.langgraph.tools import get_social_tools, get_all_tools_for_summarize, ToolExecutionError
from agents.agents_scheduler.langgraph.state import SessionState, ExitReason, ActionRecord
from agents.agents_scheduler.langgraph.prompts import (
    build_system_prompt,
    build_decision_prompt,
    build_summarize_prompt,
    build_summarize_system_prompt,
)
from agents.agents_scheduler.memory.config import get_memory_config
from agents.agents_scheduler.memory.service import get_memory_service
from agents.agents_scheduler.scheduler.context import is_stop_requested
from agents.agents_scheduler.scheduler.time_system import get_time_system

logger = logging.getLogger(__name__)


def _attach_current_unread_count(data: Any) -> Any:
    """在工具结果中按需加入当前账号未读消息数量。

    未读查询属于辅助提醒，失败时必须保留原工具结果。数量为零时不返回字段，
    避免让每一步上下文都携带无意义的零值。

    Args:
        data: 当前工具准备写入 ``last_tool_result`` 的数据。

    Returns:
        Any: 注入正数未读提醒后的工具数据。
    """

    try:
        from agents.agents_scheduler.langgraph.tools.support.platform import _get_notification_summary

        unread_count = int(_get_notification_summary().get("unread_count", 0) or 0)
    except Exception:
        logger.exception("读取未读消息数量失败")
        return data

    if not isinstance(data, dict):
        return {"result": data, "unread_count": unread_count} if unread_count > 0 else data

    updated = dict(data)
    updated.pop("unread_count", None)
    if unread_count > 0:
        updated["unread_count"] = unread_count
    return updated


# ============================================================
# 工具 → 页面位置映射
# ============================================================

TOOL_TO_LOCATION = {
    "view_notifications": "消息页",
    "view_notification_origin": "帖子详情页",
    "view_full_hot_topics": "大家都在聊",
    "search_platform": "搜索结果页",
    "get_global_feed": "主页（信息流）",
    "expand_post": "帖子详情页",
    "view_post_comments": "评论页",
    "expand_comment": "评论页",
    "get_user_profile": "用户主页",
    "update_profile": None,
    "toggle_post_like": None,
    "vote_post_poll": None,
    "toggle_comment_like": None,
    "toggle_follow": None,
    "create_comment": None,
    "repost": None,
    "create_post": None,
    "delete_content": None,
    "report_content": None,
    "scroll": None,
    "recall_memory": None,
    "web_search": None,
    "logout": None,
}

TOOLS_WITH_RETURN_VALUE = {
    "view_notifications",
    "view_notification_origin",
    "view_full_hot_topics",
    "search_platform",
    "get_user_profile",
    "update_profile",
    "get_global_feed",
    "expand_post",
    "view_post_comments",
    "expand_comment",
    "scroll",
    "vote_post_poll",
    "recall_memory",
    "web_search",
}

TOOL_NO_RETURN_VALUE = {
    "toggle_post_like",
    "toggle_comment_like",
    "toggle_follow",
    "create_comment",
    "repost",
    "create_post",
    "delete_content",
    "report_content",
    "logout",  
}


def _get_location_after_tool(tool_name: str) -> Optional[str]:
    """
    获取工具执行后的页面位置

    Args:
        tool_name: 工具名称

    Returns:
        Optional[str]: 页面位置，如果工具不改变位置则返回 None
    """
    location = TOOL_TO_LOCATION.get(tool_name.lower())
    if location is not None:
        return location

    return None


def parse_tool_calls(response: AIMessage) -> List[Dict[str, Any]]:
    """
    从 LangChain AIMessage 中提取所有工具调用

    Args:
        response: LLM 响应（AIMessage）

    Returns:
        List[Dict[str, Any]]: 工具调用列表
            每个元素包含 {"name": str, "args": Dict}
    """
    if not hasattr(response, 'tool_calls') or not response.tool_calls:
        return []
    return [
        {"name": tc.get("name", ""), "args": tc.get("args", {})}
        for tc in response.tool_calls
    ]


def _normalize_tool_calls_for_batch(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    规范化批量工具调用，确保有返回值的工具只有一个

    规则：
    1. 如果有多个有返回值的工具调用，只保留第一个
    2. 无返回值的工具调用全部保留

    Args:
        tool_calls: 原始工具调用列表

    Returns:
        List[Dict[str, Any]]: 规范化后的工具调用列表
    """
    result = []
    has_return_value_tool = False

    for tc in tool_calls:
        tool_name = tc.get("name", "").lower()
        if tool_name in TOOLS_WITH_RETURN_VALUE:
            if not has_return_value_tool:
                result.append(tc)
                has_return_value_tool = True
        else:
            result.append(tc)

    return result


def _serialize_memory_query_value(value: Any, max_length: int = 3000) -> str:
    """
    将当前视野数据序列化为适合检索的紧凑文本。

    Args:
        value: 工具返回的当前视野数据。
        max_length: 最长保留字符数，避免向量查询被超长页面内容淹没。

    Returns:
        str: 可用于向量与关键词检索的文本。
    """
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(value)

    text = text.strip()
    if len(text) <= max_length:
        return text
    return text[:max_length]


def _build_memory_query_context(state: SessionState) -> str:
    """
    从当前视野和近期操作构造长期记忆检索查询。

    查询刻意排除系统提示词、角色设定和上一轮自动召回结果，避免固定提示词
    稀释检索主题，也避免已召回记忆反复检索自身形成反馈回路。

    Args:
        state: 当前 LangGraph 会话状态。

    Returns:
        str: 紧凑的检索查询；没有可检索上下文时返回空字符串。
    """
    query_parts: List[str] = []
    last_tool_result = state.get("last_tool_result")

    # 主动回想会把结果与页面内容合并；自动召回只使用页面内容，避免记忆自反馈。
    if isinstance(last_tool_result, dict) and "current_view" in last_tool_result:
        last_tool_result = last_tool_result.get("current_view")

    if last_tool_result is not None:
        serialized_result = _serialize_memory_query_value(last_tool_result)
        if serialized_result:
            query_parts.append(serialized_result)

    recent_actions = state.get("action_history", [])
    if recent_actions:
        action_lines = []
        for record in recent_actions:
            summary = str(record.get("summary", "")).strip()
            action = str(record.get("action", "")).strip()
            reason = str(record.get("reason", "")).strip()
            action_line = "；".join(
                value for value in (summary, action, reason) if value
            )
            if action_line:
                action_lines.append(action_line)
        if action_lines:
            query_parts.append("\n".join(action_lines))

    return "\n\n".join(query_parts)


# ============================================================
# 节点实现
# ============================================================

def start_node(state: SessionState) -> SessionState:
    """
    会话开始节点

    初始化会话状态，重置工作记忆。

    Args:
        state: 当前状态（初始状态，应包含用户身份信息）

    Returns:
        SessionState: 更新后的状态
    """
    logger.info("[start] %s 初始化会话", state.get("name", "未知"))
    try:
        from agents.agents_scheduler.langgraph.tools.support.platform import _clear_scroll_cursor
        _clear_scroll_cursor()
    except Exception:
        pass

    return {
        **state,
        "step_count": 0,
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


def recall_memory_node(state: SessionState) -> SessionState:
    """
    记忆召回节点

    在 LLM 决策之前执行，从长期记忆库检索相关记忆并注入检索文本。
    查询仅使用当前视野与近期操作，不使用系统提示词或上一轮召回结果。

    Args:
        state: 当前状态

    Returns:
        SessionState: 更新后的状态，包含 recalled_memories
    """
    import asyncio
    logger.info("[recall_memory] %s 召回记忆", state.get("name", "未知"))

    if is_stop_requested():
        return {
            **state,
            "exit_reason": ExitReason.USER_CHOICE,
            "recalled_memories": "",
        }

    config = get_memory_config()

    if not config.memory_enabled:
        return {
            **state,
            "recalled_memories": "",
        }

    owner_id = state.get("user_id")
    if not owner_id:
        return {
            **state,
            "recalled_memories": "",
        }

    try:
        ts = get_time_system()
        current_time = ts.get_scaled_timestamp()

        query_context = _build_memory_query_context(state)
        if not query_context:
            return {
                **state,
                "recalled_memories": "",
            }

        service = get_memory_service()
        recalled = asyncio.run(service.recall_memories(
            owner_id=owner_id,
            context=query_context,
            current_time=current_time,
            limit=config.recall_limit,
        ))

        # 构建记忆注入文本
        if recalled:
            memory_lines = ["\n\n## relevant memorises\n"]
            for chunk, time_desc in recalled:
                memory_lines.append(f"[memorise chunk - {time_desc}]")
                memory_lines.append(chunk.content)
                memory_lines.append("---")
            recalled_memories = "\n".join(memory_lines)
        else:
            recalled_memories = ""

    except Exception as e:
        logger.warning("%s 记忆召回失败: %s", state.get("name", "未知"), e)
        recalled_memories = ""

    return {
        **state,
        "recalled_memories": recalled_memories,
    }


def llm_decision_node(
    state: SessionState,
    llm_invoker: Callable[[str, str], AIMessage]
) -> SessionState:
    """
    LLM 决策节点

    支持批量工具调用。每次批量调用中，有返回值的工具只能有一个。

    Args:
        state: 当前状态
        llm_invoker: LLM 调用函数，签名：(system_prompt, user_prompt) -> AIMessage

    Returns:
        SessionState: 更新后的状态，包含 pending_tool 或 pending_tools
    """
    name = state.get("name", "未知")
    logger.info("[llm_decision] %s 请求 LLM 决策", name)

    if is_stop_requested():
        return {
            **state,
            "pending_tool": {"tool_name": "logout", "args": {"reason": "调度器停止请求"}},
            "pending_tools": None,
        }

    system_prompt = build_system_prompt(
        username=state["username"],
        name=state.get("name", state["username"]),
        personality_prompt=state["personality_prompt"],
        personal_signature=state["personal_signature"],
        session_prompt_injection=state.get("session_prompt_injection", ""),
    )

    user_prompt = build_decision_prompt(state)

    try:
        response = llm_invoker(system_prompt, user_prompt)
        tool_calls = parse_tool_calls(response)
        success_state: SessionState = {
            **state,
            "last_error": None,
        }

        if not tool_calls:
            if state["step_count"] >= state["max_steps"]:
                return {
                    **success_state,
                    "pending_tool": {"tool_name": "logout", "args": {"reason": "达到最大步数限制"}},
                    "pending_tools": None,
                }
            else:
                return {
                    **success_state,
                    "pending_tool": None,
                    "pending_tools": None,
                }

        normalized_calls = _normalize_tool_calls_for_batch(tool_calls)

        if len(normalized_calls) == 1:
            tool_name = normalized_calls[0].get("name", "").lower()
            tool_args = normalized_calls[0].get("args", {})

            if tool_name == "logout":
                reason = tool_args.get("reason", "主动结束会话")
                return {
                    **success_state,
                    "pending_tool": {"tool_name": "logout", "args": {"reason": reason}},
                    "pending_tools": None,
                }

            return {
                **success_state,
                "pending_tool": {"tool_name": tool_name, "args": tool_args},
                "pending_tools": None,
            }
        else:
            logout_call = None
            non_logout_calls = []
            for tc in normalized_calls:
                call_name = tc.get("name", "").lower()
                if call_name == "logout":
                    logout_call = tc
                else:
                    non_logout_calls.append(tc)

            if logout_call:
                reason = logout_call.get("args", {}).get("reason", "主动结束会话")
                return {
                    **success_state,
                    "pending_tool": {"tool_name": "logout", "args": {"reason": reason}},
                    "pending_tools": None,
                }

            first_call = non_logout_calls[0]
            return {
                **success_state,
                "pending_tool": {"tool_name": first_call.get("name", "").lower(), "args": first_call.get("args", {})},
                "pending_tools": [{"name": tc.get("name", "").lower(), "args": tc.get("args", {})} for tc in non_logout_calls[1:]],
            }

    except Exception as e:
        logger.error("%s 的 LLM 请求失败: %s", name, e)
        return {
            **state,
            "pending_tool": None,
            "pending_tools": None,
            "exit_reason": ExitReason.ERROR,
            "last_error": f"LLM 决策失败: {str(e)}",
        }


def tool_execution_node(state: SessionState) -> SessionState:
    """
    工具执行节点

    支持批量工具调用执行。每次批量调用中，有返回值的工具只能有一个。
    批量执行流程：
    1. 执行 pending_tool
    2. 如果 pending_tools 还有待执行工具，保留在 state 中，下次仍进入此节点
    3. 直到所有工具执行完毕，才更新 step_count 和 last_tool_result

    工作流程：
    1. 检查是否有待执行的工具（pending_tool）
    2. 如果是登出操作，设置退出原因
    3. 执行工具调用
    4. 将执行结果存储到 last_tool_result（给下一次决策看）
    5. 将决策原因记录到 action_history（用于登出后总结）
    6. 更新当前位置
    7. 如果有待执行的批量工具，保留 pending_tools；否则清空并更新步数

    关键设计：
    - last_tool_result: 工具的完整返回值，下一次决策时作为上下文
    - action_history: 只记录决策原因（reason），登出后用于总结
    - pending_tools: 待执行的批量工具列表，执行完毕后清空

    Args:
        state: 当前状态，包含 pending_tool

    Returns:
        SessionState: 更新后的状态
    """
    name = state.get("name", "未知")
    pending = state.get("pending_tool")

    if is_stop_requested() and (pending is None or pending.get("tool_name", "").lower() != "logout"):
        logger.info("[tool_execution] %s 跳过工具执行", name)
        return {
            **state,
            "exit_reason": ExitReason.USER_CHOICE,
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
        }

    if pending is None:
        pending_tools = state.get("pending_tools")
        if pending_tools:
            next_tool = pending_tools[0]
            remaining_tools = pending_tools[1:]
            state = {
                **state,
                "pending_tool": {"tool_name": next_tool.get("name", "").lower(), "args": next_tool.get("args", {})},
                "pending_tools": remaining_tools if remaining_tools else None,
            }
            pending = state["pending_tool"]
        else:
            logger.info("[tool_execution] %s 未执行工具", name)
            # 上游节点请求结束会话时，不执行工具，也不消耗会话步骤。
            if state.get("exit_reason") is not None:
                return state
            return {
                **state,
                "step_count": state["step_count"] + 1,
            }

    assert pending is not None
    tool_name = pending.get("tool_name", "").lower()
    tool_args = pending.get("args", {})

    if tool_name == "logout":
        logger.info("[tool_execution] %s 执行了 %s 工具，参数=%s", name, tool_name, tool_args)
        return {
            **state,
            "exit_reason": ExitReason.USER_CHOICE,
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
        }

    reason = tool_args.get("reason", "未提供原因")
    summary = tool_args.get("summary", "")
    result = None

    try:
        tools = get_social_tools()
        tool_map = {t.name.lower(): t for t in tools}

        if tool_name not in tool_map:
            result = {"action": f"执行了未知工具: {tool_name}", "data": {}}
            logger.warning("[tool_execution] %s 执行的工具不存在: %s，参数=%s", name, tool_name, tool_args)
        else:
            tool = tool_map[tool_name]
            raw_result = tool.invoke(tool_args)
            if isinstance(raw_result, dict) and "action" in raw_result:
                result = raw_result
            else:
                result = {"action": f"执行了 {tool_name}", "data": raw_result if raw_result else {}}
            logger.info("[tool_execution] %s 执行了 %s 工具，参数=%s", name, tool_name, tool_args)

    except ToolExecutionError as e:
        result = {"action": f"工具执行错误: {str(e)}", "data": {}}
        logger.error("[tool_execution] %s 执行 %s 工具失败，参数=%s，错误=%s", name, tool_name, tool_args, e)
    except Exception as e:
        result = {"action": f"执行异常: {str(e)}", "data": {}}
        logger.exception(
            "[tool_execution] %s 执行 %s 工具异常，参数=%s，错误=%s",
            name,
            tool_name,
            tool_args,
            e,
        )

    pending_tools = state.get("pending_tools")
    has_pending = bool(pending_tools)

    action = result.get("action", "") if isinstance(result, dict) else str(result)

    new_record: ActionRecord = {
        "step": state["step_count"] + 1,
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "action": action,
        "reason": reason,
    }

    last_tool_result = result.get("data", {}) if isinstance(result, dict) else result
    if tool_name == "recall_memory" and isinstance(last_tool_result, dict):
        from agents.agents_scheduler.langgraph.tools.support.result_context import merge_recall_memory_result
        last_tool_result = merge_recall_memory_result(
            state.get("last_tool_result"),
            last_tool_result,
        )
    if tool_name == "web_search" and isinstance(last_tool_result, dict):
        from agents.agents_scheduler.langgraph.tools.support.result_context import merge_web_search_result
        last_tool_result = merge_web_search_result(
            state.get("last_tool_result"),
            last_tool_result,
        )
    last_tool_result = _attach_current_unread_count(last_tool_result)

    updated_username: Optional[str] = None
    updated_personal_signature: Optional[str] = None
    if tool_name == "update_profile" and isinstance(last_tool_result, dict):
        result_username = last_tool_result.get("username")
        if result_username:
            updated_username = str(result_username)
        if "bio" in last_tool_result:
            updated_personal_signature = str(last_tool_result.get("bio") or "")

    new_location = _get_location_after_tool(tool_name)
    current_location = new_location if new_location is not None else state.get("current_location", "主页（信息流）")

    if has_pending:
        updated_state: SessionState = {
            **state,
            "action_history": state["action_history"] + [new_record],
            "current_location": current_location,
            "last_tool_result": last_tool_result if last_tool_result is not None else state.get("last_tool_result"),
            "pending_tool": None,
            "last_error": None,
        }
    else:
        updated_state = {
            **state,
            "step_count": state["step_count"] + 1,
            "action_history": state["action_history"] + [new_record],
            "current_location": current_location,
            "last_tool_result": last_tool_result if last_tool_result is not None else state.get("last_tool_result"),
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
        }

    if updated_username is not None:
        updated_state["username"] = updated_username
    if updated_personal_signature is not None:
        updated_state["personal_signature"] = updated_personal_signature
    return updated_state


def should_continue_edge(state: SessionState) -> str:
    """
    决策后的路由判断边函数

    Args:
        state: 当前状态

    Returns:
        str: 下一个节点的名称
    """
    step_count = state.get("step_count", 0)
    max_steps = state.get("max_steps", 10)
    exit_reason = state.get("exit_reason")

    if is_stop_requested():
        return "summarize"

    if exit_reason is not None:
        return "summarize"

    pending_tool = state.get("pending_tool")
    if pending_tool:
        return "tool_execution"

    pending_tools = state.get("pending_tools")
    if pending_tools and len(pending_tools) > 0:
        return "tool_execution"

    if step_count >= max_steps:
        return "summarize"

    return "recall_memory"


def summarize_node(state: SessionState, llm_invoker: Callable[[str, str], AIMessage]) -> SessionState:
    """
    总结节点

    在登出后，根据 action_history（工作记忆）生成会话总结，
    并调用 write_memory 工具将重要经历写入长期记忆库。

    Args:
        state: 当前状态
        llm_invoker: LLM 调用函数

    Returns:
        SessionState: 更新后的状态，包含 summary
    """
    name = state.get("name", "未知")
    logger.info("[summarize] %s 生成会话总结", name)

    if is_stop_requested():
        return {
            **state,
            "summary": f"用户 {state.get('username', '未知')} 的本次会话因调度停止请求结束。",
        }

    if state.get("exit_reason") == ExitReason.ERROR:
        return {
            **state,
            "summary": f"用户 {state.get('username', '未知')} 的本次会话因 LLM 决策失败而提前结束。",
        }

    if not state.get("action_history"):
        return {
            **state,
            "summary": f"用户 {state.get('username', '未知')} 的本次会话未执行任何操作。",
        }

    try:
        system_prompt = build_summarize_system_prompt(
            username=state["username"],
            name=state.get("name", state["username"]),
            personality_prompt=state["personality_prompt"],
            personal_signature=state["personal_signature"]
        )

        user_prompt = build_summarize_prompt(state)

        response = llm_invoker(system_prompt, user_prompt)

        if hasattr(response, 'tool_calls') and response.tool_calls:
            tools_map = {t.name: t for t in get_all_tools_for_summarize()}

            for tc in response.tool_calls:
                tool_name = tc.get("name", "").lower()
                tool_args = tc.get("args", {})

                if tool_name in tools_map:
                    try:
                        tool_func = tools_map[tool_name]
                        result = tool_func.invoke(tool_args)
                        logger.info("%s 执行了 %s 工具，参数=%s", name, tool_name, tool_args)
                    except Exception as e:
                        logger.error("%s 执行 %s 工具失败，参数=%s，错误=%s", name, tool_name, tool_args, e)

        summary = response.content if isinstance(response.content, str) else response.text()
        if not summary:
            summary = f"用户 {state.get('username', '未知')} 执行了 {len(state.get('action_history', []))} 个操作。"

        return {
            **state,
            "summary": summary,
        }

    except Exception as e:
        logger.warning("%s 生成会话总结失败: %s", name, e)
        return {
            **state,
            "summary": f"用户 {state.get('username', '未知')} 执行了 {len(state.get('action_history', []))} 个操作。",
        }


def end_node(state: SessionState) -> SessionState:
    """
    结束节点

    Args:
        state: 当前状态

    Returns:
        SessionState: 不做任何修改的状态
    """
    logger.info("[end] %s 会话结束", state.get("name", "未知"))
    return state
