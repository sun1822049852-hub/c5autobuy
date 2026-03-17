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

    assert response.status_code == 200
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
