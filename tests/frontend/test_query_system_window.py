from __future__ import annotations

from PySide6.QtCore import Qt


def _config(config_id: str, *, name: str) -> dict:
    return {
        "config_id": config_id,
        "name": name,
        "description": f"{name}描述",
        "enabled": True,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
        "items": [
            {
                "query_item_id": f"{config_id}-item-1",
                "config_id": config_id,
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "external_item_id": "1380979899390261111",
                "item_name": "测试商品",
                "market_hash_name": "Test Item (Field-Tested)",
                "min_wear": 0.0,
                "detail_max_wear": 0.7,
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


class FakeController:
    def __init__(self) -> None:
        self.load_calls = 0
        self.created_payloads: list[dict] = []
        self.updated_config_calls: list[dict] = []
        self.deleted_config_calls = 0
        self.start_calls = 0
        self.stop_calls = 0
        self.refresh_runtime_calls = 0
        self.updated_mode_calls: list[tuple[str, dict]] = []
        self.added_item_payloads: list[dict] = []
        self.updated_item_calls: list[tuple[str, dict]] = []
        self.deleted_item_ids: list[str] = []
        self.refreshed_item_ids: list[str] = []

    def load_configs(self) -> None:
        self.load_calls += 1

    def create_config(self, payload: dict) -> None:
        self.created_payloads.append(dict(payload))

    def update_selected_config(self, payload: dict) -> None:
        self.updated_config_calls.append(dict(payload))

    def delete_selected_config(self) -> None:
        self.deleted_config_calls += 1

    def start_runtime_for_selected(self) -> None:
        self.start_calls += 1

    def stop_runtime(self) -> None:
        self.stop_calls += 1

    def refresh_runtime_status(self, *, silent: bool = True, on_complete=None) -> None:
        self.refresh_runtime_calls += 1
        if on_complete is not None:
            on_complete()

    def update_selected_mode_setting(self, mode_type: str, payload: dict) -> None:
        self.updated_mode_calls.append((mode_type, dict(payload)))

    def add_item_to_selected_config(self, payload: dict) -> None:
        self.added_item_payloads.append(dict(payload))

    def update_selected_item(self, item_id: str, payload: dict) -> None:
        self.updated_item_calls.append((item_id, dict(payload)))

    def delete_selected_item(self, item_id: str) -> None:
        self.deleted_item_ids.append(item_id)

    def refresh_selected_item_detail(self, item_id: str) -> None:
        self.refreshed_item_ids.append(item_id)


class FakeConfirmService:
    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    def ask(self, title: str, message: str) -> bool:
        self.calls.append((title, message))
        return self.answer


class FakeDialog:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def exec(self) -> int:
        return 1

    def build_payload(self) -> dict:
        return dict(self._payload)


class FakeModeDialog(FakeDialog):
    pass


class FakeItemDialog(FakeDialog):
    pass


class FakePrepareDialog:
    def __init__(self, result_code: int = 1) -> None:
        self._result_code = result_code

    def exec(self) -> int:
        return self._result_code


def test_query_system_window_updates_detail_and_dispatches_actions(qtbot):
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
    from app_frontend.app.windows.query_system_window import QuerySystemWindow

    view_model = QuerySystemViewModel()
    view_model.set_configs([_config("cfg-1", name="白天配置"), _config("cfg-2", name="夜间配置")])
    view_model.set_runtime_status(
        {
            "running": True,
            "config_id": "cfg-1",
            "config_name": "白天配置",
            "message": "运行中",
            "account_count": 2,
            "total_query_count": 5,
            "total_found_count": 1,
            "modes": {
                "new_api": {
                    "mode_type": "new_api",
                    "enabled": True,
                    "eligible_account_count": 1,
                    "active_account_count": 1,
                    "in_window": True,
                    "query_count": 5,
                    "found_count": 1,
                    "next_window_start": None,
                    "next_window_end": None,
                    "last_error": None,
                },
            },
        }
    )
    controller = FakeController()
    confirm_service = FakeConfirmService(True)
    prepare_dialog_calls: list[tuple[str, str]] = []
    window = QuerySystemWindow(
        view_model=view_model,
        controller=controller,
        confirm_service=confirm_service,
        prepare_runtime_dialog_factory=lambda config_id, config_name, parent=None: (
            prepare_dialog_calls.append((config_id, config_name)) or FakePrepareDialog()
        ),
        create_dialog_factory=lambda parent=None: FakeDialog({"name": "新配置", "description": "测试"}),
        edit_config_dialog_factory=lambda config, parent=None: FakeDialog({"name": "改后配置", "description": "改后描述"}),
        mode_settings_dialog_factory=lambda mode_setting, parent=None: FakeModeDialog(
            {
                "enabled": False,
                "window_enabled": True,
                "start_hour": 9,
                "start_minute": 30,
                "end_hour": 18,
                "end_minute": 0,
                "base_cooldown_min": 0.5,
                "base_cooldown_max": 1.5,
                "random_delay_enabled": True,
                "random_delay_min": 0.1,
                "random_delay_max": 0.4,
            }
        ),
        add_item_dialog_factory=lambda parent=None: FakeItemDialog(
            {
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267788",
                "max_wear": 0.15,
                "max_price": 188.0,
            }
        ),
        edit_item_dialog_factory=lambda item, parent=None: FakeItemDialog(
            {
                "max_wear": 0.12,
                "max_price": 166.0,
            }
        ),
    )
    qtbot.addWidget(window)

    window.refresh_configs()
    window.config_table.selectRow(1)
    qtbot.wait(20)

    assert window.detail_panel.name_input.text() == "夜间配置"
    assert window.detail_panel.item_table.item(0, 1).text() == "0.0 ~ 0.7"
    assert window.detail_panel.item_table.item(0, 2).text() == "0.25"
    assert window.detail_panel.item_table.item(0, 5).text() == "未同步"
    assert window.runtime_panel.summary_label.text() == "运行中: 白天配置 (账号 2, 查询 5, 命中 1)"
    assert window.runtime_panel.mode_table.item(0, 2).text() == "1/1"
    assert window.runtime_panel.mode_table.item(0, 3).text() == "5/1"

    qtbot.mouseClick(window.refresh_button, Qt.LeftButton)
    qtbot.mouseClick(window.create_config_button, Qt.LeftButton)
    qtbot.mouseClick(window.edit_config_button, Qt.LeftButton)
    qtbot.mouseClick(window.delete_config_button, Qt.LeftButton)
    qtbot.mouseClick(window.edit_mode_button, Qt.LeftButton)
    qtbot.mouseClick(window.add_item_button, Qt.LeftButton)
    qtbot.mouseClick(window.edit_item_button, Qt.LeftButton)
    qtbot.mouseClick(window.refresh_item_detail_button, Qt.LeftButton)
    qtbot.mouseClick(window.delete_item_button, Qt.LeftButton)
    qtbot.mouseClick(window.start_runtime_button, Qt.LeftButton)
    qtbot.mouseClick(window.stop_runtime_button, Qt.LeftButton)

    assert controller.load_calls == 1
    assert controller.created_payloads == [{"name": "新配置", "description": "测试"}]
    assert controller.updated_config_calls == [{"name": "改后配置", "description": "改后描述"}]
    assert controller.deleted_config_calls == 1
    assert controller.updated_mode_calls == [
        (
            "new_api",
            {
                "enabled": False,
                "window_enabled": True,
                "start_hour": 9,
                "start_minute": 30,
                "end_hour": 18,
                "end_minute": 0,
                "base_cooldown_min": 0.5,
                "base_cooldown_max": 1.5,
                "random_delay_enabled": True,
                "random_delay_min": 0.1,
                "random_delay_max": 0.4,
            },
        )
    ]
    assert controller.added_item_payloads == [
        {
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267788",
            "max_wear": 0.15,
            "max_price": 188.0,
        }
    ]
    assert controller.updated_item_calls == [("cfg-2-item-1", {"max_wear": 0.12, "max_price": 166.0})]
    assert controller.refreshed_item_ids == ["cfg-2-item-1"]
    assert controller.deleted_item_ids == ["cfg-2-item-1"]
    assert confirm_service.calls == [("确认删除", "确定要删除当前配置吗？"), ("确认删除", "确定要删除当前商品吗？")]
    assert prepare_dialog_calls == [("cfg-2", "夜间配置")]
    assert controller.start_calls == 1
    assert controller.stop_calls == 1


def test_query_system_window_cancel_delete_keeps_item(qtbot):
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
    from app_frontend.app.windows.query_system_window import QuerySystemWindow

    view_model = QuerySystemViewModel()
    view_model.set_configs([_config("cfg-1", name="白天配置")])
    controller = FakeController()
    confirm_service = FakeConfirmService(False)
    window = QuerySystemWindow(
        view_model=view_model,
        controller=controller,
        confirm_service=confirm_service,
    )
    qtbot.addWidget(window)

    window.refresh_configs()
    window.config_table.selectRow(0)
    qtbot.wait(20)

    qtbot.mouseClick(window.delete_item_button, Qt.LeftButton)

    assert confirm_service.calls == [("确认删除", "确定要删除当前商品吗？")]
    assert controller.deleted_item_ids == []
    assert window.status_label.text() == "已取消删除商品"
    assert window.status_label.property("tone") == "warn"


def test_query_system_window_polls_runtime_while_running(qtbot):
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
    from app_frontend.app.windows.query_system_window import QuerySystemWindow

    view_model = QuerySystemViewModel()
    view_model.set_configs([_config("cfg-1", name="白天配置")])
    view_model.set_runtime_status(
        {
            "running": True,
            "config_id": "cfg-1",
            "config_name": "白天配置",
            "message": "运行中",
            "account_count": 1,
            "total_query_count": 0,
            "total_found_count": 0,
            "modes": {},
        }
    )
    controller = FakeController()
    window = QuerySystemWindow(
        view_model=view_model,
        controller=controller,
        runtime_poll_interval_ms=30,
    )
    qtbot.addWidget(window)

    window.refresh_configs()

    qtbot.waitUntil(lambda: controller.refresh_runtime_calls >= 1, timeout=300)


def test_query_system_window_stops_polling_after_runtime_stops(qtbot):
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
    from app_frontend.app.windows.query_system_window import QuerySystemWindow

    view_model = QuerySystemViewModel()
    view_model.set_configs([_config("cfg-1", name="白天配置")])
    view_model.set_runtime_status(
        {
            "running": True,
            "config_id": "cfg-1",
            "config_name": "白天配置",
            "message": "运行中",
            "account_count": 1,
            "total_query_count": 0,
            "total_found_count": 0,
            "modes": {},
        }
    )
    controller = FakeController()
    window = QuerySystemWindow(
        view_model=view_model,
        controller=controller,
        runtime_poll_interval_ms=30,
    )
    qtbot.addWidget(window)

    window.refresh_configs()
    qtbot.waitUntil(lambda: controller.refresh_runtime_calls >= 1, timeout=300)

    call_count = controller.refresh_runtime_calls
    view_model.set_runtime_status(
        {
            "running": False,
            "config_id": None,
            "config_name": None,
            "message": "未运行",
            "account_count": 0,
            "total_query_count": 0,
            "total_found_count": 0,
            "modes": {},
        }
    )
    window.refresh_configs()

    qtbot.wait(120)

    assert controller.refresh_runtime_calls == call_count


def test_query_system_window_does_not_start_runtime_when_prepare_dialog_is_rejected(qtbot):
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
    from app_frontend.app.windows.query_system_window import QuerySystemWindow

    view_model = QuerySystemViewModel()
    view_model.set_configs([_config("cfg-1", name="白天配置")])
    controller = FakeController()
    window = QuerySystemWindow(
        view_model=view_model,
        controller=controller,
        prepare_runtime_dialog_factory=lambda config_id, config_name, parent=None: FakePrepareDialog(0),
    )
    qtbot.addWidget(window)

    window.refresh_configs()
    window.config_table.selectRow(0)
    qtbot.wait(20)
    qtbot.mouseClick(window.start_runtime_button, Qt.LeftButton)

    assert controller.start_calls == 0


def test_query_system_window_default_add_item_dialog_factory_receives_backend_services(qtbot):
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
    from app_frontend.app.windows.query_system_window import QuerySystemWindow

    backend_client = object()
    task_runner = object()
    window = QuerySystemWindow(
        view_model=QuerySystemViewModel(),
        backend_client=backend_client,
        task_runner=task_runner,
    )
    qtbot.addWidget(window)

    dialog = window.add_item_dialog_factory(window)

    assert dialog._backend_client is backend_client
    assert dialog._task_runner is task_runner


def test_query_system_window_displays_last_detail_sync_time_in_item_table(qtbot):
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
    from app_frontend.app.windows.query_system_window import QuerySystemWindow

    config = _config("cfg-1", name="白天配置")
    config["items"][0]["last_detail_sync_at"] = "2026-03-17T12:30:00"

    view_model = QuerySystemViewModel()
    view_model.set_configs([config])
    window = QuerySystemWindow(
        view_model=view_model,
        controller=FakeController(),
    )
    qtbot.addWidget(window)

    window.refresh_configs()
    window.config_table.selectRow(0)
    qtbot.wait(20)

    assert window.detail_panel.item_table.item(0, 5).text() == "2026-03-17 12:30:00"
