from __future__ import annotations

from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel


def _config(config_id: str, *, name: str) -> dict:
    return {
        "config_id": config_id,
        "name": name,
        "description": "",
        "enabled": True,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
        "items": [
            {
                "query_item_id": f"{config_id}-item-1",
                "config_id": config_id,
                "product_url": "https://example.com/1",
                "external_item_id": "1",
                "item_name": "Item 1",
                "market_hash_name": "Hash 1",
                "min_wear": 0.0,
                "max_wear": 0.25,
                "max_price": 100.0,
                "last_market_price": 90.0,
                "last_detail_sync_at": None,
                "sort_order": 0,
                "created_at": "2026-03-16T12:00:00",
                "updated_at": "2026-03-16T12:00:00",
            }
        ],
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
            }
        ],
    }


class FakeBackendClient:
    def __init__(self) -> None:
        self.configs = [_config("cfg-1", name="白天配置")]
        self.created_payloads: list[dict] = []
        self.updated_config_calls: list[tuple[str, dict]] = []
        self.deleted_config_ids: list[str] = []
        self.started_config_ids: list[str] = []
        self.stop_calls = 0
        self.updated_mode_calls: list[tuple[str, str, dict]] = []
        self.added_item_calls: list[tuple[str, dict]] = []
        self.updated_item_calls: list[tuple[str, str, dict]] = []
        self.deleted_item_calls: list[tuple[str, str]] = []
        self.refreshed_item_calls: list[tuple[str, str]] = []

    async def list_query_configs(self) -> list[dict]:
        return [dict(config) for config in self.configs]

    async def create_query_config(self, payload: dict) -> dict:
        self.created_payloads.append(dict(payload))
        created = _config(f"cfg-{len(self.configs) + 1}", name=payload["name"])
        created["description"] = payload.get("description") or ""
        self.configs.append(created)
        return dict(created)

    async def update_query_config(self, config_id: str, payload: dict) -> dict:
        self.updated_config_calls.append((config_id, dict(payload)))
        for config in self.configs:
            if config["config_id"] == config_id:
                config.update(payload)
                return dict(config)
        raise KeyError(config_id)

    async def delete_query_config(self, config_id: str) -> None:
        self.deleted_config_ids.append(config_id)
        self.configs = [config for config in self.configs if config["config_id"] != config_id]

    async def get_query_runtime_status(self) -> dict:
        return {
            "running": False,
            "config_id": None,
            "config_name": None,
            "message": "未运行",
            "account_count": 0,
            "modes": {},
        }

    async def start_query_runtime(self, config_id: str) -> dict:
        self.started_config_ids.append(config_id)
        return {
            "running": True,
            "config_id": config_id,
            "config_name": "白天配置",
            "message": "运行中",
            "account_count": 0,
            "modes": {},
        }

    async def stop_query_runtime(self) -> dict:
        self.stop_calls += 1
        return {
            "running": False,
            "config_id": None,
            "config_name": None,
            "message": "未运行",
            "account_count": 0,
            "modes": {},
        }

    async def update_query_mode_setting(self, config_id: str, mode_type: str, payload: dict) -> dict:
        self.updated_mode_calls.append((config_id, mode_type, dict(payload)))
        setting = self.configs[0]["mode_settings"][0]
        setting.update(payload)
        setting["mode_type"] = mode_type
        return dict(setting)

    async def add_query_item(self, config_id: str, payload: dict) -> dict:
        self.added_item_calls.append((config_id, dict(payload)))
        item = {
            "query_item_id": f"{config_id}-item-{len(self.configs[0]['items']) + 1}",
            "config_id": config_id,
            "product_url": payload["product_url"],
            "external_item_id": "new-id",
            "item_name": "New Item",
            "market_hash_name": "New Hash",
            "min_wear": 0.0,
            "max_wear": payload.get("max_wear"),
            "max_price": payload.get("max_price"),
            "last_market_price": 123.0,
            "last_detail_sync_at": "2026-03-16T12:00:00",
            "sort_order": len(self.configs[0]["items"]),
            "created_at": "2026-03-16T12:00:00",
            "updated_at": "2026-03-16T12:00:00",
        }
        self.configs[0]["items"].append(item)
        return dict(item)

    async def update_query_item(self, config_id: str, item_id: str, payload: dict) -> dict:
        self.updated_item_calls.append((config_id, item_id, dict(payload)))
        for item in self.configs[0]["items"]:
            if item["query_item_id"] == item_id:
                item.update(payload)
                return dict(item)
        raise KeyError(item_id)

    async def delete_query_item(self, config_id: str, item_id: str) -> None:
        self.deleted_item_calls.append((config_id, item_id))
        self.configs[0]["items"] = [item for item in self.configs[0]["items"] if item["query_item_id"] != item_id]

    async def refresh_query_item_detail(self, config_id: str, item_id: str) -> dict:
        self.refreshed_item_calls.append((config_id, item_id))
        for item in self.configs[0]["items"]:
            if item["query_item_id"] != item_id:
                continue
            item.update(
                {
                    "item_name": "Refreshed Item",
                    "market_hash_name": "Refreshed Hash",
                    "min_wear": 0.12,
                    "detail_max_wear": 0.88,
                    "last_market_price": 234.5,
                    "last_detail_sync_at": "2026-03-17T12:30:00",
                }
            )
            return dict(item)
        raise KeyError(item_id)


class ErrorBackendClient(FakeBackendClient):
    async def get_query_runtime_status(self) -> dict:
        raise RuntimeError("runtime boom")


class InlineTaskRunner:
    def submit(self, coroutine_factory, *, on_success=None, on_error=None) -> None:
        import asyncio

        try:
            result = asyncio.run(coroutine_factory())
        except Exception as exc:  # pragma: no cover - defensive
            if on_error is not None:
                on_error(str(exc))
            return
        if on_success is not None:
            on_success(result)


def _build_controller():
    from app_frontend.app.controllers.query_system_controller import QuerySystemController

    view_model = QuerySystemViewModel()
    backend_client = FakeBackendClient()
    statuses: list[str] = []
    errors: list[str] = []
    refresh_counter = {"count": 0}

    controller = QuerySystemController(
        view_model=view_model,
        backend_client=backend_client,
        task_runner=InlineTaskRunner(),
        publish_status=statuses.append,
        refresh_view=lambda: refresh_counter.__setitem__("count", refresh_counter["count"] + 1),
        publish_error=errors.append,
    )
    return controller, view_model, backend_client, statuses, errors, refresh_counter


def test_query_system_controller_loads_configs_and_runtime_status():
    controller, view_model, _backend_client, statuses, errors, refresh_counter = _build_controller()

    controller.load_configs()

    assert view_model.config_rows[0]["name"] == "白天配置"
    assert view_model.runtime_status["running"] is False
    assert refresh_counter["count"] >= 1
    assert errors == []
    assert statuses[-1] == "已加载 1 个查询配置"


def test_query_system_controller_creates_config_and_controls_runtime():
    controller, view_model, backend_client, statuses, errors, refresh_counter = _build_controller()

    controller.load_configs()
    controller.create_config({"name": "夜间配置", "description": "夜里跑"})
    view_model.select_config("cfg-1")
    controller.start_runtime_for_selected()
    controller.stop_runtime()

    assert backend_client.created_payloads == [{"name": "夜间配置", "description": "夜里跑"}]
    assert backend_client.started_config_ids == ["cfg-1"]
    assert backend_client.stop_calls == 1
    assert view_model.runtime_status["running"] is False
    assert refresh_counter["count"] >= 3
    assert errors == []
    assert statuses[-1] == "查询任务已停止"


def test_query_system_controller_updates_and_deletes_selected_config():
    controller, view_model, backend_client, statuses, errors, refresh_counter = _build_controller()

    controller.load_configs()
    view_model.select_config("cfg-1")

    controller.update_selected_config({"name": "夜间配置", "description": "夜里跑"})

    assert backend_client.updated_config_calls == [("cfg-1", {"name": "夜间配置", "description": "夜里跑"})]
    assert view_model.detail_config is not None
    assert view_model.detail_config["name"] == "夜间配置"
    assert view_model.detail_config["description"] == "夜里跑"
    assert refresh_counter["count"] >= 2
    assert errors == []
    assert statuses[-1] == "查询配置已更新"

    controller.delete_selected_config()

    assert backend_client.deleted_config_ids == ["cfg-1"]
    assert view_model.detail_config is None
    assert refresh_counter["count"] >= 3
    assert errors == []
    assert statuses[-1] == "查询配置已删除"


def test_query_system_controller_updates_selected_mode_setting():
    controller, view_model, backend_client, statuses, errors, refresh_counter = _build_controller()

    controller.load_configs()
    view_model.select_config("cfg-1")

    controller.update_selected_mode_setting(
        "new_api",
        {
            "enabled": False,
            "window_enabled": True,
            "start_hour": 9,
            "start_minute": 15,
            "end_hour": 18,
            "end_minute": 45,
            "base_cooldown_min": 0.5,
            "base_cooldown_max": 1.0,
            "random_delay_enabled": True,
            "random_delay_min": 0.1,
            "random_delay_max": 0.3,
        },
    )

    assert backend_client.updated_mode_calls == [
        (
            "cfg-1",
            "new_api",
            {
                "enabled": False,
                "window_enabled": True,
                "start_hour": 9,
                "start_minute": 15,
                "end_hour": 18,
                "end_minute": 45,
                "base_cooldown_min": 0.5,
                "base_cooldown_max": 1.0,
                "random_delay_enabled": True,
                "random_delay_min": 0.1,
                "random_delay_max": 0.3,
            },
        )
    ]
    assert view_model.detail_config["mode_settings"][0]["enabled"] is False
    assert refresh_counter["count"] >= 2
    assert errors == []
    assert statuses[-1] == "模式参数已更新"


def test_query_system_controller_adds_updates_and_deletes_items():
    controller, view_model, backend_client, statuses, errors, refresh_counter = _build_controller()

    controller.load_configs()
    view_model.select_config("cfg-1")

    controller.add_item_to_selected_config(
        {
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262233",
            "max_wear": 0.18,
            "max_price": 222.0,
        }
    )
    controller.update_selected_item(
        "cfg-1-item-1",
        {
            "max_wear": 0.11,
            "max_price": 180.0,
        },
    )
    controller.delete_selected_item("cfg-1-item-1")

    assert backend_client.added_item_calls == [
        (
            "cfg-1",
            {
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262233",
                "max_wear": 0.18,
                "max_price": 222.0,
            },
        )
    ]
    assert backend_client.updated_item_calls == [("cfg-1", "cfg-1-item-1", {"max_wear": 0.11, "max_price": 180.0})]
    assert backend_client.deleted_item_calls == [("cfg-1", "cfg-1-item-1")]
    assert len(view_model.detail_config["items"]) == 1
    assert view_model.detail_config["items"][0]["query_item_id"] != "cfg-1-item-1"
    assert refresh_counter["count"] >= 4
    assert errors == []
    assert statuses[-1] == "商品已删除"


def test_query_system_controller_refreshes_selected_item_detail():
    controller, view_model, backend_client, statuses, errors, refresh_counter = _build_controller()

    controller.load_configs()
    view_model.select_config("cfg-1")

    controller.refresh_selected_item_detail("cfg-1-item-1")

    assert backend_client.refreshed_item_calls == [("cfg-1", "cfg-1-item-1")]
    assert view_model.detail_config["items"][0]["item_name"] == "Refreshed Item"
    assert view_model.detail_config["items"][0]["detail_max_wear"] == 0.88
    assert view_model.detail_config["items"][0]["last_market_price"] == 234.5
    assert refresh_counter["count"] >= 2
    assert errors == []
    assert statuses[-1] == "商品详情已刷新"


def test_query_system_controller_refreshes_runtime_status_silently():
    controller, view_model, _backend_client, statuses, errors, refresh_counter = _build_controller()
    completed: list[str] = []

    controller.refresh_runtime_status(on_complete=lambda: completed.append("done"))

    assert view_model.runtime_status["running"] is False
    assert refresh_counter["count"] == 1
    assert statuses == []
    assert errors == []
    assert completed == ["done"]


def test_query_system_controller_refresh_runtime_status_completes_on_error():
    from app_frontend.app.controllers.query_system_controller import QuerySystemController

    view_model = QuerySystemViewModel()
    backend_client = ErrorBackendClient()
    statuses: list[str] = []
    errors: list[str] = []
    refresh_counter = {"count": 0}
    completed: list[str] = []
    controller = QuerySystemController(
        view_model=view_model,
        backend_client=backend_client,
        task_runner=InlineTaskRunner(),
        publish_status=statuses.append,
        refresh_view=lambda: refresh_counter.__setitem__("count", refresh_counter["count"] + 1),
        publish_error=errors.append,
    )

    controller.refresh_runtime_status(on_complete=lambda: completed.append("done"))

    assert refresh_counter["count"] == 0
    assert statuses == []
    assert errors == ["runtime boom"]
    assert completed == ["done"]
