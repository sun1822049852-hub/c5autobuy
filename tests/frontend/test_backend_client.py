from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app_backend.domain.models.account import Account
from app_backend.infrastructure.selenium.login_adapter import LoginCapture
from app_backend.main import create_app


@pytest.fixture
async def backend_client(tmp_path: Path):
    from app_frontend.app.services.backend_client import BackendClient

    app = create_app(db_path=tmp_path / "app.db")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        client = BackendClient(http_client=http_client, poll_interval=0.005)
        yield app, client


async def test_backend_client_lists_and_creates_accounts(backend_client):
    _app, client = backend_client

    created = await client.create_account(
        {
            "remark_name": "前端创建账号",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": "frontend-api",
        }
    )
    accounts = await client.list_accounts()

    assert created["remark_name"] == "前端创建账号"
    assert len(accounts) == 1
    assert accounts[0]["account_id"] == created["account_id"]


async def test_backend_client_updates_account_query_modes(backend_client):
    _app, client = backend_client

    created = await client.create_account(
        {
            "remark_name": "模式账号",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": "api-mode",
        }
    )

    updated = await client.update_account_query_modes(
        created["account_id"],
        {
            "new_api_enabled": False,
            "fast_api_enabled": True,
            "token_enabled": False,
        },
    )

    assert updated["account_id"] == created["account_id"]
    assert updated["new_api_enabled"] is False
    assert updated["fast_api_enabled"] is True
    assert updated["token_enabled"] is False


async def test_backend_client_watch_task_streams_until_login_task_finishes(backend_client):
    app, client = backend_client

    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            for state in ("waiting_for_scan", "captured_login_info", "waiting_for_browser_close"):
                await emit_state(state)
                await asyncio.sleep(0.01)
            return LoginCapture(
                c5_user_id="50005",
                c5_nick_name="前端登录账号",
                cookie_raw="frontend=login",
            )

    app.state.login_adapter = FakeLoginAdapter()
    account = await client.create_account(
        {
            "remark_name": "登录源账号",
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:9100",
            "api_key": None,
        }
    )

    task = await client.start_login(account["account_id"])
    snapshots = [snapshot async for snapshot in client.watch_task(task["task_id"])]

    assert snapshots[-1]["state"] == "succeeded"
    assert [event["state"] for event in snapshots[-1]["events"]] == [
        "pending",
        "starting_browser",
        "waiting_for_scan",
        "captured_login_info",
        "waiting_for_browser_close",
        "saving_account",
        "succeeded",
    ]


async def test_backend_client_lists_and_creates_query_configs(backend_client):
    _app, client = backend_client

    created = await client.create_query_config(
        {
            "name": "前端查询配置",
            "description": "查询描述",
        }
    )
    configs = await client.list_query_configs()

    assert created["name"] == "前端查询配置"
    assert len(configs) == 1
    assert configs[0]["config_id"] == created["config_id"]
    assert {mode["mode_type"] for mode in created["mode_settings"]} == {"new_api", "fast_api", "token"}


async def test_backend_client_gets_updates_and_deletes_query_config(backend_client):
    _app, client = backend_client

    created = await client.create_query_config(
        {
            "name": "待编辑配置",
            "description": "旧描述",
        }
    )

    fetched = await client.get_query_config(created["config_id"])
    updated = await client.update_query_config(
        created["config_id"],
        {
            "name": "已编辑配置",
            "description": "新描述",
        },
    )
    await client.delete_query_config(created["config_id"])
    configs = await client.list_query_configs()

    assert fetched["config_id"] == created["config_id"]
    assert fetched["name"] == "待编辑配置"
    assert updated["name"] == "已编辑配置"
    assert updated["description"] == "新描述"
    assert configs == []


async def test_backend_client_starts_and_stops_query_runtime(backend_client):
    _app, client = backend_client

    created = await client.create_query_config(
        {
            "name": "运行时配置",
            "description": "给前端跑的",
        }
    )

    started = await client.start_query_runtime(created["config_id"])
    running = await client.get_query_runtime_status()
    stopped = await client.stop_query_runtime()

    assert started["running"] is True
    assert started["config_id"] == created["config_id"]
    assert running["running"] is True
    assert running["config_name"] == "运行时配置"
    assert stopped["running"] is False


async def test_backend_client_prepares_query_runtime(backend_client):
    app, client = backend_client

    created = await client.create_query_config(
        {
            "name": "准备配置",
            "description": "给启动前准备",
        }
    )

    class FakeRefreshService:
        async def prepare(self, *, config_id: str, force_refresh: bool = False) -> dict[str, object]:
            return {
                "config_id": config_id,
                "config_name": "准备配置",
                "threshold_hours": 12,
                "updated_count": 1,
                "skipped_count": 0,
                "failed_count": 0,
                "items": [
                    {
                        "query_item_id": "item-1",
                        "external_item_id": "1380979899390267393",
                        "item_name": "AK-47 | Redline",
                        "status": "updated",
                        "message": "商品详情已刷新",
                        "last_market_price": 123.45,
                        "min_wear": 0.1,
                        "detail_max_wear": 0.7,
                        "last_detail_sync_at": "2026-03-17T12:00:00",
                    }
                ],
            }

    app.state.query_item_detail_refresh_service = FakeRefreshService()

    prepared = await client.prepare_query_runtime(created["config_id"], force_refresh=True)

    assert prepared["config_id"] == created["config_id"]
    assert prepared["threshold_hours"] == 12
    assert prepared["updated_count"] == 1
    assert prepared["items"][0]["status"] == "updated"
    assert prepared["items"][0]["detail_max_wear"] == 0.7


async def test_backend_client_fetches_purchase_runtime_status(backend_client):
    _app, client = backend_client

    payload = await client.get_purchase_runtime_status()

    assert payload["running"] is False
    assert payload["settings"]["query_only"] is False


async def test_backend_client_updates_purchase_runtime_settings(backend_client):
    _app, client = backend_client

    updated = await client.update_purchase_runtime_settings(
        {
            "query_only": True,
            "whitelist_account_ids": ["a1"],
        }
    )
    settings = await client.get_purchase_runtime_settings()

    assert updated["settings"]["query_only"] is True
    assert updated["settings"]["whitelist_account_ids"] == ["a1"]
    assert settings["whitelist_account_ids"] == ["a1"]


async def test_backend_client_fetches_purchase_runtime_inventory_detail(backend_client):
    app, client = backend_client

    app.state.account_repository.create_account(
        Account(
            account_id="a1",
            default_name="账号-a1",
            remark_name=None,
            proxy_mode="direct",
            proxy_url=None,
            api_key=None,
            c5_user_id="10001",
            c5_nick_name="主号",
            cookie_raw="NC5_accessToken=token",
            purchase_capability_state="bound",
            purchase_pool_state="not_connected",
            last_login_at="2026-03-16T20:00:00",
            last_error=None,
            created_at="2026-03-16T20:00:00",
            updated_at="2026-03-16T20:00:00",
            disabled=False,
        )
    )
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:05:00",
        last_error=None,
    )

    payload = await client.get_purchase_runtime_inventory_detail("a1")

    assert payload["account_id"] == "a1"
    assert payload["selected_steam_id"] == "steam-1"
    assert payload["inventories"][0]["remaining_capacity"] == 90
    assert payload["inventories"][0]["is_selected"] is True


async def test_backend_client_updates_query_mode_setting(backend_client):
    _app, client = backend_client

    created = await client.create_query_config(
        {
            "name": "模式配置",
            "description": "给模式编辑",
        }
    )

    updated = await client.update_query_mode_setting(
        created["config_id"],
        "new_api",
        {
            "enabled": False,
            "window_enabled": True,
            "start_hour": 8,
            "start_minute": 0,
            "end_hour": 23,
            "end_minute": 30,
            "base_cooldown_min": 0.5,
            "base_cooldown_max": 1.2,
            "random_delay_enabled": True,
            "random_delay_min": 0.1,
            "random_delay_max": 0.6,
        },
    )

    assert updated["mode_type"] == "new_api"
    assert updated["enabled"] is False
    assert updated["start_hour"] == 8
    assert updated["base_cooldown_max"] == 1.2


async def test_backend_client_adds_updates_and_deletes_query_items(backend_client):
    app, client = backend_client

    class FakeDetailCollector:
        async def fetch_detail(self, *, external_item_id: str, product_url: str):
            from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetail

            return ProductDetail(
                external_item_id=external_item_id,
                product_url=product_url,
                item_name="Desert Eagle | Printstream",
                market_hash_name="Desert Eagle | Printstream (Field-Tested)",
                min_wear=0.0,
                max_wear=0.8,
                last_market_price=321.0,
            )

    app.state.product_detail_collector = FakeDetailCollector()
    created = await client.create_query_config({"name": "商品配置", "description": "前端商品"})

    added = await client.add_query_item(
        created["config_id"],
        {
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390264321",
            "max_wear": 0.22,
            "max_price": 456.0,
        },
    )
    updated = await client.update_query_item(
        created["config_id"],
        added["query_item_id"],
        {"max_wear": 0.18, "max_price": 400.0},
    )
    await client.delete_query_item(created["config_id"], added["query_item_id"])
    configs = await client.list_query_configs()

    assert added["item_name"] == "Desert Eagle | Printstream"
    assert updated["max_wear"] == 0.18
    assert updated["max_price"] == 400.0
    assert configs[0]["items"] == []


async def test_backend_client_parses_query_item_url(backend_client):
    _app, client = backend_client

    payload = await client.parse_query_item_url(
        {
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267555",
        }
    )

    assert payload == {
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267555",
        "external_item_id": "1380979899390267555",
    }


async def test_backend_client_fetches_query_item_detail(backend_client):
    app, client = backend_client

    class FakeDetailCollector:
        async def fetch_detail(self, *, external_item_id: str, product_url: str):
            from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetail

            return ProductDetail(
                external_item_id=external_item_id,
                product_url=product_url,
                item_name="M4A1-S | Blue Phosphor",
                market_hash_name="M4A1-S | Blue Phosphor (Factory New)",
                min_wear=0.0,
                max_wear=0.08,
                last_market_price=2888.0,
            )

    app.state.product_detail_collector = FakeDetailCollector()

    payload = await client.fetch_query_item_detail(
        {
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267444",
            "external_item_id": "1380979899390267444",
        }
    )

    assert payload == {
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267444",
        "external_item_id": "1380979899390267444",
        "item_name": "M4A1-S | Blue Phosphor",
        "market_hash_name": "M4A1-S | Blue Phosphor (Factory New)",
        "min_wear": 0.0,
        "detail_max_wear": 0.08,
        "last_market_price": 2888.0,
    }


async def test_backend_client_refreshes_query_item_detail(backend_client):
    app, client = backend_client

    class FakeRefreshService:
        async def refresh_item(self, *, config_id: str, query_item_id: str):
            return {
                "query_item_id": query_item_id,
                "config_id": config_id,
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267444",
                "external_item_id": "1380979899390267444",
                "item_name": "M4A1-S | Blue Phosphor",
                "market_hash_name": "M4A1-S | Blue Phosphor (Factory New)",
                "min_wear": 0.0,
                "detail_max_wear": 0.08,
                "max_wear": 0.18,
                "max_price": 3000.0,
                "last_market_price": 2888.0,
                "last_detail_sync_at": "2026-03-17T12:30:00",
                "sort_order": 0,
                "created_at": "2026-03-17T12:00:00",
                "updated_at": "2026-03-17T12:30:00",
            }

    app.state.query_item_detail_refresh_service = FakeRefreshService()

    payload = await client.refresh_query_item_detail("cfg-1", "item-1")

    assert payload["query_item_id"] == "item-1"
    assert payload["config_id"] == "cfg-1"
    assert payload["detail_max_wear"] == 0.08
    assert payload["last_market_price"] == 2888.0


async def test_backend_client_prefers_websocket_subscription_for_task_stream():
    from app_frontend.app.services.backend_client import BackendClient

    calls: list[tuple[str, float]] = []

    class FakeWebSocketConnection:
        def __init__(self) -> None:
            self._messages = [
                json.dumps(
                    {
                        "task_id": "task-1",
                        "task_type": "login",
                        "state": "waiting_for_scan",
                        "created_at": "2026-03-16T12:00:00",
                        "updated_at": "2026-03-16T12:00:01",
                        "events": [{"state": "waiting_for_scan"}],
                        "result": None,
                        "error": None,
                        "pending_conflict": None,
                    }
                ),
                json.dumps(
                    {
                        "task_id": "task-1",
                        "task_type": "login",
                        "state": "succeeded",
                        "created_at": "2026-03-16T12:00:00",
                        "updated_at": "2026-03-16T12:00:02",
                        "events": [{"state": "succeeded"}],
                        "result": {"account_id": "a-1"},
                        "error": None,
                        "pending_conflict": None,
                    }
                ),
            ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def recv(self) -> str:
            return self._messages.pop(0)

    def ws_connect_factory(url: str, timeout: float):
        calls.append((url, timeout))
        return FakeWebSocketConnection()

    client = BackendClient(
        base_url="http://127.0.0.1:8765",
        ws_connect_factory=ws_connect_factory,
    )

    snapshots = [snapshot async for snapshot in client.watch_task("task-1")]

    assert calls == [("ws://127.0.0.1:8765/ws/tasks/task-1", 30.0)]
    assert [snapshot["state"] for snapshot in snapshots] == [
        "waiting_for_scan",
        "succeeded",
    ]
