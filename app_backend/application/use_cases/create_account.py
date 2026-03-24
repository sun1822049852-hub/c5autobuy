from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app_backend.application.services.account_name_service import AccountNameService
from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.domain.models.account import Account
from app_backend.infrastructure.c5.user_agent import pick_rotating_user_agent
from app_backend.infrastructure.proxy.value_objects import normalize_proxy_input


class CreateAccountUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        remark_name: str | None,
        account_proxy_mode: str | None = None,
        account_proxy_url: str | None = None,
        api_proxy_mode: str | None = None,
        api_proxy_url: str | None = None,
        proxy_mode: str | None = None,
        proxy_url: str | None = None,
        api_key: str | None,
    ) -> Account:
        now = datetime.now().isoformat(timespec="seconds")
        raw_account_proxy_mode = account_proxy_mode or proxy_mode or "direct"
        raw_account_proxy_url = account_proxy_url if account_proxy_url is not None else proxy_url
        normalized_account_proxy_url = normalize_proxy_input(
            proxy_mode=raw_account_proxy_mode,
            proxy_url=raw_account_proxy_url,
        )
        raw_api_proxy_mode = api_proxy_mode if api_proxy_mode is not None else raw_account_proxy_mode
        raw_api_proxy_url = api_proxy_url if api_proxy_url is not None else raw_account_proxy_url
        normalized_api_proxy_url = normalize_proxy_input(
            proxy_mode=raw_api_proxy_mode,
            proxy_url=raw_api_proxy_url,
        )
        assigned_user_agent = pick_rotating_user_agent(
            account.user_agent for account in self._repository.list_accounts()
        )
        account = Account(
            account_id=str(uuid4()),
            default_name=AccountNameService.build_default_name(),
            remark_name=remark_name,
            proxy_mode="custom" if normalized_account_proxy_url else "direct",
            proxy_url=normalized_account_proxy_url,
            api_key=(api_key or None),
            c5_user_id=None,
            c5_nick_name=None,
            cookie_raw=None,
            purchase_capability_state=PurchaseCapabilityState.UNBOUND,
            purchase_pool_state=PurchasePoolState.NOT_CONNECTED,
            last_login_at=None,
            last_error=None,
            created_at=now,
            updated_at=now,
            purchase_disabled=False,
            purchase_recovery_due_at=None,
            new_api_enabled=True,
            fast_api_enabled=True,
            token_enabled=True,
            account_proxy_mode="custom" if normalized_account_proxy_url else "direct",
            account_proxy_url=normalized_account_proxy_url,
            api_proxy_mode="custom" if normalized_api_proxy_url else "direct",
            api_proxy_url=normalized_api_proxy_url,
            user_agent=assigned_user_agent,
        )
        return self._repository.create_account(account)
