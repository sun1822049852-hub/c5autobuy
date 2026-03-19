from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app_backend.application.services.account_name_service import AccountNameService
from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.domain.models.account import Account
from app_backend.infrastructure.proxy.value_objects import normalize_proxy_input


class CreateAccountUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        remark_name: str | None,
        proxy_mode: str,
        proxy_url: str | None,
        api_key: str | None,
    ) -> Account:
        now = datetime.now().isoformat(timespec="seconds")
        normalized_proxy_url = normalize_proxy_input(proxy_mode=proxy_mode, proxy_url=proxy_url)
        account = Account(
            account_id=str(uuid4()),
            default_name=AccountNameService.build_default_name(),
            remark_name=remark_name,
            proxy_mode="custom" if normalized_proxy_url else "direct",
            proxy_url=normalized_proxy_url,
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
            disabled=False,
            purchase_disabled=False,
            purchase_recovery_due_at=None,
            new_api_enabled=True,
            fast_api_enabled=True,
            token_enabled=True,
        )
        return self._repository.create_account(account)
