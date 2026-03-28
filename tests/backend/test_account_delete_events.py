from __future__ import annotations

import asyncio


async def test_delete_account_route_publishes_delete_account_event(app, client):
    create_response = await client.post(
        "/accounts",
        json={
            "remark_name": "待删除账号",
            "browser_proxy_mode": "direct",
            "browser_proxy_url": None,
            "api_proxy_mode": "direct",
            "api_proxy_url": None,
            "api_key": None,
        },
    )
    account_id = create_response.json()["account_id"]
    queue = app.state.account_update_hub.subscribe("*")

    try:
        delete_response = await client.delete(f"/accounts/{account_id}")

        assert delete_response.status_code == 204
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event.account_id == account_id
        assert event.event == "delete_account"
        assert event.payload == {}
    finally:
        app.state.account_update_hub.unsubscribe(queue, "*")
