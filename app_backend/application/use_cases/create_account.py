from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app_backend.application.services.account_name_service import AccountNameService
from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.domain.models.account import Account
from app_backend.infrastructure.proxy.value_objects import normalize_proxy_input, render_proxy_url


class CreateAccountUseCase:
    def __init__(self, repository, proxy_pool_repository=None) -> None:
        self._repository = repository
        self._proxy_pool_repository = proxy_pool_repository

    def execute(
        self,
        *,
        remark_name: str | None,
        browser_proxy_mode: str,
        browser_proxy_url: str | None,
        api_proxy_mode: str,
        api_proxy_url: str | None,
        api_key: str | None,
        browser_proxy_id: str | None = None,
        api_proxy_id: str | None = None,
    ) -> Account:
        now = datetime.now().isoformat(timespec="seconds")
        normalized_browser_proxy_url = normalize_proxy_input(
            proxy_mode=browser_proxy_mode,
            proxy_url=browser_proxy_url,
        )
        normalized_api_proxy_url = normalize_proxy_input(
            proxy_mode=api_proxy_mode,
            proxy_url=api_proxy_url,
        )

        # Resolve proxy_id from pool
        if browser_proxy_id and self._proxy_pool_repository:
            pool_entry = self._proxy_pool_repository.get(browser_proxy_id)
            if pool_entry:
                normalized_browser_proxy_url = render_proxy_url(
                    scheme=pool_entry.scheme, host=pool_entry.host, port=pool_entry.port,
                    username=pool_entry.username, password=pool_entry.password,
                )
            else:
                browser_proxy_id = None  # pool entry deleted, fall back to direct
        if api_proxy_id and self._proxy_pool_repository:
            pool_entry = self._proxy_pool_repository.get(api_proxy_id)
            if pool_entry:
                normalized_api_proxy_url = render_proxy_url(
                    scheme=pool_entry.scheme, host=pool_entry.host, port=pool_entry.port,
                    username=pool_entry.username, password=pool_entry.password,
                )
            else:
                api_proxy_id = None  # pool entry deleted, fall back to direct

        if normalized_api_proxy_url is None and normalized_browser_proxy_url is not None:
            normalized_api_proxy_url = normalized_browser_proxy_url
        account = Account(
            account_id=str(uuid4()),
            default_name=AccountNameService.build_default_name(),
            remark_name=remark_name,
            browser_proxy_mode="pool" if browser_proxy_id else ("custom" if normalized_browser_proxy_url else "direct"),
            browser_proxy_url=normalized_browser_proxy_url,
            api_proxy_mode="pool" if api_proxy_id else ("custom" if normalized_api_proxy_url else "direct"),
            api_proxy_url=normalized_api_proxy_url,
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
            api_query_disabled_reason=None,
            browser_query_disabled_reason=None,
            browser_proxy_id=browser_proxy_id,
            api_proxy_id=api_proxy_id,
        )
        return self._repository.create_account(account)
