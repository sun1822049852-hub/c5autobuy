async def test_get_query_settings_returns_default_modes(client):
    response = await client.get("/query-settings")

    assert response.status_code == 200
    payload = response.json()
    modes = {
        mode["mode_type"]: mode
        for mode in payload["modes"]
    }
    assert payload["warnings"] == []
    assert set(modes) == {"new_api", "fast_api", "token"}
    assert modes["new_api"]["base_cooldown_min"] == 1.0
    assert modes["new_api"]["item_min_cooldown_seconds"] == 0.5
    assert modes["new_api"]["item_min_cooldown_strategy"] == "divide_by_assigned_count"
    assert modes["fast_api"]["base_cooldown_min"] == 0.2
    assert modes["token"]["base_cooldown_min"] == 10.0


async def test_put_query_settings_updates_modes_and_returns_token_warning(client):
    response = await client.put(
        "/query-settings",
        json={
            "modes": [
                {
                    "mode_type": "new_api",
                    "enabled": True,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                    "base_cooldown_min": 1.2,
                    "base_cooldown_max": 1.4,
                    "item_min_cooldown_seconds": 0.7,
                    "item_min_cooldown_strategy": "fixed",
                    "random_delay_enabled": False,
                    "random_delay_min": 0.0,
                    "random_delay_max": 0.0,
                },
                {
                    "mode_type": "fast_api",
                    "enabled": True,
                    "window_enabled": True,
                    "start_hour": 8,
                    "start_minute": 30,
                    "end_hour": 23,
                    "end_minute": 0,
                    "base_cooldown_min": 0.25,
                    "base_cooldown_max": 0.5,
                    "item_min_cooldown_seconds": 0.35,
                    "item_min_cooldown_strategy": "divide_by_assigned_count",
                    "random_delay_enabled": True,
                    "random_delay_min": 0.1,
                    "random_delay_max": 0.2,
                },
                {
                    "mode_type": "token",
                    "enabled": True,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                    "base_cooldown_min": 9.0,
                    "base_cooldown_max": 11.0,
                    "item_min_cooldown_seconds": 12.0,
                    "item_min_cooldown_strategy": "fixed",
                    "random_delay_enabled": True,
                    "random_delay_min": 1.0,
                    "random_delay_max": 2.0,
                },
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"] == [
        "浏览器查询器基础冷却低于 10 秒，封号风险极高",
    ]
    modes = {
        mode["mode_type"]: mode
        for mode in payload["modes"]
    }
    assert modes["fast_api"]["window_enabled"] is True
    assert modes["fast_api"]["start_hour"] == 8
    assert modes["fast_api"]["item_min_cooldown_seconds"] == 0.35
    assert modes["fast_api"]["item_min_cooldown_strategy"] == "divide_by_assigned_count"
    assert modes["token"]["base_cooldown_min"] == 9.0

    reloaded = await client.get("/query-settings")
    assert reloaded.status_code == 200
    reloaded_modes = {
        mode["mode_type"]: mode
        for mode in reloaded.json()["modes"]
    }
    assert reloaded_modes["new_api"]["base_cooldown_min"] == 1.2
    assert reloaded_modes["new_api"]["item_min_cooldown_strategy"] == "fixed"
    assert reloaded_modes["fast_api"]["random_delay_enabled"] is True


async def test_put_query_settings_rejects_fast_api_below_hard_minimum(client):
    response = await client.put(
        "/query-settings",
        json={
            "modes": [
                {
                    "mode_type": "new_api",
                    "enabled": True,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                    "base_cooldown_min": 1.0,
                    "base_cooldown_max": 1.0,
                    "random_delay_enabled": False,
                    "random_delay_min": 0.0,
                    "random_delay_max": 0.0,
                },
                {
                    "mode_type": "fast_api",
                    "enabled": True,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                    "base_cooldown_min": 0.1,
                    "base_cooldown_max": 0.1,
                    "random_delay_enabled": False,
                    "random_delay_min": 0.0,
                    "random_delay_max": 0.0,
                },
                {
                    "mode_type": "token",
                    "enabled": True,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                    "base_cooldown_min": 10.0,
                    "base_cooldown_max": 10.0,
                    "random_delay_enabled": False,
                    "random_delay_min": 0.0,
                    "random_delay_max": 0.0,
                },
            ]
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "fast_api 基础冷却不能低于 0.2 秒"
