# 联网搜索工具
# 为决策节点提供 Tavily 驱动的实时网络检索能力

import os
from typing import Any, Dict, List

from langchain_core.tools import tool

from agents.agents_scheduler.langgraph.config import get_session_config
from agents.agents_scheduler.langgraph.tools.types import ToolResult


def _short_query(query: str, max_length: int = 40) -> str:
    query = query.strip()
    if len(query) <= max_length:
        return query
    return f"{query[:max_length]}..."


def _normalize_max_results(max_results: int) -> int:
    try:
        value = int(max_results)
    except (TypeError, ValueError):
        return 5
    return min(max(value, 1), 10)


def _normalize_search_depth(search_depth: str) -> str:
    raw_depth = (search_depth or "advanced").strip().lower()
    aliases = {
        "advanced": "advanced",
        "depth": "advanced",
        "deep": "advanced",
        "basic": "basic",
    }
    return aliases.get(raw_depth, "advanced")


def _normalize_tavily_response(response: Any) -> Dict[str, Any]:
    if isinstance(response, dict):
        raw_results = response.get("results", [])
        answer = response.get("answer")
    elif isinstance(response, list):
        raw_results = response
        answer = None
    else:
        raw_results = []
        answer = None

    results: List[Dict[str, Any]] = []
    for item in raw_results or []:
        if not isinstance(item, dict):
            continue
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "score": item.get("score"),
        })

    return {
        "answer": answer,
        "results": results,
    }


@tool
def web_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "advanced",
) -> ToolResult:
    """
    联网搜索公开网络信息。

    当需要了解平台外的实时信息、背景资料、新闻、事实核验或公开网页内容时使用。

    Args:
        query: 检索字符串。应写清楚要查找的问题、实体、时间范围或关键词。
        max_results: 检索结果数量，默认 5，可指定 1 到 10。
        search_depth: 检索深度，默认 advanced。可指定 advanced 或 basic；depth 会按 advanced 处理。

    Returns:
        ToolResult: data 中包含 query、search_depth 和 results。执行节点会把结果追加到
        last_tool_result，让下一次决策同时看到上一步页面内容和联网搜索结果。
    """
    config = get_session_config()
    clean_query = query.strip()
    clean_max_results = _normalize_max_results(max_results)
    clean_depth = _normalize_search_depth(search_depth)

    if not config.web_search_enabled:
        return ToolResult(
            action="联网搜索未启用，无法检索网络信息",
            data={
                "source": "web_search",
                "query": clean_query,
                "search_depth": clean_depth,
                "results": [],
            },
        )

    if not config.tavily_api_key:
        return ToolResult(
            action="Tavily API Key 未配置，无法联网搜索",
            data={
                "source": "web_search",
                "query": clean_query,
                "search_depth": clean_depth,
                "results": [],
            },
        )

    if not clean_query:
        return ToolResult(
            action="没有提供检索字符串，无法联网搜索",
            data={
                "source": "web_search",
                "query": clean_query,
                "search_depth": clean_depth,
                "results": [],
            },
        )

    try:
        try:
            from langchain_tavily import TavilySearch
        except ImportError as exc:
            raise RuntimeError("缺少 langchain-tavily 依赖，请安装 agents/requirements.txt") from exc

        os.environ["TAVILY_API_KEY"] = config.tavily_api_key
        tavily_tool = TavilySearch(
            max_results=clean_max_results,
            topic="general",
            include_answer=True,
            include_raw_content=False,
            search_depth=clean_depth,
        )
        response = tavily_tool.invoke({"query": clean_query, "search_depth": clean_depth})
        normalized = _normalize_tavily_response(response)
        data = {
            "source": "web_search",
            "query": clean_query,
            "search_depth": clean_depth,
            **normalized,
        }
        return ToolResult(
            action=f"联网搜索了「{_short_query(clean_query)}」",
            data=data,
        )
    except Exception as e:
        return ToolResult(
            action=f"联网搜索失败: {str(e)}",
            data={
                "source": "web_search",
                "query": clean_query,
                "search_depth": clean_depth,
                "results": [],
            },
        )
