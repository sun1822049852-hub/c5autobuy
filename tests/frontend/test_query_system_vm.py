from __future__ import annotations


def _config(config_id: str, *, name: str, description: str = "", item_count: int = 0) -> dict:
    items = [
        {
            "query_item_id": f"{config_id}-item-{index}",
            "config_id": config_id,
            "product_url": f"https://example.com/{index}",
            "external_item_id": str(index),
            "item_name": f"Item {index}",
            "market_hash_name": f"Hash {index}",
            "min_wear": None,
            "max_wear": None,
            "max_price": None,
            "last_market_price": None,
            "last_detail_sync_at": None,
            "sort_order": index,
            "created_at": "2026-03-16T12:00:00",
            "updated_at": "2026-03-16T12:00:00",
        }
        for index in range(item_count)
    ]
    return {
        "config_id": config_id,
        "name": name,
        "description": description,
        "enabled": True,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
        "items": items,
        "mode_settings": [
            {
                "mode_setting_id": f"{config_id}-m1",
                "config_id": config_id,
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
                "created_at": "2026-03-16T12:00:00",
                "updated_at": "2026-03-16T12:00:00",
            },
            {
                "mode_setting_id": f"{config_id}-m2",
                "config_id": config_id,
                "mode_type": "fast_api",
                "enabled": False,
                "window_enabled": False,
                "start_hour": 0,
                "start_minute": 0,
                "end_hour": 0,
                "end_minute": 0,
                "base_cooldown_min": 0.2,
                "base_cooldown_max": 0.2,
                "random_delay_enabled": False,
                "random_delay_min": 0.0,
                "random_delay_max": 0.0,
                "created_at": "2026-03-16T12:00:00",
                "updated_at": "2026-03-16T12:00:00",
            },
        ],
    }


def test_query_system_vm_opens_selected_config_detail():
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel

    vm = QuerySystemViewModel()
    vm.set_configs(
        [
            _config("cfg-1", name="白天配置", description="白天跑", item_count=2),
            _config("cfg-2", name="夜间配置", description="夜里跑", item_count=1),
        ]
    )

    vm.select_config("cfg-2")

    assert vm.detail_config is not None
    assert vm.detail_config["config_id"] == "cfg-2"
    assert vm.config_rows[1]["item_count"] == 1
    assert vm.config_rows[1]["mode_summary"] == "new_api / fast_api(关)"


def test_query_system_vm_tracks_runtime_status():
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel

    vm = QuerySystemViewModel()

    vm.set_runtime_status(
        {
            "running": True,
            "config_id": "cfg-1",
            "config_name": "白天配置",
            "message": "运行中",
            "account_count": 2,
            "modes": {
                "new_api": {"mode_type": "new_api", "enabled": True, "eligible_account_count": 1},
                "fast_api": {"mode_type": "fast_api", "enabled": True, "eligible_account_count": 2},
            },
        }
    )

    assert vm.runtime_status["running"] is True
    assert vm.runtime_summary == "运行中: 白天配置 (账号 2)"


def test_query_system_vm_updates_existing_mode_setting():
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel

    vm = QuerySystemViewModel()
    vm.set_configs([_config("cfg-1", name="白天配置", item_count=1)])
    vm.select_config("cfg-1")

    vm.update_mode_setting(
        "cfg-1",
        {
            "mode_setting_id": "cfg-1-m1",
            "config_id": "cfg-1",
            "mode_type": "new_api",
            "enabled": False,
            "window_enabled": True,
            "start_hour": 8,
            "start_minute": 0,
            "end_hour": 20,
            "end_minute": 0,
            "base_cooldown_min": 0.5,
            "base_cooldown_max": 1.0,
            "random_delay_enabled": True,
            "random_delay_min": 0.2,
            "random_delay_max": 0.6,
            "created_at": "2026-03-16T12:00:00",
            "updated_at": "2026-03-16T12:30:00",
        },
    )

    assert vm.detail_config["mode_settings"][0]["enabled"] is False
    assert vm.detail_config["mode_settings"][0]["window_enabled"] is True
    assert vm.config_rows[0]["mode_summary"] == "new_api(关) / fast_api(关)"


def test_query_system_vm_adds_updates_and_removes_items():
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel

    vm = QuerySystemViewModel()
    vm.set_configs([_config("cfg-1", name="白天配置", item_count=1)])
    vm.select_config("cfg-1")

    vm.upsert_item(
        "cfg-1",
        {
            "query_item_id": "cfg-1-item-2",
            "config_id": "cfg-1",
            "product_url": "https://example.com/2",
            "external_item_id": "2",
            "item_name": "Item 2",
            "market_hash_name": "Hash 2",
            "min_wear": 0.0,
            "max_wear": 0.2,
            "max_price": 100.0,
            "last_market_price": 90.0,
            "last_detail_sync_at": None,
            "sort_order": 2,
            "created_at": "2026-03-16T12:00:00",
            "updated_at": "2026-03-16T12:00:00",
        },
    )
    vm.upsert_item(
        "cfg-1",
        {
            "query_item_id": "cfg-1-item-0",
            "config_id": "cfg-1",
            "product_url": "https://example.com/0",
            "external_item_id": "0",
            "item_name": "Item 0",
            "market_hash_name": "Hash 0",
            "min_wear": None,
            "max_wear": 0.11,
            "max_price": 88.0,
            "last_market_price": 70.0,
            "last_detail_sync_at": None,
            "sort_order": 0,
            "created_at": "2026-03-16T12:00:00",
            "updated_at": "2026-03-16T12:30:00",
        },
    )
    vm.remove_item("cfg-1", "cfg-1-item-2")

    assert len(vm.detail_config["items"]) == 1
    assert vm.detail_config["items"][0]["query_item_id"] == "cfg-1-item-0"
    assert vm.detail_config["items"][0]["max_price"] == 88.0
    assert vm.config_rows[0]["item_count"] == 1
