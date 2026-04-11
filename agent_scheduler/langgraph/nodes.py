# 节点定义模块
# 定义 LangGraph 图结构中的各个节点，包括LLM决策、工具执行、总结等
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime
import traceback

from langchain_core.messages import AIMessage

from agent_scheduler.langgraph.tools import get_social_tools, ToolExecutionError
from agent_scheduler.langgraph.state import SessionState, ExitReason, ActionRecord
from agent_scheduler.langgraph.prompts import (
    build_system_prompt,
    build_decision_prompt,
    build_summarize_prompt,
)


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
    "create_post": "主页（信息流）",
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


def _get_location_after_tool(tool_name: str, tool_args: Dict[str, Any]) -> Optional[str]:
    """
    获取工具执行后的页面位置

    Args:
        tool_name: 工具名称
        tool_args: 工具参数

    Returns:
        Optional[str]: 页面位置，如果工具不改变位置则返回 None
    """
    location = TOOL_TO_LOCATION.get(tool_name.lower())
    if location is not None:
        return location

    if tool_name.lower() == "create_post":
        return "主页（信息流）"

    return None


def _parse_langchain_tool_call(response: Union[str, AIMessage]) -> Optional[Dict[str, Any]]:
    """
    解析 LangChain LLM 响应中的工具调用（单个）

    支持 LangChain 的 AIMessage.tool_calls 格式。

    Args:
        response: LLM 响应，可以是字符串或 AIMessage

    Returns:
        Optional[Dict[str, Any]]: 解析后的工具调用信息
            {
                "tool_name": str,      # 工具名称
                "args": Dict          # 工具参数
            }
            如果解析失败或没有工具调用返回 None
    """
    tool_calls = _parse_tool_calls_from_response(response)
    if not tool_calls:
        return None
    return tool_calls[0]


def _parse_tool_calls_from_response(response: Union[str, AIMessage]) -> List[Dict[str, Any]]:
    """
    解析 LLM 响应中的所有工具调用

    支持 LangChain 的 AIMessage.tool_calls 格式和字符串格式。

    Args:
        response: LLM 响应，可以是字符串或 AIMessage

    Returns:
        List[Dict[str, Any]]: 解析后的工具调用列表
    """
    if isinstance(response, AIMessage):
        if hasattr(response, 'tool_calls') and response.tool_calls:
            return [{"name": tc.get("name", ""), "args": tc.get("args", {})} for tc in response.tool_calls]
        return []

    if isinstance(response, str):
        return _parse_tool_calls_from_string(response)

    return []


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


def _parse_tool_calls_from_string(content: str) -> List[Dict[str, Any]]:
    """
    从字符串响应中解析所有工具调用

    支持多种响应格式：
    1. JSON 格式: {"tool_name": "xxx", "args": {...}}
    2. 简单格式: tool_name(arg1=value1, arg2=value2) 或多个工具连续调用

    Args:
        content: LLM 响应内容字符串

    Returns:
        List[Dict[str, Any]]: 解析后的工具调用列表
    """
    import json
    import re

    content = content.strip()
    results = []

    json_pattern = re.compile(r'\{[^{}]*"tool_name"[^{}]*\}', re.DOTALL)
    for json_match in json_pattern.finditer(content):
        try:
            data = json.loads(json_match.group())
            tool_name = data.get("tool_name", "")
            if tool_name:
                results.append({
                    "name": tool_name,
                    "args": data.get("args", {})
                })
        except (json.JSONDecodeError, AttributeError):
            continue

    simple_pattern = re.compile(r'(\w+)\(([^)]*)\)', re.MULTILINE)
    for match in simple_pattern.finditer(content):
        tool_name = match.group(1).strip()
        if tool_name and tool_name.lower() not in ['if', 'else', 'for', 'while', 'def', 'return', 'true', 'false', 'none']:
            args_str = match.group(2).strip()
            args = _parse_args_string(args_str)
            results.append({"name": tool_name, "args": args})

    return results


def _parse_args_string(args_str: str) -> Dict[str, Any]:
    """
    解析工具参数字符串

    Args:
        args_str: 参数字符串，如 "post_id=123, reason='test'"

    Returns:
        Dict[str, Any]: 解析后的参数字典
    """
    args = {}
    if not args_str:
        return args

    for arg_pair in args_str.split(','):
        if '=' in arg_pair:
            key, value = arg_pair.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            if value.isdigit():
                value = int(value)
            elif value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            elif value.lower() == 'none':
                value = None
            args[key] = value

    return args


def _parse_llm_tool_call(response_content: str) -> Optional[Dict[str, Any]]:
    """
    解析 LLM 响应中的工具调用（单个，兼容旧逻辑）

    支持多种响应格式：
    1. JSON 格式: {"tool_name": "xxx", "args": {...}}
    2. 简单格式: tool_name(arg1=value1, arg2=value2)

    Args:
        response_content: LLM 响应内容

    Returns:
        Optional[Dict[str, Any]]: 解析后的工具调用信息
            {
                "tool_name": str,      # 工具名称
                "args": Dict          # 工具参数
            }
            如果解析失败返回 None
    """
    results = _parse_tool_calls_from_string(response_content)
    return results[0] if results else None


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
    print(f"[节点] start_node | 用户={username} | 初始化会话状态")

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
    }


def llm_decision_node(
    state: SessionState,
    llm_invoker: Callable[[str, str], str]
) -> SessionState:
    """
    LLM 决策节点

    支持批量工具调用。每次批量调用中，有返回值的工具只能有一个。

    Args:
        state: 当前状态
        llm_invoker: LLM 调用函数，签名：(system_prompt, user_prompt) -> str

    Returns:
        SessionState: 更新后的状态，包含 pending_tool 或 pending_tools
    """
    username = state.get("username", "未知")
    step_count = state.get("step_count", 0)
    current_location = state.get("current_location", "未知")
    print(f"[节点] llm_decision_node | 用户={username} | 步骤={step_count} | 位置={current_location} | 正在请求LLM决策")

    system_prompt = build_system_prompt(
        username=state["username"],
        name=state.get("name", state["username"]),
        personality_prompt=state["personality_prompt"],
        personal_signature=state["personal_signature"]
    )

    user_prompt = build_decision_prompt(state)

    try:
        response = llm_invoker(system_prompt, user_prompt)
        tool_calls = _parse_tool_calls_from_response(response)

        if not tool_calls:
            if state["step_count"] >= state["max_steps"]:
                print(f"[节点] llm_decision_node | 用户={username} | 步骤={step_count} | LLM未返回工具调用 | 达到最大步数，将执行登出")
                return {
                    **state,
                    "pending_tool": {"tool_name": "logout", "args": {"reason": "达到最大步数限制"}},
                    "pending_tools": None,
                }
            else:
                print(f"[节点] llm_decision_node | 用户={username} | 步骤={step_count} | LLM未返回工具调用")
                return {
                    **state,
                    "pending_tool": None,
                    "pending_tools": None,
                }

        normalized_calls = _normalize_tool_calls_for_batch(tool_calls)
        call_names = [tc.get("name", "") for tc in normalized_calls]
        print(f"[节点] llm_decision_node | 用户={username} | 步骤={step_count} | LLM决策: {call_names}")

        if len(normalized_calls) == 1:
            tool_name = normalized_calls[0].get("name", "").lower()
            tool_args = normalized_calls[0].get("args", {})

            if tool_name == "logout":
                reason = tool_args.get("reason", "主动结束会话")
                print(f"[节点] llm_decision_node | 用户={username} | 步骤={step_count} | LLM选择登出: reason={reason}")
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
                print(f"[节点] llm_decision_node | 用户={username} | 步骤={step_count} | LLM批量决策中包含登出: reason={reason}")
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
        print(f"[节点] llm_decision_node | 用户={username} | 步骤={step_count} | LLM决策异常: {str(e)}")
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
            print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 执行批量中的下一个工具: {next_tool.get('name', '')}")
            return {
                **state,
                "pending_tool": {"tool_name": next_tool.get("name", "").lower(), "args": next_tool.get("args", {})},
                "pending_tools": remaining_tools if remaining_tools else None,
            }
        print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 无待执行工具，步数+1")
        return {
            **state,
            "step_count": state["step_count"] + 1,
        }

    tool_name = pending.get("tool_name", "").lower()
    tool_args = pending.get("args", {})
    print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 开始执行工具: {tool_name} | 参数={tool_args}")

    if tool_name == "logout":
        logout_reason = tool_args.get("reason", "主动结束会话")
        print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 执行登出: reason={logout_reason}")
        return {
            **state,
            "exit_reason": ExitReason.USER_CHOICE,
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
        }

    reason = tool_args.pop("reason", "未提供原因")
    summary = tool_args.pop("summary", "")
    result = None

    try:
        tools = get_social_tools()
        tool_map = {t.name.lower(): t for t in tools}

        if tool_name not in tool_map:
            result = {"action": f"执行了未知工具: {tool_name}", "data": {}}
            print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 工具不存在: {tool_name}")
        else:
            tool = tool_map[tool_name]
            raw_result = tool.invoke(tool_args)
            if isinstance(raw_result, dict) and "action" in raw_result:
                result = raw_result
            else:
                result = {"action": f"执行了 {tool_name}", "data": raw_result if raw_result else {}}
            print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 工具执行成功: {tool_name}")

    except ToolExecutionError as e:
        result = {"action": f"工具执行错误: {str(e)}", "data": {}}
        print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 工具执行错误: {str(e)}")
    except Exception as e:
        result = {"action": f"执行异常: {str(e)}", "data": {}}
        print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 执行异常: {str(e)}")
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

    new_location = _get_location_after_tool(tool_name, tool_args)
    current_location = new_location if new_location is not None else state.get("current_location", "主页（信息流）")

    if has_pending:
        print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 批量工具还有 {len(pending_tools)} 个待执行")
        return {
            **state,
            "action_history": state["action_history"] + [new_record],
            "current_location": current_location,
            "last_tool_result": last_tool_result if last_tool_result else state.get("last_tool_result"),
            "pending_tool": None,
            "last_error": None,
        }

    print(f"[节点] tool_execution_node | 用户={username} | 步骤={step_count} | 批量执行完毕 | 操作已记录 | 当前位置={current_location}")

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
        print(f"[边] should_continue_edge | 用户={username} | 步骤={step_count}/{max_steps} | 退出原因={reason_str} | 路由=summarize")
        return "summarize"

    pending_tools = state.get("pending_tools")
    if pending_tools and len(pending_tools) > 0:
        print(f"[边] should_continue_edge | 用户={username} | 步骤={step_count}/{max_steps} | 批量工具还有 {len(pending_tools)} 个待执行 | 路由=tool_execution")
        return "tool_execution"

    if step_count >= max_steps:
        print(f"[边] should_continue_edge | 用户={username} | 步骤={step_count}/{max_steps} | 达到最大步数 | 路由=summarize")
        return "summarize"

    print(f"[边] should_continue_edge | 用户={username} | 步骤={step_count}/{max_steps} | 继续决策 | 路由=llm_decision")
    return "llm_decision"


def summarize_node(state: SessionState, llm_invoker: Callable[[str, str], str]) -> SessionState:
    """
    总结节点

    在登出后，根据 action_history（工作记忆）生成会话总结。

    Args:
        state: 当前状态
        llm_invoker: LLM 调用函数

    Returns:
        SessionState: 更新后的状态，包含 summary
    """
    username = state.get("username", "未知")
    action_count = len(state.get("action_history", []))
    print(f"[节点] summarize_node | 用户={username} | 开始生成总结 | 操作数={action_count}")

    if not state.get("action_history"):
        summary = f"用户 {state.get('username', '未知')} 的本次会话未执行任何操作。"
        print(f"[节点] summarize_node | 用户={username} | 无操作记录 | 总结={summary}")
        return {
            **state,
            "summary": summary,
        }

    try:
        user_prompt = build_summarize_prompt(state)

        system_prompt = """你是一个社交平台用户，正在回顾你在平台上的活动。
请根据你的操作记录，以第一人称"我"生成一段总结。
总结应该真实反映你在平台上的活动和感受。
使用中文，100-200字。"""

        summary = llm_invoker(system_prompt, user_prompt)
        print(f"[节点] summarize_node | 用户={username} | LLM总结生成成功 | 长度={len(summary)}字符")

        return {
            **state,
            "summary": summary,
        }

    except Exception as e:
        summary = f"用户 {state.get('username', '未知')} 执行了 {len(state.get('action_history', []))} 个操作。"
        print(f"[节点] summarize_node | 用户={username} | 总结生成异常 | 使用默认总结: {summary}")
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
    print(f"[节点] end_node | 用户={username} | 会话结束 | 总步骤={step_count} | 总结预览={summary_preview}...")
    return state
