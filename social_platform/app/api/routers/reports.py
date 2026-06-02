from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from social_platform.app.api.deps import get_current_user, get_db
from social_platform.app.models.user import User
from social_platform.app.schemas.report import ContentReportCreate, ContentReportResponse
from social_platform.app.services import report_service


router = APIRouter()


@router.post("", response_model=ContentReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    request: ContentReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        report = report_service.create_content_report(
            db=db,
            reporter=current_user,
            target_type=request.target_type,
            target_id=request.target_id,
            reason=request.reason,
        )
    except report_service.ReportTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except report_service.SelfReportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ContentReportResponse(id=report.id, status=report.status, message="举报已提交")
