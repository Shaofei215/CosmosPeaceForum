# 工具结果上下文合并与格式化
# 负责把不改变页面位置的主动查询结果追加到 last_tool_result。

from typing import Any, Callable, Dict


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
            previous_result.get("current_view"),
            list(previous_result.get("explicit_recalls") or []),
            list(previous_result.get("web_searches") or []),
        )
    return previous_result, [], []


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


def format_merged_tool_context_result(
    result: Dict[str, Any],
    format_current_view: Callable[[Any], str],
) -> str:
    """格式化“上一步页面内容 + 主动查询结果”结构，供 prompt 展示。"""
    lines = []
    current_view = result.get("current_view")
    if current_view is not None:
        lines.append("【上一步页面内容】")
        lines.append(format_current_view(current_view))

    explicit_recalls = result.get("explicit_recalls") or []
    for recall in explicit_recalls:
        query = recall.get("query", "")
        memories = recall.get("memories", [])
        total = recall.get("total", len(memories))
        lines.append(f"\n【主动回想】查询：{query}，共{total}条")
        if not memories:
            lines.append("没有回想起相关记忆")
            continue
        for memory in memories:
            lines.append(f"  - 记忆片段 - {memory.get('time_description', '时间未知')}")
            lines.append(f"    {memory.get('content', '')}")

    web_searches = result.get("web_searches") or []
    for search in web_searches:
        query = search.get("query", "")
        results = search.get("results", [])
        total = search.get("total", len(results))
        depth = search.get("search_depth", "advanced")
        lines.append(f"\n【联网搜索】查询：{query}，深度：{depth}，共{total}条")
        answer = search.get("answer")
        if answer:
            lines.append(f"概览：{answer}")
        if not results:
            lines.append("没有找到相关网页结果")
            continue
        for item in results:
            lines.append(f"  - {item.get('title', 'Untitled')}")
            lines.append(f"    URL: {item.get('url', '')}")
            content = item.get("content", "")
            if content:
                lines.append(f"    摘要: {content}")
    return "\n".join(lines)
