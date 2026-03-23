from __future__ import annotations

import asyncio
from datetime import datetime

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.infrastructure.selenium.login_adapter import LoginCapture


async def _wait_for_task(client, task_id: str, target_state: str) -> dict:
    for _ in range(50):
        response = await client.get(f"/tasks/{task_id}")
        payload = response.json()
        if payload["state"] == target_state:
            return payload
        await asyncio.sleep(0.02)
    raise AssertionError(f"任务 {task_id} 未进入状态 {target_state}")


async def _create_account(client, *, remark_name: str, proxy_mode: str = "custom", proxy_url: str | None = None, api_key: str | None = None) -> dict:
    response = await client.post(
        "/accounts",
        json={
            "remark_name": remark_name,
            "proxy_mode": proxy_mode,
            "proxy_url": proxy_url,
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
    assert task_payload["state"] == "succeeded"
    assert account_payload["account_id"] == account["account_id"]
    assert account_payload["remark_name"] == "原账号"
    assert account_payload["proxy_url"] == "http://127.0.0.1:9001"
    assert account_payload["account_proxy_url"] == "http://127.0.0.1:9001"
    assert account_payload["api_proxy_url"] == "http://127.0.0.1:9001"
    assert account_payload["api_key"] == "api-old"
    assert account_payload["c5_user_id"] == "10001"
    assert account_payload["c5_nick_name"] == "同账号新昵称"
    assert account_payload["cookie_raw"] == "new=same-user"


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
    account = await _create_account(
        client,
        remark_name="旧账号",
        proxy_url="http://127.0.0.1:9002",
        api_key="api-conflict",
    )
    _bind_existing_account(app, account["account_id"], c5_user_id="10001", c5_nick_name="旧绑定")

    start_response = await client.post(f"/accounts/{account['account_id']}/login")
    task_payload = await _wait_for_task(client, start_response.json()["task_id"], "conflict")

    assert task_payload["pending_conflict"]["account_id"] == account["account_id"]
    assert task_payload["pending_conflict"]["existing_c5_user_id"] == "10001"
    assert task_payload["pending_conflict"]["captured_login"]["c5_user_id"] == "20002"
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

    accounts_response = await client.get("/accounts")
    accounts_payload = accounts_response.json()
    assert len(accounts_payload) == 2

    old_account = next(item for item in accounts_payload if item["account_id"] == account["account_id"])
    new_account = next(item for item in accounts_payload if item["account_id"] != account["account_id"])
    assert old_account["remark_name"] == "保留旧账号"
    assert old_account["proxy_url"] == "http://127.0.0.1:9003"
    assert old_account["account_proxy_url"] == "http://127.0.0.1:9003"
    assert old_account["api_proxy_url"] == "http://127.0.0.1:9003"
    assert old_account["api_key"] == "api-keep"
    assert old_account["c5_user_id"] == "10001"

    assert new_account["remark_name"] is None
    assert new_account["proxy_mode"] == "direct"
    assert new_account["proxy_url"] is None
    assert new_account["account_proxy_mode"] == "direct"
    assert new_account["account_proxy_url"] is None
    assert new_account["api_proxy_mode"] == "direct"
    assert new_account["api_proxy_url"] is None
    assert new_account["api_key"] is None
    assert new_account["c5_user_id"] == "30003"
    assert new_account["c5_nick_name"] == "新增账号"
    assert new_account["cookie_raw"] == "new=create"


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
    assert new_account["proxy_mode"] == "direct"
    assert new_account["proxy_url"] is None
    assert new_account["account_proxy_mode"] == "direct"
    assert new_account["account_proxy_url"] is None
    assert new_account["api_proxy_mode"] == "direct"
    assert new_account["api_proxy_url"] is None
    assert new_account["api_key"] is None
    assert new_account["c5_user_id"] == "40004"
    assert new_account["c5_nick_name"] == "替换账号"
    assert new_account["cookie_raw"] == "new=replace"
