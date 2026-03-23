from __future__ import annotations


async def test_get_runtime_settings_returns_query_and_purchase_settings(client):
    response = await client.get("/runtime-settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["settings_id"] == "default"
    assert payload["query_settings"]["modes"]["new_api"]["cooldown_min_seconds"] == 1.0
    assert payload["query_settings"]["modes"]["fast_api"]["cooldown_min_seconds"] == 0.2
    assert payload["query_settings"]["modes"]["token"]["cooldown_min_seconds"] == 10.0
    assert payload["purchase_settings"] == {"ip_bucket_limits": {}}
    assert payload["updated_at"] is not None


async def test_put_runtime_query_settings_validates_mode_minimums(client):
    response = await client.put(
        "/runtime-settings/query",
        json={
            "modes": {
                "new_api": {
                    "enabled": True,
                    "cooldown_min_seconds": 1.0,
                    "cooldown_max_seconds": 1.0,
                    "random_delay_enabled": False,
                    "random_delay_min_seconds": 0.0,
                    "random_delay_max_seconds": 0.0,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                },
                "fast_api": {
                    "enabled": True,
                    "cooldown_min_seconds": 0.1,
                    "cooldown_max_seconds": 0.2,
                    "random_delay_enabled": False,
                    "random_delay_min_seconds": 0.0,
                    "random_delay_max_seconds": 0.0,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                },
                "token": {
                    "enabled": True,
                    "cooldown_min_seconds": 10.0,
                    "cooldown_max_seconds": 10.0,
                    "random_delay_enabled": False,
                    "random_delay_min_seconds": 0.0,
                    "random_delay_max_seconds": 0.0,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                },
            },
            "item_pacing": {
                "new_api": {
                    "strategy": "fixed_divided_by_actual_allocated_workers",
                    "fixed_seconds": 0.5,
                },
                "fast_api": {
                    "strategy": "fixed_divided_by_actual_allocated_workers",
                    "fixed_seconds": 0.5,
                },
                "token": {
                    "strategy": "fixed_divided_by_actual_allocated_workers",
                    "fixed_seconds": 0.5,
                },
            },
        },
    )

    assert response.status_code == 422


async def test_put_runtime_query_settings_saves_latest_snapshot_without_touching_purchase_settings(client):
    response = await client.put(
        "/runtime-settings/query",
        json={
            "modes": {
                "new_api": {
                    "enabled": True,
                    "cooldown_min_seconds": 1.5,
                    "cooldown_max_seconds": 1.8,
                    "random_delay_enabled": True,
                    "random_delay_min_seconds": 0.1,
                    "random_delay_max_seconds": 0.3,
                    "window_enabled": True,
                    "start_hour": 1,
                    "start_minute": 2,
                    "end_hour": 3,
                    "end_minute": 4,
                },
                "fast_api": {
                    "enabled": False,
                    "cooldown_min_seconds": 0.2,
                    "cooldown_max_seconds": 0.4,
                    "random_delay_enabled": False,
                    "random_delay_min_seconds": 0.0,
                    "random_delay_max_seconds": 0.0,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                },
                "token": {
                    "enabled": True,
                    "cooldown_min_seconds": 10.0,
                    "cooldown_max_seconds": 12.0,
                    "random_delay_enabled": False,
                    "random_delay_min_seconds": 0.0,
                    "random_delay_max_seconds": 0.0,
                    "window_enabled": False,
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 0,
                    "end_minute": 0,
                },
            },
            "item_pacing": {
                "new_api": {
                    "strategy": "fixed_divided_by_actual_allocated_workers",
                    "fixed_seconds": 1.2,
                },
                "fast_api": {
                    "strategy": "fixed_divided_by_actual_allocated_workers",
                    "fixed_seconds": 0.5,
                },
                "token": {
                    "strategy": "fixed_divided_by_actual_allocated_workers",
                    "fixed_seconds": 0.75,
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_settings"]["modes"]["new_api"]["cooldown_min_seconds"] == 1.5
    assert payload["query_settings"]["modes"]["fast_api"]["enabled"] is False
    assert payload["query_settings"]["item_pacing"]["token"]["fixed_seconds"] == 0.75
    assert payload["purchase_settings"] == {"ip_bucket_limits": {}}


async def test_put_runtime_purchase_settings_validates_concurrency_limit(client):
    response = await client.put(
        "/runtime-settings/purchase",
        json={
            "ip_bucket_limits": {
                "direct": {
                    "concurrency_limit": 0,
                }
            }
        },
    )

    assert response.status_code == 422


async def test_put_runtime_purchase_settings_saves_latest_snapshot_without_touching_query_settings(client):
    response = await client.put(
        "/runtime-settings/purchase",
        json={
            "ip_bucket_limits": {
                "direct": {
                    "concurrency_limit": 2,
                },
                "proxy://bucket-a": {
                    "concurrency_limit": 3,
                },
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_settings"]["modes"]["fast_api"]["cooldown_min_seconds"] == 0.2
    assert payload["purchase_settings"] == {
        "ip_bucket_limits": {
            "direct": {
                "concurrency_limit": 2,
            },
            "proxy://bucket-a": {
                "concurrency_limit": 3,
            },
        }
    }
