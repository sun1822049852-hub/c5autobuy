async def test_create_query_config_returns_three_modes(client):
    response = await client.post(
        "/query-configs",
        json={
            "name": "日间配置",
            "description": "白天跑",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "日间配置"
    assert payload["description"] == "白天跑"
    assert {item["mode_type"] for item in payload["mode_settings"]} == {"new_api", "fast_api", "token"}


async def test_get_query_configs_returns_created_config(client):
    await client.post(
        "/query-configs",
        json={
            "name": "周末配置",
            "description": "周末跑",
        },
    )

    response = await client.get("/query-configs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "周末配置"


async def test_get_query_config_returns_single_config(client):
    created = await client.post(
        "/query-configs",
        json={
            "name": "单配置",
            "description": "单配置描述",
        },
    )
    config_id = created.json()["config_id"]

    response = await client.get(f"/query-configs/{config_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config_id"] == config_id
    assert payload["name"] == "单配置"
    assert payload["description"] == "单配置描述"


async def test_patch_query_config_updates_name_and_description(client):
    created = await client.post(
        "/query-configs",
        json={
            "name": "原配置",
            "description": "原描述",
        },
    )
    config_id = created.json()["config_id"]

    response = await client.patch(
        f"/query-configs/{config_id}",
        json={
            "name": "新配置名",
            "description": "新描述",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["config_id"] == config_id
    assert payload["name"] == "新配置名"
    assert payload["description"] == "新描述"


async def test_delete_query_config_removes_config(client):
    created = await client.post(
        "/query-configs",
        json={
            "name": "待删配置",
            "description": "待删描述",
        },
    )
    config_id = created.json()["config_id"]

    response = await client.delete(f"/query-configs/{config_id}")
    listed = await client.get("/query-configs")

    assert response.status_code == 204
    assert listed.status_code == 200
    assert listed.json() == []


async def test_patch_query_mode_setting_updates_mode_parameters(client):
    created = await client.post(
        "/query-configs",
        json={
            "name": "夜间配置",
            "description": "晚上跑",
        },
    )
    config_id = created.json()["config_id"]

    response = await client.patch(
        f"/query-configs/{config_id}/modes/new_api",
        json={
            "enabled": True,
            "window_enabled": True,
            "start_hour": 9,
            "start_minute": 30,
            "end_hour": 18,
            "end_minute": 0,
            "base_cooldown_min": 1.0,
            "base_cooldown_max": 1.0,
            "random_delay_enabled": True,
            "random_delay_min": 0.2,
            "random_delay_max": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode_type"] == "new_api"
    assert payload["window_enabled"] is True
    assert payload["start_hour"] == 9
    assert payload["random_delay_enabled"] is True


async def test_parse_query_item_url_returns_external_item_id(client):
    response = await client.post(
        "/query-items/parse-url",
        json={
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267393",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267393",
        "external_item_id": "1380979899390267393",
    }


async def test_fetch_query_item_detail_returns_product_detail(client, app):
    class FakeDetailCollector:
        async def fetch_detail(self, *, external_item_id: str, product_url: str):
            from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetail

            return ProductDetail(
                external_item_id=external_item_id,
                product_url=product_url,
                item_name="AK-47 | Vulcan",
                market_hash_name="AK-47 | Vulcan (Field-Tested)",
                min_wear=0.07,
                max_wear=0.8,
                last_market_price=1999.0,
            )

    app.state.product_detail_collector = FakeDetailCollector()

    response = await client.post(
        "/query-items/fetch-detail",
        json={
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267000",
            "external_item_id": "1380979899390267000",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267000",
        "external_item_id": "1380979899390267000",
        "item_name": "AK-47 | Vulcan",
        "market_hash_name": "AK-47 | Vulcan (Field-Tested)",
        "min_wear": 0.07,
        "detail_max_wear": 0.8,
        "last_market_price": 1999.0,
    }


async def test_add_query_item_uses_collectors_and_persists_thresholds(client, app):
    class FakeDetailCollector:
        async def fetch_detail(self, *, external_item_id: str, product_url: str):
            from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetail

            return ProductDetail(
                external_item_id=external_item_id,
                product_url=product_url,
                item_name="AK-47 | Redline",
                market_hash_name="AK-47 | Redline (Field-Tested)",
                min_wear=0.1,
                max_wear=0.7,
                last_market_price=123.45,
            )

    app.state.product_detail_collector = FakeDetailCollector()

    created = await client.post(
        "/query-configs",
        json={
            "name": "商品配置",
            "description": "用于加商品",
        },
    )
    config_id = created.json()["config_id"]

    response = await client.post(
        f"/query-configs/{config_id}/items",
        json={
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267393",
            "max_wear": 0.25,
            "max_price": 199.0,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["external_item_id"] == "1380979899390267393"
    assert payload["item_name"] == "AK-47 | Redline"
    assert payload["market_hash_name"] == "AK-47 | Redline (Field-Tested)"
    assert payload["min_wear"] == 0.1
    assert payload["detail_max_wear"] == 0.7
    assert payload["max_wear"] == 0.25
    assert payload["max_price"] == 199.0


async def test_add_query_item_rejects_max_wear_not_greater_than_detail_min_wear(client, app):
    class FakeDetailCollector:
        async def fetch_detail(self, *, external_item_id: str, product_url: str):
            from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetail

            return ProductDetail(
                external_item_id=external_item_id,
                product_url=product_url,
                item_name="AK-47 | Redline",
                market_hash_name="AK-47 | Redline (Field-Tested)",
                min_wear=0.1,
                max_wear=0.7,
                last_market_price=123.45,
            )

    app.state.product_detail_collector = FakeDetailCollector()
    created = await client.post("/query-configs", json={"name": "商品配置", "description": "用于加商品"})
    config_id = created.json()["config_id"]

    response = await client.post(
        f"/query-configs/{config_id}/items",
        json={
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267393",
            "max_wear": 0.1,
            "max_price": 199.0,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "最大磨损值必须在范围 (0.1, 0.7] 内"


async def test_patch_query_item_updates_thresholds(client, app):
    class FakeDetailCollector:
        async def fetch_detail(self, *, external_item_id: str, product_url: str):
            from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetail

            return ProductDetail(
                external_item_id=external_item_id,
                product_url=product_url,
                item_name="M4A1-S | Printstream",
                market_hash_name="M4A1-S | Printstream (Field-Tested)",
                min_wear=0.0,
                max_wear=0.8,
                last_market_price=666.0,
            )

    app.state.product_detail_collector = FakeDetailCollector()
    created = await client.post("/query-configs", json={"name": "编辑商品", "description": "测试编辑"})
    config_id = created.json()["config_id"]
    added = await client.post(
        f"/query-configs/{config_id}/items",
        json={
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390269988",
            "max_wear": 0.3,
            "max_price": 777.0,
        },
    )
    item_id = added.json()["query_item_id"]

    response = await client.patch(
        f"/query-configs/{config_id}/items/{item_id}",
        json={
            "max_wear": 0.15,
            "max_price": 555.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_item_id"] == item_id
    assert payload["max_wear"] == 0.15
    assert payload["max_price"] == 555.0


async def test_patch_query_item_rejects_max_wear_above_detail_max_wear(client, app):
    class FakeDetailCollector:
        async def fetch_detail(self, *, external_item_id: str, product_url: str):
            from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetail

            return ProductDetail(
                external_item_id=external_item_id,
                product_url=product_url,
                item_name="M4A1-S | Printstream",
                market_hash_name="M4A1-S | Printstream (Field-Tested)",
                min_wear=0.1,
                max_wear=0.7,
                last_market_price=666.0,
            )

    app.state.product_detail_collector = FakeDetailCollector()
    created = await client.post("/query-configs", json={"name": "编辑商品", "description": "测试编辑"})
    config_id = created.json()["config_id"]
    added = await client.post(
        f"/query-configs/{config_id}/items",
        json={
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390269988",
            "max_wear": 0.3,
            "max_price": 777.0,
        },
    )
    item_id = added.json()["query_item_id"]

    response = await client.patch(
        f"/query-configs/{config_id}/items/{item_id}",
        json={
            "max_wear": 0.8,
            "max_price": 555.0,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "最大磨损值必须在范围 (0.1, 0.7] 内"


async def test_refresh_query_item_detail_updates_selected_item(client, app):
    from app_backend.domain.models.query_config import QueryItem

    class FakeRefreshService:
        async def refresh_item(self, *, config_id: str, query_item_id: str):
            assert config_id == "cfg-1"
            assert query_item_id == "item-1"
            return QueryItem(
                query_item_id="item-1",
                config_id="cfg-1",
                product_url="https://www.c5game.com/csgo/730/asset/1380979899390267788",
                external_item_id="1380979899390267788",
                item_name="M4A1-S | Blue Phosphor",
                market_hash_name="M4A1-S | Blue Phosphor (Factory New)",
                min_wear=0.0,
                detail_max_wear=0.08,
                max_wear=0.18,
                max_price=2888.0,
                last_market_price=2555.0,
                last_detail_sync_at="2026-03-17T12:30:00",
                sort_order=0,
                created_at="2026-03-17T12:00:00",
                updated_at="2026-03-17T12:30:00",
            )

    app.state.query_item_detail_refresh_service = FakeRefreshService()

    response = await client.post("/query-configs/cfg-1/items/item-1/refresh-detail")

    assert response.status_code == 200
    assert response.json() == {
        "query_item_id": "item-1",
        "config_id": "cfg-1",
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267788",
        "external_item_id": "1380979899390267788",
        "item_name": "M4A1-S | Blue Phosphor",
        "market_hash_name": "M4A1-S | Blue Phosphor (Factory New)",
        "min_wear": 0.0,
        "detail_max_wear": 0.08,
        "max_wear": 0.18,
        "max_price": 2888.0,
        "last_market_price": 2555.0,
        "last_detail_sync_at": "2026-03-17T12:30:00",
        "sort_order": 0,
        "created_at": "2026-03-17T12:00:00",
        "updated_at": "2026-03-17T12:30:00",
    }


async def test_delete_query_item_removes_item_from_config(client, app):
    class FakeDetailCollector:
        async def fetch_detail(self, *, external_item_id: str, product_url: str):
            from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetail

            return ProductDetail(
                external_item_id=external_item_id,
                product_url=product_url,
                item_name="AWP | Asiimov",
                market_hash_name="AWP | Asiimov (Field-Tested)",
                min_wear=0.18,
                max_wear=1.0,
                last_market_price=888.0,
            )

    app.state.product_detail_collector = FakeDetailCollector()
    created = await client.post("/query-configs", json={"name": "删除商品", "description": "测试删除"})
    config_id = created.json()["config_id"]
    added = await client.post(
        f"/query-configs/{config_id}/items",
        json={
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390265566",
            "max_wear": 0.45,
            "max_price": 999.0,
        },
    )
    item_id = added.json()["query_item_id"]

    response = await client.delete(f"/query-configs/{config_id}/items/{item_id}")
    listed = await client.get("/query-configs")

    assert response.status_code == 204
    payload = listed.json()
    assert payload[0]["config_id"] == config_id
    assert payload[0]["items"] == []
