from __future__ import annotations

import asyncio

from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult
from app_backend.infrastructure.selenium.login_adapter import LoginCapture


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


async def test_login_task_binds_purchase_capability_and_persists_account(app, client):
    class FakeLoginAdapter:
        def __init__(self) -> None:
            self.received_proxy_url: str | None = None

        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            self.received_proxy_url = proxy_url
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="90001",
                c5_nick_name="扫码账号",
                cookie_raw="foo=bar",
            )

    adapter = FakeLoginAdapter()
    app.state.login_adapter = adapter

    create_response = await client.post(
        "/accounts",
        json={
            "remark_name": "待绑定账号",
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:8899",
            "api_key": None,
        },
    )
    account_id = create_response.json()["account_id"]

    response = await client.post(f"/accounts/{account_id}/login")

    assert response.status_code == 202
    task_id = response.json()["task_id"]
    task_payload = await _wait_for_task(client, task_id, "succeeded")

    assert adapter.received_proxy_url == "http://127.0.0.1:8899"
    assert [event["state"] for event in task_payload["events"]] == [
        "pending",
        "starting_browser",
        "waiting_for_scan",
        "captured_login_info",
        "waiting_for_browser_close",
        "saving_account",
        "succeeded",
    ]

    account_response = await client.get(f"/accounts/{account_id}")
    account_payload = account_response.json()
    assert account_payload["c5_user_id"] == "90001"
    assert account_payload["c5_nick_name"] == "扫码账号"
    assert account_payload["cookie_raw"] == "foo=bar"
    assert account_payload["purchase_capability_state"] == "bound"
    assert account_payload["purchase_pool_state"] == "not_connected"


async def test_login_task_refreshes_inventory_once_when_captured_cookie_contains_token(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="90002",
                c5_nick_name="带 token 账号",
                cookie_raw="foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1",
            )

    refresh_gateway = _RecordingRefreshGateway(
        InventoryRefreshResult.success(
            inventories=[
                {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 880, "inventory_max": 1000},
            ]
        )
    )
    app.state.login_adapter = FakeLoginAdapter()
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: refresh_gateway

    create_response = await client.post(
        "/accounts",
        json={
            "remark_name": "待绑定账号",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": None,
        },
    )
    account_id = create_response.json()["account_id"]

    start_response = await client.post(f"/accounts/{account_id}/login")
    task_payload = await _wait_for_task(client, start_response.json()["task_id"], "succeeded")

    assert task_payload["state"] == "succeeded"
    assert refresh_gateway.calls == [
        {
            "account_id": account_id,
            "cookie_raw": "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1",
        }
    ]
    snapshot = app.state.purchase_runtime_service._inventory_snapshot_repository.get(account_id)
    assert snapshot is not None
    assert snapshot.inventories[0]["steamId"] == "steam-1"
    assert snapshot.inventories[0]["inventory_num"] == 880


async def test_login_task_keeps_success_when_inventory_refresh_after_token_binding_fails(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id="90003",
                c5_nick_name="刷新失败账号",
                cookie_raw="foo=bar; NC5_accessToken=token-2; NC5_deviceId=device-2",
            )

    refresh_gateway = _RecordingRefreshGateway(RuntimeError("inventory refresh boom"))
    app.state.login_adapter = FakeLoginAdapter()
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: refresh_gateway

    create_response = await client.post(
        "/accounts",
        json={
            "remark_name": "刷新失败也成功",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": None,
        },
    )
    account_id = create_response.json()["account_id"]

    start_response = await client.post(f"/accounts/{account_id}/login")
    task_payload = await _wait_for_task(client, start_response.json()["task_id"], "succeeded")

    assert task_payload["state"] == "succeeded"
    assert refresh_gateway.calls == [
        {
            "account_id": account_id,
            "cookie_raw": "foo=bar; NC5_accessToken=token-2; NC5_deviceId=device-2",
        }
    ]
    account_response = await client.get(f"/accounts/{account_id}")
    assert account_response.json()["purchase_capability_state"] == "bound"
