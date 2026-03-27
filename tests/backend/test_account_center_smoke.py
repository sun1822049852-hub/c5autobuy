from __future__ import annotations

import asyncio

from app_backend.infrastructure.browser_runtime.login_adapter import LoginCapture


async def _wait_for_task(client, task_id: str, target_state: str) -> dict:
    for _ in range(60):
        response = await client.get(f"/tasks/{task_id}")
        payload = response.json()
        if payload["state"] == target_state:
            return payload
        await asyncio.sleep(0.02)
    raise AssertionError(f"任务 {task_id} 未进入状态 {target_state}")


async def test_account_center_smoke_flow(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
            for state in ("waiting_for_scan", "captured_login_info", "waiting_for_browser_close"):
                await emit_state(state)
            return LoginCapture(
                c5_user_id="70007",
                c5_nick_name="烟测账号",
                cookie_raw="smoke=cookie",
            )

    app.state.login_adapter = FakeLoginAdapter()

    create_response = await client.post(
        "/accounts",
        json={
            "remark_name": "烟测备注",
            "browser_proxy_mode": "custom",
            "browser_proxy_url": "http://127.0.0.1:9600",
            "api_proxy_mode": "direct",
            "api_proxy_url": None,
            "api_key": "smoke-api",
        },
    )
    assert create_response.status_code == 201
    account = create_response.json()
    account_id = account["account_id"]

    patch_response = await client.patch(
        f"/accounts/{account_id}",
        json={
            "remark_name": "更新后备注",
            "browser_proxy_mode": "direct",
            "browser_proxy_url": None,
            "api_proxy_mode": "direct",
            "api_proxy_url": None,
            "api_key": "updated-api",
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["remark_name"] == "更新后备注"

    login_response = await client.post(f"/accounts/{account_id}/login")
    assert login_response.status_code == 202
    task_payload = await _wait_for_task(client, login_response.json()["task_id"], "succeeded")
    assert task_payload["result"]["account_id"] == account_id

    detail_response = await client.get(f"/accounts/{account_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["api_key"] == "updated-api"
    assert detail_payload["purchase_capability_state"] == "bound"
    assert detail_payload["purchase_pool_state"] == "not_connected"
    assert detail_payload["c5_user_id"] == "70007"

    clear_response = await client.post(f"/accounts/{account_id}/purchase-capability/clear")
    assert clear_response.status_code == 200
    cleared_payload = clear_response.json()
    assert cleared_payload["api_key"] == "updated-api"
    assert cleared_payload["purchase_capability_state"] == "unbound"
    assert cleared_payload["c5_user_id"] is None

    delete_response = await client.delete(f"/accounts/{account_id}")
    assert delete_response.status_code == 204

    list_response = await client.get("/accounts")
    assert list_response.status_code == 200
    assert list_response.json() == []


