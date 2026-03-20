from __future__ import annotations

import importlib
import importlib.util
from types import SimpleNamespace


def build_account(
    account_id: str,
    *,
    api_key: str | None = None,
    cookie_raw: str | None = None,
    disabled: bool = False,
    purchase_disabled: bool = False,
    new_api_enabled: bool = True,
    fast_api_enabled: bool = True,
    token_enabled: bool = True,
    last_error: str | None = None,
) -> object:
    return SimpleNamespace(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        display_name=f"账号-{account_id}",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=api_key,
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw=cookie_raw,
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=last_error,
        created_at="2026-03-19T10:00:00",
        updated_at="2026-03-19T10:00:00",
        disabled=disabled,
        purchase_disabled=purchase_disabled,
        new_api_enabled=new_api_enabled,
        fast_api_enabled=fast_api_enabled,
        token_enabled=token_enabled,
    )


class FakeAccountRepository:
    def __init__(self, accounts: list[object]) -> None:
        self._accounts = list(accounts)

    def list_accounts(self) -> list[object]:
        return list(self._accounts)


def test_query_mode_capacity_service_counts_available_accounts_by_mode():
    module_spec = importlib.util.find_spec("app_backend.application.services.query_mode_capacity_service")

    assert module_spec is not None

    module = importlib.import_module("app_backend.application.services.query_mode_capacity_service")
    service = module.QueryModeCapacityService(
        FakeAccountRepository(
            [
                build_account("api-both", api_key="api-both"),
                build_account("api-fast-only", api_key="api-fast", new_api_enabled=False),
                build_account("token-ok", cookie_raw="foo=bar; NC5_accessToken=token-1"),
                build_account(
                    "purchase-disabled-query-ok",
                    api_key="api-query-ok",
                    cookie_raw="NC5_accessToken=token-4",
                    purchase_disabled=True,
                ),
                build_account("token-invalid", cookie_raw="NC5_accessToken=token-2", last_error="Not login"),
                build_account("disabled-api", api_key="api-disabled", disabled=True),
                build_account("disabled-token", cookie_raw="NC5_accessToken=token-3", disabled=True),
            ]
        )
    )

    assert service.get_summary() == {
        "modes": {
            "new_api": {"mode_type": "new_api", "available_account_count": 3},
            "fast_api": {"mode_type": "fast_api", "available_account_count": 4},
            "token": {"mode_type": "token", "available_account_count": 3},
        }
    }
