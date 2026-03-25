from __future__ import annotations

from pydantic import BaseModel


class QueryItemStatsSourceModeResponse(BaseModel):
    mode_type: str
    hit_count: int


class QueryItemStatsRowResponse(BaseModel):
    external_item_id: str
    item_name: str | None = None
    product_url: str | None = None
    query_execution_count: int = 0
    matched_product_count: int = 0
    purchase_success_count: int = 0
    purchase_failed_count: int = 0
    source_mode_stats: list[QueryItemStatsSourceModeResponse] = []
    updated_at: str | None = None


class QueryItemStatsResponse(BaseModel):
    range_mode: str
    date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    items: list[QueryItemStatsRowResponse] = []


class AccountCapabilityCellResponse(BaseModel):
    avg_latency_ms: float | None = None
    sample_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error: str | None = None
    display_text: str = "--"


class AccountCapabilityStatsRowResponse(BaseModel):
    account_id: str
    account_display_name: str | None = None
    new_api: AccountCapabilityCellResponse
    fast_api: AccountCapabilityCellResponse
    browser: AccountCapabilityCellResponse
    create_order: AccountCapabilityCellResponse
    submit_order: AccountCapabilityCellResponse


class AccountCapabilityStatsResponse(BaseModel):
    range_mode: str
    date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    items: list[AccountCapabilityStatsRowResponse] = []
