# 工具结果上下文合并
# 负责把不改变页面位置的主动查询结果追加到 last_tool_result。

from typing import Any, Dict


def _without_unread_reminder(value: Any) -> Any:
    """从被保留的旧页面视野中移除已经过时的未读提醒。"""

    if not isinstance(value, dict) or "unread_count" not in value:
        return value
    result = dict(value)
    result.pop("unread_count", None)
    return result


def is_merged_tool_context_result(result: Any) -> bool:
    """判断 last_tool_result 是否为“页面内容 + 主动查询结果”的合并结构。"""
    return (
        isinstance(result, dict)
        and "current_view" in result
        and "explicit_recalls" in result
    )


def _split_previous_result(previous_result: Any) -> tuple[Any, list, list]:
    if is_merged_tool_context_result(previous_result):
        return (
            _without_unread_reminder(previous_result.get("current_view")),
            list(previous_result.get("explicit_recalls") or []),
            list(previous_result.get("web_searches") or []),
        )
    return _without_unread_reminder(previous_result), [], []


def merge_recall_memory_result(
    previous_result: Any,
    recall_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    将主动回想结果追加到 last_tool_result，而不是替换上一步页面内容。

    自动 recall_memory_node 仍负责每轮环境式召回；这里保存的是 Agent 主动查询的
    定向召回结果，下一次决策会在“上一步执行后当前查看的内容”中一起看到。
    """
    current_view, explicit_recalls, web_searches = _split_previous_result(previous_result)
    explicit_recalls.append(recall_result)
    return {
        "current_view": current_view,
        "explicit_recalls": explicit_recalls,
        "web_searches": web_searches,
    }

def merge_web_search_result(
    previous_result: Any,
    web_search_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    将主动联网搜索结果追加到 last_tool_result，而不是替换上一步页面内容。

    这样 LLM 下一步能同时看到“刚才在看什么”和“刚才为什么搜索、搜到了什么”。
    """
    current_view, explicit_recalls, web_searches = _split_previous_result(previous_result)
    web_searches.append(web_search_result)
    return {
        "current_view": current_view,
        "explicit_recalls": explicit_recalls,
        "web_searches": web_searches,
    }
