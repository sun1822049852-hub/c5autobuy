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
    assert payload["api_query_disabled_reason"] is None
    assert payload["browser_query_disabled_reason"] is None


async def test_post_accounts_treats_blank_custom_proxy_as_direct(client):
    response = await client.post(
        "/accounts",
        json={
            "remark_name": "测试备注",
            "proxy_mode": "custom",
            "proxy_url": "   ",
            "api_key": None,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["proxy_mode"] == "direct"
    assert payload["proxy_url"] is None
    assert payload["api_key"] is None


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


async def test_patch_account_normalizes_scheme_less_proxy_and_auth(client):
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
            "remark_name": None,
            "proxy_mode": "custom",
            "proxy_url": "user:pass@127.0.0.1:8080",
            "api_key": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["proxy_mode"] == "custom"
    assert payload["proxy_url"] == "http://user:pass@127.0.0.1:8080"


async def test_patch_account_query_modes_updates_api_and_browser_flags(client):
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
            "api_query_enabled": False,
            "api_query_disabled_reason": "manual_disabled",
            "browser_query_enabled": False,
            "browser_query_disabled_reason": "manual_disabled",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["new_api_enabled"] is False
    assert payload["fast_api_enabled"] is False
    assert payload["token_enabled"] is False
    assert payload["api_query_disabled_reason"] == "manual_disabled"
    assert payload["browser_query_disabled_reason"] == "manual_disabled"


async def test_patch_account_query_modes_supports_partial_browser_toggle(client):
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

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "browser_query_enabled": False,
            "browser_query_disabled_reason": "manual_disabled",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["new_api_enabled"] is True
    assert payload["fast_api_enabled"] is True
    assert payload["token_enabled"] is False
    assert payload["api_query_disabled_reason"] is None
    assert payload["browser_query_disabled_reason"] == "manual_disabled"


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


async def test_delete_account_removes_active_session_bundle(app, client):
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
    bundle_repository = app.state.account_session_bundle_repository
    staged = bundle_repository.stage_bundle(
        account_id=account_id,
        captured_c5_user_id="10001",
        payload={"cookie_raw": "cookie=value"},
    )
    verified = bundle_repository.mark_bundle_verified(staged.bundle_id)
    bundle_repository.activate_bundle(verified.bundle_id, account_id=account_id)

    delete_response = await client.delete(f"/accounts/{account_id}")

    assert delete_response.status_code == 204
    assert bundle_repository.get_active_bundle(account_id) is None
