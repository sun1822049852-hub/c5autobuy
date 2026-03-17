from app_backend.domain.enums.account_states import PurchaseCapabilityState


async def test_post_accounts_creates_account(client):
    response = await client.post(
        "/accounts",
        json={
            "remark_name": "测试备注",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": "key-123",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["remark_name"] == "测试备注"
    assert payload["api_key"] == "key-123"
    assert payload["purchase_capability_state"] == "unbound"
    assert payload["purchase_pool_state"] == "not_connected"
    assert payload["default_name"]
    assert payload["new_api_enabled"] is True
    assert payload["fast_api_enabled"] is True
    assert payload["token_enabled"] is True


async def test_get_accounts_returns_created_accounts(client):
    await client.post(
        "/accounts",
        json={
            "remark_name": "账号A",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": None,
        },
    )

    response = await client.get("/accounts")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["display_name"] == "账号A"


async def test_patch_account_updates_allowed_fields(client):
    created = await client.post(
        "/accounts",
        json={
            "remark_name": None,
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": None,
        },
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}",
        json={
            "remark_name": "新备注",
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:8080",
            "api_key": "new-key",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remark_name"] == "新备注"
    assert payload["proxy_url"] == "http://127.0.0.1:8080"
    assert payload["api_key"] == "new-key"


async def test_patch_account_query_modes_updates_global_flags(client):
    created = await client.post(
        "/accounts",
        json={
            "remark_name": "账号A",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": None,
        },
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "new_api_enabled": False,
            "fast_api_enabled": True,
            "token_enabled": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["new_api_enabled"] is False
    assert payload["fast_api_enabled"] is True
    assert payload["token_enabled"] is False


async def test_clear_purchase_capability_keeps_api_key(client, app):
    created = await client.post(
        "/accounts",
        json={
            "remark_name": "账号A",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": "key-123",
        },
    )
    account_id = created.json()["account_id"]
    repository = app.state.account_repository
    repository.update_account(
        account_id,
        c5_user_id="10001",
        c5_nick_name="nick",
        cookie_raw="cookie=value",
        purchase_capability_state=PurchaseCapabilityState.BOUND,
    )

    response = await client.post(f"/accounts/{account_id}/purchase-capability/clear")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key"] == "key-123"
    assert payload["c5_user_id"] is None
    assert payload["cookie_raw"] is None
    assert payload["purchase_capability_state"] == "unbound"


async def test_delete_account_removes_record(client):
    created = await client.post(
        "/accounts",
        json={
            "remark_name": "账号A",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": None,
        },
    )
    account_id = created.json()["account_id"]

    delete_response = await client.delete(f"/accounts/{account_id}")
    list_response = await client.get("/accounts")

    assert delete_response.status_code == 204
    assert list_response.json() == []
