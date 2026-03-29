from app_backend.domain.models.account import Account


def _build_query_purchase_account(account_id: str) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
        c5_user_id="10001",
        c5_nick_name="购买查询账号",
        cookie_raw="NC5_accessToken=token-1",
        purchase_capability_state="bound",
        purchase_pool_state="not_connected",
        last_login_at="2026-03-16T10:00:00",
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        new_api_enabled=False,
        fast_api_enabled=False,
        token_enabled=False,
    )


def _prepare_active_purchase_account(app, account_id: str = "a1") -> None:
    app.state.account_repository.create_account(_build_query_purchase_account(account_id))
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id=account_id,
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at="2026-03-16T10:00:00",
        last_error=None,
    )


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
        "item_rows": [],
    }


async def test_start_query_runtime_returns_waiting_snapshot_when_no_purchase_account_is_available(client):
    created = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于运行时",
        },
    )
    config_id = created.json()["config_id"]

    response = await client.post("/query-runtime/start", json={"config_id": config_id})
    payload = response.json()

    assert response.status_code == 200
    assert payload == {
        "running": False,
        "config_id": config_id,
        "config_name": "查询配置A",
        "message": "等待购买账号恢复",
        "account_count": 0,
        "started_at": None,
        "stopped_at": payload["stopped_at"],
        "total_query_count": 0,
        "total_found_count": 0,
        "modes": {
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
        },
        "group_rows": [],
        "recent_events": [],
        "item_rows": [],
    }
    assert payload["stopped_at"] is not None


async def test_start_query_runtime_returns_running_snapshot(client, app):
    created = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于运行时",
        },
    )
    config_id = created.json()["config_id"]
    _prepare_active_purchase_account(app)

    response = await client.post("/query-runtime/start", json={"config_id": config_id})
    purchase_status = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    assert purchase_status.status_code == 200
    payload = response.json()
    assert payload["running"] is True
    assert payload["config_id"] == config_id
    assert payload["config_name"] == "查询配置A"
    assert payload["message"] == "运行中"
    assert payload["account_count"] == 1
    assert payload["total_query_count"] == 0
    assert payload["total_found_count"] == 0
    assert payload["group_rows"] == []
    assert payload["recent_events"] == []
    assert payload["item_rows"] == []
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
                        "max_wear": 0.7,
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
    assert response.json()["items"][0]["max_wear"] == 0.7


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


async def test_start_query_runtime_rejects_second_running_task(client, app):
    created = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于运行时",
        },
    )
    config_id = created.json()["config_id"]
    _prepare_active_purchase_account(app)

    await client.post("/query-runtime/start", json={"config_id": config_id})
    response = await client.post("/query-runtime/start", json={"config_id": config_id})

    assert response.status_code == 409
    assert response.json() == {"detail": "已有查询任务在运行"}


async def test_start_query_runtime_switches_to_another_config_when_request_targets_new_config(client, app):
    created_first = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于运行时",
        },
    )
    created_second = await client.post(
        "/query-configs",
        json={
            "name": "查询配置B",
            "description": "第二套配置",
        },
    )
    config_id_first = created_first.json()["config_id"]
    config_id_second = created_second.json()["config_id"]
    _prepare_active_purchase_account(app)

    await client.post("/query-runtime/start", json={"config_id": config_id_first})
    response = await client.post("/query-runtime/start", json={"config_id": config_id_second})
    status_response = await client.get("/query-runtime/status")

    assert response.status_code == 200
    assert response.json()["running"] is True
    assert response.json()["config_id"] == config_id_second
    assert response.json()["config_name"] == "查询配置B"
    assert status_response.status_code == 200
    assert status_response.json()["config_id"] == config_id_second
    assert status_response.json()["config_name"] == "查询配置B"


async def test_stop_query_runtime_returns_idle_snapshot(client, app):
    created = await client.post(
        "/query-configs",
        json={
            "name": "查询配置A",
            "description": "用于运行时",
        },
    )
    config_id = created.json()["config_id"]
    _prepare_active_purchase_account(app)

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
        "item_rows": [],
    }
    assert purchase_status.json()["running"] is False


async def test_query_runtime_status_returns_item_rows_for_mode_status_labels(client, app):
    class FakeQueryRuntimeService:
        def get_status(self) -> dict[str, object]:
            return {
                "running": True,
                "config_id": "cfg-1",
                "config_name": "查询配置A",
                "message": "运行中",
                "account_count": 2,
                "started_at": "2026-03-19T12:00:00",
                "stopped_at": None,
                "total_query_count": 3,
                "total_found_count": 1,
                "modes": {},
                "group_rows": [],
                "recent_events": [],
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "item_name": "AK-47 | Redline",
                        "max_price": 123.45,
                        "min_wear": 0.1,
                        "max_wear": 0.7,
                        "detail_min_wear": 0.12,
                        "detail_max_wear": 0.3,
                        "manual_paused": False,
                        "query_count": 5,
                        "modes": {
                            "new_api": {
                                "mode_type": "new_api",
                                "target_dedicated_count": 1,
                                "actual_dedicated_count": 1,
                                "status": "dedicated",
                                "status_message": "专属中 1/1",
                            },
                            "token": {
                                "mode_type": "token",
                                "target_dedicated_count": 0,
                                "actual_dedicated_count": 0,
                                "status": "shared",
                                "status_message": "共享中",
                            },
                        },
                    }
                ],
            }

    app.state.query_runtime_service = FakeQueryRuntimeService()

    response = await client.get("/query-runtime/status")

    assert response.status_code == 200
    assert response.json()["item_rows"] == [
        {
            "query_item_id": "item-1",
            "item_name": "AK-47 | Redline",
            "max_price": 123.45,
            "min_wear": 0.1,
            "max_wear": 0.7,
            "detail_min_wear": 0.12,
            "detail_max_wear": 0.3,
            "manual_paused": False,
            "query_count": 5,
            "modes": {
                "new_api": {
                    "mode_type": "new_api",
                    "target_dedicated_count": 1,
                    "actual_dedicated_count": 1,
                    "status": "dedicated",
                    "status_message": "专属中 1/1",
                },
                "token": {
                    "mode_type": "token",
                    "target_dedicated_count": 0,
                    "actual_dedicated_count": 0,
                    "status": "shared",
                    "status_message": "共享中",
                },
            },
        }
    ]


async def test_update_query_runtime_manual_allocations_returns_runtime_snapshot(client, app):
    class FakeQueryRuntimeService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def apply_manual_allocations(self, *, config_id: str, items: list[dict[str, object]]) -> dict[str, object]:
            self.calls.append(
                {
                    "config_id": config_id,
                    "items": items,
                }
            )
            return {
                "running": True,
                "config_id": config_id,
                "config_name": "查询配置A",
                "message": "运行中",
                "account_count": 1,
                "started_at": "2026-03-22T12:00:00",
                "stopped_at": None,
                "total_query_count": 0,
                "total_found_count": 0,
                "modes": {},
                "group_rows": [],
                "recent_events": [],
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "item_name": "AK-47 | Redline",
                        "max_price": 123.45,
                        "min_wear": 0.1,
                        "max_wear": 0.7,
                        "detail_min_wear": 0.12,
                        "detail_max_wear": 0.3,
                        "manual_paused": False,
                        "query_count": 5,
                        "modes": {
                            "new_api": {
                                "mode_type": "new_api",
                                "target_dedicated_count": 1,
                                "actual_dedicated_count": 2,
                                "status": "dedicated",
                                "status_message": "专属中 2/1",
                            }
                        },
                    }
                ],
            }

    app.state.query_runtime_service = FakeQueryRuntimeService()

    response = await client.put(
        "/query-runtime/configs/cfg-1/manual-assignments",
        json={
            "items": [
                {
                    "query_item_id": "item-1",
                    "mode_type": "new_api",
                    "target_actual_count": 2,
                }
            ]
        },
    )

    assert response.status_code == 200
    assert app.state.query_runtime_service.calls == [
        {
            "config_id": "cfg-1",
            "items": [
                {
                    "query_item_id": "item-1",
                    "mode_type": "new_api",
                    "target_actual_count": 2,
                }
            ],
        }
    ]
    assert response.json()["item_rows"][0]["modes"]["new_api"]["actual_dedicated_count"] == 2


async def test_apply_query_runtime_config_returns_runtime_snapshot(client, app):
    class FakeQueryRuntimeService:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def apply_runtime_config(self, *, config_id: str) -> dict[str, object]:
            self.calls.append(config_id)
            return {
                "running": True,
                "config_id": config_id,
                "config_name": "查询配置A",
                "message": "运行中",
                "account_count": 1,
                "started_at": "2026-03-22T12:00:00",
                "stopped_at": None,
                "total_query_count": 0,
                "total_found_count": 0,
                "modes": {},
                "group_rows": [],
                "recent_events": [],
                "item_rows": [],
            }

    app.state.query_runtime_service = FakeQueryRuntimeService()

    response = await client.post("/query-runtime/configs/cfg-1/apply-config")

    assert response.status_code == 200
    assert app.state.query_runtime_service.calls == ["cfg-1"]
    assert response.json()["config_id"] == "cfg-1"


async def test_update_query_runtime_manual_allocations_returns_404_for_missing_config(client, app):
    class FakeQueryRuntimeService:
        def apply_manual_allocations(self, *, config_id: str, items: list[dict[str, object]]) -> dict[str, object]:
            raise KeyError("查询配置不存在")

    app.state.query_runtime_service = FakeQueryRuntimeService()

    response = await client.put(
        "/query-runtime/configs/missing/manual-assignments",
        json={
            "items": [
                {
                    "query_item_id": "item-1",
                    "mode_type": "new_api",
                    "target_actual_count": 1,
                }
            ]
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "查询配置不存在"}


async def test_update_query_runtime_manual_allocations_returns_409_when_config_is_not_running(client, app):
    class FakeQueryRuntimeService:
        def apply_manual_allocations(self, *, config_id: str, items: list[dict[str, object]]) -> dict[str, object]:
            raise ValueError("当前配置未在运行，无法提交运行时分配")

    app.state.query_runtime_service = FakeQueryRuntimeService()

    response = await client.put(
        "/query-runtime/configs/cfg-1/manual-assignments",
        json={
            "items": [
                {
                    "query_item_id": "item-1",
                    "mode_type": "new_api",
                    "target_actual_count": 1,
                }
            ]
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "当前配置未在运行，无法提交运行时分配"}
