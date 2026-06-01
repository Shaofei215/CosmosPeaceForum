import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Callable, Iterable, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from social_platform.app.db.session import SessionLocal
from social_platform.app.models.hot_topic import HotTopic, HotTopicGeneration, HotTopicSettings
from social_platform.app.models.post import Post

logger = logging.getLogger(__name__)

HOT_TOPIC_SCHEDULER_JOB_ID = "generate_hot_topics"
VALID_SOURCES = {"manual", "agent"}
VALID_STATUSES = {"active", "draft", "archived"}
VALID_GENERATION_STATUSES = {"pending", "success", "failed"}
VALID_PUBLISH_POLICIES = {"auto", "draft"}
SECRET_MASK = "********"
DEFAULT_HISTORY_LIMIT = 3
HOT_TOPIC_LLM_TIMEOUT_SECONDS = 90
HOT_TOPIC_LLM_MAX_RETRIES = 1

_scheduler = None
_agent_run_lock = threading.Lock()


class HotTopicAgentRunError(RuntimeError):
    """Raised when a hot topic generation run cannot be represented safely."""


def _now() -> datetime:
    return datetime.utcnow()


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_choice(value: str, choices: set[str], field_name: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in choices:
        raise ValueError(f"{field_name} 必须是 {', '.join(sorted(choices))} 之一")
    return normalized


def _mask_secret(value: str | None) -> str | None:
    return SECRET_MASK if value else None


def _normalize_rank(value: Any, default: int = 1) -> int:
    try:
        rank = int(value)
    except (TypeError, ValueError):
        rank = default
    return max(rank, 1)


def _ordered_topics_for_status(db: Session, status: str) -> list[HotTopic]:
    return (
        db.query(HotTopic)
        .filter(HotTopic.status == status)
        .order_by(HotTopic.rank.asc(), HotTopic.created_at.asc(), HotTopic.id.asc())
        .all()
    )


def _renumber_topic_status(
    db: Session,
    status: str,
    focus_topic: HotTopic | None = None,
    desired_rank: int | None = None,
) -> None:
    topics = _ordered_topics_for_status(db, status)
    if focus_topic is not None and focus_topic.status == status:
        topics = [topic for topic in topics if topic.id != focus_topic.id]
        insert_at = min(_normalize_rank(desired_rank, focus_topic.rank) - 1, len(topics))
        topics.insert(insert_at, focus_topic)

    for index, topic in enumerate(topics, start=1):
        topic.rank = index
        topic.updated_at = _now()


def get_hot_topic_settings(db: Session) -> HotTopicSettings:
    settings = db.query(HotTopicSettings).filter(HotTopicSettings.id == 1).first()
    if settings:
        return settings

    settings = HotTopicSettings(id=1)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def serialize_settings(settings: HotTopicSettings) -> dict[str, Any]:
    return {
        "id": settings.id,
        "agent_enabled": settings.agent_enabled,
        "agent_interval_minutes": settings.agent_interval_minutes,
        "publish_policy": settings.publish_policy,
        "llm_base_url": settings.llm_base_url,
        "llm_model_name": settings.llm_model_name,
        "llm_api_key": _mask_secret(settings.llm_api_key),
        "web_search_enabled": settings.web_search_enabled,
        "tavily_api_key": _mask_secret(settings.tavily_api_key),
        "history_limit": settings.history_limit,
        "updated_at": settings.updated_at,
    }


def update_hot_topic_settings(db: Session, payload: dict[str, Any]) -> HotTopicSettings:
    settings = get_hot_topic_settings(db)
    string_fields = {"llm_base_url", "llm_model_name", "llm_api_key", "tavily_api_key"}

    for field, value in payload.items():
        if value is None:
            continue
        if field == "publish_policy":
            value = _validate_choice(value, VALID_PUBLISH_POLICIES, "publish_policy")
        if field == "agent_interval_minutes":
            value = max(5, int(value))
        if field == "history_limit":
            value = max(1, min(int(value), 10))
        if field in string_fields:
            value = _normalize_text(value)
            if value == SECRET_MASK:
                continue
        if hasattr(settings, field):
            setattr(settings, field, value)

    settings.updated_at = _now()
    db.add(settings)
    db.commit()
    db.refresh(settings)
    configure_hot_topic_agent_job()
    return settings


def list_public_hot_topics(db: Session, limit: int = 20) -> list[HotTopic]:
    return (
        db.query(HotTopic)
        .filter(HotTopic.status == "active")
        .order_by(
            HotTopic.rank.asc(),
            HotTopic.created_at.desc(),
            HotTopic.id.desc(),
        )
        .limit(limit)
        .all()
    )


def list_admin_hot_topics(
    db: Session,
    status: str | None = None,
    source: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[HotTopic], int]:
    query = db.query(HotTopic)
    if status:
        query = query.filter(HotTopic.status == _validate_choice(status, VALID_STATUSES, "status"))
    if source:
        query = query.filter(HotTopic.source == _validate_choice(source, VALID_SOURCES, "source"))

    total = query.with_entities(func.count(HotTopic.id)).scalar() or 0
    items = (
        query.order_by(
            HotTopic.status.asc(),
            HotTopic.rank.asc(),
            HotTopic.created_at.desc(),
            HotTopic.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def create_hot_topic(db: Session, payload: dict[str, Any]) -> HotTopic:
    source = _validate_choice(payload.get("source", "manual"), VALID_SOURCES, "source")
    status = _validate_choice(payload.get("status", "active"), VALID_STATUSES, "status")
    title = _normalize_text(payload.get("title"))
    search_query = _normalize_text(payload.get("search_query"))
    if not title or not search_query:
        raise ValueError("title 和 search_query 不能为空")

    desired_rank = _normalize_rank(payload.get("rank"), default=1)
    topic = HotTopic(
        title=title,
        search_query=search_query,
        summary=_normalize_text(payload.get("summary")),
        source=source,
        status=status,
        rank=desired_rank,
        weight=0,
        is_pinned=False,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(topic)
    db.flush()
    _renumber_topic_status(db, status, focus_topic=topic, desired_rank=desired_rank)
    db.commit()
    db.refresh(topic)
    return topic


def update_hot_topic(db: Session, topic_id: int, payload: dict[str, Any]) -> HotTopic:
    topic = db.query(HotTopic).filter(HotTopic.id == topic_id).first()
    if not topic:
        raise ValueError("热点不存在")

    old_status = topic.status
    desired_rank = topic.rank
    rank_is_explicit = "rank" in payload

    for field, value in payload.items():
        if value is None:
            continue
        if field == "source":
            value = _validate_choice(value, VALID_SOURCES, "source")
        elif field == "status":
            value = _validate_choice(value, VALID_STATUSES, "status")
        elif field in {"title", "search_query"}:
            value = _normalize_text(value)
            if not value:
                raise ValueError(f"{field} 不能为空")
        elif field == "summary":
            value = _normalize_text(value)
        elif field == "rank":
            value = _normalize_rank(value, default=topic.rank)
            desired_rank = value
        elif field in {"weight", "is_pinned"}:
            continue

        if hasattr(topic, field):
            setattr(topic, field, value)

    topic.updated_at = _now()
    db.add(topic)
    db.flush()
    if old_status != topic.status:
        _renumber_topic_status(db, old_status)
        _renumber_topic_status(db, topic.status, focus_topic=topic, desired_rank=desired_rank)
    elif rank_is_explicit:
        _renumber_topic_status(db, topic.status, focus_topic=topic, desired_rank=desired_rank)
    else:
        _renumber_topic_status(db, topic.status)
    db.commit()
    db.refresh(topic)
    return topic


def delete_hot_topic(db: Session, topic_id: int) -> None:
    topic = db.query(HotTopic).filter(HotTopic.id == topic_id).first()
    if not topic:
        raise ValueError("热点不存在")
    status = topic.status
    db.delete(topic)
    db.flush()
    _renumber_topic_status(db, status)
    db.commit()


def publish_hot_topic(db: Session, topic_id: int) -> HotTopic:
    return update_hot_topic(db, topic_id, {"status": "active"})


def archive_hot_topic(db: Session, topic_id: int) -> HotTopic:
    return update_hot_topic(db, topic_id, {"status": "archived"})


def publish_generation(db: Session, generation_id: int) -> list[HotTopic]:
    generation = db.query(HotTopicGeneration).filter(HotTopicGeneration.id == generation_id).first()
    if not generation:
        raise ValueError("生成记录不存在")

    previous_agent_active = (
        db.query(HotTopic)
        .filter(HotTopic.source == "agent", HotTopic.status == "active")
        .all()
    )
    for topic in previous_agent_active:
        topic.status = "archived"
        topic.updated_at = _now()

    topics = (
        db.query(HotTopic)
        .filter(HotTopic.generation_id == generation_id)
        .order_by(HotTopic.rank.asc(), HotTopic.id.asc())
        .all()
    )
    for topic in topics:
        topic.status = "active"
        topic.updated_at = _now()

    generation.publish_policy = "auto"
    db.flush()
    _renumber_topic_status(db, "active")
    _renumber_topic_status(db, "archived")
    db.commit()
    return topics


def list_generations(db: Session, skip: int = 0, limit: int = 20) -> tuple[list[HotTopicGeneration], int]:
    query = db.query(HotTopicGeneration)
    total = query.with_entities(func.count(HotTopicGeneration.id)).scalar() or 0
    items = (
        query.order_by(HotTopicGeneration.created_at.desc(), HotTopicGeneration.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def _compact_topic(topic: HotTopic) -> dict[str, Any]:
    return {
        "title": topic.title,
        "search_query": topic.search_query,
        "summary": topic.summary,
            "source": topic.source,
            "status": topic.status,
            "rank": topic.rank,
    }


def _format_top_posts(db: Session, limit: int = 10) -> list[dict[str, Any]]:
    posts = (
        db.query(Post)
        .options(joinedload(Post.author))
        .order_by(func.coalesce(Post.heat_score, 0).desc(), Post.created_at.desc(), Post.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "author": post.author.username if post.author else "",
            "author_bio": post.author.bio if post.author else "",
            "title": post.title or "",
            "content": (post.content or "")[:1000],
            "like_count": post.like_count or 0,
            "comment_count": post.comment_count or 0,
            "repost_count": post.repost_count or 0,
            "heat_score": round(post.heat_score or 0, 4),
            "created_at": post.created_at.isoformat() if post.created_at else None,
        }
        for post in posts
    ]


def build_hot_topic_agent_context(db: Session, history_limit: int = DEFAULT_HISTORY_LIMIT) -> dict[str, Any]:
    current_topics = [_compact_topic(topic) for topic in list_public_hot_topics(db, limit=20)]
    generations = (
        db.query(HotTopicGeneration)
        .filter(HotTopicGeneration.status == "success")
        .order_by(HotTopicGeneration.created_at.desc(), HotTopicGeneration.id.desc())
        .limit(history_limit)
        .all()
    )
    history = [
        {
            "id": generation.id,
            "created_at": generation.created_at.isoformat() if generation.created_at else None,
            "output_json": generation.output_json,
        }
        for generation in generations
    ]
    return {
        "top_posts": _format_top_posts(db),
        "current_hot_topics": current_topics,
        "recent_generations": history,
    }


def build_hot_topic_agent_prompt(context: dict[str, Any]) -> str:
    return (
        "你是 CosmosPeaceForum 的热榜编辑 Agent。请根据站内热点、当前热榜和以往热榜生成新的热榜候选。\n"
        "目标：标题要适合公开展示，search_query 用于提取关键词，要适合站内搜索召回相关帖子。\n"
        "约束：不要编造无法从上下文或搜索工具支撑的事实；每条必须包含 title 和 search_query；"
        "建议输出 5 到 10 条，rank 从 1 开始递增。\n"
        "可先调用 search_platform 复核站内讨论；如果启用了 web_search，可以检索外部背景。\n"
        "最终必须调用 submit_hot_topics 工具，参数 topics_json 为 JSON 数组字符串。\n\n"
        "当前上下文 JSON：\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def _extract_json_array(value: str) -> list[dict[str, Any]]:
    cleaned = (value or "").strip()
    if not cleaned:
        return []
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start >= 0 and end >= start:
        cleaned = cleaned[start:end + 1]
    parsed = json.loads(cleaned)
    if not isinstance(parsed, list):
        raise ValueError("热榜输出必须是 JSON 数组")
    return [item for item in parsed if isinstance(item, dict)]


def normalize_agent_topics(raw_topics: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    for index, item in enumerate(raw_topics, start=1):
        title = _normalize_text(str(item.get("title") or ""))
        search_query = _normalize_text(str(item.get("search_query") or item.get("query") or title or ""))
        if not title or not search_query:
            continue
        topics.append({
            "title": title[:120],
            "search_query": search_query[:200],
            "summary": _normalize_text(str(item.get("summary") or item.get("reason") or "")),
            "rank": _normalize_rank(item.get("rank"), default=index),
        })
    return topics[:10]


def apply_generated_hot_topics(
    db: Session,
    generation: HotTopicGeneration,
    topics: list[dict[str, Any]],
    publish_policy: str,
) -> list[HotTopic]:
    status = "active" if publish_policy == "auto" else "draft"

    if publish_policy == "auto":
        previous_agent_active = (
            db.query(HotTopic)
            .filter(HotTopic.source == "agent", HotTopic.status == "active")
            .all()
        )
        for topic in previous_agent_active:
            topic.status = "archived"
            topic.updated_at = _now()

    created: list[HotTopic] = []
    for item in topics:
        topic = HotTopic(
            title=item["title"],
            search_query=item["search_query"],
            summary=item.get("summary"),
            source="agent",
            status=status,
            rank=_normalize_rank(item.get("rank"), default=len(created) + 1),
            weight=0,
            is_pinned=False,
            generation_id=generation.id,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(topic)
        created.append(topic)

    generation.status = "success"
    generation.completed_at = _now()
    db.flush()
    _renumber_topic_status(db, status)
    if publish_policy == "auto":
        _renumber_topic_status(db, "archived")
    db.commit()
    for topic in created:
        db.refresh(topic)
    db.refresh(generation)
    return created


def _search_platform_posts_for_agent(db: Session, query: str, count: int = 5) -> list[dict[str, Any]]:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return []

    safe_count = max(1, min(int(count or 5), 10))
    like_query = f"%{normalized_query}%"
    posts = (
        db.query(Post)
        .options(joinedload(Post.author))
        .filter(or_(Post.title.ilike(like_query), Post.content.ilike(like_query)))
        .order_by(func.coalesce(Post.heat_score, 0).desc(), Post.created_at.desc(), Post.id.desc())
        .limit(safe_count)
        .all()
    )
    return [
        {
            "title": post.title,
            "content": (post.content or "")[:500],
            "author": post.author.username if post.author else "",
            "like_count": post.like_count or 0,
            "comment_count": post.comment_count or 0,
            "repost_count": post.repost_count or 0,
            "heat_score": post.heat_score or 0,
        }
        for post in posts
    ]


def _create_search_tool(db: Session):
    from langchain_core.tools import tool

    @tool
    def search_platform(query: str, count: int = 5) -> str:
        """搜索站内帖子和文章内容，返回紧凑 JSON。"""
        try:
            safe_count = max(1, min(int(count or 5), 10))
            logger.info("热榜 Agent 站内搜索开始 query=%r count=%s", (query or "")[:80], safe_count)
            posts = _search_platform_posts_for_agent(db, query, safe_count)
            logger.info("热榜 Agent 站内搜索完成 query=%r results=%s", (query or "")[:80], len(posts))
            return json.dumps({"query": query, "posts": posts}, ensure_ascii=False)
        except Exception as exc:
            logger.exception("热榜 Agent 站内搜索失败 query=%r", (query or "")[:80])
            return json.dumps({"query": query, "posts": [], "error": str(exc)}, ensure_ascii=False)

    return search_platform


def _create_submit_tool(submitted: dict[str, list[dict[str, Any]]]):
    from langchain_core.tools import tool

    @tool
    def submit_hot_topics(topics_json: str) -> str:
        """提交最终热榜。topics_json 必须是 JSON 数组字符串。"""
        submitted["topics"] = normalize_agent_topics(_extract_json_array(topics_json))
        return json.dumps({"accepted": len(submitted["topics"])}, ensure_ascii=False)

    return submit_hot_topics


def _create_web_search_tool(settings: HotTopicSettings):
    from langchain_core.tools import tool

    @tool
    def web_search(query: str, max_results: int = 5) -> str:
        """联网搜索公开信息，返回紧凑 JSON。"""
        if not settings.web_search_enabled:
            return json.dumps({"query": query, "results": [], "error": "web_search_disabled"}, ensure_ascii=False)
        if not settings.tavily_api_key:
            return json.dumps({"query": query, "results": [], "error": "missing_tavily_api_key"}, ensure_ascii=False)
        try:
            from langchain_tavily import TavilySearch

            os.environ["TAVILY_API_KEY"] = settings.tavily_api_key
            tavily = TavilySearch(
                max_results=max(1, min(int(max_results or 5), 10)),
                topic="general",
                include_answer=True,
                include_raw_content=False,
                search_depth="basic",
            )
            response = tavily.invoke({"query": query})
            return json.dumps(response, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"query": query, "results": [], "error": str(exc)}, ensure_ascii=False)

    return web_search


def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    tool_calls = getattr(response, "tool_calls", None) or []
    additional_kwargs = getattr(response, "additional_kwargs", None) or {}
    if not tool_calls and isinstance(additional_kwargs, dict):
        tool_calls = additional_kwargs.get("tool_calls", []) or []

    normalized: list[dict[str, Any]] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("function", {}).get("name")
        args = call.get("args")
        if args is None:
            raw_args = call.get("function", {}).get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {}
        normalized.append({"name": name or "", "args": args or {}})
    return normalized


def _invoke_hot_topic_llm(llm: Any, system_prompt: str, user_prompt: str) -> Any:
    # 和 agents 侧一致：每一轮重新发送 system/user，把工具结果写进 user 文本。
    # 不把上一轮 AIMessage/ToolMessage 作为消息历史回传，避免部分 thinking 模型要求
    # reasoning_content 必须随历史消息一起回传。
    return llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])


def _create_generation_record(db: Session, publish_policy: str) -> HotTopicGeneration:
    generation = HotTopicGeneration(
        status="pending",
        publish_policy=publish_policy,
        created_at=_now(),
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    return generation


def _mark_generation_failed(
    db: Session,
    generation: HotTopicGeneration,
    exc: BaseException,
) -> HotTopicGeneration:
    db.rollback()
    try:
        persisted = db.get(HotTopicGeneration, generation.id)
        if persisted is None:
            raise HotTopicAgentRunError("热榜生成记录不存在，无法写入失败状态")

        persisted.status = "failed"
        persisted.error_message = str(exc)
        persisted.completed_at = _now()
        db.add(persisted)
        db.commit()
        db.refresh(persisted)
        return persisted
    except Exception as record_exc:
        db.rollback()
        logger.exception("热榜 Agent 失败状态写入失败")
        raise HotTopicAgentRunError(
            "热榜 Agent 生成失败，且失败状态无法写入数据库；请检查数据库迁移、连接和写入权限"
        ) from record_exc


def run_hot_topic_agent(
    db: Session,
    force: bool = False,
    llm_factory: Optional[Callable[[HotTopicSettings, list[Any]], Any]] = None,
) -> tuple[HotTopicGeneration, list[HotTopic]]:
    run_started_at = time.perf_counter()
    if not _agent_run_lock.acquire(blocking=False):
        logger.warning("热榜 Agent 已在运行，拒绝新的生成请求 force=%s", force)
        raise HotTopicAgentRunError("热榜 Agent 已在运行，请稍后再试")

    try:
        try:
            settings = get_hot_topic_settings(db)
            if not force and not settings.agent_enabled:
                raise ValueError("热榜 Agent 未启用")

            publish_policy = _validate_choice(
                settings.publish_policy,
                VALID_PUBLISH_POLICIES,
                "publish_policy",
            )
            logger.info(
                "热榜 Agent 开始运行 force=%s enabled=%s publish_policy=%s history_limit=%s web_search=%s model=%s base_url_configured=%s",
                force,
                settings.agent_enabled,
                publish_policy,
                settings.history_limit,
                settings.web_search_enabled,
                settings.llm_model_name or "",
                bool(settings.llm_base_url),
            )
            generation = _create_generation_record(db, publish_policy)
            logger.info("热榜 Agent 创建生成记录 generation_id=%s", generation.id)
        except Exception as exc:
            db.rollback()
            logger.exception("热榜 Agent 初始化失败")
            raise HotTopicAgentRunError(
                "热榜 Agent 初始化失败；请检查数据库迁移、连接和写入权限"
            ) from exc

        submitted: dict[str, list[dict[str, Any]]] = {"topics": []}

        try:
            logger.info("热榜 Agent 构建上下文开始 generation_id=%s", generation.id)
            context = build_hot_topic_agent_context(db, settings.history_limit or DEFAULT_HISTORY_LIMIT)
            prompt = build_hot_topic_agent_prompt(context)
            generation.input_snapshot = json.dumps(context, ensure_ascii=False)
            db.add(generation)
            db.commit()
            db.refresh(generation)
            logger.info(
                "热榜 Agent 构建上下文完成 generation_id=%s top_posts=%s current_topics=%s history=%s",
                generation.id,
                len(context.get("top_posts", [])),
                len(context.get("current_hot_topics", [])),
                len(context.get("recent_generations", [])),
            )

            tools = [_create_search_tool(db), _create_submit_tool(submitted)]
            if settings.web_search_enabled:
                tools.append(_create_web_search_tool(settings))
            logger.info(
                "热榜 Agent 工具准备完成 generation_id=%s tools=%s",
                generation.id,
                [tool.name for tool in tools],
            )

            if llm_factory is None:
                if not settings.llm_model_name or not settings.llm_api_key:
                    raise ValueError("请先配置热榜 Agent 的模型名称和 API Key")
                from langchain_openai import ChatOpenAI

                kwargs: dict[str, Any] = {
                    "model": settings.llm_model_name,
                    "api_key": settings.llm_api_key,
                    "temperature": 0.7,
                    "timeout": HOT_TOPIC_LLM_TIMEOUT_SECONDS,
                    "max_retries": HOT_TOPIC_LLM_MAX_RETRIES,
                }
                if settings.llm_base_url:
                    kwargs["base_url"] = settings.llm_base_url
                logger.info(
                    "热榜 Agent 初始化 LLM generation_id=%s model=%s timeout=%ss max_retries=%s",
                    generation.id,
                    settings.llm_model_name,
                    HOT_TOPIC_LLM_TIMEOUT_SECONDS,
                    HOT_TOPIC_LLM_MAX_RETRIES,
                )
                llm = ChatOpenAI(**kwargs).bind_tools(tools)
            else:
                logger.info("热榜 Agent 使用测试/自定义 LLM factory generation_id=%s", generation.id)
                llm = llm_factory(settings, tools)

            observations: list[str] = []
            for round_index in range(1, 7):
                user_prompt = (
                    "请生成本轮热榜，必要时调用工具，最终调用 submit_hot_topics。\n"
                    "如果已有工具观察结果，请基于这些结果继续判断。\n\n"
                )
                if observations:
                    user_prompt += "## 已有工具观察结果\n" + "\n\n".join(observations)
                logger.info(
                    "热榜 Agent 调用 LLM generation_id=%s round=%s observations=%s",
                    generation.id,
                    round_index,
                    len(observations),
                )
                response = _invoke_hot_topic_llm(llm, prompt, user_prompt)
                tool_calls = _extract_tool_calls(response)
                logger.info(
                    "热榜 Agent LLM 返回 generation_id=%s round=%s tool_calls=%s",
                    generation.id,
                    round_index,
                    [call.get("name") for call in tool_calls],
                )
                if not tool_calls:
                    if not submitted["topics"]:
                        submitted["topics"] = normalize_agent_topics(_extract_json_array(str(response.content)))
                    break

                tool_map = {tool.name: tool for tool in tools}
                for call in tool_calls:
                    tool_name = call.get("name")
                    tool_args = call.get("args") or {}
                    logger.info(
                        "热榜 Agent 调用工具 generation_id=%s round=%s tool=%s",
                        generation.id,
                        round_index,
                        tool_name,
                    )
                    if tool_name not in tool_map:
                        content = f"未知工具: {tool_name}"
                    else:
                        content = str(tool_map[tool_name].invoke(tool_args))
                    observations.append(f"工具 {tool_name} 返回：\n{content}")
                    if tool_name == "submit_hot_topics":
                        break
                if submitted["topics"]:
                    break

            if not submitted["topics"]:
                raise ValueError("热榜 Agent 没有提交有效热榜")

            generation.output_json = json.dumps(submitted["topics"], ensure_ascii=False)
            logger.info(
                "热榜 Agent 写入生成结果开始 generation_id=%s topic_count=%s publish_policy=%s",
                generation.id,
                len(submitted["topics"]),
                publish_policy,
            )
            topics = apply_generated_hot_topics(db, generation, submitted["topics"], publish_policy)
            logger.info(
                "热榜 Agent 生成成功 generation_id=%s topic_count=%s duration=%.2fs",
                generation.id,
                len(topics),
                time.perf_counter() - run_started_at,
            )
            return generation, topics
        except Exception as exc:
            generation = _mark_generation_failed(db, generation, exc)
            logger.exception(
                "热榜 Agent 生成失败 generation_id=%s duration=%.2fs",
                generation.id,
                time.perf_counter() - run_started_at,
            )
            return generation, []
    finally:
        _agent_run_lock.release()


def run_scheduled_hot_topic_agent() -> None:
    db = SessionLocal()
    try:
        settings = get_hot_topic_settings(db)
        if not settings.agent_enabled:
            return
        run_hot_topic_agent(db)
    except Exception:
        logger.exception("定时热榜 Agent 运行失败")
    finally:
        db.close()


def register_hot_topic_scheduler(scheduler) -> None:
    global _scheduler
    _scheduler = scheduler
    configure_hot_topic_agent_job()


def configure_hot_topic_agent_job(scheduler=None) -> None:
    active_scheduler = scheduler or _scheduler
    if active_scheduler is None:
        return

    db = SessionLocal()
    try:
        settings = get_hot_topic_settings(db)
        existing = active_scheduler.get_job(HOT_TOPIC_SCHEDULER_JOB_ID)
        if existing:
            active_scheduler.remove_job(HOT_TOPIC_SCHEDULER_JOB_ID)
        if not settings.agent_enabled:
            return
        active_scheduler.add_job(
            run_scheduled_hot_topic_agent,
            "interval",
            minutes=max(5, settings.agent_interval_minutes or 180),
            id=HOT_TOPIC_SCHEDULER_JOB_ID,
            replace_existing=True,
        )
        logger.info("热榜 Agent 调度已启用，每 %s 分钟运行一次", settings.agent_interval_minutes)
    finally:
        db.close()
