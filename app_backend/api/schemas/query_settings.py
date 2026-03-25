from __future__ import annotations

from pydantic import BaseModel, Field


class QuerySettingsModeResponse(BaseModel):
    mode_type: str
    enabled: bool
    window_enabled: bool
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    base_cooldown_min: float
    base_cooldown_max: float
    item_min_cooldown_seconds: float
    item_min_cooldown_strategy: str
    random_delay_enabled: bool
    random_delay_min: float
    random_delay_max: float
    created_at: str
    updated_at: str


class QuerySettingsResponse(BaseModel):
    modes: list[QuerySettingsModeResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class QuerySettingsModeUpdateRequest(BaseModel):
    mode_type: str
    enabled: bool
    window_enabled: bool
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    base_cooldown_min: float
    base_cooldown_max: float
    item_min_cooldown_seconds: float = 0.5
    item_min_cooldown_strategy: str = "divide_by_assigned_count"
    random_delay_enabled: bool
    random_delay_min: float
    random_delay_max: float


class QuerySettingsUpdateRequest(BaseModel):
    modes: list[QuerySettingsModeUpdateRequest]
