from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class QuerySettingsMode:
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


@dataclass(slots=True)
class QuerySettings:
    modes: list[QuerySettingsMode] = field(default_factory=list)
    updated_at: str | None = None
