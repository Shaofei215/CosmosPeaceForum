# 节点定义模块
# 定义 LangGraph 图结构中的各个节点，包括LLM决策、工具执行、总结等
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import traceback

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

logger = logging.getLogger(__name__)


# ============================================================
# 工具 → 页面位置映射
# ============================================================

TOOL_TO_LOCATION = {
    "get_global_feed": "主页（信息流）",
    "expand_post": "帖子详情页",
    "expand_comments": "评论页",
    "get_user_profile": "用户主页",
    "get_post_detail": "帖子详情页",
    "scroll_global_feed": "主页（信息流）",
    "scroll_user_posts": "用户主页",
    "toggle_post_like": None,
    "toggle_comment_like": None,
    "toggle_follow": None,
    "create_comment": None,
    "create_post": None,
    "get_profile": "主页（信息流）",
    "logout": None,
}

TOOLS_WITH_RETURN_VALUE = {
    "get_profile",
    "get_user_profile",
    "get_global_feed",
    "expand_post",
    "expand_comments",
    "get_post_detail",
    "scroll_global_feed",
    "scroll_user_posts",
}

TOOL_NO_RETURN_VALUE = {
    "toggle_post_like",
    "toggle_comment_like",
    "toggle_follow",
    "create_comment",
    "create_post",
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
    username = state.get("username", "未知")
    logger.info("start_node | 用户=%s | 初始化会话状态", username)

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

    在 LLM 决策之前执行，从长期记忆库检索相关记忆并注入 Prompt。
    使用 asyncio.run() 调用异步记忆服务，适配 LangGraph 同步调用。

    Args:
        state: 当前状态

    Returns:
        SessionState: 更新后的状态，包含 recalled_memories
    """
    import asyncio

    config = get_memory_config()

    if not config.memory_enabled:
        return state

    owner_id = state.get("user_id")
    if not owner_id:
        return state

    # 构建当前上下文（用于检索）
    # 留空，由 llm_decision_node 在构建决策 prompt 时填充
    state["recalled_memories"] = ""
    logger.info("recall_memory_node | 用户=%s | 上下文已准备好", state.get('username', '未知'))

    return state


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
    username = state.get("username", "未知")
    step_count = state.get("step_count", 0)
    current_location = state.get("current_location", "未知")
    logger.info("llm_decision_node | 用户=%s | 步骤=%d | 位置=%s | 正在请求LLM决策", username, step_count, current_location)

    # 检索相关记忆（使用完整上下文作为查询，与 build_decision_prompt 一致）
    # 查询上下文包括：current_location + last_tool_result + action_history
    import asyncio
    config = get_memory_config()
    if config.memory_enabled:
        owner_id = state.get("user_id")
        if owner_id:
            try:
                from agents.agents_scheduler.scheduler.time_system import get_time_system
                ts = get_time_system()
                current_time = ts.get_scaled_timestamp()

                # 构建查询上下文（与 build_decision_prompt 保持一致）
                context_parts = [current_location]

                # 添加 last_tool_result
                last_result = state.get("last_tool_result")
                if last_result and isinstance(last_result, dict):
                    action = last_result.get("action", "")
                    if action:
                        context_parts.append(action)

                # 添加 action_history（工作记忆）的关键信息
                action_history = state.get("action_history", [])
                if action_history:
                    for record in action_history[-3:]:  # 取最近 3 条
                        summary = record.get("summary", "")
                        action = record.get("action", "")
                        if summary:
                            context_parts.append(f"我{action}了：{summary[:30]}")
                        elif action:
                            context_parts.append(f"我{action}了")

                query_context = "；".join(context_parts)

                from agents.agents_scheduler.memory.service import get_memory_service
                service = get_memory_service()
                recalled = asyncio.run(service.recall_memories(
                    owner_id=owner_id,
                    context=query_context,
                    current_time=current_time,
                    limit=config.recall_limit
                ))

                # 构建记忆注入文本
                if recalled:
                    memory_lines = ["\n\n## 相关记忆"]
                    for chunk, time_desc in recalled:
                        memory_lines.append(f"[记忆片段 - {time_desc}]")
                        memory_lines.append(chunk.content)
                        memory_lines.append("---")
                    state["recalled_memories"] = "\n".join(memory_lines)
                    logger.info("llm_decision_node | 召回%d条相关记忆", len(recalled))
                else:
                    state["recalled_memories"] = ""
            except Exception as e:
                logger.warning("llm_decision_node | 记忆召回异常: %s", e)
                state["recalled_memories"] = ""

    system_prompt = build_system_prompt(
        username=state["username"],
        name=state.get("name", state["username"]),
        personality_prompt=state["personality_prompt"],
        personal_signature=state["personal_signature"]
    )

    user_prompt = build_decision_prompt(state)

    try:
        response = llm_invoker(system_prompt, user_prompt)
        tool_calls = parse_tool_calls(response)

        if not tool_calls:
            if state["step_count"] >= state["max_steps"]:
                logger.info("llm_decision_node | 用户=%s | 步骤=%d | LLM未返回工具调用 | 达到最大步数，将执行登出", username, step_count)
                return {
                    **state,
                    "pending_tool": {"tool_name": "logout", "args": {"reason": "达到最大步数限制"}},
                    "pending_tools": None,
                }
            else:
                logger.info("llm_decision_node | 用户=%s | 步骤=%d | LLM未返回工具调用", username, step_count)
                return {
                    **state,
                    "pending_tool": None,
                    "pending_tools": None,
                }

        normalized_calls = _normalize_tool_calls_for_batch(tool_calls)
        call_names = [tc.get("name", "") for tc in normalized_calls]
        logger.info("llm_decision_node | 用户=%s | 步骤=%d | LLM决策: %s", username, step_count, call_names)

        if len(normalized_calls) == 1:
            tool_name = normalized_calls[0].get("name", "").lower()
            tool_args = normalized_calls[0].get("args", {})

            if tool_name == "logout":
                reason = tool_args.get("reason", "主动结束会话")
                logger.info("llm_decision_node | 用户=%s | 步骤=%d | LLM选择登出: reason=%s", username, step_count, reason)
                return {
                    **state,
                    "pending_tool": {"tool_name": "logout", "args": {"reason": reason}},
                    "pending_tools": None,
                }

            return {
                **state,
                "pending_tool": {"tool_name": tool_name, "args": tool_args},
                "pending_tools": None,
            }
        else:
            logout_call = None
            non_logout_calls = []
            for tc in normalized_calls:
                name = tc.get("name", "").lower()
                if name == "logout":
                    logout_call = tc
                else:
                    non_logout_calls.append(tc)

            if logout_call:
                reason = logout_call.get("args", {}).get("reason", "主动结束会话")
                logger.info("llm_decision_node | 用户=%s | 步骤=%d | LLM批量决策中包含登出: reason=%s", username, step_count, reason)
                return {
                    **state,
                    "pending_tool": {"tool_name": "logout", "args": {"reason": reason}},
                    "pending_tools": None,
                }

            first_call = non_logout_calls[0]
            return {
                **state,
                "pending_tool": {"tool_name": first_call.get("name", "").lower(), "args": first_call.get("args", {})},
                "pending_tools": [{"name": tc.get("name", "").lower(), "args": tc.get("args", {})} for tc in non_logout_calls[1:]],
            }

    except Exception as e:
        logger.error("llm_decision_node | 用户=%s | 步骤=%d | LLM决策异常: %s", username, step_count, str(e))
        return {
            **state,
            "pending_tool": None,
            "pending_tools": None,
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
    username = state.get("username", "未知")
    step_count = state.get("step_count", 0)
    pending = state.get("pending_tool")

    if pending is None:
        pending_tools = state.get("pending_tools")
        if pending_tools:
            next_tool = pending_tools[0]
            remaining_tools = pending_tools[1:]
            logger.info("tool_execution_node | 用户=%s | 步骤=%d | 执行批量中的下一个工具: %s", username, step_count, next_tool.get('name', ''))
            return {
                **state,
                "pending_tool": {"tool_name": next_tool.get("name", "").lower(), "args": next_tool.get("args", {})},
                "pending_tools": remaining_tools if remaining_tools else None,
            }
        logger.info("tool_execution_node | 用户=%s | 步骤=%d | 无待执行工具，步数+1", username, step_count)
        return {
            **state,
            "step_count": state["step_count"] + 1,
        }

    tool_name = pending.get("tool_name", "").lower()
    tool_args = pending.get("args", {})
    logger.info("tool_execution_node | 用户=%s | 步骤=%d | 开始执行工具: %s | 参数=%s", username, step_count, tool_name, tool_args)

    if tool_name == "logout":
        logout_reason = tool_args.get("reason", "主动结束会话")
        logger.info("tool_execution_node | 用户=%s | 步骤=%d | 执行登出: reason=%s", username, step_count, logout_reason)
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
            logger.warning("tool_execution_node | 用户=%s | 步骤=%d | 工具不存在: %s", username, step_count, tool_name)
        else:
            tool = tool_map[tool_name]
            raw_result = tool.invoke(tool_args)
            if isinstance(raw_result, dict) and "action" in raw_result:
                result = raw_result
            else:
                result = {"action": f"执行了 {tool_name}", "data": raw_result if raw_result else {}}
            logger.info("tool_execution_node | 用户=%s | 步骤=%d | 工具执行成功: %s", username, step_count, tool_name)

    except ToolExecutionError as e:
        result = {"action": f"工具执行错误: {str(e)}", "data": {}}
        logger.error("tool_execution_node | 用户=%s | 步骤=%d | 工具执行错误: %s", username, step_count, str(e))
    except Exception as e:
        result = {"action": f"执行异常: {str(e)}", "data": {}}
        logger.error("tool_execution_node | 用户=%s | 步骤=%d | 执行异常: %s", username, step_count, str(e))
        traceback.print_exc()

    pending_tools = state.get("pending_tools")
    has_pending = pending_tools and len(pending_tools) > 0

    action = result.get("action", "") if isinstance(result, dict) else str(result)

    new_record: ActionRecord = {
        "step": state["step_count"] + 1,
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "action": action,
        "reason": reason,
    }

    last_tool_result = result.get("data", {}) if isinstance(result, dict) else result

    new_location = _get_location_after_tool(tool_name)
    current_location = new_location if new_location is not None else state.get("current_location", "主页（信息流）")

    if has_pending:
        logger.info("tool_execution_node | 用户=%s | 步骤=%d | 批量工具还有 %d 个待执行", username, step_count, len(pending_tools))
        return {
            **state,
            "action_history": state["action_history"] + [new_record],
            "current_location": current_location,
            "last_tool_result": last_tool_result if last_tool_result else state.get("last_tool_result"),
            "pending_tool": None,
            "last_error": None,
        }

    logger.info("tool_execution_node | 用户=%s | 步骤=%d | 批量执行完毕 | 操作已记录 | 当前位置=%s", username, step_count, current_location)

    return {
        **state,
        "step_count": state["step_count"] + 1,
        "action_history": state["action_history"] + [new_record],
        "current_location": current_location,
        "last_tool_result": last_tool_result if last_tool_result else state.get("last_tool_result"),
        "pending_tool": None,
        "pending_tools": None,
        "last_error": None,
    }


def should_continue_edge(state: SessionState) -> str:
    """
    决策后的路由判断边函数

    Args:
        state: 当前状态

    Returns:
        str: 下一个节点的名称
    """
    username = state.get("username", "未知")
    step_count = state.get("step_count", 0)
    max_steps = state.get("max_steps", 10)
    exit_reason = state.get("exit_reason")

    if exit_reason is not None:
        reason_str = exit_reason.value if isinstance(exit_reason, ExitReason) else str(exit_reason)
        logger.info("should_continue_edge | 用户=%s | 步骤=%d/%d | 退出原因=%s | 路由=summarize", username, step_count, max_steps, reason_str)
        return "summarize"

    pending_tools = state.get("pending_tools")
    if pending_tools and len(pending_tools) > 0:
        logger.info("should_continue_edge | 用户=%s | 步骤=%d/%d | 批量工具还有 %d 个待执行 | 路由=tool_execution", username, step_count, max_steps, len(pending_tools))
        return "tool_execution"

    if step_count >= max_steps:
        logger.info("should_continue_edge | 用户=%s | 步骤=%d/%d | 达到最大步数 | 路由=summarize", username, step_count, max_steps)
        return "summarize"

    logger.info("should_continue_edge | 用户=%s | 步骤=%d/%d | 继续决策 | 路由=recall_memory", username, step_count, max_steps)
    return "recall_memory"


def summarize_node(state: SessionState, llm_invoker: Callable[[str, str], AIMessage]) -> SessionState:
    """
    总结节点

    在登出后，根据 action_history（工作记忆）生成会话总结。
    只做节点流程控制，提示词工程全部在 prompts.py 中完成。
    LLM 可能会调用 write_memory 工具写入记忆，需要执行这些工具调用。

    Args:
        state: 当前状态
        llm_invoker: LLM 调用函数

    Returns:
        SessionState: 更新后的状态，包含 summary
    """
    username = state.get("username", "未知")
    action_count = len(state.get("action_history", []))
    logger.info("summarize_node | 用户=%s | 开始生成总结 | 操作数=%d", username, action_count)

    if not state.get("action_history"):
        summary = f"用户 {state.get('username', '未知')} 的本次会话未执行任何操作。"
        logger.info("summarize_node | 用户=%s | 无操作记录 | 总结=%s", username, summary)
        return {
            **state,
            "summary": summary,
        }

    try:
        # 使用共用的系统提示词（与决策节点一致的角色设定）
        system_prompt = build_summarize_system_prompt(
            username=state["username"],
            name=state.get("name", state["username"]),
            personality_prompt=state["personality_prompt"],
            personal_signature=state["personal_signature"]
        )

        # 用户提示词包含操作历史和记忆写入指令
        user_prompt = build_summarize_prompt(state)

        response = llm_invoker(system_prompt, user_prompt)

        # 检查 LLM 是否返回了工具调用
        tool_calls = []
        summary = ""

        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_calls = response.tool_calls
            logger.info("summarize_node | 用户=%s | LLM返回%d个工具调用", username, len(tool_calls))

            # 执行工具调用（主要是 write_memory）
            tools_map = {t.name: t for t in get_all_tools_for_summarize()}

            for tc in tool_calls:
                tool_name = tc.get("name", "").lower()
                tool_args = tc.get("args", {})

                if tool_name in tools_map:
                    try:
                        tool_func = tools_map[tool_name]
                        result = tool_func.invoke(tool_args)
                        logger.info("summarize_node | 工具执行: %s | 结果: %s", tool_name, result.action if hasattr(result, 'action') else str(result))
                    except Exception as e:
                        logger.error("summarize_node | 工具执行失败: %s | 错误: %s", tool_name, e)

        # 提取总结内容
        if hasattr(response, 'content'):
            summary = response.content
        else:
            summary = str(response)

        # 如果总结内容为空或只包含工具调用，生成默认总结
        if not summary or len(summary.strip()) < 10:
            summary = f"用户 {username} 执行了 {action_count} 个操作，并写入了相关记忆。"

        logger.info("summarize_node | 用户=%s | LLM总结生成成功 | 长度=%d字符", username, len(summary))

        return {
            **state,
            "summary": summary,
        }

    except Exception as e:
        summary = f"用户 {state.get('username', '未知')} 执行了 {len(state.get('action_history', []))} 个操作。"
        logger.error("summarize_node | 用户=%s | 总结生成异常 | 使用默认总结: %s", username, summary)
        return {
            **state,
            "summary": summary,
        }


def end_node(state: SessionState) -> SessionState:
    """
    结束节点

    Args:
        state: 当前状态

    Returns:
        SessionState: 不做任何修改的状态
    """
    username = state.get("username", "未知")
    step_count = state.get("step_count", 0)
    summary_preview = str(state.get("summary", ""))[:50] if state.get("summary") else "无"
    logger.info("end_node | 用户=%s | 会话结束 | 总步骤=%d | 总结预览=%s...", username, step_count, summary_preview)
    return state
