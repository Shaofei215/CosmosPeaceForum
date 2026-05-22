from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import DashboardStatsResponse
from social_platform.app.admin.services.moderation_service import get_dashboard_stats
from social_platform.app.admin.services.permissions import PERMISSION_VIEW_DASHBOARD
from social_platform.app.api.deps import get_db

router = APIRouter(prefix="/dashboard", tags=["platform-admin-dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def stats(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_VIEW_DASHBOARD)),
):
    return get_dashboard_stats(db)

