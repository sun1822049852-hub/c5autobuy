from __future__ import annotations

from pydantic import BaseModel


class SidebarDiagnosticsSummaryResponse(BaseModel):
    backend_online: bool
    query_running: bool
    purchase_running: bool
    active_query_config_name: str | None = None
    last_error: str | None = None
    updated_at: str


class SidebarQueryModeRowResponse(BaseModel):
    mode_type: str
    enabled: bool
    eligible_account_count: int
    active_account_count: int
    query_count: int
    found_count: int
    last_error: str | None = None


class SidebarQueryAccountRowResponse(BaseModel):
    account_id: str
    display_name: str | None = None
    mode_type: str
    active: bool
    query_count: int
    found_count: int
    last_error: str | None = None
    disabled_reason: str | None = None
    last_seen_at: str | None = None


class SidebarQueryRecentEventResponse(BaseModel):
    timestamp: str
    level: str
    mode_type: str
    account_id: str
    account_display_name: str | None = None
    query_item_id: str
    query_item_name: str | None = None
    message: str
    match_count: int
    total_price: float | None = None
    total_wear_sum: float | None = None
    latency_ms: float | None = None
    error: str | None = None
    status_code: int | None = None
    request_method: str | None = None
    request_path: str | None = None
    response_text: str | None = None


class SidebarQueryDiagnosticsResponse(BaseModel):
    running: bool
    config_id: str | None = None
    config_name: str | None = None
    message: str
    total_query_count: int
    total_found_count: int
    last_error: str | None = None
    updated_at: str
    mode_rows: list[SidebarQueryModeRowResponse]
    account_rows: list[SidebarQueryAccountRowResponse]
    recent_events: list[SidebarQueryRecentEventResponse]


class SidebarPurchaseAccountRowResponse(BaseModel):
    account_id: str
    display_name: str | None = None
    purchase_capability_state: str | None = None
    purchase_pool_state: str | None = None
    purchase_disabled: bool = False
    selected_inventory_name: str | None = None
    selected_inventory_remaining_capacity: int | None = None
    last_error: str | None = None


class SidebarPurchaseRecentEventResponse(BaseModel):
    occurred_at: str
    status: str
    message: str
    query_item_name: str
    source_mode_type: str
    total_price: float | None = None
    total_wear_sum: float | None = None
    status_code: int | None = None
    request_method: str | None = None
    request_path: str | None = None
    response_text: str | None = None


class SidebarPurchaseDiagnosticsResponse(BaseModel):
    running: bool
    message: str
    active_account_count: int
    total_purchased_count: int
    last_error: str | None = None
    updated_at: str
    account_rows: list[SidebarPurchaseAccountRowResponse]
    recent_events: list[SidebarPurchaseRecentEventResponse]


class SidebarLoginTaskEventResponse(BaseModel):
    state: str
    timestamp: str
    message: str | None = None
    payload: dict[str, object] | None = None


class SidebarLoginTaskRowResponse(BaseModel):
    task_id: str
    account_id: str | None = None
    account_display_name: str | None = None
    state: str
    started_at: str
    updated_at: str
    last_message: str | None = None
    result: dict[str, object] | None = None
    error: str | None = None
    pending_conflict: dict[str, object] | None = None
    events: list[SidebarLoginTaskEventResponse]


class SidebarLoginTasksDiagnosticsResponse(BaseModel):
    running_count: int
    conflict_count: int
    failed_count: int
    updated_at: str
    recent_tasks: list[SidebarLoginTaskRowResponse]


class SidebarDiagnosticsResponse(BaseModel):
    summary: SidebarDiagnosticsSummaryResponse
    query: SidebarQueryDiagnosticsResponse
    purchase: SidebarPurchaseDiagnosticsResponse
    login_tasks: SidebarLoginTasksDiagnosticsResponse
    updated_at: str
