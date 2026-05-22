from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_ADMINS
from social_platform.app.api.deps import get_db
from social_platform.app.schemas.theme import ThemeSettingsResponse, ThemeSettingsUpdate
from social_platform.app.services.theme_service import get_theme_settings, update_theme_settings

router = APIRouter(prefix="/theme", tags=["platform-admin-theme"])


@router.get("", response_model=ThemeSettingsResponse)
def read_admin_theme_settings(
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    return get_theme_settings(db)


@router.put("", response_model=ThemeSettingsResponse)
def update_admin_theme_settings(
    request: ThemeSettingsUpdate,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    settings = update_theme_settings(db, request)
    create_operation_log(
        db,
        current_admin,
        action="update_theme_settings",
        target_type="theme",
        target_id=settings.id,
    )
    db.commit()
    return settings
