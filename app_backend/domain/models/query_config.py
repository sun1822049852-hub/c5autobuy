from __future__ import annotations

from dataclasses import dataclass, field


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
