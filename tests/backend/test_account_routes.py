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


async def test_post_accounts_assigns_distinct_user_agents_for_api_key_only_accounts(client, app):
    first_response = await client.post(
        "/accounts",
        json={
            "remark_name": "查询账号A",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": "key-a",
        },
    )
    second_response = await client.post(
        "/accounts",
        json={
            "remark_name": "查询账号B",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": "key-b",
        },
    )

    first_account = app.state.account_repository.get_account(first_response.json()["account_id"])
    second_account = app.state.account_repository.get_account(second_response.json()["account_id"])

    assert first_account is not None
    assert second_account is not None
    assert first_account.user_agent
    assert second_account.user_agent
    assert first_account.user_agent != second_account.user_agent


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
    assert payload["account_proxy_mode"] == "direct"
    assert payload["account_proxy_url"] is None
    assert payload["api_proxy_mode"] == "direct"
    assert payload["api_proxy_url"] is None


async def test_post_accounts_accepts_split_proxy_fields(client):
    response = await client.post(
        "/accounts",
        json={
            "remark_name": "双代理账号",
            "account_proxy_mode": "custom",
            "account_proxy_url": "http://127.0.0.1:8001",
            "api_proxy_mode": "custom",
            "api_proxy_url": "http://127.0.0.1:8002",
            "api_key": "key-123",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["account_proxy_url"] == "http://127.0.0.1:8001"
    assert payload["api_proxy_url"] == "http://127.0.0.1:8002"
    assert payload["proxy_url"] == "http://127.0.0.1:8001"


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


async def test_patch_account_keeps_api_proxy_independent(client):
    created = await client.post(
        "/accounts",
        json={
            "remark_name": None,
            "account_proxy_mode": "custom",
            "account_proxy_url": "http://127.0.0.1:8001",
            "api_proxy_mode": "custom",
            "api_proxy_url": "http://127.0.0.1:8002",
            "api_key": None,
        },
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}",
        json={
            "remark_name": None,
            "account_proxy_mode": "custom",
            "account_proxy_url": "http://127.0.0.1:8101",
            "api_proxy_mode": "custom",
            "api_proxy_url": "http://127.0.0.1:8102",
            "api_key": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_proxy_url"] == "http://127.0.0.1:8101"
    assert payload["api_proxy_url"] == "http://127.0.0.1:8102"


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
