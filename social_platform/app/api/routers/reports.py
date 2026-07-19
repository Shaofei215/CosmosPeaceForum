from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from social_platform.app.admin.services.moderation_guard import ensure_action_allowed
from social_platform.app.api.deps import get_agent_operation_source, get_current_user, get_db
from social_platform.app.domains.user.models import User
from social_platform.app.domains.content_safety.schemas import ContentReportCreate, ContentReportResponse
from social_platform.app.domains.content_safety import application as report_service
from social_platform.app.domains.content_safety import llm_moderation as content_moderation_llm_service


router = APIRouter()


@router.post("", response_model=ContentReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    request: ContentReportCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    created_by_agent: bool = Depends(get_agent_operation_source),
):
    ensure_action_allowed(db, current_user, "interaction")
    try:
        report = report_service.create_content_report(
            db=db,
            reporter=current_user,
            target_type=request.target_type,
            target_id=request.target_id,
            reason=request.reason,
            created_by_agent=created_by_agent,
        )
    except report_service.ReportTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except report_service.SelfReportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    content_moderation_llm_service.logger.info(
        "被举报内容 LLM 审查已入队 report_id=%s target_type=%s",
        report.id,
        report.target_type,
    )
    background_tasks.add_task(content_moderation_llm_service.review_report_in_background, report.id)
    return ContentReportResponse(
        id=report.id,
        status=report.status,
        message="举报已提交",
        created_by_agent=report.created_by_agent,
    )
