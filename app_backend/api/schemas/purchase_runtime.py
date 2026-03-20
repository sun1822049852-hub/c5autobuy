from __future__ import annotations

from pydantic import BaseModel

class PurchaseRuntimeRecentEventResponse(BaseModel):
    class ProductResponse(BaseModel):
        productId: str
        price: float
        actRebateAmount: float

    occurred_at: str
    status: str
    message: str
    query_item_name: str
    product_list: list[ProductResponse]
    total_price: float | None
    total_wear_sum: float | None
    source_mode_type: str


class PurchaseRuntimeAccountResponse(BaseModel):
    account_id: str
    display_name: str | None = None
    purchase_capability_state: str | None = None
    purchase_pool_state: str | None = None
    purchase_disabled: bool = False
    selected_steam_id: str | None = None
    selected_inventory_remaining_capacity: int | None = None
    selected_inventory_max: int | None = None
    last_error: str | None = None
    total_purchased_count: int | None = None
    submitted_product_count: int = 0
    purchase_success_count: int = 0
    purchase_failed_count: int = 0


class PurchaseRuntimeActiveQueryConfigResponse(BaseModel):
    config_id: str
    config_name: str | None = None
    state: str
    message: str


class PurchaseRuntimeItemRowResponse(BaseModel):
    query_item_id: str
    item_name: str | None = None
    max_price: float | None = None
    min_wear: float | None = None
    max_wear: float | None = None
    detail_min_wear: float | None = None
    detail_max_wear: float | None = None
    query_execution_count: int = 0
    matched_product_count: int = 0
    purchase_success_count: int = 0
    purchase_failed_count: int = 0


class PurchaseRuntimeInventoryDetailResponse(BaseModel):
    class InventoryResponse(BaseModel):
        steamId: str
        nickname: str | None = None
        inventory_num: int
        inventory_max: int
        remaining_capacity: int
        is_selected: bool
        is_available: bool

    account_id: str
    display_name: str
    selected_steam_id: str | None
    refreshed_at: str | None
    last_error: str | None
    auto_refresh_due_at: str | None = None
    auto_refresh_remaining_seconds: int | None = None
    inventories: list[InventoryResponse]


class PurchaseRuntimeStatusResponse(BaseModel):
    running: bool
    message: str
    started_at: str | None
    stopped_at: str | None
    queue_size: int
    active_account_count: int
    total_account_count: int
    total_purchased_count: int
    runtime_session_id: str | None = None
    active_query_config: PurchaseRuntimeActiveQueryConfigResponse | None = None
    matched_product_count: int = 0
    purchase_success_count: int = 0
    purchase_failed_count: int = 0
    recent_events: list[PurchaseRuntimeRecentEventResponse]
    accounts: list[PurchaseRuntimeAccountResponse]
    item_rows: list[PurchaseRuntimeItemRowResponse] = []
