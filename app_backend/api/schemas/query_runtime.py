from __future__ import annotations

from pydantic import BaseModel


class QueryRuntimeModeResponse(BaseModel):
    mode_type: str
    enabled: bool
    eligible_account_count: int
    active_account_count: int
    in_window: bool
    next_window_start: str | None
    next_window_end: str | None
    query_count: int
    found_count: int
    last_error: str | None


class QueryRuntimeRecentEventResponse(BaseModel):
    class ProductResponse(BaseModel):
        productId: str
        price: float
        actRebateAmount: float

    timestamp: str
    level: str
    mode_type: str
    account_id: str
    account_display_name: str | None
    query_item_id: str
    query_item_name: str | None
    message: str
    match_count: int
    product_list: list[ProductResponse]
    total_price: float | None
    total_wear_sum: float | None
    latency_ms: float | None
    error: str | None


class QueryRuntimeGroupRowResponse(BaseModel):
    account_id: str
    account_display_name: str
    mode_type: str
    active: bool
    in_window: bool
    cooldown_until: str | None
    last_query_at: str | None
    last_success_at: str | None
    query_count: int
    found_count: int
    disabled_reason: str | None
    last_error: str | None
    rate_limit_increment: float


class QueryRuntimeItemModeResponse(BaseModel):
    mode_type: str
    target_dedicated_count: int
    actual_dedicated_count: int
    status: str
    status_message: str


class QueryRuntimeItemRowResponse(BaseModel):
    query_item_id: str
    item_name: str | None
    max_price: float | None
    min_wear: float | None
    max_wear: float | None
    detail_min_wear: float | None
    detail_max_wear: float | None
    manual_paused: bool
    query_count: int
    modes: dict[str, QueryRuntimeItemModeResponse]


class QueryRuntimeStatusResponse(BaseModel):
    running: bool
    config_id: str | None
    config_name: str | None
    message: str
    account_count: int
    started_at: str | None
    stopped_at: str | None
    total_query_count: int
    total_found_count: int
    modes: dict[str, QueryRuntimeModeResponse]
    group_rows: list[QueryRuntimeGroupRowResponse]
    recent_events: list[QueryRuntimeRecentEventResponse]
    item_rows: list[QueryRuntimeItemRowResponse]


class QueryRuntimeStartRequest(BaseModel):
    config_id: str


class QueryRuntimePrepareItemResponse(BaseModel):
    query_item_id: str
    external_item_id: str
    item_name: str | None
    status: str
    message: str
    last_market_price: float | None
    min_wear: float | None
    max_wear: float | None
    last_detail_sync_at: str | None


class QueryRuntimePrepareResponse(BaseModel):
    config_id: str
    config_name: str
    threshold_hours: int
    updated_count: int
    skipped_count: int
    failed_count: int
    items: list[QueryRuntimePrepareItemResponse]


class QueryRuntimePrepareRequest(BaseModel):
    config_id: str
    force_refresh: bool = False
