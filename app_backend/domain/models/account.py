from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Account:
    account_id: str
    default_name: str
    remark_name: str | None
    browser_proxy_mode: str
    browser_proxy_url: str | None
    api_proxy_mode: str
    api_proxy_url: str | None
    api_key: str | None
    c5_user_id: str | None
    c5_nick_name: str | None
    cookie_raw: str | None
    purchase_capability_state: str
    purchase_pool_state: str
    last_login_at: str | None
    last_error: str | None
    created_at: str
    updated_at: str
    purchase_disabled: bool = False
    purchase_recovery_due_at: str | None = None
    new_api_enabled: bool = True
    fast_api_enabled: bool = True
    token_enabled: bool = True
    api_query_disabled_reason: str | None = None
    browser_query_disabled_reason: str | None = None
    api_ip_allow_list: str | None = None
    browser_public_ip: str | None = None
    api_public_ip: str | None = None
    balance_amount: float | None = None
    balance_source: str | None = None
    balance_updated_at: str | None = None
    balance_refresh_after_at: str | None = None
    balance_last_error: str | None = None

    @property
    def display_name(self) -> str:
        return self.remark_name or self.c5_nick_name or self.default_name

    @property
    def proxy_public_ip(self) -> str | None:
        return self.api_public_ip
