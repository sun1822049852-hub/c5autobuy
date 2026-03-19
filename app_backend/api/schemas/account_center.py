from __future__ import annotations

from pydantic import BaseModel


class AccountCenterAccountResponse(BaseModel):
    account_id: str
    display_name: str
    remark_name: str | None = None
    c5_nick_name: str | None = None
    default_name: str
    api_key_present: bool
    api_key: str | None = None
    proxy_mode: str
    proxy_url: str | None = None
    proxy_display: str
    purchase_capability_state: str
    purchase_pool_state: str
    disabled: bool
    selected_steam_id: str | None = None
    selected_warehouse_text: str | None = None
    purchase_status_code: str
    purchase_status_text: str


class AccountPurchaseConfigUpdateRequest(BaseModel):
    disabled: bool
    selected_steam_id: str | None = None
