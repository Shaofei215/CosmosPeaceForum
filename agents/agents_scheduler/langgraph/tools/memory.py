# 记忆工具函数
# 包含与记忆操作相关的工具
# 注意：write_memory 工具应该仅在总结节点中绑定给 LLM，而不是随其他工具一起绑定

import asyncio
from typing import List, Dict, Any, Callable

from langchain_core.tools import tool

from agents.agents_scheduler.scheduler.context import get_current_user_id
from agents.agents_scheduler.scheduler.time_system import get_time_system
from agents.agents_scheduler.memory.service import get_memory_service
from agents.agents_scheduler.memory.config import get_memory_config
from agents.agents_scheduler.langgraph.tools.types import ToolResult


def _short_query(query: str, max_length: int = 40) -> str:
    query = query.strip()
    if len(query) <= max_length:
        return query
    return f"{query[:max_length]}..."


def merge_recall_memory_result(
    previous_result: Any,
    recall_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    将主动回想结果追加到 last_tool_result，而不是替换上一步页面内容。

    自动 recall_memory_node 仍负责每轮环境式召回；这里保存的是 Agent 主动查询的
    定向召回结果，下一次决策会在“上一步执行后当前查看的内容”中一起看到。
    """
    if is_merged_recall_memory_result(previous_result):
        current_view = previous_result.get("current_view")
        explicit_recalls = list(previous_result.get("explicit_recalls") or [])
    else:
        current_view = previous_result
        explicit_recalls = []

    explicit_recalls.append(recall_result)
    web_searches = []
    if is_merged_recall_memory_result(previous_result):
        web_searches = list(previous_result.get("web_searches") or [])
    return {
        "current_view": current_view,
        "explicit_recalls": explicit_recalls,
        "web_searches": web_searches,
    }


def is_merged_recall_memory_result(result: Any) -> bool:
    """判断 last_tool_result 是否包含主动回想合并结果。"""
    return (
        isinstance(result, dict)
        and "current_view" in result
        and "explicit_recalls" in result
    )


def format_merged_recall_memory_result(
    result: Dict[str, Any],
    format_current_view: Callable[[Any], str],
) -> str:
    """格式化“上一步页面内容 + 主动回想”结构，供 prompt 展示。"""
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


@tool
def recall_memory(query: str, reason: str = "", summary: str = "") -> ToolResult:
    """
    主动回想长期记忆。

    当当前看到的内容让你想起某个具体人物、主题、事件或偏好，但自动召回的记忆不够精确时，
    使用此工具传入一段查询文本，从长期记忆库中定向检索相关记忆。

    Args:
        query: 查询文本。应写清楚你想回想的具体对象、主题或问题。
        reason: 调用该工具的原因，用于记录操作动机与上下文，75字以内。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。

    Returns:
        ToolResult: data 中包含 query、memories 和 total。执行节点会把结果追加到 last_tool_result，
        让下一次决策同时看到上一步页面内容和主动回想内容。
    """
    owner_id = get_current_user_id()
    config = get_memory_config()
    clean_query = query.strip()

    if not config.memory_enabled:
        return ToolResult(
            action="记忆系统未启用，无法回想",
            data={"query": clean_query, "memories": [], "total": 0}
        )

    if not owner_id:
        return ToolResult(
            action="当前用户不存在，无法回想长期记忆",
            data={"query": clean_query, "memories": [], "total": 0}
        )

    if not clean_query:
        return ToolResult(
            action="没有提供回想查询，无法回想长期记忆",
            data={"query": clean_query, "memories": [], "total": 0}
        )

    try:
        service = get_memory_service()
        current_time = get_time_system().get_scaled_timestamp()
        recalled = asyncio.run(service.recall_memories(
            owner_id=owner_id,
            context=clean_query,
            current_time=current_time,
            limit=config.recall_limit
        ))

        memories = [
            {
                "id": getattr(chunk, "id", None),
                "content": chunk.content,
                "time_description": time_desc,
                "memory_coefficient": getattr(chunk, "memory_coefficient", None),
            }
            for chunk, time_desc in recalled
        ]

        return ToolResult(
            action=f"回想了与「{_short_query(clean_query)}」相关的{len(memories)}条记忆",
            data={"query": clean_query, "memories": memories, "total": len(memories)}
        )
    except Exception as e:
        return ToolResult(
            action=f"记忆回想失败: {str(e)}",
            data={"query": clean_query, "memories": [], "total": 0}
        )


@tool
def write_memory(memories: List[Dict[str, Any]]) -> ToolResult:
    """
    将记忆写入长期记忆库

    【重要！】注意！如果提示词中未提及调用此工具，此工具严禁被调用！

    使用场景：
    - 总结节点中，LLM 根据会话操作历史，将重要经历写入长期记忆
    - LLM 需将内容拆分为 n 个语义完整的记忆片段，一次性传入

    注意：
    - 每条记忆应以"我"为主语，第一人称描述
    - 每次调用可写入多条记忆，每条记忆分块上限512 tokens，每个分块都必须有完整的上下文叙事、指代明确的人物信息。
    - memories 是一个列表，每个元素是一个字典，包含 content 和 memory_coefficient

    Args:
        memories: 记忆列表，每个元素为字典，包含以下字段：
            - content (str): 记忆内容，第一人称叙事性描述（必填）
            - memory_coefficient (float): 记忆系数 [0.0, 1.0]，越高表明记忆越重要

    Returns:
        ToolResult: 包含操作结果和记忆 ID 列表
    """
    owner_id = get_current_user_id()
    config = get_memory_config()

    if not config.memory_enabled:
        return ToolResult(
            action="记忆系统未启用，无法写入",
            data={"memory_ids": []}
        )

    try:
        service = get_memory_service()

        memory_ids = []
        for mem in memories:
            content = mem.get("content", "")
            coefficient = mem.get("memory_coefficient", 0.85)

            if not content:
                continue

            memory_id = asyncio.run(service.write_memory(
                content=content,
                owner_id=owner_id,
                memory_coefficient=coefficient,
                semantic_timestamp=0.0
            ))
            memory_ids.append(memory_id)

        return ToolResult(
            action=f"将{len(memory_ids)}条记忆写入长期记忆库",
            data={"memory_ids": memory_ids}
        )
    except Exception as e:
        return ToolResult(
            action=f"记忆写入失败: {str(e)}",
            data={"memory_ids": []}
        )
