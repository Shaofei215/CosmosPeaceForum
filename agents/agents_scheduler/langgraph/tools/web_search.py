# 联网搜索工具
# 为决策节点提供 Tavily 驱动的实时网络检索能力

import os
from datetime import datetime
from typing import Any, Dict, List, Literal

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
        return 10
    return min(max(value, 1), 20)


def _normalize_search_depth(search_depth: str) -> str:
    raw_depth = (search_depth or "advanced").strip().lower()
    aliases = {
        "advanced": "advanced",
        "depth": "advanced",
        "deep": "advanced",
        "basic": "basic",
        "fast": "fast",
        "ultra-fast": "ultra-fast",
    }
    return aliases.get(raw_depth, "advanced")


def _normalize_topic(topic: str) -> str:
    """清理 Tavily 搜索类别。

    Args:
        topic: Agent 或管理员提供的搜索类别。

    Returns:
        str: Tavily 支持的搜索类别，非法值回退为 general。
    """

    normalized = (topic or "general").strip().lower()
    return normalized if normalized in {"general", "news", "finance"} else "general"


def _normalize_domains(domains: List[str] | None) -> List[str]:
    """清理 Tavily 域名列表并保持原有顺序。

    Args:
        domains: Agent 提供的域名列表。

    Returns:
        List[str]: 去空、去重后的域名列表。
    """

    normalized: List[str] = []
    seen: set[str] = set()
    for domain in domains or []:
        value = str(domain).strip().lower()
        if value and value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


def _parse_domain_config(value: str) -> List[str]:
    """把管理员填写的逗号分隔域名转换为 Tavily 参数。

    Args:
        value: 管理员保存的逗号分隔域名。

    Returns:
        List[str]: 可直接传给 Tavily 的域名列表。
    """

    if not isinstance(value, str) or not value.strip():
        return []
    return _normalize_domains(value.replace("，", ",").split(","))


def _normalize_date(value: str | None, field_name: str) -> str | None:
    """校验并清理 Tavily 的绝对日期参数。

    Args:
        value: Agent 提供的日期字符串。
        field_name: 对外展示的参数名。

    Returns:
        str | None: ``YYYY-MM-DD`` 日期或空值。

    Raises:
        ValueError: 日期格式不符合 Tavily 要求。
    """

    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        parsed = datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须使用 YYYY-MM-DD 格式") from exc
    if parsed.strftime("%Y-%m-%d") != normalized:
        raise ValueError(f"{field_name} 必须使用 YYYY-MM-DD 格式")
    return normalized


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
            "published_date": item.get("published_date"),
        })

    return {
        "answer": answer,
        "results": results,
    }


@tool
def web_search(
    query: str,
    topic: Literal["general", "news", "finance"] = "general",
    max_results: int = 10,
    search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "advanced",
    time_range: Literal["day", "week", "month", "year"] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    include_domains: List[str] | None = None,
    exclude_domains: List[str] | None = None,
) -> ToolResult:
    """联网搜索公开网络信息。

    当需要了解平台外的实时信息、背景资料、新闻、事实核验或公开网页内容时使用。

    Args:
        query: 必填搜索查询。需要最新信息时应包含明确的事件、实体和时间意图。
        topic: 搜索类别。general 用于通用信息，news 用于时政、体育等主流新闻，
            finance 用于金融市场信息。默认 general。
        max_results: 最大结果数，范围 1 到 20，默认 10。
        search_depth: 搜索深度。basic 平衡速度与相关性，advanced 提高相关性，
            fast 优先低延迟，ultra-fast 优先最低延迟。默认 advanced。
        time_range: 相对当前日期的发布时间范围，可选 day、week、month、year。
            查询“今天”“最新”“最近”等信息时应主动设置。
        start_time: 最早发布日期，格式 YYYY-MM-DD。与 end_time 组合可限定绝对
            日期区间；提供绝对日期时会忽略 time_range。
        end_time: 最晚发布日期，格式 YYYY-MM-DD。与 start_time 组合可限定绝对
            日期区间；提供绝对日期时会忽略 time_range。
        include_domains: 只允许这些域名出现在结果中，例如 ["who.int"]。
        exclude_domains: 排除这些域名，例如 ["example.com"]。

    Returns:
        ToolResult: data 中包含实际生效的搜索参数、answer 和 results。执行节点会把
        结果追加到 last_tool_result，让下一次决策同时看到页面内容和联网搜索结果。
    """
    config = get_session_config()
    clean_query = query.strip()
    configured_topic = getattr(config, "tavily_topic", "")
    configured_max_results = getattr(config, "tavily_max_results", None)
    configured_search_depth = getattr(config, "tavily_search_depth", "")
    effective_topic = _normalize_topic(
        configured_topic if isinstance(configured_topic, str) and configured_topic else topic
    )
    effective_max_results = _normalize_max_results(
        configured_max_results
        if isinstance(configured_max_results, int)
        else max_results
    )
    effective_search_depth = _normalize_search_depth(
        configured_search_depth
        if isinstance(configured_search_depth, str) and configured_search_depth
        else search_depth
    )
    configured_include_domains = _parse_domain_config(
        getattr(config, "tavily_include_domains", "")
    )
    configured_exclude_domains = _parse_domain_config(
        getattr(config, "tavily_exclude_domains", "")
    )
    effective_include_domains = configured_include_domains or _normalize_domains(
        include_domains
    )
    effective_exclude_domains = configured_exclude_domains or _normalize_domains(
        exclude_domains
    )
    clean_start_time = _normalize_date(start_time, "start_time")
    clean_end_time = _normalize_date(end_time, "end_time")
    if clean_start_time and clean_end_time and clean_start_time > clean_end_time:
        raise ValueError("start_time 不能晚于 end_time")
    effective_time_range = None if clean_start_time or clean_end_time else time_range

    search_parameters = {
        "topic": effective_topic,
        "max_results": effective_max_results,
        "search_depth": effective_search_depth,
        "time_range": effective_time_range,
        "start_time": clean_start_time,
        "end_time": clean_end_time,
        "include_domains": effective_include_domains,
        "exclude_domains": effective_exclude_domains,
    }

    if not config.web_search_enabled:
        return ToolResult(
            action="联网搜索未启用，无法检索网络信息",
            data={
                "source": "web_search",
                "query": clean_query,
                **search_parameters,
                "results": [],
            },
        )

    if not config.tavily_api_key:
        return ToolResult(
            action="Tavily API Key 未配置，无法联网搜索",
            data={
                "source": "web_search",
                "query": clean_query,
                **search_parameters,
                "results": [],
            },
        )

    if not clean_query:
        return ToolResult(
            action="没有提供检索字符串，无法联网搜索",
            data={
                "source": "web_search",
                "query": clean_query,
                **search_parameters,
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
            max_results=effective_max_results,
            include_answer=True,
            include_raw_content=False,
        )
        search_args: Dict[str, Any] = {
            "query": clean_query,
            "topic": effective_topic,
            "search_depth": effective_search_depth,
        }
        if effective_time_range:
            search_args["time_range"] = effective_time_range
        if clean_start_time:
            search_args["start_date"] = clean_start_time
        if clean_end_time:
            search_args["end_date"] = clean_end_time
        if effective_include_domains:
            search_args["include_domains"] = effective_include_domains
        if effective_exclude_domains:
            search_args["exclude_domains"] = effective_exclude_domains

        response = tavily_tool.invoke(search_args)
        normalized = _normalize_tavily_response(response)
        data = {
            "source": "web_search",
            "query": clean_query,
            **search_parameters,
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
                **search_parameters,
                "results": [],
            },
        )
