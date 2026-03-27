from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AccountCenterAccountResponse(BaseModel):
    account_id: str
    display_name: str
    remark_name: str | None = None
    c5_nick_name: str | None = None
    default_name: str
    api_key_present: bool
    api_query_enabled: bool
    api_query_status_code: str
    api_query_status_text: str
    api_query_disable_reason_code: str | None = None
    api_query_disable_reason_text: str | None = None
    browser_query_enabled: bool
    browser_query_status_code: str
    browser_query_status_text: str
    browser_query_disable_reason_code: str | None = None
    browser_query_disable_reason_text: str | None = None
    api_key: str | None = None
    browser_proxy_mode: str
    browser_proxy_url: str | None = None
    browser_proxy_display: str
    api_proxy_mode: str
    api_proxy_url: str | None = None
    api_proxy_display: str
    proxy_mode: str | None = None
    proxy_url: str | None = None
    proxy_display: str | None = None
    api_ip_allow_list: str | None = None
    browser_public_ip: str | None = None
    api_public_ip: str | None = None
    purchase_capability_state: str
    purchase_pool_state: str
    purchase_disabled: bool
    selected_steam_id: str | None = None
    selected_warehouse_text: str | None = None
    purchase_status_code: str
    purchase_status_text: str


class AccountPurchaseConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_disabled: bool = False
    selected_steam_id: str | None = None
