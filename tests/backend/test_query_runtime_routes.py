async def test_query_runtime_status_defaults_to_idle(client):
    response = await client.get("/query-runtime/status")

    assert response.status_code == 200
    assert response.json() == {
        "running": False,
        "config_id": None,
        "config_name": None,
        "message": "未运行",
        "account_count": 0,
        "started_at": None,
        "stopped_at": None,
        "total_query_count": 0,
        "total_found_count": 0,
        "modes": {},
        "group_rows": [],
        "recent_events": [],
    }


async def test_start_query_runtime_returns_running_snapshot(client):
    created = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于运行时",
        },
    )
    config_id = created.json()["config_id"]

    response = await client.post("/query-runtime/start", json={"config_id": config_id})
    purchase_status = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    assert purchase_status.status_code == 200
    payload = response.json()
    assert payload["running"] is True
    assert payload["config_id"] == config_id
    assert payload["config_name"] == "查询配置A"
    assert payload["message"] == "运行中"
    assert payload["account_count"] == 0
    assert payload["total_query_count"] == 0
    assert payload["total_found_count"] == 0
    assert payload["group_rows"] == []
    assert payload["recent_events"] == []
    assert payload["started_at"] is not None
    assert payload["stopped_at"] is None
    assert purchase_status.json()["running"] is True
    assert payload["modes"] == {
        "new_api": {
            "mode_type": "new_api",
            "enabled": True,
            "eligible_account_count": 0,
            "active_account_count": 0,
            "in_window": True,
            "next_window_start": None,
            "next_window_end": None,
            "query_count": 0,
            "found_count": 0,
            "last_error": None,
        },
        "fast_api": {
            "mode_type": "fast_api",
            "enabled": True,
            "eligible_account_count": 0,
            "active_account_count": 0,
            "in_window": True,
            "next_window_start": None,
            "next_window_end": None,
            "query_count": 0,
            "found_count": 0,
            "last_error": None,
        },
        "token": {
            "mode_type": "token",
            "enabled": True,
            "eligible_account_count": 0,
            "active_account_count": 0,
            "in_window": True,
            "next_window_start": None,
            "next_window_end": None,
            "query_count": 0,
            "found_count": 0,
            "last_error": None,
        },
    }


async def test_prepare_query_runtime_returns_refresh_summary(client, app):
    created = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于运行时",
        },
    )
    config_id = created.json()["config_id"]

    class FakeRefreshService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def prepare(self, *, config_id: str, force_refresh: bool = False) -> dict[str, object]:
            self.calls.append({"config_id": config_id, "force_refresh": force_refresh})
            return {
                "config_id": config_id,
                "config_name": "查询配置A",
                "threshold_hours": 12,
                "updated_count": 1,
                "skipped_count": 0,
                "failed_count": 0,
                "items": [
                    {
                        "query_item_id": "item-1",
                        "external_item_id": "1380979899390267393",
                        "item_name": "AK-47 | Redline",
                        "status": "updated",
                        "message": "商品详情已刷新",
                        "last_market_price": 123.45,
                        "min_wear": 0.1,
                        "detail_max_wear": 0.7,
                        "last_detail_sync_at": "2026-03-17T12:00:00",
                    }
                ],
            }

    service = FakeRefreshService()
    app.state.query_item_detail_refresh_service = service

    response = await client.post("/query-runtime/prepare", json={"config_id": config_id, "force_refresh": True})

    assert response.status_code == 200
    assert service.calls == [{"config_id": config_id, "force_refresh": True}]
    assert response.json()["updated_count"] == 1
    assert response.json()["threshold_hours"] == 12
    assert response.json()["items"][0]["status"] == "updated"
    assert response.json()["items"][0]["detail_max_wear"] == 0.7


async def test_prepare_query_runtime_returns_404_for_missing_config(client, app):
    class MissingConfigRefreshService:
        async def prepare(self, *, config_id: str, force_refresh: bool = False) -> dict[str, object]:
            raise KeyError(config_id)

    app.state.query_item_detail_refresh_service = MissingConfigRefreshService()

    response = await client.post("/query-runtime/prepare", json={"config_id": "missing"})

    assert response.status_code == 404
    assert response.json() == {"detail": "查询配置不存在"}


async def test_prepare_query_runtime_returns_409_for_prepare_conflict(client, app):
    class ConflictRefreshService:
        async def prepare(self, *, config_id: str, force_refresh: bool = False) -> dict[str, object]:
            raise ValueError("没有可用于商品信息补全的已登录账号")

    app.state.query_item_detail_refresh_service = ConflictRefreshService()

    response = await client.post("/query-runtime/prepare", json={"config_id": "cfg-1"})

    assert response.status_code == 409
    assert response.json() == {"detail": "没有可用于商品信息补全的已登录账号"}


async def test_start_query_runtime_rejects_second_running_task(client):
    created = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于运行时",
        },
    )
    config_id = created.json()["config_id"]

    await client.post("/query-runtime/start", json={"config_id": config_id})
    response = await client.post("/query-runtime/start", json={"config_id": config_id})

    assert response.status_code == 409
    assert response.json() == {"detail": "已有查询任务在运行"}


async def test_stop_query_runtime_returns_idle_snapshot(client):
    created = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于运行时",
        },
    )
    config_id = created.json()["config_id"]

    await client.post("/query-runtime/start", json={"config_id": config_id})
    response = await client.post("/query-runtime/stop")
    purchase_status = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    assert purchase_status.status_code == 200
    assert response.json() == {
        "running": False,
        "config_id": None,
        "config_name": None,
        "message": "未运行",
        "account_count": 0,
        "started_at": None,
        "stopped_at": None,
        "total_query_count": 0,
        "total_found_count": 0,
        "modes": {},
        "group_rows": [],
        "recent_events": [],
    }
    assert purchase_status.json()["running"] is False
