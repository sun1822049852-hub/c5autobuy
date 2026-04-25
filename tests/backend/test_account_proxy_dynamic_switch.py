from __future__ import annotations

import asyncio

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.domain.models.account import Account


def _build_account(
    account_id: str,
    *,
    browser_proxy_mode: str = "custom",
    browser_proxy_url: str | None = "http://browser.proxy:9001",
    api_proxy_mode: str = "custom",
    api_proxy_url: str | None = "http://api.proxy:9002",
    browser_proxy_id: str | None = None,
    api_proxy_id: str | None = None,
    purchase_capability_state: str = PurchaseCapabilityState.BOUND,
    purchase_pool_state: str = PurchasePoolState.ACTIVE,
    purchase_disabled: bool = False,
) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=f"备注-{account_id}",
        browser_proxy_mode=browser_proxy_mode,
        browser_proxy_url=browser_proxy_url,
        api_proxy_mode=api_proxy_mode,
        api_proxy_url=api_proxy_url,
        api_key="api-key",
        c5_user_id="10001",
        c5_nick_name=f"昵称-{account_id}",
        cookie_raw="NC5_accessToken=token; NC5_deviceId=device",
        purchase_capability_state=purchase_capability_state,
        purchase_pool_state=purchase_pool_state,
        last_login_at="2026-04-25T20:00:00",
        last_error=None,
        created_at="2026-04-25T20:00:00",
        updated_at="2026-04-25T20:00:00",
        purchase_disabled=purchase_disabled,
        browser_proxy_id=browser_proxy_id,
        api_proxy_id=api_proxy_id,
    )


class _FakeSession:
    def __init__(self, *, proxy_url: str | None, loop) -> None:
        self._loop = loop
        self.closed = False
        self.proxy_url = proxy_url

    async def close(self) -> None:
        self.closed = True


async def test_runtime_account_adapter_recreates_api_session_after_proxy_switch(monkeypatch):
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    adapter = RuntimeAccountAdapter(
        _build_account(
            "adapter-api",
            api_proxy_url="http://api.proxy:9002",
        )
    )
    created_sessions: list[_FakeSession] = []

    def fake_create_session(**kwargs):
        session = _FakeSession(proxy_url=kwargs.get("proxy_url"), loop=asyncio.get_running_loop())
        created_sessions.append(session)
        return session

    monkeypatch.setattr(adapter, "_create_session", fake_create_session)

    first_session = await adapter.get_api_session()
    adapter.bind_account(
        _build_account(
            "adapter-api",
            api_proxy_url="http://api.proxy:9012",
        )
    )
    second_session = await adapter.get_api_session()

    assert first_session is not second_session
    assert len(created_sessions) == 2
    assert created_sessions[0].proxy_url == "http://api.proxy:9002"
    assert created_sessions[1].proxy_url == "http://api.proxy:9012"


async def test_patch_account_refreshes_runtime_services_and_publishes_account_update(client, app):
    class _FakeQueryRuntimeService:
        def __init__(self) -> None:
            self.calls = 0

        def refresh_runtime_accounts(self) -> None:
            self.calls += 1

    class _FakePurchaseRuntimeService:
        def __init__(self) -> None:
            self.calls = 0

        def refresh_runtime_accounts(self) -> None:
            self.calls += 1

    class _FakeAccountUpdateHub:
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

    app.state.query_runtime_service = _FakeQueryRuntimeService()
    app.state.purchase_runtime_service = _FakePurchaseRuntimeService()
    app.state.account_update_hub = _FakeAccountUpdateHub()

    created = await client.post(
        "/accounts",
        json={
            "remark_name": "代理热切换账号",
            "browser_proxy_mode": "custom",
            "browser_proxy_url": "http://127.0.0.1:9001",
            "api_proxy_mode": "custom",
            "api_proxy_url": "http://127.0.0.1:9002",
            "api_key": "api-key",
            "browser_proxy_id": None,
            "api_proxy_id": None,
        },
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}",
        json={
            "remark_name": "代理热切换账号",
            "browser_proxy_mode": "custom",
            "browser_proxy_url": "http://127.0.0.1:9101",
            "api_proxy_mode": "custom",
            "api_proxy_url": "http://127.0.0.1:9102",
            "api_key": "api-key",
            "browser_proxy_id": None,
            "api_proxy_id": None,
        },
    )

    assert response.status_code == 200
    assert app.state.query_runtime_service.calls == 1
    assert app.state.purchase_runtime_service.calls == 1
    assert app.state.account_update_hub.events == [
        {
            "account_id": account_id,
            "event": "update_account",
            "payload": {
                "browser_proxy_mode": "custom",
                "browser_proxy_url": "http://127.0.0.1:9101",
                "api_proxy_mode": "custom",
                "api_proxy_url": "http://127.0.0.1:9102",
                "browser_proxy_id": None,
                "api_proxy_id": None,
            },
        }
    ]


async def test_account_center_route_keeps_proxy_pool_binding_ids(client, app):
    proxy_entry = app.state.proxy_pool_repository.create(
        type(
            "ProxyEntry",
            (),
            {
                "proxy_id": "proxy-browser-1",
                "name": "浏览器代理",
                "scheme": "http",
                "host": "127.0.0.1",
                "port": "9801",
                "username": None,
                "password": None,
                "created_at": "2026-04-25T20:00:00",
                "updated_at": "2026-04-25T20:00:00",
            },
        )()
    )
    app.state.proxy_pool_repository.create(
        type(
            "ProxyEntry",
            (),
            {
                "proxy_id": "proxy-api-1",
                "name": "API代理",
                "scheme": "http",
                "host": "127.0.0.1",
                "port": "9802",
                "username": None,
                "password": None,
                "created_at": "2026-04-25T20:00:00",
                "updated_at": "2026-04-25T20:00:00",
            },
        )()
    )
    app.state.account_repository.create_account(
        _build_account(
            "pool-account",
            browser_proxy_mode="pool",
            browser_proxy_url="http://127.0.0.1:9801",
            api_proxy_mode="pool",
            api_proxy_url="http://127.0.0.1:9802",
            browser_proxy_id=proxy_entry.proxy_id,
            api_proxy_id="proxy-api-1",
        )
    )

    response = await client.get("/account-center/accounts/pool-account")

    assert response.status_code == 200
    payload = response.json()
    assert payload["browser_proxy_mode"] == "pool"
    assert payload["browser_proxy_id"] == "proxy-browser-1"
    assert payload["api_proxy_mode"] == "pool"
    assert payload["api_proxy_id"] == "proxy-api-1"


async def test_purchase_runtime_refresh_runtime_accounts_rebinds_bucket_and_worker(app):
    service = app.state.purchase_runtime_service
    account = _build_account(
        "purchase-runtime-proxy",
        browser_proxy_url="http://127.0.0.1:9901",
        api_proxy_url="http://127.0.0.1:9902",
    )
    app.state.account_repository.create_account(account)
    service._inventory_snapshot_repository.save(
        account_id=account.account_id,
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "inventory_num": 800, "inventory_max": 1000}],
        refreshed_at="2026-04-25T20:10:00",
        last_error=None,
    )

    started, _ = service.start()
    assert started is True
    runtime = service._runtime
    assert runtime is not None
    assert runtime._scheduler.account_status(account.account_id)["bucket_key"] == "http://127.0.0.1:9901"

    app.state.account_repository.update_account(
        account.account_id,
        browser_proxy_mode="custom",
        browser_proxy_url="http://127.0.0.1:9911",
        api_proxy_mode="custom",
        api_proxy_url="http://127.0.0.1:9912",
        updated_at="2026-04-25T20:20:00",
    )

    service.refresh_runtime_accounts()

    runtime_state = runtime._account_states[account.account_id]
    assert runtime_state.account.browser_proxy_url == "http://127.0.0.1:9911"
    assert runtime_state.worker._runtime_account._browser_proxy_url_or_none == "http://127.0.0.1:9911"
    assert runtime._scheduler.account_status(account.account_id)["bucket_key"] == "http://127.0.0.1:9911"


async def test_patch_proxy_pool_refreshes_runtime_services_and_publishes_account_updates(client, app):
    class _FakeQueryRuntimeService:
        def __init__(self) -> None:
            self.calls = 0

        def refresh_runtime_accounts(self) -> None:
            self.calls += 1

    class _FakePurchaseRuntimeService:
        def __init__(self) -> None:
            self.calls = 0

        def refresh_runtime_accounts(self) -> None:
            self.calls += 1

    class _FakeAccountUpdateHub:
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

    app.state.query_runtime_service = _FakeQueryRuntimeService()
    app.state.purchase_runtime_service = _FakePurchaseRuntimeService()
    app.state.account_update_hub = _FakeAccountUpdateHub()

    await client.post(
        "/proxy-pool",
        json={
            "name": "池代理-1",
            "scheme": "http",
            "host": "127.0.0.1",
            "port": "9901",
            "username": None,
            "password": None,
        },
    )
    proxy_id = app.state.proxy_pool_repository.list_all()[0].proxy_id
    app.state.account_repository.create_account(
        _build_account(
            "pool-route-account",
            browser_proxy_mode="pool",
            browser_proxy_url="http://127.0.0.1:9901",
            api_proxy_mode="pool",
            api_proxy_url="http://127.0.0.1:9901",
            browser_proxy_id=proxy_id,
            api_proxy_id=proxy_id,
        )
    )

    response = await client.patch(
        f"/proxy-pool/{proxy_id}",
        json={
            "host": "127.0.0.2",
        },
    )

    assert response.status_code == 200
    assert app.state.query_runtime_service.calls == 1
    assert app.state.purchase_runtime_service.calls == 1
    assert app.state.account_update_hub.events == [
        {
            "account_id": "pool-route-account",
            "event": "update_account",
            "payload": {"proxy_id": proxy_id},
        }
    ]
