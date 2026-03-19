from __future__ import annotations

from pydantic import BaseModel, model_validator


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
    purchase_disabled: bool
    selected_steam_id: str | None = None
    selected_warehouse_text: str | None = None
    purchase_status_code: str
    purchase_status_text: str


class AccountPurchaseConfigUpdateRequest(BaseModel):
    purchase_disabled: bool = False
    disabled: bool | None = None
    selected_steam_id: str | None = None

    @model_validator(mode="after")
    def merge_legacy_disabled_field(self) -> "AccountPurchaseConfigUpdateRequest":
        if self.disabled is not None:
            self.purchase_disabled = bool(self.disabled)
        return self
