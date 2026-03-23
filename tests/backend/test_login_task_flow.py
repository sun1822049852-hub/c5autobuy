from __future__ import annotations

import asyncio

from app_backend.infrastructure.selenium.login_adapter import LoginCapture


async def _wait_for_task(client, task_id: str, target_state: str) -> dict:
    for _ in range(50):
        response = await client.get(f"/tasks/{task_id}")
        payload = response.json()
        if payload["state"] == target_state:
            return payload
        await asyncio.sleep(0.02)
    raise AssertionError(f"任务 {task_id} 未进入状态 {target_state}")


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
    assert account_payload["account_proxy_url"] == "http://127.0.0.1:8899"
    assert account_payload["api_proxy_url"] == "http://127.0.0.1:8899"
    assert account_payload["purchase_capability_state"] == "bound"
    assert account_payload["purchase_pool_state"] == "not_connected"
