from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AccountCreateRequest(BaseModel):
    remark_name: str | None = None
    browser_proxy_mode: str
    browser_proxy_url: str | None = None
    api_proxy_mode: str
    api_proxy_url: str | None = None
    api_key: str | None = None
    browser_proxy_id: str | None = None
    api_proxy_id: str | None = None


class AccountUpdateRequest(BaseModel):
    remark_name: str | None = None
    browser_proxy_mode: str
    browser_proxy_url: str | None = None
    api_proxy_mode: str
    api_proxy_url: str | None = None
    api_key: str | None = None
    browser_proxy_id: str | None = None
    api_proxy_id: str | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: str
    default_name: str
    remark_name: str | None
    display_name: str
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
    purchase_disabled: bool
    purchase_recovery_due_at: str | None = None
    new_api_enabled: bool
    fast_api_enabled: bool
    token_enabled: bool
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
    browser_proxy_id: str | None = None
    api_proxy_id: str | None = None


class AccountQueryModeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_query_enabled: bool | None = None
    browser_query_enabled: bool | None = None
    api_query_disabled_reason: str | None = None
    browser_query_disabled_reason: str | None = None


class LoginConflictResolveRequest(BaseModel):
    task_id: str
    action: str
