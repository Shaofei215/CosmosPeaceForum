"""热榜领域应用服务，被公开 API、管理 API 和后台调度共同使用。

本模块把热榜生命周期收束在一处：人工编辑、Agent 生成草稿、发布归档、
LLM 工具编排和 APScheduler 注册都复用同一套持久化规则。
"""

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
from social_platform.app.domains.hot_topic.models import HotTopic, HotTopicGeneration, HotTopicSettings
from social_platform.app.domains.post.models import Post

logger = logging.getLogger(__name__)

HOT_TOPIC_SCHEDULER_JOB_ID = "generate_hot_topics"
VALID_SOURCES = {"manual", "agent"}
VALID_STATUSES = {"active", "draft", "archived"}
VALID_GENERATION_STATUSES = {"pending", "success", "failed"}
VALID_PUBLISH_POLICIES = {"auto", "draft"}
SECRET_MASK = "********"
DEFAULT_HISTORY_LIMIT = 3
DEFAULT_MAX_LLM_ROUNDS = 6
HOT_TOPIC_TITLE_MAX_LENGTH = 120
HOT_TOPIC_SEARCH_QUERY_MAX_LENGTH = 200
HOT_TOPIC_SUMMARY_MAX_LENGTH = 150
HOT_TOPIC_LLM_TIMEOUT_SECONDS = 90
HOT_TOPIC_LLM_MAX_RETRIES = 1
HOT_TOPIC_AGENT_PROMPT_KEY = "hot_topic_agent_prompt"
HOT_TOPIC_AGENT_PROMPT_NAME = "热榜生成提示词"
HOT_TOPIC_AGENT_PROMPT_DESCRIPTION = "用于指导热榜 Agent 生成候选热点。"
DEFAULT_HOT_TOPIC_AGENT_PROMPT = """你是 CosmosPeaceForum 的热榜编辑 Agent。请从站内讨论、当前热榜和历史生成记录中提炼新的候选事件。

任务目标：
- 生成 5 到 10 条适合公开展示的候选事件。
- 每条都必须来自上下文、站内搜索结果或可验证的外部搜索结果，不得补写没有依据的事实。
- 标题、摘要和搜索词都只描述事件本身，不评价热度、排名、趋势、爆火程度或推荐理由。

输出字段：
- title：简洁中文标题，聚焦一个具体事件或讨论主题，不写“热榜”“热门”“第几名”“最受关注”等与事件无关的表达。
- summary：一句话说明事件核心信息，不超过 150 个中文字符；不要解释入选原因、讨论量、排序依据或热度变化。
- search_query：只能是一个搜索关键词或一个不可拆分的短语，用于站内检索；不要放多个关键词、不要使用逗号、顿号、斜杠、分号、换行或“和/与/及”等并列词连接多个查询。
- rank：从 1 开始递增，按事件热度或重大程度排序；不要在 title、summary 或 search_query 中提到排序信息。

工具使用：
- 可先调用 search_platform 复核站内讨论；如果启用了 web_search，可以检索外部背景。
- 最终必须通过 submit_hot_topics 工具提交 JSON 数组字符串，数组项至少包含 title 和 search_query，可包含 summary 和 rank。
- 如果证据不足，减少条目数量，也不要编造。

当前上下文 JSON：
{context_json}"""

_scheduler = None
_agent_run_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 基础归一化和运行配置
# ---------------------------------------------------------------------------


class HotTopicAgentRunError(RuntimeError):
    """热榜生成流程无法安全表达结果时抛出。"""


def _now() -> datetime:
    return datetime.utcnow()


def _normalize_text(value: str | None) -> str | None:
    """统一清理人工输入和模型输出，空字符串按 NULL 处理。"""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_choice(value: str, choices: set[str], field_name: str) -> str:
    """枚举字段入库前统一小写和校验，避免脏状态扩散。"""
    normalized = (value or "").strip().lower()
    if normalized not in choices:
        raise ValueError(f"{field_name} 必须是 {', '.join(sorted(choices))} 之一")
    return normalized


def _mask_secret(value: str | None) -> str | None:
    """对外序列化密钥时只返回稳定掩码，避免管理端误清空。"""
    return SECRET_MASK if value else None


def _normalize_rank(value: Any, default: int = 1) -> int:
    """所有状态桶都使用从 1 开始的连续 rank。"""
    try:
        rank = int(value)
    except (TypeError, ValueError):
        rank = default
    return max(rank, 1)


def _normalize_search_query(value: str | None) -> str | None:
    """只保留一个检索短语，让一条热榜对应一个召回意图。"""
    normalized = _normalize_text(value)
    if not normalized:
        return None

    for separator in ("\n", "\r", "，", ",", "、", "；", ";", "/", "|"):
        normalized = normalized.split(separator, 1)[0].strip()
    return normalized[:HOT_TOPIC_SEARCH_QUERY_MAX_LENGTH] or None


def _normalize_summary(value: str | None) -> str | None:
    """摘要遵守公开卡片的 150 字上限。"""
    normalized = _normalize_text(value)
    if not normalized:
        return None
    return normalized[:HOT_TOPIC_SUMMARY_MAX_LENGTH]


def _ordered_topics_for_status(db: Session, status: str) -> list[HotTopic]:
    """按 rank 修复时使用的稳定顺序读取同一状态桶。"""
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
    """插入、移动、发布或删除后修复连续 rank。"""
    topics = _ordered_topics_for_status(db, status)
    if focus_topic is not None and focus_topic.status == status:
        topics = [topic for topic in topics if topic.id != focus_topic.id]
        insert_at = min(_normalize_rank(desired_rank, focus_topic.rank) - 1, len(topics))
        topics.insert(insert_at, focus_topic)

    for index, topic in enumerate(topics, start=1):
        topic.rank = index
        topic.updated_at = _now()


def get_hot_topic_settings(db: Session) -> HotTopicSettings:
    """读取单例配置；新库首次访问时顺手创建默认行。"""
    settings = db.query(HotTopicSettings).filter(HotTopicSettings.id == 1).first()
    if settings:
        return settings

    settings = HotTopicSettings(id=1)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def serialize_settings(settings: HotTopicSettings) -> dict[str, Any]:
    """序列化管理端配置，同时避免泄露 API Key。"""
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
        "max_llm_rounds": settings.max_llm_rounds or DEFAULT_MAX_LLM_ROUNDS,
        "updated_at": settings.updated_at,
    }


def serialize_prompt_config(settings: HotTopicSettings) -> dict[str, Any]:
    """同时暴露当前提示词和内置默认值，供管理端编辑与重置。"""
    value = settings.prompt_template or DEFAULT_HOT_TOPIC_AGENT_PROMPT
    return {
        "key": HOT_TOPIC_AGENT_PROMPT_KEY,
        "name": HOT_TOPIC_AGENT_PROMPT_NAME,
        "description": HOT_TOPIC_AGENT_PROMPT_DESCRIPTION,
        "value": value,
        "default_value": DEFAULT_HOT_TOPIC_AGENT_PROMPT,
        "updated_at": settings.updated_at,
    }


def update_hot_topic_settings(db: Session, payload: dict[str, Any]) -> HotTopicSettings:
    """应用管理端局部更新；调度相关字段变更后重配后台任务。"""
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
            value = max(0, min(int(value), 10))
        if field == "max_llm_rounds":
            value = max(1, min(int(value), 20))
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


def update_hot_topic_prompt_template(db: Session, value: str) -> HotTopicSettings:
    """保存自定义提示词；缺少上下文占位符时构建阶段会自动补上。"""
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("提示词模板不能为空")

    settings = get_hot_topic_settings(db)
    settings.prompt_template = normalized
    settings.updated_at = _now()
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def reset_hot_topic_prompt_template(db: Session) -> HotTopicSettings:
    """恢复新一轮热榜生成使用的内置提示词。"""
    settings = get_hot_topic_settings(db)
    settings.prompt_template = DEFAULT_HOT_TOPIC_AGENT_PROMPT
    settings.updated_at = _now()
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def list_public_hot_topics(db: Session, limit: int = 20) -> list[HotTopic]:
    """公开 API 只展示 active 热榜，并尊重编辑控制的 rank。"""
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
    """管理端列表保留 draft、active、archived 的完整可见性。"""
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


# ---------------------------------------------------------------------------
# 人工热榜 CRUD 和生成记录发布
# ---------------------------------------------------------------------------


def create_hot_topic(db: Session, payload: dict[str, Any]) -> HotTopic:
    """创建人工热榜，并把目标状态桶的 rank 调整为连续值。"""
    source = _validate_choice(payload.get("source", "manual"), VALID_SOURCES, "source")
    status = _validate_choice(payload.get("status", "active"), VALID_STATUSES, "status")
    title = _normalize_text(payload.get("title"))
    search_query = _normalize_search_query(payload.get("search_query"))
    if not title or not search_query:
        raise ValueError("title 和 search_query 不能为空")

    desired_rank = _normalize_rank(payload.get("rank"), default=1)
    topic = HotTopic(
        title=title[:HOT_TOPIC_TITLE_MAX_LENGTH],
        search_query=search_query,
        summary=_normalize_summary(payload.get("summary")),
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
    """更新一条热榜；状态或 rank 变化会触发两侧状态桶重排。"""
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
        elif field == "title":
            value = _normalize_text(value)
            if not value:
                raise ValueError(f"{field} 不能为空")
            value = value[:HOT_TOPIC_TITLE_MAX_LENGTH]
        elif field == "search_query":
            value = _normalize_search_query(value)
            if not value:
                raise ValueError(f"{field} 不能为空")
        elif field == "summary":
            value = _normalize_summary(value)
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
    """删除热榜后修复原状态桶 rank，避免公开列表出现空洞。"""
    topic = db.query(HotTopic).filter(HotTopic.id == topic_id).first()
    if not topic:
        raise ValueError("热点不存在")
    status = topic.status
    db.delete(topic)
    db.flush()
    _renumber_topic_status(db, status)
    db.commit()


def publish_hot_topic(db: Session, topic_id: int) -> HotTopic:
    """把单条热榜发布到 active 状态。"""

    return update_hot_topic(db, topic_id, {"status": "active"})


def archive_hot_topic(db: Session, topic_id: int) -> HotTopic:
    """把单条热榜归档到 archived 状态。"""

    return update_hot_topic(db, topic_id, {"status": "archived"})


def publish_generation(db: Session, generation_id: int) -> list[HotTopic]:
    """把某次 Agent 生成记录发布为 active，并归档旧的 Agent 热榜。"""
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
    """分页查看 Agent 生成历史，供管理端审计失败和发布状态。"""
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
    """压缩热榜字段，避免把数据库对象细节塞进 LLM 上下文。"""
    return {
        "title": topic.title,
        "search_query": topic.search_query,
        "summary": topic.summary,
        "source": topic.source,
        "status": topic.status,
        "rank": topic.rank,
    }


def _format_top_posts(db: Session, limit: int = 10) -> list[dict[str, Any]]:
    """给 Agent 提供站内讨论样本；作者信息用 joinedload 避免 N+1。"""
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


# ---------------------------------------------------------------------------
# Agent 上下文、提示词和输出清洗
# ---------------------------------------------------------------------------


def build_hot_topic_agent_context(db: Session, history_limit: int = DEFAULT_HISTORY_LIMIT) -> dict[str, Any]:
    """组装一轮生成需要的站内帖子、当前热榜和近期生成历史。"""
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


def build_hot_topic_agent_prompt(context: dict[str, Any], template: str | None = None) -> str:
    """渲染系统提示词，并兼容缺少 {context_json} 的旧自定义模板。"""
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt_template = template or DEFAULT_HOT_TOPIC_AGENT_PROMPT
    if "{context_json}" not in prompt_template:
        prompt_template = f"{prompt_template.rstrip()}\n\n当前上下文 JSON：\n{{context_json}}"
    return prompt_template.replace("{context_json}", context_json).strip()


def _extract_json_array(value: str) -> list[dict[str, Any]]:
    """从模型直出文本或 Markdown 代码块中提取 JSON 数组。"""
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
    """清洗模型提交结果，兜底执行标题、单一搜索词和摘要长度约束。"""
    topics: list[dict[str, Any]] = []
    for index, item in enumerate(raw_topics, start=1):
        title = _normalize_text(str(item.get("title") or ""))
        search_query = _normalize_search_query(
            str(item.get("search_query") or item.get("query") or title or "")
        )
        if not title or not search_query:
            continue
        topics.append({
            "title": title[:HOT_TOPIC_TITLE_MAX_LENGTH],
            "search_query": search_query,
            "summary": _normalize_summary(str(item.get("summary") or item.get("reason") or "")),
            "rank": _normalize_rank(item.get("rank"), default=index),
        })
    return topics[:10]


def apply_generated_hot_topics(
    db: Session,
    generation: HotTopicGeneration,
    topics: list[dict[str, Any]],
    publish_policy: str,
) -> list[HotTopic]:
    """把已清洗的 Agent 结果落库；auto 模式会替换旧 Agent active 项。"""
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


# ---------------------------------------------------------------------------
# LLM 工具适配层
# ---------------------------------------------------------------------------


def _search_platform_posts_for_agent(db: Session, query: str, count: int = 5) -> list[dict[str, Any]]:
    """站内搜索工具的实际查询实现，返回紧凑帖子摘要。"""
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
    """把站内搜索封装成 LangChain 工具，供 LLM 自助复核。"""
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
    """把最终提交动作做成工具，用闭包保存本轮已接受结果。"""
    from langchain_core.tools import tool

    @tool
    def submit_hot_topics(topics_json: str) -> str:
        """提交最终热榜。topics_json 必须是合法 JSON 数组字符串，每项包含 title、search_query，可选 summary、rank。"""
        try:
            topics = normalize_agent_topics(_extract_json_array(topics_json))
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("热榜 Agent 提交了非法 topics_json: %s", exc)
            return json.dumps(
                {
                    "accepted": 0,
                    "error": "invalid_topics_json",
                    "message": str(exc),
                    "hint": "请重新调用 submit_hot_topics，传入合法 JSON 数组字符串。数组项至少包含 title 和 search_query，字符串内部双引号必须转义，数组项之间必须用逗号分隔。",
                },
                ensure_ascii=False,
            )

        if not topics:
            return json.dumps(
                {
                    "accepted": 0,
                    "error": "empty_topics",
                    "message": "没有可接受的热榜条目；每项至少需要非空 title 和 search_query。",
                },
                ensure_ascii=False,
            )

        submitted["topics"] = topics
        return json.dumps({"accepted": len(submitted["topics"])}, ensure_ascii=False)

    return submit_hot_topics


def _create_web_search_tool(settings: HotTopicSettings):
    """按配置启用 Tavily 外部搜索，缺配置时返回结构化错误。"""
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
    """兼容 LangChain 标准 tool_calls 和 OpenAI function-call 结构。"""
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


# ---------------------------------------------------------------------------
# LLM 调用和生成生命周期
# ---------------------------------------------------------------------------


def _invoke_hot_topic_llm(llm: Any, system_prompt: str, user_prompt: str) -> Any:
    """每轮重新发送 system/user，让工具结果沉淀在新的 user 文本里。"""
    # 不把上一轮 AIMessage/ToolMessage 作为消息历史回传，避免部分 thinking 模型要求
    # reasoning_content 必须随历史消息一起回传。
    return llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])


def _create_generation_record(db: Session, publish_policy: str) -> HotTopicGeneration:
    """先写 pending 记录，确保后续失败也有可审计的 generation_id。"""
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
    """失败路径单独提交，避免被前一个异常后的事务状态吞掉。"""
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
    """执行一轮热榜 Agent：建上下文、跑工具循环、落库或记录失败。"""
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
                "热榜 Agent 开始运行 force=%s enabled=%s publish_policy=%s history_limit=%s max_llm_rounds=%s web_search=%s model=%s base_url_configured=%s",
                force,
                settings.agent_enabled,
                publish_policy,
                settings.history_limit,
                settings.max_llm_rounds or DEFAULT_MAX_LLM_ROUNDS,
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
            history_limit = DEFAULT_HISTORY_LIMIT if settings.history_limit is None else settings.history_limit
            context = build_hot_topic_agent_context(db, history_limit)
            prompt = build_hot_topic_agent_prompt(context, settings.prompt_template)
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
            max_rounds = max(1, min(settings.max_llm_rounds or DEFAULT_MAX_LLM_ROUNDS, 20))
            for round_index in range(1, max_rounds + 1):
                remaining_rounds = max_rounds - round_index
                if remaining_rounds == 0:
                    round_instruction = "这是最后一轮 LLM 决策，请立即通过 submit_hot_topics 提交最终热榜。"
                else:
                    round_instruction = (
                        f"本次最多还有 {remaining_rounds} 轮后续 LLM 决策机会；"
                        "必要时调用工具，但请在信息足够时尽早通过 submit_hot_topics 提交最终热榜。"
                    )
                user_prompt = (
                    f"请生成本轮热榜。{round_instruction}\n"
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
                    if submitted["topics"]:
                        break
                    try:
                        direct_topics = normalize_agent_topics(_extract_json_array(str(response.content)))
                    except (json.JSONDecodeError, ValueError) as exc:
                        observations.append(
                            "模型直接输出不是合法热榜 JSON："
                            f"{exc}。请改为调用 submit_hot_topics 工具提交合法 JSON 数组字符串。"
                        )
                        continue
                    if not direct_topics:
                        observations.append(
                            "模型直接输出没有有效热榜条目；请调用 submit_hot_topics，"
                            "每项至少包含非空 title 和 search_query。"
                        )
                        continue
                    submitted["topics"] = direct_topics
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
                        try:
                            content = str(tool_map[tool_name].invoke(tool_args))
                        except Exception as exc:
                            logger.exception(
                                "热榜 Agent 工具调用异常 generation_id=%s round=%s tool=%s",
                                generation.id,
                                round_index,
                                tool_name,
                            )
                            content = json.dumps(
                                {
                                    "error": "tool_execution_error",
                                    "message": str(exc),
                                    "hint": "请根据错误修正工具参数后重新调用。",
                                },
                                ensure_ascii=False,
                            )
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


# ---------------------------------------------------------------------------
# APScheduler 集成
# ---------------------------------------------------------------------------


def run_scheduled_hot_topic_agent() -> None:
    """调度入口负责自己的数据库会话，避免复用请求上下文。"""
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
    """在应用启动时保存 scheduler 实例，并立即按配置同步任务。"""
    global _scheduler
    _scheduler = scheduler
    configure_hot_topic_agent_job()


def configure_hot_topic_agent_job(scheduler=None) -> None:
    """根据当前设置重建 interval job，保证禁用和间隔修改立即生效。"""
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
