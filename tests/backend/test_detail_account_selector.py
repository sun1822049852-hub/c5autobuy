from __future__ import annotations

import pytest

from app_backend.domain.models.account import Account


def build_account(
    account_id: str,
    *,
    cookie_raw: str | None = None,
    disabled: bool = False,
    purchase_disabled: bool = False,
) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw=cookie_raw,
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-17T00:00:00",
        updated_at="2026-03-17T00:00:00",
        disabled=disabled,
        purchase_disabled=purchase_disabled,
        new_api_enabled=True,
        fast_api_enabled=True,
        token_enabled=True,
    )


class FakeAccountRepository:
    def __init__(self, accounts: list[Account]) -> None:
        self._accounts = list(accounts)

    def list_accounts(self) -> list[Account]:
        return list(self._accounts)


def test_detail_account_selector_builds_round_robin_attempt_order_for_eligible_accounts():
    from app_backend.infrastructure.query.collectors.detail_account_selector import DetailAccountSelector

    selector = DetailAccountSelector(
        FakeAccountRepository(
            [
                build_account("a1", cookie_raw=None),
                build_account("a2", cookie_raw="NC5_accessToken=token-2"),
                build_account("a3", cookie_raw="NC5_accessToken=token-3", disabled=True),
                build_account("a4", cookie_raw="foo=bar; NC5_accessToken=token-4"),
            ]
        )
    )

    assert [account.account_id for account in selector.build_attempt_order()] == ["a2", "a4"]
    assert [account.account_id for account in selector.build_attempt_order()] == ["a4", "a2"]
    assert [account.account_id for account in selector.build_attempt_order()] == ["a2", "a4"]


def test_detail_account_selector_raises_when_no_eligible_account_exists():
    from app_backend.infrastructure.query.collectors.detail_account_selector import DetailAccountSelector

    selector = DetailAccountSelector(
        FakeAccountRepository(
            [
                build_account("a1", cookie_raw=None),
                build_account("a2", cookie_raw="NC5_accessToken=token-2", disabled=True),
            ]
        )
    )

    with pytest.raises(ValueError, match="没有可用于商品信息补全的已登录账号"):
        selector.build_attempt_order()


def test_detail_account_selector_keeps_purchase_disabled_accounts_query_eligible():
    from app_backend.infrastructure.query.collectors.detail_account_selector import DetailAccountSelector

    selector = DetailAccountSelector(
        FakeAccountRepository(
            [
                build_account("a1", cookie_raw="NC5_accessToken=token-1", purchase_disabled=True),
                build_account("a2", cookie_raw="NC5_accessToken=token-2"),
            ]
        )
    )

    assert [account.account_id for account in selector.build_attempt_order()] == ["a1", "a2"]
