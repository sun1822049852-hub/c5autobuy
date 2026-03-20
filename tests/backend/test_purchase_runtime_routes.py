from datetime import datetime, timedelta

import asyncio
from app_backend.domain.models.account import Account
from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseExecutionResult


def _build_account(account_id: str) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
        c5_user_id="10001",
        c5_nick_name="购买账号",
        cookie_raw="NC5_accessToken=token",
        purchase_capability_state="bound",
        purchase_pool_state="not_connected",
        last_login_at="2026-03-16T20:00:00",
        last_error=None,
        created_at="2026-03-16T20:00:00",
        updated_at="2026-03-16T20:00:00",
    )


async def _create_query_config(client, *, name: str = "查询配置A") -> str:
    response = await client.post(
        "/query-configs",
        json={
            "name": name,
            "description": "用于购买运行时",
        },
    )
    return response.json()["config_id"]


async def test_purchase_runtime_status_defaults_to_idle(client):
    response = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    assert response.json() == {
        "running": False,
        "message": "未运行",
        "started_at": None,
        "stopped_at": None,
        "queue_size": 0,
        "active_account_count": 0,
        "total_account_count": 0,
        "total_purchased_count": 0,
        "runtime_session_id": None,
        "active_query_config": None,
        "matched_product_count": 0,
        "purchase_success_count": 0,
        "purchase_failed_count": 0,
        "recent_events": [],
        "accounts": [],
        "item_rows": [],
    }


async def test_start_purchase_runtime_requires_config_id(client):
    response = await client.post("/purchase-runtime/start", json={})

    assert response.status_code == 422


async def test_start_purchase_runtime_returns_running_snapshot_with_selected_config(client, app):
    config_id = await _create_query_config(client)
    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:00:00",
        last_error=None,
    )
    response = await client.post("/purchase-runtime/start", json={"config_id": config_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["running"] is True
    assert payload["message"] == "运行中"
    assert payload["queue_size"] == 0
    assert payload["active_account_count"] == 1
    assert payload["total_account_count"] == 1
    assert payload["total_purchased_count"] == 0
    assert payload["recent_events"] == []
    assert payload["accounts"][0]["account_id"] == "a1"
    assert payload["started_at"] is not None
    assert payload["stopped_at"] is None
    assert payload["active_query_config"] == {
        "config_id": config_id,
        "config_name": "查询配置A",
        "state": "running",
        "message": "运行中",
    }


async def test_stop_purchase_runtime_returns_idle_snapshot(client):
    config_id = await _create_query_config(client)
    await client.post("/purchase-runtime/start", json={"config_id": config_id})

    response = await client.post("/purchase-runtime/stop")

    assert response.status_code == 200
    assert response.json() == {
        "running": False,
        "message": "未运行",
        "started_at": None,
        "stopped_at": None,
        "queue_size": 0,
        "active_account_count": 0,
        "total_account_count": 0,
        "total_purchased_count": 0,
        "runtime_session_id": None,
        "active_query_config": None,
        "matched_product_count": 0,
        "purchase_success_count": 0,
        "purchase_failed_count": 0,
        "recent_events": [],
        "accounts": [],
        "item_rows": [],
    }


async def test_purchase_runtime_settings_routes_are_removed(client):
    get_response = await client.get("/purchase-runtime/settings")
    put_response = await client.put(
        "/purchase-runtime/settings",
        json={"whitelist_account_ids": ["a1"]},
    )

    assert get_response.status_code == 404
    assert put_response.status_code == 404


async def _wait_until_status(client, predicate, *, timeout: float = 1.0, interval: float = 0.01):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get("/purchase-runtime/status")
        if predicate(response.json()):
            return response
        if asyncio.get_running_loop().time() >= deadline:
            return response
        await asyncio.sleep(interval)
async def test_purchase_runtime_end_to_end_handles_hit(client, app):
    class StubExecutionGateway:
        async def execute(self, *, account, batch, selected_steam_id: str):
            return PurchaseExecutionResult.success(purchased_count=1)

    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._execution_gateway_factory = lambda: StubExecutionGateway()
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:00:00",
        last_error=None,
    )
    config_id = await _create_query_config(client)
    await client.post("/purchase-runtime/start", json={"config_id": config_id})

    result = app.state.purchase_runtime_service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )
    response = await _wait_until_status(
        client,
        lambda payload: payload["total_purchased_count"] == 1 and payload["recent_events"][0]["status"] == "success",
    )

    assert result == {"accepted": True, "status": "queued"}
    assert response.status_code == 200
    assert response.json()["queue_size"] == 0
    assert response.json()["total_purchased_count"] == 1
    assert response.json()["recent_events"][0]["status"] == "success"


async def test_purchase_runtime_status_returns_selected_inventory_summary(client, app):
    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:00:00",
        last_error=None,
    )
    config_id = await _create_query_config(client)
    await client.post("/purchase-runtime/start", json={"config_id": config_id})

    response = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["accounts"][0]["selected_steam_id"] == "steam-1"
    assert payload["accounts"][0]["selected_inventory_name"] == "主仓"
    assert payload["accounts"][0]["selected_inventory_remaining_capacity"] == 90
    assert payload["accounts"][0]["selected_inventory_max"] == 1000


async def test_purchase_runtime_status_includes_stats_and_keeps_accounts_shape(client, app):
    class FakePurchaseRuntimeService:
        def get_status(self) -> dict[str, object]:
            return {
                "running": True,
                "message": "运行中",
                "started_at": "2026-03-19T13:00:00",
                "stopped_at": None,
                "queue_size": 0,
                "active_account_count": 1,
                "total_account_count": 1,
                "total_purchased_count": 1,
                "runtime_session_id": "run-1",
                "matched_product_count": 3,
                "purchase_success_count": 1,
                "purchase_failed_count": 2,
                "recent_events": [],
                "accounts": [
                    {
                        "account_id": "a1",
                        "display_name": "购买账号",
                        "purchase_capability_state": "bound",
                        "purchase_pool_state": "active",
                        "selected_steam_id": "steam-1",
                        "selected_inventory_name": "主仓",
                        "selected_inventory_remaining_capacity": 90,
                        "selected_inventory_max": 1000,
                        "last_error": None,
                        "total_purchased_count": 1,
                        "submitted_product_count": 3,
                        "purchase_success_count": 1,
                        "purchase_failed_count": 2,
                    }
                ],
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "matched_product_count": 3,
                        "purchase_success_count": 1,
                        "purchase_failed_count": 2,
                    }
                ],
            }

    class FakeQueryRuntimeService:
        def get_status(self) -> dict[str, object]:
            return {
                "running": False,
                "config_id": "cfg-1",
                "config_name": "查询配置A",
                "message": "等待购买账号恢复",
                "account_count": 0,
                "started_at": None,
                "stopped_at": "2026-03-19T13:00:01",
                "total_query_count": 7,
                "total_found_count": 3,
                "modes": {},
                "group_rows": [],
                "recent_events": [],
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "item_name": "AK-47 | Redline",
                        "max_price": 123.45,
                        "min_wear": 0.1,
                        "max_wear": 0.7,
                        "detail_min_wear": 0.12,
                        "detail_max_wear": 0.3,
                        "manual_paused": False,
                        "query_count": 7,
                        "modes": {},
                    }
                ],
            }

    app.state.purchase_runtime_service = FakePurchaseRuntimeService()
    app.state.query_runtime_service = FakeQueryRuntimeService()

    response = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    assert response.json()["runtime_session_id"] == "run-1"
    assert response.json()["active_query_config"] == {
        "config_id": "cfg-1",
        "config_name": "查询配置A",
        "state": "waiting",
        "message": "等待购买账号恢复",
    }
    assert response.json()["matched_product_count"] == 3
    assert response.json()["purchase_success_count"] == 1
    assert response.json()["purchase_failed_count"] == 2
    assert response.json()["accounts"][0]["submitted_product_count"] == 3
    assert response.json()["accounts"][0]["purchase_success_count"] == 1
    assert response.json()["accounts"][0]["purchase_failed_count"] == 2
    assert response.json()["item_rows"] == [
        {
            "query_item_id": "item-1",
            "item_name": "AK-47 | Redline",
            "max_price": 123.45,
            "min_wear": 0.1,
            "max_wear": 0.7,
            "detail_min_wear": 0.12,
            "detail_max_wear": 0.3,
            "query_execution_count": 7,
            "matched_product_count": 3,
            "purchase_success_count": 1,
            "purchase_failed_count": 2,
        }
    ]


async def test_purchase_runtime_inventory_detail_route_returns_snapshot(client, app):
    account = _build_account("a1")
    account.purchase_recovery_due_at = (datetime.now() + timedelta(seconds=180)).isoformat()
    app.state.account_repository.create_account(account)
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-2",
        inventories=[
            {"steamId": "steam-1", "nickname": "备用仓", "inventory_num": 990, "inventory_max": 1000},
            {"steamId": "steam-2", "nickname": "主仓", "inventory_num": 920, "inventory_max": 1000},
        ],
        refreshed_at="2026-03-16T21:00:00",
        last_error="等待恢复检查",
    )

    response = await client.get("/purchase-runtime/accounts/a1/inventory")

    assert response.status_code == 200
    assert response.json() == {
        "account_id": "a1",
        "display_name": "购买账号",
        "selected_steam_id": "steam-2",
        "refreshed_at": "2026-03-16T21:00:00",
        "last_error": "等待恢复检查",
        "auto_refresh_due_at": account.purchase_recovery_due_at,
        "auto_refresh_remaining_seconds": response.json()["auto_refresh_remaining_seconds"],
        "inventories": [
            {
                "steamId": "steam-1",
                "nickname": "备用仓",
                "inventory_num": 990,
                "inventory_max": 1000,
                "remaining_capacity": 10,
                "is_selected": False,
                "is_available": False,
            },
            {
                "steamId": "steam-2",
                "nickname": "主仓",
                "inventory_num": 920,
                "inventory_max": 1000,
                "remaining_capacity": 80,
                "is_selected": True,
                "is_available": True,
            },
        ],
    }
    assert 0 < response.json()["auto_refresh_remaining_seconds"] <= 180


async def test_purchase_runtime_inventory_refresh_route_returns_latest_detail(client, app):
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[
            {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 900, "inventory_max": 1000},
        ],
        refreshed_at="2026-03-16T21:00:00",
        last_error=None,
    )

    class RefreshGateway:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def refresh(self, *, account):
            self.calls.append({"account_id": account.account_id})
            return InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 800, "inventory_max": 1000},
                ]
            )

    refresh_gateway = RefreshGateway()
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: refresh_gateway

    response = await client.post("/purchase-runtime/accounts/a1/inventory/refresh")

    assert response.status_code == 200
    assert refresh_gateway.calls == [{"account_id": "a1"}]
    assert response.json()["selected_steam_id"] == "steam-1"
    assert response.json()["inventories"][0]["nickname"] == "主仓"
    assert response.json()["inventories"][0]["inventory_num"] == 800
