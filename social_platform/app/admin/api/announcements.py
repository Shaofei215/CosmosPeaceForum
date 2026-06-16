from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import AdminAnnouncementRequest, AdminAnnouncementResponse
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_USERS
from social_platform.app.api.deps import get_db
from social_platform.app.domains.notification.announcement import publish_announcement

router = APIRouter(prefix="/announcements", tags=["platform-admin-announcements"])


@router.post("/", response_model=AdminAnnouncementResponse)
async def create_announcement(
    request: AdminAnnouncementRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    recipient_count = publish_announcement(db, request.content, current_admin)
    return AdminAnnouncementResponse(recipient_count=recipient_count)
