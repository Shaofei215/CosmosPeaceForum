from sqlalchemy.orm import Session

from app_platform.app.models.theme import PlatformThemeSettings
from app_platform.app.schemas.theme import ThemeSettingsUpdate


THEME_SETTINGS_ID = 1


def get_theme_settings(db: Session) -> PlatformThemeSettings:
    settings = db.get(PlatformThemeSettings, THEME_SETTINGS_ID)
    if settings is not None:
        return settings

    settings = PlatformThemeSettings(id=THEME_SETTINGS_ID)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def update_theme_settings(db: Session, payload: ThemeSettingsUpdate) -> PlatformThemeSettings:
    settings = get_theme_settings(db)
    for field, value in payload.model_dump().items():
        setattr(settings, field, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings
