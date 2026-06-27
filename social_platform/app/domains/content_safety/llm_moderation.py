"""内容安全领域的被举报内容 LLM 自动审核用例。"""

import json
import logging
from datetime import datetime
from social_platform.app.core.timezone import local_now
from typing import Any, Callable, Literal, Optional

from sqlalchemy.orm import Session, joinedload

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.services import auth_service, log_service
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_CONTENT, PERMISSION_MANAGE_USERS
from social_platform.app.core.branding import get_platform_display_name
from social_platform.app.db.session import SessionLocal
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.content_safety import admin_application as moderation_service
from social_platform.app.domains.content_safety.models import ContentModerationLLMSettings
from social_platform.app.domains.content_safety.models import ContentReport, ContentReportEscalation
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User

logger = logging.getLogger(__name__)

SECRET_MASK = "********"
CONTENT_MODERATION_LLM_PROMPT_KEY = "content_moderation_llm_prompt"
CONTENT_MODERATION_LLM_PROMPT_NAME = "被举报内容 LLM 审查提示词"
CONTENT_MODERATION_LLM_PROMPT_DESCRIPTION = "用于指导 LLM 对举报内容做放行、删除、局部资料控制或留给人工审查的判断。"
CONTENT_MODERATION_LLM_TIMEOUT_SECONDS = 60
CONTENT_MODERATION_LLM_MAX_RETRIES = 1
LLM_MODERATOR_USERNAME = "llm_moderator"

DEFAULT_CONTENT_MODERATION_LLM_PROMPT = f"""你是 {get_platform_display_name()} 的内容安全审查员。你每次只审查一条被举报内容或用户账号，不保留任何历史对话，也不得参考上下文以外的信息。

审查目标：
- 判断被举报内容是否应继续展示，以及用户资料应局部控制还是账号封禁。
- 只根据提供的 JSON 上下文判断；不要编造未提供的事实。
- 对评论进行判断时，应同时参考所属帖子和父评论，区分引用、反驳、玩笑、上下文承接和真实违规表达。
- 对用户进行判断时，应同时参考用户资料、举报原因和最近内容，优先只控制违规的用户名或签名。
- 通常仅在多项、持续或跨类别违规时封禁账号；极严重单项违规可以直接封禁账号。
- 对存在明显违法犯罪、色情低俗、暴力威胁、仇恨歧视、人身攻击、诈骗广告、恶意刷屏、隐私泄露或平台规则显著不允许的内容，应删除。
- 对表达正常观点、事实讨论、轻微争执、可解释的讽刺或证据不足的内容，不要轻易删除。
- 如果内容存在争议、语义不清、需要人工结合更多背景判断，输出 drop。

你只能输出以下五种格式之一，不能输出解释、Markdown、JSON 或多余文字：
1. pass
2. delete {{处理原因}}
3. drop
4. control_username {{处理原因}}
5. control_bio {{处理原因}}

输出约束：
- pass 表示通过，放行内容。
- delete 后必须跟一段简短中文处理原因；内容举报会归档内容，用户举报会封禁账号并撤下全部资料。
- control_username 和 control_bio 仅用于用户举报，分别撤下用户名或签名并累计对应违规。
- drop 表示放弃自动判断，保留在人工待审队列。

待审上下文 JSON：
{{context_json}}"""

Decision = Literal["pass", "delete", "drop", "control_username", "control_bio"]


def _now() -> datetime:
    """返回当前系统本地时间，便于统一写入更新时间。"""

    return local_now()


def _normalize_text(value: str | None) -> str | None:
    """清理可选文本字段，空字符串按 ``None`` 处理。"""

    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _mask_secret(value: str | None) -> str | None:
    """对外序列化密钥字段时返回固定掩码。"""

    return SECRET_MASK if value else None


def get_content_moderation_llm_settings(db: Session) -> ContentModerationLLMSettings:
    """读取或创建被举报内容 LLM 审核单例配置。"""

    settings = db.query(ContentModerationLLMSettings).filter(ContentModerationLLMSettings.id == 1).first()
    if settings:
        return settings
    settings = ContentModerationLLMSettings(id=1)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def serialize_settings(settings: ContentModerationLLMSettings) -> dict[str, Any]:
    """序列化 LLM 审核配置并隐藏 API Key。"""

    return {
        "id": settings.id,
        "enabled": settings.enabled,
        "llm_base_url": settings.llm_base_url,
        "llm_model_name": settings.llm_model_name,
        "llm_api_key": _mask_secret(settings.llm_api_key),
        "updated_at": settings.updated_at,
    }


def update_content_moderation_llm_settings(db: Session, payload: dict[str, Any]) -> ContentModerationLLMSettings:
    """应用管理端提交的 LLM 审核配置局部更新。"""

    settings = get_content_moderation_llm_settings(db)
    string_fields = {"llm_base_url", "llm_model_name", "llm_api_key"}
    for field, value in payload.items():
        if value is None:
            continue
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
    return settings


def serialize_prompt_config(settings: ContentModerationLLMSettings) -> dict[str, Any]:
    """序列化当前提示词、默认提示词和元信息。"""

    value = settings.prompt_template or DEFAULT_CONTENT_MODERATION_LLM_PROMPT
    return {
        "key": CONTENT_MODERATION_LLM_PROMPT_KEY,
        "name": CONTENT_MODERATION_LLM_PROMPT_NAME,
        "description": CONTENT_MODERATION_LLM_PROMPT_DESCRIPTION,
        "value": value,
        "default_value": DEFAULT_CONTENT_MODERATION_LLM_PROMPT,
        "updated_at": settings.updated_at,
    }


def update_prompt_template(db: Session, value: str) -> ContentModerationLLMSettings:
    """保存自定义 LLM 审核提示词模板。"""

    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("提示词模板不能为空")
    settings = get_content_moderation_llm_settings(db)
    settings.prompt_template = normalized
    settings.updated_at = _now()
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def reset_prompt_template(db: Session) -> ContentModerationLLMSettings:
    """恢复 LLM 审核默认提示词模板。"""

    settings = get_content_moderation_llm_settings(db)
    settings.prompt_template = DEFAULT_CONTENT_MODERATION_LLM_PROMPT
    settings.updated_at = _now()
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def build_prompt(context: dict[str, Any], template: str | None = None) -> str:
    """把举报上下文渲染进审核提示词。"""

    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = (template or DEFAULT_CONTENT_MODERATION_LLM_PROMPT).strip()
    if "{context_json}" in prompt:
        return prompt.replace("{context_json}", context_json)
    return f"{prompt}\n\n待审上下文 JSON：\n{context_json}"


def parse_llm_decision(raw_output: str) -> tuple[Decision, str | None]:
    """解析模型输出为审核决策和可选删除原因。"""

    first_line = (raw_output or "").strip().splitlines()[0].strip() if (raw_output or "").strip() else ""
    lowered = first_line.lower()
    if lowered == "pass":
        return "pass", None
    if lowered == "drop":
        return "drop", None
    if lowered.startswith("delete"):
        reason = first_line[len("delete"):].strip()
        if reason.startswith(":") or reason.startswith("："):
            reason = reason[1:].strip()
        return "delete", reason or "LLM 审查判定内容违反社区规则"
    for action in ("control_username", "control_bio"):
        if lowered.startswith(action):
            reason = first_line[len(action):].strip()
            if reason.startswith(":") or reason.startswith("："):
                reason = reason[1:].strip()
            return action, reason or "LLM 审查判定用户资料违反社区规则"
    return "drop", None


def review_report(
    db: Session,
    report_id: int,
    llm_factory: Optional[Callable[[ContentModerationLLMSettings], Any]] = None,
) -> tuple[Decision, str | None]:
    """执行单条待审举报的 LLM 自动审核流程。"""

    settings = get_content_moderation_llm_settings(db)
    if not settings.enabled:
        return "drop", "LLM 审查未启用"

    report = _get_pending_report(db, report_id)
    if report is None:
        return "drop", "待审举报不存在"

    context = build_report_context(db, report)
    prompt = build_prompt(context, settings.prompt_template)
    if llm_factory is None:
        if not settings.llm_model_name or not settings.llm_api_key:
            raise ValueError("请先配置被举报内容 LLM 审查的模型名称和 API Key")
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": settings.llm_model_name,
            "api_key": settings.llm_api_key,
            "temperature": 0,
            "timeout": CONTENT_MODERATION_LLM_TIMEOUT_SECONDS,
            "max_retries": CONTENT_MODERATION_LLM_MAX_RETRIES,
        }
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        llm = ChatOpenAI(**kwargs)
    else:
        llm = llm_factory(settings)

    response = llm.invoke([
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": "请审查并只输出 pass、delete {原因}、drop、control_username {原因} 或 control_bio {原因}。",
        },
    ])
    decision, reason = parse_llm_decision(str(getattr(response, "content", response)))
    apply_llm_decision(db, report, decision, reason)
    return decision, reason


def review_report_in_background(report_id: int) -> None:
    """在后台任务中使用独立数据库会话审核举报。"""

    db = SessionLocal()
    try:
        review_report(db, report_id)
    except Exception as exc:
        db.rollback()
        logger.exception("被举报内容 LLM 审查失败 report_id=%s", report_id)
        _log_llm_failure(db, report_id, exc)
    finally:
        db.close()


def apply_llm_decision(
    db: Session,
    report: ContentReport,
    decision: Decision,
    reason: str | None,
) -> None:
    """把 LLM 决策应用到被举报内容。"""

    admin = get_or_create_llm_moderator_admin(db)
    content_type = report.target_type
    if content_type == "post":
        content_id = report.post_id
    elif content_type == "comment":
        content_id = report.comment_id
    else:
        content_id = report.user_id
    if content_id is None:
        return

    if decision == "pass":
        if content_type == "user":
            moderation_service.release_reported_user(db, content_id, admin)
        else:
            moderation_service.release_reported_content(db, content_type, content_id, admin)
        return
    if decision == "delete":
        if content_type == "user":
            moderation_service.ban_reported_user_as_admin(
                db,
                user_id=content_id,
                admin=admin,
                reason=reason,
                notify_user=True,
            )
        elif content_type == "comment":
            moderation_service.delete_reported_comment_as_admin(
                db,
                comment_id=content_id,
                admin=admin,
                reason=reason,
                notify_author=True,
            )
        else:
            moderation_service.delete_reported_post_as_admin(
                db,
                post_id=content_id,
                admin=admin,
                reason=reason,
                notify_author=True,
            )
        return

    if decision in {"control_username", "control_bio"}:
        if content_type != "user":
            decision = "drop"
        else:
            from social_platform.app.admin.schemas import UserViolationRequest

            moderation_service.moderate_reported_user_as_admin(
                db,
                user_id=content_id,
                request=UserViolationRequest(
                    category="username" if decision == "control_username" else "bio",
                    reason=reason,
                ),
                admin=admin,
            )
            return

    log_service.create_operation_log(
        db,
        admin,
        action="content_moderation_llm_drop",
        target_type=content_type,
        target_id=content_id,
        details={"report_id": report.id, "reason": reason or "模型放弃自动决策"},
    )
    db.commit()


def build_report_context(db: Session, report: ContentReport) -> dict[str, Any]:
    """构建单条举报的 LLM 审核上下文。"""

    target_type = report.target_type
    if target_type == "post":
        content_id = report.post_id
    elif target_type == "comment":
        content_id = report.comment_id
    else:
        content_id = report.user_id
    reports = _pending_reports_for_same_target(db, target_type, content_id)
    context: dict[str, Any] = {
        "report": {
            "id": report.id,
            "target_type": target_type,
            "target_id": content_id,
            "reason": report.reason,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        },
        "all_pending_report_reasons": [
            {
                "report_id": item.id,
                "reason": item.reason,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in reports
        ],
    }

    if target_type == "post":
        post = db.query(Post).options(joinedload(Post.author)).filter(Post.id == report.post_id).first()
        context["target_post"] = _post_payload(post) if post else None
        return context

    if target_type == "user":
        user = db.query(User).filter(User.id == report.user_id).first()
        context["target_user"] = _user_payload(user)
        context.update(_recent_user_content_payloads(db, report.user_id))
        context["triggering_reported_contents"] = _triggering_reported_content_payloads(
            db,
            report.user_id,
        )
        return context

    comment = db.query(Comment).options(joinedload(Comment.owner)).filter(Comment.id == report.comment_id).first()
    post = db.query(Post).options(joinedload(Post.author)).filter(Post.id == comment.post_id).first() if comment else None
    parent = None
    if comment and comment.parent_id:
        parent = db.query(Comment).options(joinedload(Comment.owner)).filter(Comment.id == comment.parent_id).first()
    context["target_comment"] = _comment_payload(comment) if comment else None
    context["parent_comment"] = _comment_payload(parent) if parent else None
    context["post"] = _post_payload(post) if post else None
    return context


def get_or_create_llm_moderator_admin(db: Session) -> PlatformAdminUser:
    """读取或创建代表自动审核系统的禁用管理员账号。"""

    admin = auth_service.get_admin_by_username(db, LLM_MODERATOR_USERNAME)
    if admin:
        return admin
    admin = PlatformAdminUser(
        username=LLM_MODERATOR_USERNAME,
        email=None,
        password_hash="system-managed",
        permissions=auth_service.dump_permissions([PERMISSION_MANAGE_CONTENT, PERMISSION_MANAGE_USERS]),
        is_active=False,
        is_super_admin=False,
        must_change_credentials=False,
    )
    db.add(admin)
    db.flush()
    return admin


def _get_pending_report(db: Session, report_id: int) -> ContentReport | None:
    """读取指定待审举报。"""

    return db.query(ContentReport).filter(
        ContentReport.id == report_id,
        ContentReport.status == "pending",
    ).first()


def _pending_reports_for_same_target(
    db: Session,
    target_type: str,
    content_id: int | None,
) -> list[ContentReport]:
    """读取同一目标内容下的全部待审举报。"""

    if content_id is None:
        return []
    query = db.query(ContentReport).filter(
        ContentReport.status == "pending",
        ContentReport.target_type == target_type,
    )
    if target_type == "post":
        query = query.filter(ContentReport.post_id == content_id)
    elif target_type == "comment":
        query = query.filter(ContentReport.comment_id == content_id)
    else:
        query = query.filter(ContentReport.user_id == content_id)
    return query.order_by(ContentReport.created_at.asc(), ContentReport.id.asc()).all()


def _user_payload(user: User | None) -> dict[str, Any] | None:
    """把用户资料压缩为 LLM 审核上下文中的 JSON 片段。"""

    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "bio": user.bio,
        "is_ai_agent": user.is_ai_agent,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "followers_count": user.followers_count,
        "following_count": user.following_count,
    }


def _recent_user_content_payloads(db: Session, user_id: int | None) -> dict[str, list[dict[str, Any]]]:
    """读取被举报用户最近 5 条帖子和 5 条评论作为账号审查上下文。"""

    if user_id is None:
        return {"recent_posts": [], "recent_comments": []}
    posts = db.query(Post).filter(
        Post.author_id == user_id,
        Post.moderation_status == "active",
    ).order_by(Post.created_at.desc()).limit(5).all()
    comments = db.query(Comment).filter(
        Comment.owner_id == user_id,
        Comment.moderation_status == "active",
    ).order_by(Comment.created_at.desc()).limit(5).all()
    return {
        "recent_posts": [
            {
                "type": "post",
                "id": post.id,
                "title": post.title,
                "content": post.content,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "like_count": post.like_count,
                "comment_count": post.comment_count,
            }
            for post in posts
        ],
        "recent_comments": [
            {
                "type": "comment",
                "id": comment.id,
                "post_id": comment.post_id,
                "content": comment.content,
                "created_at": comment.created_at.isoformat() if comment.created_at else None,
                "like_count": comment.like_count,
                "reply_count": comment.reply_count,
            }
            for comment in comments
        ],
    }


def _triggering_reported_content_payloads(db: Session, user_id: int | None) -> list[dict[str, Any]]:
    """读取待审用户升级批次中的 5 条触发内容。"""

    if user_id is None:
        return []
    escalation = db.query(ContentReportEscalation).filter(
        ContentReportEscalation.user_id == user_id,
        ContentReportEscalation.status == "pending",
    ).order_by(ContentReportEscalation.created_at.desc()).first()
    if escalation is None:
        return []
    try:
        payload = json.loads(escalation.trigger_content_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)][:5]


def _post_payload(post: Post | None) -> dict[str, Any] | None:
    """把帖子压缩为 LLM 审核上下文中的 JSON 片段。"""

    if post is None:
        return None
    return {
        "id": post.id,
        "type": post.type,
        "author_id": post.author_id,
        "author_username": post.author.username if post.author else None,
        "title": post.title,
        "content": post.content,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
    }


def _comment_payload(comment: Comment | None) -> dict[str, Any] | None:
    """把评论压缩为 LLM 审核上下文中的 JSON 片段。"""

    if comment is None:
        return None
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "parent_id": comment.parent_id,
        "root_comment_id": comment.root_comment_id,
        "author_id": comment.owner_id,
        "author_username": comment.owner.username if comment.owner else None,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "like_count": comment.like_count,
        "reply_count": comment.reply_count,
    }


def _log_llm_failure(db: Session, report_id: int, exc: BaseException) -> None:
    """记录 LLM 审核失败的管理员操作日志。"""

    try:
        admin = get_or_create_llm_moderator_admin(db)
        log_service.create_operation_log(
            db,
            admin,
            action="content_moderation_llm_failed",
            target_type="content_report",
            target_id=report_id,
            details={"error": str(exc)},
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("被举报内容 LLM 审查失败日志写入失败 report_id=%s", report_id)
