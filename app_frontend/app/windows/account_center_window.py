from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QMessageBox
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_frontend.app.dialogs.create_account_dialog import CreateAccountDialog
from app_frontend.app.dialogs.edit_account_dialog import EditAccountDialog
from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog
from app_frontend.app.controllers.account_center_controller import AccountCenterController
from app_frontend.app.services.async_runner import InlineTaskRunner, QtAsyncRunner
from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
from app_frontend.app.widgets.account_detail_panel import AccountDetailPanel
from app_frontend.app.widgets.account_table import AccountTableWidget


class AccountCenterWindow(QWidget):
    def __init__(
        self,
        *,
        view_model: AccountCenterViewModel,
        backend_client=None,
        task_runner=None,
        create_dialog_factory=None,
        edit_dialog_factory=None,
        login_task_dialog_factory=None,
        confirm_service=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self.backend_client = backend_client
        self.task_runner = task_runner or (QtAsyncRunner() if backend_client is not None else InlineTaskRunner())
        self.create_dialog_factory = create_dialog_factory or (lambda parent=None: CreateAccountDialog(parent=parent))
        self.edit_dialog_factory = edit_dialog_factory or (
            lambda account, parent=None: EditAccountDialog(account=account, parent=parent)
        )
        self.login_task_dialog_factory = login_task_dialog_factory or (
            lambda on_resolve_conflict, parent=None: LoginTaskDialog(
                on_resolve_conflict=on_resolve_conflict,
                parent=parent,
            )
        )
        self.confirm_service = confirm_service or _QtConfirmService(self)
        self.login_task_dialog: LoginTaskDialog | None = None

        self.setWindowTitle("C5 账号中心")
        self.account_table = AccountTableWidget()
        self.detail_panel = AccountDetailPanel()
        self.status_label = QLabel("准备就绪")
        self.status_label.setProperty("tone", "neutral")
        self.refresh_button = QPushButton("刷新列表")
        self.create_account_button = QPushButton("新建账号")
        self.view_detail_button = QPushButton("查看详情")
        self.edit_account_button = self.detail_panel.edit_query_button
        self.start_login_button = self.detail_panel.start_login_button
        self.clear_purchase_button = self.detail_panel.clear_purchase_button
        self.delete_account_button = self.detail_panel.delete_account_button
        self.controller = AccountCenterController(
            view_model=self.view_model,
            backend_client=self.backend_client,
            task_runner=self.task_runner,
            publish_status=self._publish_status,
            refresh_view=self.refresh_accounts,
            publish_login_task=self._publish_login_task,
            publish_error=self._handle_error,
        )

        action_grid = QGridLayout()
        action_grid.addWidget(self.refresh_button, 0, 0)
        action_grid.addWidget(self.create_account_button, 0, 1)
        action_grid.addWidget(self.view_detail_button, 1, 0, 1, 2)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.account_table)
        left_layout.addLayout(action_grid)

        root_layout = QHBoxLayout(self)
        root_layout.addLayout(left_layout, 3)
        root_layout.addWidget(self.detail_panel, 2)

        self.account_table.itemSelectionChanged.connect(self._handle_selection_changed)
        self.refresh_button.clicked.connect(self.load_accounts)
        self.create_account_button.clicked.connect(self._create_account)
        self.edit_account_button.clicked.connect(self._edit_account)
        self.view_detail_button.clicked.connect(self._open_selected_detail)
        self.start_login_button.clicked.connect(self._start_login)
        self.clear_purchase_button.clicked.connect(self._clear_purchase_capability)
        self.delete_account_button.clicked.connect(self._delete_account)

        self.setStyleSheet(
            """
            QWidget {
                background: #f4efe6;
                color: #1f1b16;
                font-family: "Microsoft YaHei UI";
                font-size: 13px;
            }
            QTableWidget {
                background: #fffdf8;
                border: 1px solid #ccbda8;
                gridline-color: #e5d8c4;
                selection-background-color: #d56f3e;
                selection-color: #fffdf8;
            }
            QHeaderView::section {
                background: #e6dac8;
                color: #1f1b16;
                padding: 8px;
                border: none;
                font-weight: 600;
            }
            QPushButton {
                background: #1f5f4a;
                color: #fffdf8;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #174a3a;
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

        self._publish_status("准备就绪")
        self.refresh_accounts()

    def refresh_accounts(self) -> None:
        self.account_table.set_rows(self.view_model.table_rows)
        if self.view_model.detail_account is None:
            self.detail_panel.clear_account()
        else:
            self.detail_panel.load_account(self.view_model.detail_account)
        self._sync_action_states()

    def load_accounts(self) -> None:
        self.controller.load_accounts()

    def _handle_selection_changed(self) -> None:
        self.view_model.select_account(self.account_table.selected_account_id())
        self._sync_action_states()

    def _open_selected_detail(self) -> None:
        account = self.view_model.open_selected_account_detail()
        if account is None:
            self.detail_panel.clear_account()
            self._sync_action_states()
            return
        self.detail_panel.load_account(account)
        self._sync_action_states()

    def _create_account(self) -> None:
        if self.backend_client is None:
            return
        dialog = self.create_dialog_factory(self)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        self.controller.create_account(dialog.build_payload())

    def _edit_account(self) -> None:
        if self.backend_client is None:
            return
        account = self.view_model.detail_account
        if account is None:
            return
        dialog = self.edit_dialog_factory(account, self)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        self.controller.edit_detail_account(dialog.build_payload())

    def _start_login(self) -> None:
        self.controller.start_login_for_detail()

    def _clear_purchase_capability(self) -> None:
        if self.backend_client is None:
            return
        account = self.view_model.detail_account
        if account is None:
            return
        if not self.confirm_service.ask("确认清除", "确定要清除当前账号的购买能力吗？"):
            self._publish_status("已取消清除购买能力")
            return
        self.controller.clear_purchase_capability_for_detail()

    def _delete_account(self) -> None:
        if self.backend_client is None:
            return
        account = self.view_model.detail_account
        if account is None:
            return
        if not self.confirm_service.ask("确认删除", "确定要删除当前账号吗？"):
            self._publish_status("已取消删除账号")
            return
        self.controller.delete_detail_account()

    def _resolve_login_conflict(self, action: str) -> None:
        self.controller.resolve_login_conflict(action)

    def _sync_action_states(self) -> None:
        has_selection = self.view_model.selected_account is not None
        backend_ready = self.backend_client is not None
        self.refresh_button.setEnabled(backend_ready)
        self.create_account_button.setEnabled(backend_ready)
        self.view_detail_button.setEnabled(has_selection)
        detail_loaded = self.view_model.detail_account is not None
        self.edit_account_button.setEnabled(backend_ready and detail_loaded)
        self.start_login_button.setEnabled(backend_ready and detail_loaded)
        self.clear_purchase_button.setEnabled(backend_ready and detail_loaded)
        self.delete_account_button.setEnabled(backend_ready and detail_loaded)

    def _handle_error(self, message: str) -> None:
        self._publish_status(f"操作失败: {message}")
        QMessageBox.warning(self, "操作失败", message)

    def _publish_login_task(self, task_payload: dict[str, Any]) -> None:
        if self.login_task_dialog is None:
            self.login_task_dialog = self.login_task_dialog_factory(self._resolve_login_conflict, self)
            self.login_task_dialog.show()
        self.login_task_dialog.update_task(task_payload)

    def _publish_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("tone", _status_tone(message))
        self.style().unpolish(self.status_label)
        self.style().polish(self.status_label)
        self.status_label.update()


class _QtConfirmService:
    def __init__(self, parent: QWidget) -> None:
        self._parent = parent

    def ask(self, title: str, message: str) -> bool:
        result = QMessageBox.question(
            self._parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes


def _status_tone(message: str) -> str:
    if message.startswith("操作失败:"):
        return "error"
    if message.startswith("已取消"):
        return "warn"
    if message.startswith("冲突处理完成:") or message.startswith("已") or message.endswith("完成"):
        return "ok"
    if "冲突" in message:
        return "warn"
    return "neutral"
