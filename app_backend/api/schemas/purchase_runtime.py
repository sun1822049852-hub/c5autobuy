from __future__ import annotations

from pydantic import BaseModel


class PurchaseRuntimeSettingsResponse(BaseModel):
    whitelist_account_ids: list[str]
    updated_at: str | None


class PurchaseRuntimeSettingsUpdateRequest(BaseModel):
    whitelist_account_ids: list[str]


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
    selected_steam_id: str | None = None
    selected_inventory_remaining_capacity: int | None = None
    selected_inventory_max: int | None = None
    last_error: str | None = None
    total_purchased_count: int | None = None


class PurchaseRuntimeInventoryDetailResponse(BaseModel):
    class InventoryResponse(BaseModel):
        steamId: str
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
    recent_events: list[PurchaseRuntimeRecentEventResponse]
    accounts: list[PurchaseRuntimeAccountResponse]
    settings: PurchaseRuntimeSettingsResponse
