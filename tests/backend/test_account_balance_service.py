from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import time

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


class FakeSigner:
    def __init__(self, *, result: str = "fake-sign") -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def generate(self, *, path: str, method: str, timestamp: str, token: str) -> str:
        self.calls.append(
            {
                "path": path,
                "method": method,
                "timestamp": timestamp,
                "token": token,
            }
        )
        return self._result


class FakeResponse:
    def __init__(self, *, text: str) -> None:
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def text(self) -> str:
        return self._text


class FakeClientSession:
    instances: list["FakeClientSession"] = []

    def __init__(self, *, timeout, cookie_jar=None) -> None:
        self.timeout = timeout
        self.cookie_jar = cookie_jar
        self.calls: list[dict[str, object]] = []
        FakeClientSession.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, url: str, *, proxy: str | None = None, headers=None):
        self.calls.append(
            {
                "url": url,
                "proxy": proxy,
                "headers": dict(headers or {}),
            }
        )
        return FakeResponse(text=json.dumps({"success": True, "data": {"balance": 66.6}}))


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


@pytest.mark.asyncio
async def test_account_balance_service_browser_fetch_uses_standalone_session_with_browser_like_headers(monkeypatch):
    import app_backend.application.services.account_balance_service as module
    from app_backend.application.services.account_balance_service import AccountBalanceService
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    account = build_account(api_key=None)
    signer = FakeSigner()
    FakeClientSession.instances.clear()

    async def unexpected_get_global_session(self, force_new: bool = False):
        raise AssertionError("browser balance fetch should not reuse the global purchase session")

    monkeypatch.setattr(RuntimeAccountAdapter, "get_global_session", unexpected_get_global_session)
    monkeypatch.setattr(module.aiohttp, "ClientSession", FakeClientSession)
    monkeypatch.setattr(module.aiohttp, "ClientTimeout", lambda total: {"total": total})

    service = AccountBalanceService(
        account_repository=FakeRepository(account),
        xsign_wrapper=signer,
    )

    amount = await service._fetch_browser_balance(account, proxy_url="http://browser.proxy:9001")

    assert amount == 66.6
    assert len(FakeClientSession.instances) == 1
    assert FakeClientSession.instances[0].cookie_jar is None
    assert FakeClientSession.instances[0].calls[0]["url"].endswith("/account/v1/my/account")
    assert FakeClientSession.instances[0].calls[0]["proxy"] == "http://browser.proxy:9001"
    headers = FakeClientSession.instances[0].calls[0]["headers"]
    assert headers["Host"] == "www.c5game.com"
    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert headers["Accept"] == "application/json, text/plain, */*"
    assert headers["Accept-Encoding"] == "gzip, deflate, br, zstd"
    assert headers["Connection"] == "keep-alive"
    assert headers["Sec-Fetch-Dest"] == "empty"
    assert headers["Sec-Fetch-Mode"] == "no-cors"
    assert headers["Sec-Fetch-Site"] == "same-origin"
    assert headers["TE"] == "trailers"
    assert headers["Priority"] == "u=4"
    assert headers["Pragma"] == "no-cache"
    assert headers["Cache-Control"] == "no-cache"
    assert headers["Cookie"] == account.cookie_raw
    assert headers["x-sign"] == "fake-sign"
    assert headers["x-access-token"] == "token-1"
    assert headers["x-device-id"] == "device-1"
    assert signer.calls[0]["path"] == "account/v1/my/account"
    assert signer.calls[0]["method"] == "GET"


def test_account_balance_service_maybe_schedule_refresh_works_without_running_loop():
    from app_backend.application.services.account_balance_service import AccountBalanceService

    repository = FakeRepository(build_account(api_key="api-key-1"))
    openapi_calls: list[str] = []

    async def fake_openapi_fetcher(account: Account, *, proxy_url: str | None) -> float:
        openapi_calls.append(account.account_id)
        return 77.7

    service = AccountBalanceService(
        account_repository=repository,
        openapi_fetcher=fake_openapi_fetcher,
        browser_balance_fetcher=None,
        now_provider=lambda: datetime(2026, 3, 29, 12, 8, 0),
        random_seconds_provider=lambda: 300,
    )

    scheduled = service.maybe_schedule_refresh("a-1")

    assert scheduled is True
    deadline = time.time() + 1.0
    while time.time() < deadline:
      updated = repository.get_account("a-1")
      if updated is not None and updated.balance_amount == 77.7:
          break
      time.sleep(0.01)

    updated = repository.get_account("a-1")
    assert updated is not None
    assert updated.balance_amount == 77.7
    assert updated.balance_source == "openapi"
    assert openapi_calls == ["a-1"]
