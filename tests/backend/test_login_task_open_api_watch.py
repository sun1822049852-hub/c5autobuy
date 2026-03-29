from __future__ import annotations

import asyncio


async def test_login_task_starts_open_api_binding_watch_after_success(app, client):
    class FakeLoginAdapter:
        async def run_login(self, *, proxy_url: str | None, emit_state=None):
            await emit_state("waiting_for_scan")
            await emit_state("captured_login_info")
            return {
                "c5_user_id": "90001",
                "c5_nick_name": "扫码账号",
                "cookie_raw": "NC5_accessToken=token-1",
                "debugger_address": "127.0.0.1:9222",
            }

    class FakeOpenApiBindingSyncService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str | None]] = []

        def schedule_account_watch(self, account_id: str, debugger_address: str | None = None) -> None:
            self.calls.append((account_id, debugger_address))

    class FakeAccountBalanceService:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def refresh_after_login(self, account_id: str) -> None:
            self.calls.append(account_id)

    app.state.login_adapter = FakeLoginAdapter()
    app.state.open_api_binding_sync_service = FakeOpenApiBindingSyncService()
    app.state.account_balance_service = FakeAccountBalanceService()

    create_response = await client.post(
        "/accounts",
        json={
            "remark_name": "待绑定账号",
            "browser_proxy_mode": "custom",
            "browser_proxy_url": "http://127.0.0.1:8899",
            "api_proxy_mode": "custom",
            "api_proxy_url": "http://127.0.0.1:8899",
            "api_key": None,
        },
    )
    account_id = create_response.json()["account_id"]

    start_response = await client.post(f"/accounts/{account_id}/login")
    assert start_response.status_code == 202

    for _ in range(50):
        task_response = await client.get(f"/tasks/{start_response.json()['task_id']}")
        if task_response.json()["state"] == "succeeded":
            break
        await asyncio.sleep(0.02)
    else:
        raise AssertionError("login task did not succeed in time")

    assert app.state.open_api_binding_sync_service.calls == [(account_id, "127.0.0.1:9222")]
    assert app.state.account_balance_service.calls == [account_id]
