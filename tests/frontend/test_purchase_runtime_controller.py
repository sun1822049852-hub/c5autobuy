from __future__ import annotations


from app_frontend.app.viewmodels.purchase_runtime_vm import PurchaseRuntimeViewModel


def build_snapshot(*, running: bool = False, query_only: bool = False) -> dict:
    return {
        "running": running,
        "message": "运行中" if running else "未运行",
        "started_at": "2026-03-16T12:00:00" if running else None,
        "stopped_at": None if running else "2026-03-16T12:30:00",
        "queue_size": 1 if running else 0,
        "active_account_count": 1 if running else 0,
        "total_account_count": 2,
        "total_purchased_count": 3,
        "recent_events": [],
        "accounts": [],
        "settings": {
            "query_only": query_only,
            "whitelist_account_ids": ["a1"],
            "updated_at": "2026-03-16T12:05:00",
        },
    }


def build_inventory_detail() -> dict:
    return {
        "account_id": "a1",
        "display_name": "主号",
        "selected_steam_id": "steam-1",
        "refreshed_at": "2026-03-16T12:15:00",
        "last_error": None,
        "inventories": [
            {
                "steamId": "steam-1",
                "inventory_num": 910,
                "inventory_max": 1000,
                "remaining_capacity": 90,
                "is_selected": True,
                "is_available": True,
            }
        ],
    }


class FakeBackendClient:
    def __init__(self) -> None:
        self.updated_payloads: list[dict] = []
        self.start_calls = 0
        self.stop_calls = 0
        self.detail_calls: list[str] = []

    async def get_purchase_runtime_status(self) -> dict:
        return build_snapshot()

    async def start_purchase_runtime(self) -> dict:
        self.start_calls += 1
        return build_snapshot(running=True)

    async def stop_purchase_runtime(self) -> dict:
        self.stop_calls += 1
        return build_snapshot(running=False)

    async def update_purchase_runtime_settings(self, payload: dict) -> dict:
        self.updated_payloads.append(dict(payload))
        return build_snapshot(running=False, query_only=bool(payload["query_only"]))

    async def get_purchase_runtime_inventory_detail(self, account_id: str) -> dict:
        self.detail_calls.append(account_id)
        return build_inventory_detail()


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
    from app_frontend.app.controllers.purchase_runtime_controller import PurchaseRuntimeController

    view_model = PurchaseRuntimeViewModel()
    backend_client = FakeBackendClient()
    statuses: list[str] = []
    errors: list[str] = []
    refresh_counter = {"count": 0}

    controller = PurchaseRuntimeController(
        view_model=view_model,
        backend_client=backend_client,
        task_runner=InlineTaskRunner(),
        publish_status=statuses.append,
        refresh_view=lambda: refresh_counter.__setitem__("count", refresh_counter["count"] + 1),
        publish_error=errors.append,
    )
    return controller, view_model, backend_client, statuses, errors, refresh_counter


def test_purchase_runtime_controller_loads_status():
    controller, view_model, _backend_client, statuses, errors, refresh_counter = _build_controller()

    controller.load_status(silent=False)

    assert view_model.summary["message"] == "未运行"
    assert refresh_counter["count"] == 1
    assert errors == []
    assert statuses[-1] == "购买运行状态已刷新"


def test_purchase_runtime_controller_updates_settings_and_controls_runtime():
    controller, view_model, backend_client, statuses, errors, refresh_counter = _build_controller()

    controller.save_settings({"query_only": True, "whitelist_account_ids": ["a1"]})
    controller.start_runtime()
    controller.stop_runtime()

    assert backend_client.updated_payloads == [{"query_only": True, "whitelist_account_ids": ["a1"]}]
    assert backend_client.start_calls == 1
    assert backend_client.stop_calls == 1
    assert view_model.summary["message"] == "未运行"
    assert view_model.settings["query_only"] is False
    assert refresh_counter["count"] == 3
    assert errors == []
    assert statuses[-1] == "购买运行已停止"


def test_purchase_runtime_controller_loads_inventory_detail():
    controller, _view_model, backend_client, statuses, errors, _refresh_counter = _build_controller()
    loaded_details: list[dict] = []
    detail_errors: list[str] = []

    controller.load_inventory_detail(
        "a1",
        on_success=loaded_details.append,
        on_error=detail_errors.append,
    )

    assert backend_client.detail_calls == ["a1"]
    assert loaded_details == [build_inventory_detail()]
    assert detail_errors == []
    assert errors == []
    assert statuses[-1] == "库存详情已加载"
