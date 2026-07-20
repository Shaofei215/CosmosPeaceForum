import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    HotTopicCreateRequest,
    HotTopicGenerationResponse,
    HotTopicGenerationRunResponse,
    HotTopicPromptConfigResponse,
    HotTopicPromptConfigUpdateRequest,
    HotTopicResponse,
    HotTopicSettingsResponse,
    HotTopicSettingsUpdateRequest,
    HotTopicUpdateRequest,
    PaginatedResponse,
)
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_HOT_TOPICS
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.api.deps import get_db
from social_platform.app.db.session import SessionLocal
from social_platform.app.domains.hot_topic import application as hot_topic_service
from social_platform.app.shared.external_errors import format_external_error

router = APIRouter(prefix="/hot-topics", tags=["platform-admin-hot-topics"])
logger = logging.getLogger(__name__)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _serialize_generation_run(generation, topics) -> dict:
    return {
        "generation": HotTopicGenerationResponse.model_validate(generation).model_dump(mode="json"),
        "topics": [HotTopicResponse.model_validate(topic).model_dump(mode="json") for topic in topics],
    }


def _run_generation_for_stream(admin_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        generation, topics = hot_topic_service.run_hot_topic_agent(db, force=True)
        if generation.status != "failed" and admin_id is not None:
            admin = db.query(PlatformAdminUser).filter(PlatformAdminUser.id == admin_id).first()
            create_operation_log(
                db,
                admin,
                "generate_hot_topics",
                "hot_topic_generation",
                generation.id,
                details={"topic_count": len(topics), "stream": True},
            )
            db.commit()
        payload = _serialize_generation_run(generation, topics)
        if generation.status == "failed":
            payload["error"] = generation.error_message or "生成失败，请检查后端日志"
        return payload
    except Exception as exc:
        logger.exception("热榜 SSE 响应生成或序列化失败")
        safe_error = format_external_error(exc)
        return {"error_code": safe_error.code, "error": safe_error.message}
    finally:
        db.close()


@router.get("/", response_model=PaginatedResponse[HotTopicResponse])
async def list_hot_topics(
    status_filter: str | None = Query(default=None, alias="status"),
    source: str | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        items, total = hot_topic_service.list_admin_hot_topics(
            db,
            status=status_filter,
            source=source,
            skip=skip,
            limit=limit,
        )
        return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/", response_model=HotTopicResponse, status_code=status.HTTP_201_CREATED)
async def create_hot_topic(
    request: HotTopicCreateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        topic = hot_topic_service.create_hot_topic(db, request.model_dump())
        create_operation_log(db, current_admin, "create_hot_topic", "hot_topic", topic.id)
        db.commit()
        return topic
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/items/{topic_id}", response_model=HotTopicResponse)
async def update_hot_topic(
    topic_id: int,
    request: HotTopicUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        topic = hot_topic_service.update_hot_topic(
            db,
            topic_id=topic_id,
            payload=request.model_dump(exclude_unset=True),
        )
        create_operation_log(db, current_admin, "update_hot_topic", "hot_topic", topic_id)
        db.commit()
        return topic
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/items/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hot_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        hot_topic_service.delete_hot_topic(db, topic_id)
        create_operation_log(db, current_admin, "delete_hot_topic", "hot_topic", topic_id)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.post("/items/{topic_id}/publish", response_model=HotTopicResponse)
async def publish_hot_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        topic = hot_topic_service.publish_hot_topic(db, topic_id)
        create_operation_log(db, current_admin, "publish_hot_topic", "hot_topic", topic_id)
        db.commit()
        return topic
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/items/{topic_id}/archive", response_model=HotTopicResponse)
async def archive_hot_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        topic = hot_topic_service.archive_hot_topic(db, topic_id)
        create_operation_log(db, current_admin, "archive_hot_topic", "hot_topic", topic_id)
        db.commit()
        return topic
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/settings", response_model=HotTopicSettingsResponse)
async def get_settings(
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    settings = hot_topic_service.get_hot_topic_settings(db)
    return hot_topic_service.serialize_settings(settings)


@router.put("/settings", response_model=HotTopicSettingsResponse)
async def update_settings(
    request: HotTopicSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        settings = hot_topic_service.update_hot_topic_settings(
            db,
            request.model_dump(exclude_unset=True),
        )
        create_operation_log(db, current_admin, "update_hot_topic_settings", "hot_topic_settings")
        db.commit()
        return hot_topic_service.serialize_settings(settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/prompt", response_model=HotTopicPromptConfigResponse)
async def get_prompt_config(
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    settings = hot_topic_service.get_hot_topic_settings(db)
    return hot_topic_service.serialize_prompt_config(settings)


@router.put("/prompt", response_model=HotTopicPromptConfigResponse)
async def update_prompt_config(
    request: HotTopicPromptConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        settings = hot_topic_service.update_hot_topic_prompt_template(db, request.value)
        create_operation_log(db, current_admin, "update_hot_topic_prompt", "hot_topic_settings")
        db.commit()
        return hot_topic_service.serialize_prompt_config(settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/prompt/reset", response_model=HotTopicPromptConfigResponse)
async def reset_prompt_config(
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    settings = hot_topic_service.reset_hot_topic_prompt_template(db)
    create_operation_log(db, current_admin, "reset_hot_topic_prompt", "hot_topic_settings")
    db.commit()
    return hot_topic_service.serialize_prompt_config(settings)


@router.get("/generations", response_model=PaginatedResponse[HotTopicGenerationResponse])
async def list_generations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    items, total = hot_topic_service.list_generations(db, skip=skip, limit=limit)
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.post("/generate/events")
async def stream_generate_hot_topics(
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    """通过 Authorization Header 流式触发热门话题生成。"""

    async def event_stream():
        yield _sse_event("hot-topics.generate.started", {"status": "running"})
        payload = await asyncio.to_thread(_run_generation_for_stream, current_admin.id)
        event_name = "hot-topics.generate.failed" if payload.get("error") else "hot-topics.generate.completed"
        yield _sse_event(event_name, payload)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/generate", response_model=HotTopicGenerationRunResponse)
def generate_hot_topics(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        generation, topics = hot_topic_service.run_hot_topic_agent(db, force=True)
        if generation.status == "failed":
            logger.error(
                "立即生成热榜失败 generation_id=%s error=%s",
                generation.id,
                generation.error_message,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=generation.error_message or "热榜生成失败，请检查后端日志",
            )
        create_operation_log(
            db,
            _,
            "generate_hot_topics",
            "hot_topic_generation",
            generation.id,
            details={"topic_count": len(topics), "stream": False},
        )
        db.commit()
        return {"generation": generation, "topics": topics}
    except hot_topic_service.HotTopicAgentRunError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except HTTPException:
        # 业务失败已经转换为带安全消息的 HTTPException，避免再次记录并覆盖响应。
        raise
    except Exception as exc:
        logger.exception("立即生成失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成失败，请检查后端日志",
        ) from exc


@router.post("/generations/{generation_id}/publish", response_model=list[HotTopicResponse])
async def publish_generation(
    generation_id: int,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_HOT_TOPICS)),
):
    try:
        topics = hot_topic_service.publish_generation(db, generation_id)
        create_operation_log(
            db,
            current_admin,
            "publish_hot_topic_generation",
            "hot_topic_generation",
            generation_id,
            details={"topic_count": len(topics)},
        )
        db.commit()
        return topics
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
