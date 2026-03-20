from __future__ import annotations

from PySide6.QtCore import Qt


def build_snapshot(*, running: bool = False) -> dict:
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
        "accounts": [
            {
                "account_id": "a1",
                "display_name": "主号",
                "purchase_capability_state": "bound",
                "purchase_pool_state": "active",
                "selected_steam_id": "steam-1",
                "selected_inventory_remaining_capacity": 90,
                "selected_inventory_max": 1000,
                "last_error": None,
                "total_purchased_count": 2,
            }
        ],
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
        self.start_calls = 0
        self.stop_calls = 0
        self.status_calls = 0
        self.detail_calls: list[str] = []

    async def get_purchase_runtime_status(self) -> dict:
        self.status_calls += 1
        return build_snapshot()

    async def start_purchase_runtime(self) -> dict:
        self.start_calls += 1
        return build_snapshot(running=True)

    async def stop_purchase_runtime(self) -> dict:
        self.stop_calls += 1
        return build_snapshot(running=False)

    async def get_purchase_runtime_inventory_detail(self, account_id: str) -> dict:
        self.detail_calls.append(account_id)
        return build_inventory_detail()


class FakeInventoryDetailDialog:
    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.loaded_detail = None
        self.error_message = None
        self.shown = False

    def load_detail(self, detail: dict) -> None:
        self.loaded_detail = dict(detail)

    def show_error(self, message: str) -> None:
        self.error_message = message

    def show(self) -> None:
        self.shown = True


def test_purchase_runtime_window_controls_runtime_without_settings_form(qtbot):
    from app_frontend.app.services.async_runner import InlineTaskRunner
    from app_frontend.app.viewmodels.purchase_runtime_vm import PurchaseRuntimeViewModel
    from app_frontend.app.windows.purchase_runtime_window import PurchaseRuntimeWindow

    backend_client = FakeBackendClient()
    window = PurchaseRuntimeWindow(
        view_model=PurchaseRuntimeViewModel(),
        backend_client=backend_client,
        task_runner=InlineTaskRunner(),
    )
    qtbot.addWidget(window)
    assert not hasattr(window, "whitelist_input")
    assert not hasattr(window, "save_settings_button")

    qtbot.mouseClick(window.start_button, Qt.LeftButton)
    assert window.runtime_panel.summary_label.text() == "运行中"

    qtbot.mouseClick(window.stop_button, Qt.LeftButton)

    assert not hasattr(window, "query_only_checkbox")
    assert backend_client.start_calls == 1
    assert backend_client.stop_calls == 1
    assert window.status_label.text() == "购买运行已停止"


def test_purchase_runtime_window_refreshes_status_from_backend(qtbot):
    from app_frontend.app.services.async_runner import InlineTaskRunner
    from app_frontend.app.viewmodels.purchase_runtime_vm import PurchaseRuntimeViewModel
    from app_frontend.app.windows.purchase_runtime_window import PurchaseRuntimeWindow

    backend_client = FakeBackendClient()
    window = PurchaseRuntimeWindow(
        view_model=PurchaseRuntimeViewModel(),
        backend_client=backend_client,
        task_runner=InlineTaskRunner(),
    )
    qtbot.addWidget(window)

    qtbot.mouseClick(window.refresh_button, Qt.LeftButton)

    assert backend_client.status_calls == 1
    assert window.status_label.text() == "购买运行状态已刷新"
    assert window.runtime_panel.summary_label.text() == "未运行"


def test_purchase_runtime_window_opens_inventory_detail_on_account_double_click(qtbot):
    from app_frontend.app.services.async_runner import InlineTaskRunner
    from app_frontend.app.viewmodels.purchase_runtime_vm import PurchaseRuntimeViewModel
    from app_frontend.app.windows.purchase_runtime_window import PurchaseRuntimeWindow

    backend_client = FakeBackendClient()
    dialogs: list[FakeInventoryDetailDialog] = []

    def dialog_factory(parent=None):
        dialog = FakeInventoryDetailDialog(parent=parent)
        dialogs.append(dialog)
        return dialog

    window = PurchaseRuntimeWindow(
        view_model=PurchaseRuntimeViewModel(),
        backend_client=backend_client,
        task_runner=InlineTaskRunner(),
        inventory_detail_dialog_factory=dialog_factory,
    )
    qtbot.addWidget(window)
    window.view_model.load_status(build_snapshot(running=True))
    window.refresh_view()

    window.runtime_panel.account_table.cellDoubleClicked.emit(0, 0)

    assert backend_client.detail_calls == ["a1"]
    assert len(dialogs) == 1
    assert dialogs[0].loaded_detail == build_inventory_detail()
    assert dialogs[0].shown is True
