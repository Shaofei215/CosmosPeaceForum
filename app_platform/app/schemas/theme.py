from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


ColorValue = str


class ThemeSettingsBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accent_color: ColorValue = Field(default="#111827", min_length=1, max_length=120)
    accent_foreground_color: ColorValue = Field(default="#ffffff", min_length=1, max_length=120)
    subtle_color: ColorValue = Field(
        default="rgba(243, 244, 246, 0.82)", min_length=1, max_length=120
    )
    subtle_foreground_color: ColorValue = Field(default="#4b5563", min_length=1, max_length=120)

    topbar_background_mode: Literal["solid", "gradient"] = "solid"
    topbar_solid_color: ColorValue = Field(default="#ffffff", min_length=1, max_length=120)
    topbar_gradient_from: ColorValue = Field(default="#ffffff", min_length=1, max_length=120)
    topbar_gradient_to: ColorValue = Field(default="#f3f4f6", min_length=1, max_length=120)
    topbar_gradient_direction: str = Field(default="90deg", min_length=1, max_length=40)
    topbar_scrolled_background: ColorValue = Field(
        default="rgba(255, 255, 255, 0.45)", min_length=1, max_length=120
    )

    topbar_decoration_top: Optional[str] = Field(default=None, max_length=6000000)
    topbar_decoration_bottom: Optional[str] = Field(default=None, max_length=6000000)
    topbar_decoration_left: Optional[str] = Field(default=None, max_length=6000000)
    topbar_decoration_right: Optional[str] = Field(default=None, max_length=6000000)

    topbar_action_active_color: Optional[ColorValue] = Field(default=None, max_length=120)
    topbar_action_active_foreground_color: Optional[ColorValue] = Field(default=None, max_length=120)
    topbar_action_inactive_color: Optional[ColorValue] = Field(default=None, max_length=120)
    topbar_action_inactive_foreground_color: Optional[ColorValue] = Field(
        default=None, max_length=120
    )

    @field_validator(
        "accent_color",
        "accent_foreground_color",
        "subtle_color",
        "subtle_foreground_color",
        "topbar_solid_color",
        "topbar_gradient_from",
        "topbar_gradient_to",
        "topbar_gradient_direction",
        "topbar_scrolled_background",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "topbar_decoration_top",
        "topbar_decoration_bottom",
        "topbar_decoration_left",
        "topbar_decoration_right",
        "topbar_action_active_color",
        "topbar_action_active_foreground_color",
        "topbar_action_inactive_color",
        "topbar_action_inactive_foreground_color",
    )
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ThemeSettingsUpdate(ThemeSettingsBase):
    pass


class ThemeSettingsResponse(ThemeSettingsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_at: datetime
