from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from social_platform.app.api.deps import get_db
from social_platform.app.schemas.theme import ThemeSettingsResponse
from social_platform.app.services.theme_service import get_theme_settings

router = APIRouter()


@router.get("", response_model=ThemeSettingsResponse)
def read_theme_settings(db: Session = Depends(get_db)):
    return get_theme_settings(db)
