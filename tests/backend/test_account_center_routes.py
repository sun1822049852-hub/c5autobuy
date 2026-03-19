from __future__ import annotations

from app_backend.domain.models.account import Account


def _build_account(
    account_id: str,
    *,
    remark_name: str | None = None,
    c5_nick_name: str | None = None,
    api_key: str | None = None,
    purchase_capability_state: str = "bound",
    purchase_pool_state: str = "not_connected",
    disabled: bool = False,
    cookie_raw: str | None = "NC5_accessToken=token",
) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"默认-{account_id}",
        remark_name=remark_name,
        proxy_mode="custom",
        proxy_url=f"http://127.0.0.1:{9000 + len(account_id)}",
        api_key=api_key,
        c5_user_id="10001" if cookie_raw else None,
        c5_nick_name=c5_nick_name,
        cookie_raw=cookie_raw,
        purchase_capability_state=purchase_capability_state,
        purchase_pool_state=purchase_pool_state,
        last_login_at="2026-03-16T20:00:00" if cookie_raw else None,
        last_error=None,
        created_at="2026-03-16T20:00:00",
        updated_at="2026-03-16T20:00:00",
        disabled=disabled,
    )


async def test_account_center_accounts_route_renders_purchase_status_priority(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "not-login",
            remark_name="未登录账号",
            purchase_capability_state="unbound",
            purchase_pool_state="not_connected",
            cookie_raw=None,
        )
    )
    app.state.account_repository.create_account(
        _build_account(
            "disabled",
            remark_name="禁用账号",
            c5_nick_name="平台禁用号",
            api_key="api-disabled",
            disabled=True,
        )
    )
    app.state.account_repository.create_account(
        _build_account(
            "full",
            remark_name="满仓账号",
            purchase_pool_state="paused_no_inventory",
        )
    )
    app.state.account_repository.create_account(
        _build_account(
            "ready",
            remark_name="可买账号",
            c5_nick_name="平台可买号",
            api_key="api-ready",
        )
    )
    snapshot_repo = app.state.purchase_runtime_service._inventory_snapshot_repository
    snapshot_repo.save(
        account_id="disabled",
        selected_steam_id="steam-disabled",
        inventories=[{"steamId": "steam-disabled", "inventory_num": 900, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:10:00",
        last_error=None,
    )
    snapshot_repo.save(
        account_id="full",
        selected_steam_id=None,
        inventories=[{"steamId": "steam-full", "inventory_num": 995, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:10:00",
        last_error="没有可用仓库",
    )
    snapshot_repo.save(
        account_id="ready",
        selected_steam_id="steam-ready",
        inventories=[{"steamId": "steam-ready", "inventory_num": 900, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:10:00",
        last_error=None,
    )

    response = await client.get("/account-center/accounts")

    assert response.status_code == 200
    assert response.json() == [
        {
            "account_id": "not-login",
            "display_name": "未登录账号",
            "remark_name": "未登录账号",
            "c5_nick_name": None,
            "default_name": "默认-not-login",
            "api_key_present": False,
            "api_key": None,
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:9009",
            "proxy_display": "http://127.0.0.1:9009",
            "purchase_capability_state": "unbound",
            "purchase_pool_state": "not_connected",
            "disabled": False,
            "selected_steam_id": None,
            "selected_warehouse_text": None,
            "purchase_status_code": "not_logged_in",
            "purchase_status_text": "未登录",
        },
        {
            "account_id": "disabled",
            "display_name": "禁用账号",
            "remark_name": "禁用账号",
            "c5_nick_name": "平台禁用号",
            "default_name": "默认-disabled",
            "api_key_present": True,
            "api_key": "api-disabled",
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:9008",
            "proxy_display": "http://127.0.0.1:9008",
            "purchase_capability_state": "bound",
            "purchase_pool_state": "not_connected",
            "disabled": True,
            "selected_steam_id": "steam-disabled",
            "selected_warehouse_text": "steam-disabled",
            "purchase_status_code": "disabled",
            "purchase_status_text": "禁用",
        },
        {
            "account_id": "full",
            "display_name": "满仓账号",
            "remark_name": "满仓账号",
            "c5_nick_name": None,
            "default_name": "默认-full",
            "api_key_present": False,
            "api_key": None,
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:9004",
            "proxy_display": "http://127.0.0.1:9004",
            "purchase_capability_state": "bound",
            "purchase_pool_state": "paused_no_inventory",
            "disabled": False,
            "selected_steam_id": None,
            "selected_warehouse_text": None,
            "purchase_status_code": "inventory_full",
            "purchase_status_text": "库存已满",
        },
        {
            "account_id": "ready",
            "display_name": "可买账号",
            "remark_name": "可买账号",
            "c5_nick_name": "平台可买号",
            "default_name": "默认-ready",
            "api_key_present": True,
            "api_key": "api-ready",
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:9005",
            "proxy_display": "http://127.0.0.1:9005",
            "purchase_capability_state": "bound",
            "purchase_pool_state": "not_connected",
            "disabled": False,
            "selected_steam_id": "steam-ready",
            "selected_warehouse_text": "steam-ready",
            "purchase_status_code": "selected_warehouse",
            "purchase_status_text": "steam-ready",
        },
    ]


async def test_account_center_accounts_route_prefers_runtime_selected_inventory_over_snapshot(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "runtime-first",
            remark_name="运行时优先账号",
            api_key="api-runtime",
        )
    )
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="runtime-first",
        selected_steam_id="steam-snapshot",
        inventories=[
            {"steamId": "steam-snapshot", "inventory_num": 900, "inventory_max": 1000},
            {"steamId": "steam-runtime", "inventory_num": 800, "inventory_max": 1000},
        ],
        refreshed_at="2026-03-16T20:05:00",
        last_error=None,
    )
    start_response = await client.post("/purchase-runtime/start")
    assert start_response.status_code == 200
    runtime = app.state.purchase_runtime_service._runtime
    runtime._account_states["runtime-first"].inventory_state.selected_steam_id = "steam-runtime"

    response = await client.get("/account-center/accounts")

    assert response.status_code == 200
    assert response.json()[0]["selected_steam_id"] == "steam-runtime"
    assert response.json()[0]["selected_warehouse_text"] == "steam-runtime"
    assert response.json()[0]["purchase_status_text"] == "steam-runtime"


async def test_update_purchase_config_route_updates_disabled_and_selected_inventory(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "config-target",
            remark_name="配置目标",
            api_key="api-config",
        )
    )
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="config-target",
        selected_steam_id="steam-1",
        inventories=[
            {"steamId": "steam-1", "inventory_num": 900, "inventory_max": 1000},
            {"steamId": "steam-2", "inventory_num": 800, "inventory_max": 1000},
        ],
        refreshed_at="2026-03-16T20:05:00",
        last_error=None,
    )

    response = await client.patch(
        "/accounts/config-target/purchase-config",
        json={"disabled": True, "selected_steam_id": "steam-2"},
    )

    assert response.status_code == 200
    assert response.json()["disabled"] is True
    assert response.json()["selected_steam_id"] == "steam-2"
    assert response.json()["selected_warehouse_text"] == "steam-2"
    assert response.json()["purchase_status_code"] == "disabled"
    assert response.json()["purchase_status_text"] == "禁用"

    snapshot = app.state.purchase_runtime_service._inventory_snapshot_repository.get("config-target")
    assert snapshot is not None
    assert snapshot.selected_steam_id == "steam-2"


async def test_update_purchase_config_route_rejects_selected_inventory_for_unbound_account(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "not-bound",
            remark_name="未绑定账号",
            purchase_capability_state="unbound",
            purchase_pool_state="not_connected",
            cookie_raw=None,
        )
    )
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="not-bound",
        selected_steam_id=None,
        inventories=[{"steamId": "steam-1", "inventory_num": 800, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:05:00",
        last_error=None,
    )

    response = await client.patch(
        "/accounts/not-bound/purchase-config",
        json={"disabled": False, "selected_steam_id": "steam-1"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "当前账号未登录，无法设置购买仓库"


async def test_update_purchase_config_route_rejects_unavailable_inventory(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "full-only",
            remark_name="满仓校验账号",
            api_key="api-full-only",
        )
    )
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="full-only",
        selected_steam_id=None,
        inventories=[{"steamId": "steam-full", "inventory_num": 995, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:05:00",
        last_error="没有可用仓库",
    )

    response = await client.patch(
        "/accounts/full-only/purchase-config",
        json={"disabled": False, "selected_steam_id": "steam-full"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "目标仓库不可用，无法选中"
