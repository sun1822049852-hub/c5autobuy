from __future__ import annotations

from app_backend.domain.models.account import Account


def _build_account(
    account_id: str,
    *,
    remark_name: str | None = None,
    c5_nick_name: str | None = None,
    api_key: str | None = None,
    balance_amount: float | None = None,
    balance_source: str | None = None,
    balance_updated_at: str | None = None,
    balance_refresh_after_at: str | None = None,
    balance_last_error: str | None = None,
    purchase_capability_state: str = "bound",
    purchase_pool_state: str = "not_connected",
    purchase_disabled: bool = False,
    purchase_recovery_due_at: str | None = None,
    cookie_raw: str | None = "NC5_accessToken=token",
) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"默认-{account_id}",
        remark_name=remark_name,
        browser_proxy_mode="custom",
        browser_proxy_url=f"http://127.0.0.1:{9000 + len(account_id)}",
        api_proxy_mode="custom",
        api_proxy_url=f"http://127.0.0.1:{9000 + len(account_id)}",
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
        purchase_disabled=purchase_disabled,
        purchase_recovery_due_at=purchase_recovery_due_at,
        balance_amount=balance_amount,
        balance_source=balance_source,
        balance_updated_at=balance_updated_at,
        balance_refresh_after_at=balance_refresh_after_at,
        balance_last_error=balance_last_error,
    )


def _assert_dual_proxy_payload(row: dict, proxy_url: str) -> None:
    assert row["browser_proxy_mode"] == "custom"
    assert row["browser_proxy_url"] == proxy_url
    assert row["browser_proxy_display"] == proxy_url
    assert row["api_proxy_mode"] == "custom"
    assert row["api_proxy_url"] == proxy_url
    assert row["api_proxy_display"] == proxy_url
    assert row["proxy_mode"] == "custom"
    assert row["proxy_url"] == proxy_url
    assert row["proxy_display"] == proxy_url


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
            purchase_disabled=True,
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
        inventories=[{"steamId": "steam-disabled", "nickname": "禁用仓", "inventory_num": 900, "inventory_max": 1000}],
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
        inventories=[{"steamId": "steam-ready", "nickname": "可买主仓", "inventory_num": 900, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:10:00",
        last_error=None,
    )

    response = await client.get("/account-center/accounts")

    assert response.status_code == 200
    rows = response.json()
    assert [row["account_id"] for row in rows] == ["not-login", "disabled", "full", "ready"]
    _assert_dual_proxy_payload(rows[0], "http://127.0.0.1:9009")
    _assert_dual_proxy_payload(rows[1], "http://127.0.0.1:9008")
    _assert_dual_proxy_payload(rows[2], "http://127.0.0.1:9004")
    _assert_dual_proxy_payload(rows[3], "http://127.0.0.1:9005")
    assert rows[0]["purchase_status_code"] == "not_logged_in"
    assert rows[1]["purchase_status_code"] == "disabled"
    assert rows[2]["purchase_status_code"] == "inventory_full"
    assert rows[3]["purchase_status_code"] == "selected_warehouse"
    assert rows[3]["selected_warehouse_text"] == "可买主仓"


async def test_account_center_accounts_route_marks_ip_invalid_api_key(client, app):
    account = _build_account(
        "ip-invalid",
        remark_name="白名单失效账号",
        api_key="api-ip-invalid",
    )
    account.last_error = "API请求失败: 未设置ip白名单或ip不在白名单中, 当前请求ip 39.71.213.149 (代码: 499103)"
    account.new_api_enabled = False
    account.fast_api_enabled = False
    account.api_query_disabled_reason = "ip_invalid"
    app.state.account_repository.create_account(account)

    response = await client.get("/account-center/accounts")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    _assert_dual_proxy_payload(row, "http://127.0.0.1:9010")
    assert row["api_query_disable_reason_code"] == "ip_invalid"
    assert row["api_query_disable_reason_text"] == "IP 不在白名单内，请手动绑定"


async def test_account_center_accounts_route_marks_manual_disabled_api_query(client, app):
    account = _build_account(
        "api-disabled",
        remark_name="API禁用账号",
        api_key="api-manual-disabled",
    )
    account.new_api_enabled = False
    account.fast_api_enabled = False
    account.api_query_disabled_reason = "manual_disabled"
    app.state.account_repository.create_account(account)

    response = await client.get("/account-center/accounts")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    _assert_dual_proxy_payload(row, "http://127.0.0.1:9012")
    assert row["api_query_disable_reason_code"] == "manual_disabled"
    assert row["api_query_disable_reason_text"] == "手动禁用"


async def test_account_center_accounts_route_marks_manual_disabled_browser_query(client, app):
    account = _build_account(
        "browser-disabled",
        remark_name="浏览器禁用账号",
        api_key="api-browser",
    )
    account.token_enabled = False
    account.browser_query_disabled_reason = "manual_disabled"
    app.state.account_repository.create_account(account)

    response = await client.get("/account-center/accounts")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    _assert_dual_proxy_payload(row, "http://127.0.0.1:9016")
    assert row["browser_query_disable_reason_code"] == "manual_disabled"
    assert row["browser_query_disable_reason_text"] == "手动禁用"


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
            {"steamId": "steam-snapshot", "nickname": "快照仓", "inventory_num": 900, "inventory_max": 1000},
            {"steamId": "steam-runtime", "nickname": "运行时主仓", "inventory_num": 800, "inventory_max": 1000},
        ],
        refreshed_at="2026-03-16T20:05:00",
        last_error=None,
    )
    config_response = await client.post(
        "/query-configs",
        json={
            "name": "运行时配置",
            "description": "用于账号中心测试",
        },
    )
    config_id = config_response.json()["config_id"]
    start_response = await client.post("/purchase-runtime/start", json={"config_id": config_id})
    assert start_response.status_code == 200
    runtime = app.state.purchase_runtime_service._runtime
    runtime._account_states["runtime-first"].inventory_state.selected_steam_id = "steam-runtime"

    response = await client.get("/account-center/accounts")

    assert response.status_code == 200
    assert response.json()[0]["selected_steam_id"] == "steam-runtime"
    assert response.json()[0]["selected_warehouse_text"] == "运行时主仓"
    assert response.json()[0]["purchase_status_text"] == "运行时主仓"


async def test_account_center_single_account_route_returns_computed_purchase_status(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "single-ready",
            remark_name="单账号可买",
            c5_nick_name="单账号平台号",
            api_key="api-single-ready",
        )
    )
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="single-ready",
        selected_steam_id="steam-single",
        inventories=[
            {"steamId": "steam-single", "nickname": "单账号主仓", "inventory_num": 860, "inventory_max": 1000},
        ],
        refreshed_at="2026-03-16T20:10:00",
        last_error=None,
    )

    response = await client.get("/account-center/accounts/single-ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == "single-ready"
    assert payload["purchase_status_code"] == "selected_warehouse"
    assert payload["purchase_status_text"] == "单账号主仓"
    assert payload["selected_warehouse_text"] == "单账号主仓"


async def test_account_center_accounts_route_returns_cached_balance_fields(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "balance-ready",
            remark_name="余额账号",
            api_key="api-balance",
            balance_amount=234.56,
            balance_source="openapi",
            balance_updated_at="2026-03-29T12:00:00",
            balance_refresh_after_at="2026-03-29T12:09:00",
            balance_last_error=None,
        )
    )

    response = await client.get("/account-center/accounts")

    assert response.status_code == 200
    row = response.json()[0]
    assert row["balance_amount"] == 234.56
    assert row["balance_source"] == "openapi"
    assert row["balance_updated_at"] == "2026-03-29T12:00:00"
    assert row["balance_refresh_after_at"] == "2026-03-29T12:09:00"
    assert row["balance_last_error"] is None


async def test_update_purchase_config_route_updates_purchase_disabled_and_selected_inventory(client, app):
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
        json={"purchase_disabled": True, "selected_steam_id": "steam-2"},
    )

    assert response.status_code == 200
    assert "disabled" not in response.json()
    assert response.json()["purchase_disabled"] is True
    assert response.json()["selected_steam_id"] == "steam-2"
    assert response.json()["selected_warehouse_text"] == "steam-2"
    assert response.json()["purchase_status_code"] == "disabled"
    assert response.json()["purchase_status_text"] == "禁用"

    stored = app.state.account_repository.get_account("config-target")
    assert stored is not None
    assert stored.purchase_disabled is True

    snapshot = app.state.purchase_runtime_service._inventory_snapshot_repository.get("config-target")
    assert snapshot is not None
    assert snapshot.selected_steam_id == "steam-2"


async def test_update_purchase_config_route_rejects_legacy_disabled_field(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "legacy-disabled",
            remark_name="旧字段账号",
            api_key="api-legacy",
        )
    )

    response = await client.patch(
        "/accounts/legacy-disabled/purchase-config",
        json={"disabled": True, "selected_steam_id": None},
    )

    assert response.status_code == 422


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
        json={"purchase_disabled": False, "selected_steam_id": "steam-1"},
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
        json={"purchase_disabled": False, "selected_steam_id": "steam-full"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "目标仓库不可用，无法选中"


async def test_sync_open_api_binding_route_refreshes_allow_list_and_public_ip(client, app):
    account = _build_account(
        "sync-open-api",
        remark_name="同步白名单账号",
        api_key="api-key-old",
    )
    account.api_ip_allow_list = "1.1.1.1"
    app.state.account_repository.create_account(account)

    service = app.state.open_api_binding_sync_service
    service._public_ip_fetcher = lambda proxy_url: "2.2.2.2"

    response = await client.post("/accounts/sync-open-api/open-api/sync")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key"] == "api-key-old"
    assert payload["api_ip_allow_list"] == "1.1.1.1"
    assert payload["api_public_ip"] == "http://127.0.0.1:9013"


async def test_sync_open_api_binding_route_rejects_not_logged_in_account(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "sync-open-api-no-login",
            remark_name="未登录同步账号",
            cookie_raw=None,
        )
    )

    response = await client.post("/accounts/sync-open-api-no-login/open-api/sync")

    assert response.status_code == 409
    assert response.json()["detail"] == "当前账号未登录，无法同步 API 白名单"


async def test_open_open_api_binding_page_route_rejects_account_without_saved_profile(client, app):
    account = _build_account(
        "open-open-api",
        remark_name="打开绑定页账号",
        api_key="api-key",
    )
    app.state.account_repository.create_account(account)

    response = await client.post("/accounts/open-open-api/open-api/open")

    assert response.status_code == 409
    assert response.json()["detail"] == "当前账号缺少可复用登录会话，请重新登录后再添加白名单"


async def test_open_open_api_binding_page_route_prefers_saved_profile_bundle(client, app):
    account = _build_account(
        "open-open-api-profile",
        remark_name="打开绑定页复用 profile",
        api_key="api-key",
    )
    app.state.account_repository.create_account(account)
    bundle_repository = app.state.account_session_bundle_repository
    staged = bundle_repository.stage_bundle(
        account_id="open-open-api-profile",
        captured_c5_user_id="10001",
        payload={
            "cookie_raw": "NC5_accessToken=token",
            "profile_root": "C:/profiles/open-open-api-profile",
            "profile_directory": "Default",
            "profile_kind": "account",
        },
    )
    bundle_repository.activate_bundle(
        bundle_repository.mark_bundle_verified(staged.bundle_id).bundle_id,
        account_id="open-open-api-profile",
    )

    calls = []

    class FakeLauncher:
        def launch(
            self,
            *,
            account_id: str | None = None,
            profile_root: str | None = None,
            profile_directory: str | None = None,
            login_session_root: str | None = None,
            debugger_address: str | None = None,
            proxy_url: str | None = None,
            sync_service=None,
        ) -> dict[str, object]:
            calls.append(
                {
                    "account_id": account_id,
                    "profile_root": profile_root,
                    "profile_directory": profile_directory,
                    "login_session_root": login_session_root,
                    "debugger_address": debugger_address,
                    "proxy_url": proxy_url,
                    "sync_service": sync_service,
                }
            )
            return {"open_api_url": "https://www.c5game.com/user/user/open-api"}

    app.state.open_api_binding_page_launcher = FakeLauncher()

    response = await client.post("/accounts/open-open-api-profile/open-api/open")

    assert response.status_code == 200
    assert response.json()["launched"] is True
    assert calls[0]["account_id"] == "open-open-api-profile"
    assert calls[0]["profile_root"] == "C:/profiles/open-open-api-profile"
    assert calls[0]["profile_directory"] == "Default"
    assert calls[0]["login_session_root"] is None
    assert calls[0]["debugger_address"] is None
    assert calls[0]["proxy_url"] == "http://127.0.0.1:9021"
    assert calls[0]["sync_service"] is app.state.open_api_binding_sync_service


async def test_open_open_api_binding_page_route_passes_bundle_debugger_address(client, app):
    account = _build_account(
        "open-open-api-live",
        remark_name="打开绑定页复用活跃登录浏览器",
        api_key="api-key",
    )
    app.state.account_repository.create_account(account)
    bundle_repository = app.state.account_session_bundle_repository
    staged = bundle_repository.stage_bundle(
        account_id="open-open-api-live",
        captured_c5_user_id="10001",
        payload={
            "cookie_raw": "NC5_accessToken=token",
            "profile_root": "C:/profiles/open-open-api-live",
            "profile_directory": "Default",
            "profile_kind": "account",
            "login_session_root": "C:/sessions/login-open-open-api-live",
            "debugger_address": "127.0.0.1:9555",
        },
    )
    bundle_repository.activate_bundle(
        bundle_repository.mark_bundle_verified(staged.bundle_id).bundle_id,
        account_id="open-open-api-live",
    )

    calls = []

    class FakeLauncher:
        def launch(
            self,
            *,
            account_id: str | None = None,
            profile_root: str | None = None,
            profile_directory: str | None = None,
            login_session_root: str | None = None,
            debugger_address: str | None = None,
            proxy_url: str | None = None,
            sync_service=None,
        ) -> dict[str, object]:
            calls.append(
                {
                    "account_id": account_id,
                    "profile_root": profile_root,
                    "profile_directory": profile_directory,
                    "login_session_root": login_session_root,
                    "debugger_address": debugger_address,
                    "proxy_url": proxy_url,
                    "sync_service": sync_service,
                }
            )
            return {"open_api_url": "https://www.c5game.com/user/user/open-api"}

    app.state.open_api_binding_page_launcher = FakeLauncher()

    response = await client.post("/accounts/open-open-api-live/open-api/open")

    assert response.status_code == 200
    assert response.json()["launched"] is True
    assert calls[0]["account_id"] == "open-open-api-live"
    assert calls[0]["profile_root"] == "C:/profiles/open-open-api-live"
    assert calls[0]["profile_directory"] == "Default"
    assert calls[0]["login_session_root"] == "C:/sessions/login-open-open-api-live"
    assert calls[0]["debugger_address"] == "127.0.0.1:9555"


async def test_open_open_api_binding_page_route_rejects_not_logged_in_account(client, app):
    app.state.account_repository.create_account(
        _build_account(
            "open-open-api-no-login",
            remark_name="未登录打开绑定页账号",
            cookie_raw=None,
        )
    )

    response = await client.post("/accounts/open-open-api-no-login/open-api/open")

    assert response.status_code == 409
    assert response.json()["detail"] == "当前账号缺少可复用登录会话，请重新登录后再添加白名单"
