from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AccountCreateRequest(BaseModel):
    remark_name: str | None = None
    proxy_mode: str
    proxy_url: str | None = None
    api_key: str | None = None


class AccountUpdateRequest(BaseModel):
    remark_name: str | None = None
    proxy_mode: str
    proxy_url: str | None = None
    api_key: str | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: str
    default_name: str
    remark_name: str | None
    display_name: str
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
    disabled: bool
    purchase_disabled: bool
    purchase_recovery_due_at: str | None = None
    new_api_enabled: bool
    fast_api_enabled: bool
    token_enabled: bool


class AccountQueryModeUpdateRequest(BaseModel):
    new_api_enabled: bool
    fast_api_enabled: bool
    token_enabled: bool


class LoginConflictResolveRequest(BaseModel):
    task_id: str
    action: str
