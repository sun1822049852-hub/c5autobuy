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
            self.received_user_agent: str | None = None

        async def run_login(self, *, proxy_url: str | None, user_agent: str | None = None, emit_state=None) -> LoginCapture:
            self.received_proxy_url = proxy_url
            self.received_user_agent = user_agent
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
    assert adapter.received_user_agent
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
    stored_account = app.state.account_repository.get_account(account_id)
    assert stored_account is not None
    assert stored_account.user_agent == adapter.received_user_agent


async def test_login_task_assigns_distinct_user_agents_per_account(app, client):
    class FakeLoginAdapter:
        def __init__(self) -> None:
            self.received_user_agents: list[str | None] = []
            self._user_index = 0

        async def run_login(self, *, proxy_url: str | None, user_agent: str | None = None, emit_state=None) -> LoginCapture:
            self.received_user_agents.append(user_agent)
            self._user_index += 1
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
            return LoginCapture(
                c5_user_id=f"9000{self._user_index}",
                c5_nick_name=f"扫码账号-{self._user_index}",
                cookie_raw=f"foo=bar-{self._user_index}",
            )

    adapter = FakeLoginAdapter()
    app.state.login_adapter = adapter

    first_account = (await client.post("/accounts", json={"remark_name": "账号一"})).json()["account_id"]
    second_account = (await client.post("/accounts", json={"remark_name": "账号二"})).json()["account_id"]

    first_task = (await client.post(f"/accounts/{first_account}/login")).json()["task_id"]
    second_task = (await client.post(f"/accounts/{second_account}/login")).json()["task_id"]

    await _wait_for_task(client, first_task, "succeeded")
    await _wait_for_task(client, second_task, "succeeded")

    first_stored = app.state.account_repository.get_account(first_account)
    second_stored = app.state.account_repository.get_account(second_account)

    assert first_stored is not None
    assert second_stored is not None
    assert first_stored.user_agent
    assert second_stored.user_agent
    assert first_stored.user_agent != second_stored.user_agent
    assert adapter.received_user_agents == [first_stored.user_agent, second_stored.user_agent]
