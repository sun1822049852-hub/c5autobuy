from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Account:
    account_id: str
    default_name: str
    remark_name: str | None
    proxy_mode: str
    proxy_url: str | None
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

    @property
    def display_name(self) -> str:
        return self.remark_name or self.c5_nick_name or self.default_name
