from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from app_frontend.app.services.async_runner import InlineTaskRunner


class FakeBackendClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    async def prepare_query_runtime(self, config_id: str, *, force_refresh: bool = False) -> dict:
        self.calls.append((config_id, force_refresh))
        return {
            "config_id": config_id,
            "config_name": "白天配置",
            "threshold_hours": 12,
            "updated_count": 1 if force_refresh else 0,
            "skipped_count": 0 if force_refresh else 1,
            "failed_count": 0,
            "items": [
                {
                    "query_item_id": "item-1",
                    "external_item_id": "1380979899390267393",
                    "item_name": "AK-47 | Redline",
                    "status": "updated" if force_refresh else "skipped",
                    "message": "商品详情已刷新" if force_refresh else "12小时内已同步，跳过",
                    "last_market_price": 123.45,
                    "min_wear": 0.1,
                    "detail_max_wear": 0.7,
                    "last_detail_sync_at": "2026-03-17T12:00:00",
                }
            ],
        }


def test_prepare_dialog_auto_refreshes_on_open_and_can_force_refresh(qtbot):
    from app_frontend.app.dialogs.query_runtime_prepare_dialog import QueryRuntimePrepareDialog

    backend_client = FakeBackendClient()
    dialog = QueryRuntimePrepareDialog(
        config_id="cfg-1",
        config_name="白天配置",
        backend_client=backend_client,
        task_runner=InlineTaskRunner(),
    )
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitUntil(lambda: backend_client.calls == [("cfg-1", False)], timeout=500)

    assert "白天配置" in dialog.summary_label.text()
    assert dialog.item_table.rowCount() == 1
    assert dialog.item_table.item(0, 3).text() == "0.1 ~ 0.7"
    assert dialog.start_button.isEnabled() is True

    qtbot.mouseClick(dialog.refresh_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: backend_client.calls == [("cfg-1", False), ("cfg-1", True)], timeout=500)

    assert "已更新 1" in dialog.summary_label.text()


def test_prepare_dialog_accepts_after_user_confirms_start(qtbot):
    from app_frontend.app.dialogs.query_runtime_prepare_dialog import QueryRuntimePrepareDialog

    dialog = QueryRuntimePrepareDialog(
        config_id="cfg-1",
        config_name="白天配置",
        backend_client=FakeBackendClient(),
        task_runner=InlineTaskRunner(),
    )
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitUntil(lambda: dialog.start_button.isEnabled() is True, timeout=500)
    qtbot.mouseClick(dialog.start_button, Qt.LeftButton)

    assert dialog.result() == int(QDialog.DialogCode.Accepted)
