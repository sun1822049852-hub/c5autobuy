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
        disabled=False,
    )


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
        "recent_events": [],
        "accounts": [],
        "settings": {
            "whitelist_account_ids": [],
            "updated_at": None,
        },
    }


async def test_start_purchase_runtime_returns_running_snapshot(client):
    response = await client.post("/purchase-runtime/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["running"] is True
    assert payload["message"] == "运行中"
    assert payload["queue_size"] == 0
    assert payload["active_account_count"] == 0
    assert payload["total_account_count"] == 0
    assert payload["total_purchased_count"] == 0
    assert payload["recent_events"] == []
    assert payload["accounts"] == []
    assert payload["started_at"] is not None
    assert payload["stopped_at"] is None
    assert payload["settings"] == {
        "whitelist_account_ids": [],
        "updated_at": None,
    }


async def test_stop_purchase_runtime_returns_idle_snapshot(client):
    await client.post("/purchase-runtime/start")

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
        "recent_events": [],
        "accounts": [],
        "settings": {
            "whitelist_account_ids": [],
            "updated_at": None,
        },
    }


async def test_purchase_runtime_settings_routes_update_whitelist(client):
    update_response = await client.put(
        "/purchase-runtime/settings",
        json={
            "whitelist_account_ids": ["a1"],
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["settings"]["whitelist_account_ids"] == ["a1"]
    assert payload["settings"]["updated_at"] is not None

    get_response = await client.get("/purchase-runtime/settings")

    assert get_response.status_code == 200
    assert get_response.json() == payload["settings"]


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
    await client.post("/purchase-runtime/start")

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
    response = await client.get("/purchase-runtime/status")

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
        inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:00:00",
        last_error=None,
    )
    await client.post("/purchase-runtime/start")

    response = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["accounts"][0]["selected_steam_id"] == "steam-1"
    assert payload["accounts"][0]["selected_inventory_remaining_capacity"] == 90
    assert payload["accounts"][0]["selected_inventory_max"] == 1000


async def test_purchase_runtime_inventory_detail_route_returns_snapshot(client, app):
    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-2",
        inventories=[
            {"steamId": "steam-1", "inventory_num": 990, "inventory_max": 1000},
            {"steamId": "steam-2", "inventory_num": 920, "inventory_max": 1000},
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
        "inventories": [
            {
                "steamId": "steam-1",
                "inventory_num": 990,
                "inventory_max": 1000,
                "remaining_capacity": 10,
                "is_selected": False,
                "is_available": False,
            },
            {
                "steamId": "steam-2",
                "inventory_num": 920,
                "inventory_max": 1000,
                "remaining_capacity": 80,
                "is_selected": True,
                "is_available": True,
            },
        ],
    }
