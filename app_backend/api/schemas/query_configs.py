from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class QueryItemModeAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mode_type: str
    target_dedicated_count: int


class QueryModeSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class QueryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query_item_id: str
    config_id: str
    product_url: str
    external_item_id: str
    item_name: str | None
    market_hash_name: str | None
    min_wear: float | None
    max_wear: float | None
    detail_min_wear: float | None
    detail_max_wear: float | None
    max_price: float | None
    last_market_price: float | None
    last_detail_sync_at: str | None
    manual_paused: bool
    mode_allocations: list[QueryItemModeAllocationResponse]
    sort_order: int
    created_at: str
    updated_at: str


class QueryConfigCreateRequest(BaseModel):
    name: str
    description: str | None = None


class QueryConfigUpdateRequest(BaseModel):
    name: str
    description: str | None = None


class QueryItemCreateRequest(BaseModel):
    product_url: str
    detail_min_wear: float | None = None
    detail_max_wear: float | None = None
    max_price: float | None = None
    manual_paused: bool = False
    mode_allocations: dict[str, int] | None = None


class QueryItemUpdateRequest(BaseModel):
    detail_min_wear: float | None = None
    detail_max_wear: float | None = None
    max_price: float | None = None
    manual_paused: bool | None = None
    mode_allocations: dict[str, int] | None = None


class QueryItemRuntimeApplyResponse(BaseModel):
    status: str
    message: str
    config_id: str
    query_item_id: str


class QueryModeCapacityResponse(BaseModel):
    mode_type: str
    available_account_count: int


class QueryCapacitySummaryResponse(BaseModel):
    modes: dict[str, QueryModeCapacityResponse]


class QueryItemUrlParseRequest(BaseModel):
    product_url: str


class QueryItemUrlParseResponse(BaseModel):
    product_url: str
    external_item_id: str


class QueryItemDetailFetchRequest(BaseModel):
    product_url: str
    external_item_id: str


class QueryItemDetailFetchResponse(BaseModel):
    product_url: str
    external_item_id: str
    item_name: str | None
    market_hash_name: str | None
    min_wear: float | None
    max_wear: float | None
    last_market_price: float | None


class QueryModeSettingUpdateRequest(BaseModel):
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


class QueryConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_id: str
    name: str
    description: str | None
    enabled: bool
    created_at: str
    updated_at: str
    items: list[QueryItemResponse]
    mode_settings: list[QueryModeSettingResponse]
