from __future__ import annotations

import asyncio
from datetime import datetime

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult
from app_backend.infrastructure.browser_runtime.login_adapter import LoginCapture


class _NoopAccountBalanceService:
    async def refresh_after_login(self, account_id: str, *, wait_for_api_key: bool = True) -> dict:
        return {"account_id": account_id, "wait_for_api_key": wait_for_api_key}



async def _wait_for_task(client, task_id: str, target_state: str) -> dict:
    for _ in range(50):
        response = await client.get(f"/tasks/{task_id}")
        payload = response.json()
        if payload["state"] == target_state:
            return payload
        await asyncio.sleep(0.02)
    raise AssertionError(f"任务 {task_id} 未进入状态 {target_state}")


class _RecordingRefreshGateway:
    def __init__(self, result: InventoryRefreshResult | Exception) -> None:
        self._result = result
        self.calls: list[dict[str, str | None]] = []

    async def refresh(self, *, account):
        self.calls.append(
            {
                "account_id": account.account_id,
                "cookie_raw": account.cookie_raw,
            }
        )
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _RecordingOpenApiBindingSyncService:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    def schedule_account_watch(
        self,
        account_id: str,
        debugger_address: str | None = None,
        source_account_id: str | None = None,
        source_api_key: str | None = None,
    ) -> None:
        self.calls.append(
            {
                "account_id": account_id,
                "debugger_address": debugger_address,
                "source_account_id": source_account_id,
                "source_api_key": source_api_key,
            }
        )


async def _create_account(client, *, remark_name: str, proxy_mode: str = "custom", proxy_url: str | None = None, api_key: str | None = None) -> dict:
    response = await client.post(
        "/accounts",
        json={
            "remark_name": remark_name,
            "browser_proxy_mode": proxy_mode,
            "browser_proxy_url": proxy_url,
            "api_proxy_mode": "direct",
            "api_proxy_url": None,
            "api_key": api_key,
        },
    )
    return response.json()


def _bind_existing_account(app, account_id: str, *, c5_user_id: str, c5_nick_name: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    app.state.account_repository.update_account(
        account_id,
        c5_user_id=c5_user_id,
        c5_nick_name=c5_nick_name,
        cookie_raw="old=cookie",
        purchase_capability_state=PurchaseCapabilityState.BOUND,
        purchase_pool_state=PurchasePoolState.NOT_CONNECTED,
        last_login_at=now,
        updated_at=now,
    )


async def test_login_task_with_same_c5_user_updates_existing_account(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="10001",
                c5_nick_name="同账号新昵称",
                cookie_raw="new=same-user",
            )

    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    account = await _create_account(
        client,
        remark_name="原账号",
        proxy_url="http://127.0.0.1:9001",
        api_key="api-old",
    )
    _bind_existing_account(app, account["account_id"], c5_user_id="10001", c5_nick_name="旧昵称")

    start_response = await client.post(f"/accounts/{account['account_id']}/login")
    task_payload = await _wait_for_task(client, start_response.json()["task_id"], "succeeded")

    account_response = await client.get(f"/accounts/{account['account_id']}")
    account_payload = account_response.json()
    active_bundle = app.state.account_session_bundle_repository.get_active_bundle(account["account_id"])
    assert task_payload["state"] == "succeeded"
    assert account_payload["account_id"] == account["account_id"]
    assert account_payload["remark_name"] == "原账号"
    assert account_payload["browser_proxy_url"] == "http://127.0.0.1:9001"
    assert account_payload["api_key"] == "api-old"
    assert account_payload["c5_user_id"] == "10001"
    assert account_payload["c5_nick_name"] == "同账号新昵称"
    assert account_payload["cookie_raw"] == "new=same-user"
    assert active_bundle is not None
    assert active_bundle.payload["cookie_raw"] == "new=same-user"


async def test_login_task_enters_conflict_state_for_different_c5_user(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="20002",
                c5_nick_name="冲突账号",
                cookie_raw="new=conflict",
            )

    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    account = await _create_account(
        client,
        remark_name="旧账号",
        proxy_url="http://127.0.0.1:9002",
        api_key="api-conflict",
    )
    _bind_existing_account(app, account["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")

    start_response = await client.post(f"/accounts/{account['account_id']}/login")
    task_payload = await _wait_for_task(client, start_response.json()["task_id"], "conflict")
    bundle_ref = task_payload["pending_conflict"]["bundle_ref"]
    staged_bundle = app.state.account_session_bundle_repository.get_bundle(bundle_ref["bundle_id"])

    assert task_payload["pending_conflict"]["account_id"] == account["account_id"]
    assert task_payload["pending_conflict"]["existing_c5_user_id"] == "10001"
    assert task_payload["pending_conflict"]["captured_login"]["c5_user_id"] == "20002"
    assert app.state.account_session_bundle_repository.get_active_bundle(account["account_id"]) is None
    assert staged_bundle is not None
    assert staged_bundle.state.value == "verified"
    assert task_payload["pending_conflict"]["actions"] == [
        "create_new_account",
        "replace_with_new_account",
        "cancel",
    ]


async def test_resolve_login_conflict_create_new_account_keeps_old_account(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="30003",
                c5_nick_name="新增账号",
                cookie_raw="new=create",
            )

    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    account = await _create_account(
        client,
        remark_name="保留旧账号",
        proxy_url="http://127.0.0.1:9003",
        api_key="api-keep",
    )
    _bind_existing_account(app, account["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")

    start_response = await client.post(f"/accounts/{account['account_id']}/login")
    conflict_payload = await _wait_for_task(client, start_response.json()["task_id"], "conflict")

    resolve_response = await client.post(
        f"/accounts/{account['account_id']}/login/resolve",
        json={
            "task_id": conflict_payload["task_id"],
            "action": "create_new_account",
        },
    )

    assert resolve_response.status_code == 200
    resolved_task = resolve_response.json()
    assert resolved_task["state"] == "succeeded"
    bundle_id = conflict_payload["pending_conflict"]["bundle_ref"]["bundle_id"]

    accounts_response = await client.get("/accounts")
    accounts_payload = accounts_response.json()
    assert len(accounts_payload) == 2

    old_account = next(item for item in accounts_payload if item["account_id"] == account["account_id"])
    new_account = next(item for item in accounts_payload if item["account_id"] != account["account_id"])
    assert old_account["remark_name"] == "保留旧账号"
    assert old_account["browser_proxy_url"] == "http://127.0.0.1:9003"
    assert old_account["api_key"] == "api-keep"
    assert old_account["c5_user_id"] == "10001"

    assert new_account["remark_name"] is None
    assert new_account["browser_proxy_mode"] == "direct"
    assert new_account["browser_proxy_url"] is None
    assert new_account["api_key"] is None
    assert new_account["c5_user_id"] == "30003"
    assert new_account["c5_nick_name"] == "新增账号"
    assert new_account["cookie_raw"] == "new=create"
    active_bundle = app.state.account_session_bundle_repository.get_active_bundle(new_account["account_id"])
    assert active_bundle is not None
    assert active_bundle.bundle_id == bundle_id


async def test_resolve_login_conflict_cancel_discards_staged_bundle(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="35555",
                c5_nick_name="取消账号",
                cookie_raw="new=cancel",
            )

    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    account = await _create_account(
        client,
        remark_name="取消旧账号",
        proxy_url="http://127.0.0.1:9055",
        api_key="api-cancel",
    )
    _bind_existing_account(app, account["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")

    start_response = await client.post(f"/accounts/{account['account_id']}/login")
    conflict_payload = await _wait_for_task(client, start_response.json()["task_id"], "conflict")
    bundle_id = conflict_payload["pending_conflict"]["bundle_ref"]["bundle_id"]

    resolve_response = await client.post(
        f"/accounts/{account['account_id']}/login/resolve",
        json={
            "task_id": conflict_payload["task_id"],
            "action": "cancel",
        },
    )

    assert resolve_response.status_code == 200
    assert resolve_response.json()["state"] == "cancelled"
    deleted_bundle = app.state.account_session_bundle_repository.get_bundle(bundle_id)
    assert deleted_bundle is not None
    assert deleted_bundle.state.value == "deleted"


async def test_resolve_login_conflict_create_new_account_refreshes_inventory_when_token_present(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="30030",
                c5_nick_name="新增带 token 账号",
                cookie_raw="foo=bar; NC5_accessToken=token-30; NC5_deviceId=device-30",
            )

    refresh_gateway = _RecordingRefreshGateway(
        InventoryRefreshResult.success(
            inventories=[
                {"steamId": "steam-30", "nickname": "主仓", "inventory_num": 870, "inventory_max": 1000},
            ]
        )
    )
    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: refresh_gateway
    account = await _create_account(
        client,
        remark_name="保留旧账号",
        proxy_url="http://127.0.0.1:9013",
        api_key="api-keep",
    )
    _bind_existing_account(app, account["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")

    start_response = await client.post(f"/accounts/{account['account_id']}/login")
    conflict_payload = await _wait_for_task(client, start_response.json()["task_id"], "conflict")

    resolve_response = await client.post(
        f"/accounts/{account['account_id']}/login/resolve",
        json={
            "task_id": conflict_payload["task_id"],
            "action": "create_new_account",
        },
    )

    assert resolve_response.status_code == 200
    resolved_task = resolve_response.json()
    new_account_id = resolved_task["result"]["account_id"]
    assert refresh_gateway.calls == [
        {
            "account_id": new_account_id,
            "cookie_raw": "foo=bar; NC5_accessToken=token-30; NC5_deviceId=device-30",
        }
    ]
    snapshot = app.state.purchase_runtime_service._inventory_snapshot_repository.get(new_account_id)
    assert snapshot is not None
    assert snapshot.inventories[0]["steamId"] == "steam-30"


async def test_resolve_login_conflict_replace_with_new_account_recreates_account(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="40004",
                c5_nick_name="替换账号",
                cookie_raw="new=replace",
            )

    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    account = await _create_account(
        client,
        remark_name="将被替换",
        proxy_url="http://127.0.0.1:9004",
        api_key="api-replace",
    )
    _bind_existing_account(app, account["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")

    start_response = await client.post(f"/accounts/{account['account_id']}/login")
    conflict_payload = await _wait_for_task(client, start_response.json()["task_id"], "conflict")

    resolve_response = await client.post(
        f"/accounts/{account['account_id']}/login/resolve",
        json={
            "task_id": conflict_payload["task_id"],
            "action": "replace_with_new_account",
        },
    )

    assert resolve_response.status_code == 200
    resolved_task = resolve_response.json()
    assert resolved_task["state"] == "succeeded"

    accounts_response = await client.get("/accounts")
    accounts_payload = accounts_response.json()
    assert len(accounts_payload) == 1

    new_account = accounts_payload[0]
    assert new_account["account_id"] != account["account_id"]
    assert new_account["remark_name"] is None
    assert new_account["browser_proxy_mode"] == "direct"
    assert new_account["browser_proxy_url"] is None
    assert new_account["api_key"] is None
    assert new_account["c5_user_id"] == "40004"
    assert new_account["c5_nick_name"] == "替换账号"
    assert new_account["cookie_raw"] == "new=replace"


async def test_resolve_login_conflict_replace_with_new_account_deletes_old_active_bundle(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="40014",
                c5_nick_name="替换账号",
                cookie_raw="new=replace-bundle",
            )

    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    account = await _create_account(
        client,
        remark_name="将被替换",
        proxy_url="http://127.0.0.1:9044",
        api_key="api-replace",
    )
    _bind_existing_account(app, account["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")
    old_bundle_repo = app.state.account_session_bundle_repository
    old_bundle = old_bundle_repo.activate_bundle(
        old_bundle_repo.mark_bundle_verified(
            old_bundle_repo.stage_bundle(
                account_id=account["account_id"],
                captured_c5_user_id="10001",
                payload={"cookie_raw": "old=bundle"},
            ).bundle_id
        ).bundle_id,
        account_id=account["account_id"],
    )

    start_response = await client.post(f"/accounts/{account['account_id']}/login")
    conflict_payload = await _wait_for_task(client, start_response.json()["task_id"], "conflict")
    new_bundle_id = conflict_payload["pending_conflict"]["bundle_ref"]["bundle_id"]

    resolve_response = await client.post(
        f"/accounts/{account['account_id']}/login/resolve",
        json={
            "task_id": conflict_payload["task_id"],
            "action": "replace_with_new_account",
        },
    )

    assert resolve_response.status_code == 200
    new_account_id = resolve_response.json()["result"]["account_id"]
    deleted_old_bundle = old_bundle_repo.get_bundle(old_bundle.bundle_id)
    active_bundle = old_bundle_repo.get_active_bundle(new_account_id)
    assert deleted_old_bundle is not None
    assert deleted_old_bundle.state.value == "deleted"
    assert active_bundle is not None
    assert active_bundle.bundle_id == new_bundle_id


async def test_resolve_login_conflict_replace_with_new_account_keeps_success_when_inventory_refresh_fails(
    app,
    client,
):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="40040",
                c5_nick_name="替换带 token 账号",
                cookie_raw="foo=bar; NC5_accessToken=token-40; NC5_deviceId=device-40",
            )

    refresh_gateway = _RecordingRefreshGateway(RuntimeError("inventory refresh boom"))
    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: refresh_gateway
    account = await _create_account(
        client,
        remark_name="将被替换",
        proxy_url="http://127.0.0.1:9014",
        api_key="api-replace",
    )
    _bind_existing_account(app, account["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")

    start_response = await client.post(f"/accounts/{account['account_id']}/login")
    conflict_payload = await _wait_for_task(client, start_response.json()["task_id"], "conflict")

    resolve_response = await client.post(
        f"/accounts/{account['account_id']}/login/resolve",
        json={
            "task_id": conflict_payload["task_id"],
            "action": "replace_with_new_account",
        },
    )

    assert resolve_response.status_code == 200
    resolved_task = resolve_response.json()
    new_account_id = resolved_task["result"]["account_id"]
    assert resolved_task["state"] == "succeeded"
    assert refresh_gateway.calls == [
        {
            "account_id": new_account_id,
            "cookie_raw": "foo=bar; NC5_accessToken=token-40; NC5_deviceId=device-40",
        }
    ]


async def test_login_task_on_regular_new_account_routes_to_existing_c5_account_when_existing_match_found(
    app,
    client,
):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None, account_id=None):
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return {
                "c5_user_id": "10001",
                "c5_nick_name": "重复登录账号",
                "cookie_raw": "foo=bar; NC5_accessToken=token-dup; NC5_deviceId=device-dup",
            }

    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()

    existing = await _create_account(
        client,
        remark_name="老账号",
        proxy_mode="custom",
        proxy_url="http://127.0.0.1:9101",
        api_key="api-old",
    )
    _bind_existing_account(app, existing["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")

    source = await _create_account(
        client,
        remark_name="新建空账号",
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
    )

    start_response = await client.post(f"/accounts/{source['account_id']}/login")
    task_payload = await _wait_for_task(client, start_response.json()["task_id"], "succeeded")

    assert task_payload["result"]["account_id"] == existing["account_id"]

    existing_response = await client.get(f"/accounts/{existing['account_id']}")
    existing_payload = existing_response.json()
    assert existing_payload["remark_name"] == "老账号"
    assert existing_payload["browser_proxy_url"] == "http://127.0.0.1:9101"
    assert existing_payload["api_key"] == "api-old"
    assert existing_payload["c5_user_id"] == "10001"
    assert existing_payload["c5_nick_name"] == "重复登录账号"
    assert existing_payload["cookie_raw"] == "foo=bar; NC5_accessToken=token-dup; NC5_deviceId=device-dup"

    source_response = await client.get(f"/accounts/{source['account_id']}")
    source_payload = source_response.json()
    assert source_payload["remark_name"] == "新建空账号"
    assert source_payload["browser_proxy_mode"] == "direct"
    assert source_payload["browser_proxy_url"] is None
    assert source_payload["api_key"] is None
    assert source_payload["c5_user_id"] is None
    assert source_payload["c5_nick_name"] is None
    assert source_payload["cookie_raw"] is None

    active_bundle = app.state.account_session_bundle_repository.get_active_bundle(existing["account_id"])
    assert active_bundle is not None
    assert active_bundle.bundle_id == task_payload["result"]["bundle_id"]


async def test_login_task_on_api_only_account_routes_to_existing_c5_account_and_keeps_old_account_config(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None, account_id=None):
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return {
                "c5_user_id": "10001",
                "c5_nick_name": "命中老账号",
                "cookie_raw": "foo=bar; NC5_accessToken=token-merge; NC5_deviceId=device-merge",
                "debugger_address": "127.0.0.1:9222",
            }

    refresh_gateway = _RecordingRefreshGateway(
        InventoryRefreshResult.success(
            inventories=[
                {"steamId": "steam-merge", "nickname": "新仓", "inventory_num": 0, "inventory_max": 1000},
            ]
        )
    )
    watch_service = _RecordingOpenApiBindingSyncService()
    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: refresh_gateway
    app.state.open_api_binding_sync_service = watch_service

    existing = await _create_account(
        client,
        remark_name="老账号",
        proxy_mode="custom",
        proxy_url="http://127.0.0.1:9101",
        api_key="api-old",
    )
    _bind_existing_account(app, existing["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")

    source = await _create_account(
        client,
        remark_name="API only 来源",
        proxy_mode="custom",
        proxy_url="http://127.0.0.1:9301",
        api_key="api-source",
    )
    await client.patch(
        f"/accounts/{source['account_id']}/query-modes",
        json={
            "browser_query_enabled": False,
            "browser_query_disabled_reason": "manual_disabled",
        },
    )

    start_response = await client.post(f"/accounts/{source['account_id']}/login")
    task_payload = await _wait_for_task(client, start_response.json()["task_id"], "succeeded")

    assert task_payload["result"]["account_id"] == existing["account_id"]
    assert app.state.account_repository.get_account(source["account_id"]) is not None

    existing_response = await client.get(f"/accounts/{existing['account_id']}")
    payload = existing_response.json()
    assert payload["remark_name"] == "老账号"
    assert payload["browser_proxy_url"] == "http://127.0.0.1:9101"
    assert payload["api_proxy_url"] == "http://127.0.0.1:9101"
    assert payload["api_key"] == "api-old"
    assert payload["token_enabled"] is True
    assert payload["browser_query_disabled_reason"] is None
    assert payload["c5_user_id"] == "10001"
    assert payload["c5_nick_name"] == "命中老账号"
    assert payload["cookie_raw"] == "foo=bar; NC5_accessToken=token-merge; NC5_deviceId=device-merge"

    active_bundle = app.state.account_session_bundle_repository.get_active_bundle(existing["account_id"])
    assert active_bundle is not None
    assert active_bundle.bundle_id == task_payload["result"]["bundle_id"]
    assert watch_service.calls == [
        {
            "account_id": existing["account_id"],
            "debugger_address": "127.0.0.1:9222",
            "source_account_id": source["account_id"],
            "source_api_key": "api-source",
        }
    ]
    assert refresh_gateway.calls == [
        {
            "account_id": existing["account_id"],
            "cookie_raw": "foo=bar; NC5_accessToken=token-merge; NC5_deviceId=device-merge",
        }
    ]

    snapshot = app.state.purchase_runtime_service._inventory_snapshot_repository.get(existing["account_id"])
    assert snapshot is not None
    assert snapshot.selected_steam_id == "steam-merge"


async def test_login_task_on_api_only_account_creates_new_logged_in_account_without_inheriting_source_config(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None, account_id=None):
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return {
                "c5_user_id": "50005",
                "c5_nick_name": "新增登录账号",
                "cookie_raw": "foo=bar; NC5_accessToken=token-new; NC5_deviceId=device-new",
                "debugger_address": "127.0.0.1:9222",
            }

    refresh_gateway = _RecordingRefreshGateway(
        InventoryRefreshResult.success(
            inventories=[
                {"steamId": "steam-new", "nickname": "新仓", "inventory_num": 0, "inventory_max": 1000},
            ]
        )
    )
    watch_service = _RecordingOpenApiBindingSyncService()
    app.state.login_adapter = FakeLoginAdapter()
    app.state.account_balance_service = _NoopAccountBalanceService()
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: refresh_gateway
    app.state.open_api_binding_sync_service = watch_service

    source = await _create_account(
        client,
        remark_name="API only 来源",
        proxy_mode="custom",
        proxy_url="http://127.0.0.1:9401",
        api_key="api-source",
    )
    await client.patch(
        f"/accounts/{source['account_id']}/query-modes",
        json={
            "browser_query_enabled": False,
            "browser_query_disabled_reason": "manual_disabled",
        },
    )

    start_response = await client.post(f"/accounts/{source['account_id']}/login")
    task_payload = await _wait_for_task(client, start_response.json()["task_id"], "succeeded")

    new_account_id = task_payload["result"]["account_id"]
    assert new_account_id != source["account_id"]
    assert app.state.account_repository.get_account(source["account_id"]) is not None

    accounts_response = await client.get("/accounts")
    accounts = accounts_response.json()
    assert len(accounts) == 2
    payload = next(item for item in accounts if item["account_id"] == new_account_id)
    assert payload["account_id"] == new_account_id
    assert payload["remark_name"] is None
    assert payload["browser_proxy_url"] is None
    assert payload["api_proxy_url"] is None
    assert payload["api_key"] is None
    assert payload["token_enabled"] is True
    assert payload["browser_query_disabled_reason"] is None
    assert payload["c5_user_id"] == "50005"
    assert payload["c5_nick_name"] == "新增登录账号"

    active_bundle = app.state.account_session_bundle_repository.get_active_bundle(new_account_id)
    assert active_bundle is not None
    assert active_bundle.bundle_id == task_payload["result"]["bundle_id"]
    assert watch_service.calls == [
        {
            "account_id": new_account_id,
            "debugger_address": "127.0.0.1:9222",
            "source_account_id": source["account_id"],
            "source_api_key": "api-source",
        }
    ]
    assert refresh_gateway.calls == [
        {
            "account_id": new_account_id,
            "cookie_raw": "foo=bar; NC5_accessToken=token-new; NC5_deviceId=device-new",
        }
    ]

    snapshot = app.state.purchase_runtime_service._inventory_snapshot_repository.get(new_account_id)
    assert snapshot is not None
    assert snapshot.selected_steam_id == "steam-new"

