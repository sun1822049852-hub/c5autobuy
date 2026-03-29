from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app_backend.domain.models.account import Account


def build_account(
    *,
    account_id: str = "a-1",
    api_key: str | None = None,
    browser_proxy_url: str | None = "http://browser.proxy:9001",
    api_proxy_url: str | None = "http://api.proxy:9002",
    cookie_raw: str | None = "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1",
) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"default-{account_id}",
        remark_name=None,
        browser_proxy_mode="custom" if browser_proxy_url else "direct",
        browser_proxy_url=browser_proxy_url,
        api_proxy_mode="custom" if api_proxy_url else "direct",
        api_proxy_url=api_proxy_url,
        api_key=api_key,
        c5_user_id="10001" if cookie_raw else None,
        c5_nick_name="测试账号" if cookie_raw else None,
        cookie_raw=cookie_raw,
        purchase_capability_state="bound" if cookie_raw else "unbound",
        purchase_pool_state="not_connected",
        last_login_at="2026-03-29T11:00:00" if cookie_raw else None,
        last_error=None,
        created_at="2026-03-29T11:00:00",
        updated_at="2026-03-29T11:00:00",
        purchase_disabled=False,
        purchase_recovery_due_at=None,
        new_api_enabled=True,
        fast_api_enabled=True,
        token_enabled=True,
        api_query_disabled_reason=None,
        browser_query_disabled_reason=None,
        api_ip_allow_list=None,
        browser_public_ip=None,
        api_public_ip=None,
        balance_amount=None,
        balance_source=None,
        balance_updated_at=None,
        balance_refresh_after_at=None,
        balance_last_error=None,
    )


class FakeRepository:
    def __init__(self, *accounts: Account) -> None:
        self._accounts = {account.account_id: account for account in accounts}
        self.update_calls: list[tuple[str, dict[str, object]]] = []

    def get_account(self, account_id: str) -> Account | None:
        return self._accounts.get(account_id)

    def update_account(self, account_id: str, **changes) -> Account:
        account = self._accounts[account_id]
        next_account = replace(account, **changes)
        self._accounts[account_id] = next_account
        self.update_calls.append((account_id, dict(changes)))
        return next_account


class FakeAccountUpdateHub:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def publish(self, *, account_id: str, event: str, payload: dict[str, object]) -> None:
        self.events.append(
            {
                "account_id": account_id,
                "event": event,
                "payload": dict(payload),
            }
        )


@pytest.mark.asyncio
async def test_account_balance_service_prefers_openapi_money_amount_and_sets_refresh_window():
    from app_backend.application.services.account_balance_service import AccountBalanceService

    repository = FakeRepository(build_account(api_key="api-key-1"))
    hub = FakeAccountUpdateHub()
    openapi_calls: list[dict[str, object]] = []

    async def fake_openapi_fetcher(account: Account, *, proxy_url: str | None) -> float:
        openapi_calls.append(
            {
                "account_id": account.account_id,
                "proxy_url": proxy_url,
                "api_key": account.api_key,
            }
        )
        return 123.45

    async def unexpected_browser_fetcher(account: Account, *, proxy_url: str | None) -> float:
        raise AssertionError("browser fallback should not run when api_key exists")

    service = AccountBalanceService(
        account_repository=repository,
        account_update_hub=hub,
        openapi_fetcher=fake_openapi_fetcher,
        browser_balance_fetcher=unexpected_browser_fetcher,
        now_provider=lambda: datetime(2026, 3, 29, 12, 0, 0),
        random_seconds_provider=lambda: 540,
    )

    await service.refresh_account("a-1", force=True)

    updated = repository.get_account("a-1")
    assert updated is not None
    assert updated.balance_amount == 123.45
    assert updated.balance_source == "openapi"
    assert updated.balance_updated_at == "2026-03-29T12:00:00"
    assert updated.balance_refresh_after_at == "2026-03-29T12:09:00"
    assert updated.balance_last_error is None
    assert openapi_calls == [
        {
            "account_id": "a-1",
            "proxy_url": "http://api.proxy:9002",
            "api_key": "api-key-1",
        }
    ]
    assert hub.events[-1]["payload"]["balance_amount"] == 123.45


@pytest.mark.asyncio
async def test_account_balance_service_uses_browser_session_fallback_once_without_api_key():
    from app_backend.application.services.account_balance_service import AccountBalanceService

    repository = FakeRepository(build_account(api_key=None))
    browser_calls: list[dict[str, object]] = []

    async def unexpected_openapi_fetcher(account: Account, *, proxy_url: str | None) -> float:
        raise AssertionError("openapi fetch should not run without api_key")

    async def fake_browser_fetcher(account: Account, *, proxy_url: str | None) -> float:
        browser_calls.append(
            {
                "account_id": account.account_id,
                "proxy_url": proxy_url,
                "api_proxy_url": account.api_proxy_url,
            }
        )
        return 66.6

    service = AccountBalanceService(
        account_repository=repository,
        openapi_fetcher=unexpected_openapi_fetcher,
        browser_balance_fetcher=fake_browser_fetcher,
        now_provider=lambda: datetime(2026, 3, 29, 12, 5, 0),
        random_seconds_provider=lambda: 600,
    )

    await service.refresh_account("a-1", force=True)

    updated = repository.get_account("a-1")
    assert updated is not None
    assert updated.balance_amount == 66.6
    assert updated.balance_source == "browser_session"
    assert browser_calls == [
        {
            "account_id": "a-1",
            "proxy_url": "http://browser.proxy:9001",
            "api_proxy_url": "http://api.proxy:9002",
        }
    ]


@pytest.mark.asyncio
async def test_account_balance_service_does_not_retry_failed_browser_session_fallback():
    from app_backend.application.services.account_balance_service import AccountBalanceService

    repository = FakeRepository(build_account(api_key=None))
    browser_calls: list[str | None] = []

    async def fake_browser_fetcher(account: Account, *, proxy_url: str | None) -> float:
        browser_calls.append(proxy_url)
        raise RuntimeError("browser balance failed")

    service = AccountBalanceService(
        account_repository=repository,
        openapi_fetcher=None,
        browser_balance_fetcher=fake_browser_fetcher,
        now_provider=lambda: datetime(2026, 3, 29, 12, 6, 0),
        random_seconds_provider=lambda: 480,
    )

    await service.refresh_account("a-1", force=True)

    updated = repository.get_account("a-1")
    assert updated is not None
    assert browser_calls == ["http://browser.proxy:9001"]
    assert updated.balance_amount is None
    assert updated.balance_last_error == "browser balance failed"
    assert updated.balance_refresh_after_at == "2026-03-29T12:14:00"


@pytest.mark.asyncio
async def test_account_balance_service_waits_for_api_key_before_falling_back():
    from app_backend.application.services.account_balance_service import AccountBalanceService

    repository = FakeRepository(build_account(api_key=None))
    openapi_calls: list[str] = []
    browser_calls: list[str | None] = []

    async def fake_openapi_fetcher(account: Account, *, proxy_url: str | None) -> float:
        openapi_calls.append(str(account.api_key))
        return 88.8

    async def fake_browser_fetcher(account: Account, *, proxy_url: str | None) -> float:
        browser_calls.append(proxy_url)
        return 11.1

    sleep_calls = {"count": 0}

    async def fake_sleep(_: float) -> None:
        sleep_calls["count"] += 1
        if sleep_calls["count"] == 2:
            repository.update_account("a-1", api_key="late-api-key")

    service = AccountBalanceService(
        account_repository=repository,
        openapi_fetcher=fake_openapi_fetcher,
        browser_balance_fetcher=fake_browser_fetcher,
        now_provider=lambda: datetime(2026, 3, 29, 12, 7, 0),
        random_seconds_provider=lambda: 510,
        sleep=fake_sleep,
        api_key_wait_seconds=10.0,
        api_key_poll_interval_seconds=0.1,
    )

    await service.refresh_after_login("a-1")

    updated = repository.get_account("a-1")
    assert updated is not None
    assert updated.balance_amount == 88.8
    assert updated.balance_source == "openapi"
    assert openapi_calls == ["late-api-key"]
    assert browser_calls == []
