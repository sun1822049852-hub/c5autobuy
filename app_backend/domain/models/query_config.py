from __future__ import annotations

from dataclasses import dataclass, field

from app_backend.domain.enums.query_modes import QueryMode


@dataclass(slots=True)
class QueryProduct:
    external_item_id: str
    product_url: str
    item_name: str | None
    market_hash_name: str | None
    min_wear: float | None
    max_wear: float | None
    last_market_price: float | None
    last_detail_sync_at: str | None
    created_at: str
    updated_at: str


@dataclass(slots=True)
class QueryItemModeAllocation:
    mode_type: str
    target_dedicated_count: int


def _default_mode_allocations() -> list[QueryItemModeAllocation]:
    return [
        QueryItemModeAllocation(mode_type=mode_type, target_dedicated_count=0)
        for mode_type in QueryMode.ALL
    ]


@dataclass(slots=True)
class QueryItem:
    query_item_id: str
    config_id: str
    product_url: str
    external_item_id: str
    item_name: str | None
    market_hash_name: str | None
    min_wear: float | None
    max_wear: float | None
    max_price: float | None
    last_market_price: float | None
    last_detail_sync_at: str | None
    sort_order: int
    created_at: str
    updated_at: str
    detail_min_wear: float | None = None
    detail_max_wear: float | None = None
    manual_paused: bool = False
    mode_allocations: list[QueryItemModeAllocation] = field(default_factory=_default_mode_allocations)

    @property
    def configured_min_wear(self) -> float | None:
        return self.detail_min_wear

    @property
    def configured_max_wear(self) -> float | None:
        return self.detail_max_wear

    def require_configured_wear_range(self) -> tuple[float, float]:
        if self.detail_min_wear is None or self.detail_max_wear is None:
            raise ValueError("查询配置缺少最终磨损范围")
        return float(self.detail_min_wear), float(self.detail_max_wear)


@dataclass(slots=True)
class QueryModeSetting:
    mode_setting_id: str
    config_id: str
    mode_type: str
    enabled: bool
    window_enabled: bool
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    base_cooldown_min: float
    base_cooldown_max: float
    random_delay_enabled: bool
    random_delay_min: float
    random_delay_max: float
    created_at: str
    updated_at: str


@dataclass(slots=True)
class QueryConfig:
    config_id: str
    name: str
    description: str | None
    enabled: bool
    created_at: str
    updated_at: str
    items: list[QueryItem] = field(default_factory=list)
    mode_settings: list[QueryModeSetting] = field(default_factory=list)
