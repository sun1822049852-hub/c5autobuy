from __future__ import annotations

import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_frontend.app.controllers.purchase_runtime_controller import PurchaseRuntimeController
from app_frontend.app.dialogs.purchase_inventory_detail_dialog import PurchaseInventoryDetailDialog
from app_frontend.app.services.async_runner import InlineTaskRunner, QtAsyncRunner
from app_frontend.app.viewmodels.purchase_runtime_vm import PurchaseRuntimeViewModel
from app_frontend.app.widgets.purchase_runtime_panel import PurchaseRuntimePanel


class PurchaseRuntimeWindow(QWidget):
    def __init__(
        self,
        *,
        view_model: PurchaseRuntimeViewModel,
        backend_client=None,
        task_runner=None,
        controller=None,
        inventory_detail_dialog_factory=None,
        runtime_poll_interval_ms: int = 1000,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self.backend_client = backend_client
        self.task_runner = task_runner or (QtAsyncRunner() if backend_client is not None else InlineTaskRunner())
        self._runtime_poll_interval_ms = runtime_poll_interval_ms
        self._runtime_refresh_in_flight = False
        self.inventory_detail_dialog_factory = inventory_detail_dialog_factory or (
            lambda parent=None: PurchaseInventoryDetailDialog(parent=parent)
        )
        self.inventory_detail_dialog = None
        self.controller = controller or PurchaseRuntimeController(
            view_model=self.view_model,
            backend_client=self.backend_client,
            task_runner=self.task_runner,
            publish_status=self._publish_status,
            refresh_view=self.refresh_view,
            publish_error=self._handle_error,
        )
        self._runtime_poll_timer = QTimer(self)
        self._runtime_poll_timer.setSingleShot(True)
        self._runtime_poll_timer.timeout.connect(self._refresh_runtime_status)

        self.setWindowTitle("C5 购买运行")
        self.status_label = QLabel("准备就绪")
        self.status_label.setProperty("tone", "neutral")
        self.query_only_checkbox = QCheckBox("仅查询模式")
        self.whitelist_input = QLineEdit()
        self.whitelist_input.setPlaceholderText("账号 ID，使用逗号分隔")
        self.refresh_button = QPushButton("刷新状态")
        self.save_settings_button = QPushButton("保存设置")
        self.start_button = QPushButton("启动购买")
        self.stop_button = QPushButton("停止购买")
        self.runtime_panel = PurchaseRuntimePanel()

        settings_group = QGroupBox("运行设置")
        settings_form = QFormLayout(settings_group)
        settings_form.addRow("模式", self.query_only_checkbox)
        settings_form.addRow("白名单", self.whitelist_input)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.refresh_button)
        action_layout.addWidget(self.save_settings_button)
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.stop_button)
        action_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(settings_group)
        layout.addLayout(action_layout)
        layout.addWidget(self.runtime_panel, 1)

        self.refresh_button.clicked.connect(self.load_status)
        self.save_settings_button.clicked.connect(self._save_settings)
        self.start_button.clicked.connect(self._start_runtime)
        self.stop_button.clicked.connect(self._stop_runtime)
        self.runtime_panel.account_table.cellDoubleClicked.connect(self._open_inventory_detail_for_row)

        self.setStyleSheet(
            """
            QWidget {
                background: #f4efe6;
                color: #1f1b16;
                font-family: "Microsoft YaHei UI";
                font-size: 13px;
            }
            QPushButton {
                background: #7a4a2e;
                color: #fffdf8;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #603823;
            }
            QGroupBox {
                background: #fbf7f0;
                border: 1px solid #d8ccb9;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                left: 12px;
                padding: 0 6px;
            }
            QLineEdit {
                background: #fffdf8;
                border: 1px solid #d8ccb9;
                border-radius: 6px;
                padding: 6px 8px;
            }
            QLabel[tone="ok"] {
                color: #174a2f;
                background: #e7f6ee;
                border: 1px solid #7dbb91;
                border-radius: 8px;
                padding: 8px 10px;
                font-weight: 600;
            }
            QLabel[tone="warn"] {
                color: #8a4b10;
                background: #fff1db;
                border: 1px solid #d9a14a;
                border-radius: 8px;
                padding: 8px 10px;
                font-weight: 600;
            }
            QLabel[tone="error"] {
                color: #8f2416;
                background: #fde8e4;
                border: 1px solid #cf6f5b;
                border-radius: 8px;
                padding: 8px 10px;
                font-weight: 600;
            }
            QLabel[tone="neutral"] {
                color: #1f1b16;
                background: #ebe2d5;
                border: 1px solid #ccbda8;
                border-radius: 8px;
                padding: 8px 10px;
                font-weight: 600;
            }
            """
        )

        self.refresh_view()
        self._publish_status("准备就绪")

    def refresh_view(self) -> None:
        self.runtime_panel.load_status(self.view_model.raw_status)
        settings = self.view_model.settings
        self.query_only_checkbox.setChecked(bool(settings["query_only"]))
        self.whitelist_input.setText(str(settings["whitelist_text"] or ""))
        self._sync_action_states()
        self._sync_runtime_polling()

    def load_status(self) -> None:
        self.controller.load_status(silent=False)

    def _save_settings(self) -> None:
        payload = {
            "query_only": self.query_only_checkbox.isChecked(),
            "whitelist_account_ids": self._parse_whitelist(self.whitelist_input.text()),
        }
        self.controller.save_settings(payload)

    def _start_runtime(self) -> None:
        self.controller.start_runtime()

    def _stop_runtime(self) -> None:
        self.controller.stop_runtime()

    def _sync_action_states(self) -> None:
        backend_ready = self.backend_client is not None or self.controller is not None
        self.refresh_button.setEnabled(backend_ready)
        self.save_settings_button.setEnabled(backend_ready)
        self.start_button.setEnabled(backend_ready)
        self.stop_button.setEnabled(backend_ready)

    def _sync_runtime_polling(self) -> None:
        if not self.view_model.raw_status.get("running"):
            self._runtime_poll_timer.stop()
            return
        if self._runtime_refresh_in_flight:
            return
        if not self._runtime_poll_timer.isActive():
            self._runtime_poll_timer.start(self._runtime_poll_interval_ms)

    def _refresh_runtime_status(self) -> None:
        if self._runtime_refresh_in_flight or not self.view_model.raw_status.get("running"):
            return
        refresh_runtime_status = getattr(self.controller, "load_status", None)
        if refresh_runtime_status is None:
            return
        self._runtime_refresh_in_flight = True
        try:
            refresh_runtime_status(silent=True, on_complete=self._handle_runtime_refresh_finished)
        except Exception:
            self._runtime_refresh_in_flight = False
            raise

    def _handle_runtime_refresh_finished(self) -> None:
        self._runtime_refresh_in_flight = False
        self._sync_runtime_polling()

    def _publish_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("tone", _status_tone(message))
        self.style().unpolish(self.status_label)
        self.style().polish(self.status_label)
        self.status_label.update()

    def _handle_error(self, message: str) -> None:
        self._publish_status(f"操作失败: {message}")
        QMessageBox.warning(self, "操作失败", message)

    def _open_inventory_detail_for_row(self, row_index: int, _column_index: int) -> None:
        account_rows = self.view_model.account_rows
        if row_index < 0 or row_index >= len(account_rows):
            return

        account_id = str(account_rows[row_index].get("account_id") or "")
        if not account_id:
            return

        dialog = self.inventory_detail_dialog_factory(self)
        self.inventory_detail_dialog = dialog
        self.controller.load_inventory_detail(
            account_id,
            on_success=lambda detail: self._show_inventory_detail(dialog, detail),
            on_error=lambda message: self._show_inventory_detail_error(dialog, message),
        )

    @staticmethod
    def _show_inventory_detail(dialog, detail: dict) -> None:
        load_detail = getattr(dialog, "load_detail", None)
        if callable(load_detail):
            load_detail(detail)
        show = getattr(dialog, "show", None)
        if callable(show):
            show()

    @staticmethod
    def _show_inventory_detail_error(dialog, message: str) -> None:
        show_error = getattr(dialog, "show_error", None)
        if callable(show_error):
            show_error(message)
        show = getattr(dialog, "show", None)
        if callable(show):
            show()

    @staticmethod
    def _parse_whitelist(raw_text: str) -> list[str]:
        parts = [part.strip() for part in re.split(r"[\s,，]+", raw_text or "") if part.strip()]
        return parts


def _status_tone(message: str) -> str:
    if message.startswith("操作失败:"):
        return "error"
    if message.startswith("已取消"):
        return "warn"
    if message.startswith("购买设置已保存") or message.endswith("运行中") or message.endswith("已停止"):
        return "ok"
    return "neutral"
