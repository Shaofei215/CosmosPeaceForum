import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    HotTopicCreateRequest,
    HotTopicGenerationResponse,
    HotTopicGenerationRunResponse,
    HotTopicResponse,
    HotTopicSettingsResponse,
    HotTopicSettingsUpdateRequest,
    HotTopicUpdateRequest,
    PaginatedResponse,
)
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_CONTENT
from social_platform.app.api.deps import get_db
from social_platform.app.services import hot_topic_service

router = APIRouter(prefix="/hot-topics", tags=["platform-admin-hot-topics"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=PaginatedResponse[HotTopicResponse])
async def list_hot_topics(
    status_filter: str | None = Query(default=None, alias="status"),
    source: str | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
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
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        return hot_topic_service.create_hot_topic(db, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/items/{topic_id}", response_model=HotTopicResponse)
async def update_hot_topic(
    topic_id: int,
    request: HotTopicUpdateRequest,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        return hot_topic_service.update_hot_topic(
            db,
            topic_id=topic_id,
            payload=request.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/items/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hot_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        hot_topic_service.delete_hot_topic(db, topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.post("/items/{topic_id}/publish", response_model=HotTopicResponse)
async def publish_hot_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        return hot_topic_service.publish_hot_topic(db, topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/items/{topic_id}/archive", response_model=HotTopicResponse)
async def archive_hot_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        return hot_topic_service.archive_hot_topic(db, topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/settings", response_model=HotTopicSettingsResponse)
async def get_settings(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    settings = hot_topic_service.get_hot_topic_settings(db)
    return hot_topic_service.serialize_settings(settings)


@router.put("/settings", response_model=HotTopicSettingsResponse)
async def update_settings(
    request: HotTopicSettingsUpdateRequest,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        settings = hot_topic_service.update_hot_topic_settings(
            db,
            request.model_dump(exclude_unset=True),
        )
        return hot_topic_service.serialize_settings(settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/generations", response_model=PaginatedResponse[HotTopicGenerationResponse])
async def list_generations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    items, total = hot_topic_service.list_generations(db, skip=skip, limit=limit)
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.post("/generate", response_model=HotTopicGenerationRunResponse)
def generate_hot_topics(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        logger.info("收到立即生成热榜请求")
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
        return {"generation": generation, "topics": topics}
    except hot_topic_service.HotTopicAgentRunError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("立即生成热榜失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="热榜生成失败，请检查后端日志",
        ) from exc


@router.post("/generations/{generation_id}/publish", response_model=list[HotTopicResponse])
async def publish_generation(
    generation_id: int,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        return hot_topic_service.publish_generation(db, generation_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
