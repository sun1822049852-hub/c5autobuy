from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app_frontend.app.controllers.query_system_controller import QuerySystemController
from app_frontend.app.dialogs.query_config_dialog import QueryConfigDialog
from app_frontend.app.dialogs.query_item_dialog import QueryItemDialog
from app_frontend.app.dialogs.query_mode_settings_dialog import QueryModeSettingsDialog
from app_frontend.app.dialogs.query_runtime_prepare_dialog import QueryRuntimePrepareDialog
from app_frontend.app.services.async_runner import InlineTaskRunner, QtAsyncRunner
from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
from app_frontend.app.widgets.query_config_detail_panel import QueryConfigDetailPanel
from app_frontend.app.widgets.query_config_list import QueryConfigListWidget
from app_frontend.app.widgets.query_runtime_panel import QueryRuntimePanel


class QuerySystemWindow(QWidget):
    def __init__(
        self,
        *,
        view_model: QuerySystemViewModel,
        backend_client=None,
        task_runner=None,
        controller=None,
        create_dialog_factory=None,
        edit_config_dialog_factory=None,
        mode_settings_dialog_factory=None,
        add_item_dialog_factory=None,
        edit_item_dialog_factory=None,
        prepare_runtime_dialog_factory=None,
        confirm_service=None,
        runtime_poll_interval_ms: int = 1000,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.view_model = view_model
        self.backend_client = backend_client
        self.task_runner = task_runner or (QtAsyncRunner() if backend_client is not None else InlineTaskRunner())
        self._runtime_poll_interval_ms = runtime_poll_interval_ms
        self._runtime_refresh_in_flight = False
        self.create_dialog_factory = create_dialog_factory or (lambda parent=None: QueryConfigDialog(parent=parent))
        self.edit_config_dialog_factory = edit_config_dialog_factory or (
            lambda config, parent=None: QueryConfigDialog(config=config, parent=parent)
        )
        self.mode_settings_dialog_factory = mode_settings_dialog_factory or (
            lambda mode_setting, parent=None: QueryModeSettingsDialog(mode_setting=mode_setting, parent=parent)
        )
        self.add_item_dialog_factory = add_item_dialog_factory or (
            lambda parent=None: QueryItemDialog(
                backend_client=self.backend_client,
                task_runner=self.task_runner,
                parent=parent,
            )
        )
        self.edit_item_dialog_factory = edit_item_dialog_factory or (
            lambda item, parent=None: QueryItemDialog(
                item=item,
                backend_client=self.backend_client,
                task_runner=self.task_runner,
                parent=parent,
            )
        )
        self.prepare_runtime_dialog_factory = prepare_runtime_dialog_factory or (
            lambda config_id, config_name, parent=None: QueryRuntimePrepareDialog(
                config_id=config_id,
                config_name=config_name,
                backend_client=self.backend_client,
                task_runner=self.task_runner,
                parent=parent,
            )
        )
        self.confirm_service = confirm_service or _QtConfirmService(self)
        self.controller = controller or QuerySystemController(
            view_model=self.view_model,
            backend_client=self.backend_client,
            task_runner=self.task_runner,
            publish_status=self._publish_status,
            refresh_view=self.refresh_configs,
            publish_error=self._handle_error,
        )
        self._runtime_poll_timer = QTimer(self)
        self._runtime_poll_timer.setSingleShot(True)
        self._runtime_poll_timer.timeout.connect(self._refresh_runtime_status)

        self.setWindowTitle("C5 查询系统")
        self.status_label = QLabel("准备就绪")
        self.status_label.setProperty("tone", "neutral")
        self.config_table = QueryConfigListWidget()
        self.detail_panel = QueryConfigDetailPanel()
        self.runtime_panel = QueryRuntimePanel()
        self.refresh_button = QPushButton("刷新配置")
        self.create_config_button = QPushButton("新建配置")
        self.edit_config_button = QPushButton("编辑配置")
        self.delete_config_button = QPushButton("删除配置")
        self.add_item_button = QPushButton("新增商品")
        self.edit_item_button = QPushButton("编辑商品")
        self.refresh_item_detail_button = QPushButton("刷新详情")
        self.delete_item_button = QPushButton("删除商品")
        self.edit_mode_button = QPushButton("模式设置")
        self.start_runtime_button = QPushButton("启动查询")
        self.stop_runtime_button = QPushButton("停止查询")

        action_grid = QGridLayout()
        action_grid.addWidget(self.refresh_button, 0, 0)
        action_grid.addWidget(self.create_config_button, 0, 1)
        action_grid.addWidget(self.edit_config_button, 1, 0)
        action_grid.addWidget(self.delete_config_button, 1, 1)
        action_grid.addWidget(self.add_item_button, 2, 0)
        action_grid.addWidget(self.edit_item_button, 2, 1)
        action_grid.addWidget(self.refresh_item_detail_button, 3, 0)
        action_grid.addWidget(self.delete_item_button, 3, 1)
        action_grid.addWidget(self.edit_mode_button, 4, 0)
        action_grid.addWidget(self.start_runtime_button, 4, 1)
        action_grid.addWidget(self.stop_runtime_button, 5, 0)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.config_table)
        left_layout.addLayout(action_grid)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.detail_panel, 1)
        right_layout.addWidget(self.runtime_panel, 1)

        root_layout = QHBoxLayout(self)
        root_layout.addLayout(left_layout, 3)
        root_layout.addLayout(right_layout, 2)

        self.config_table.itemSelectionChanged.connect(self._handle_selection_changed)
        self.detail_panel.item_table.itemSelectionChanged.connect(self._sync_action_states)
        self.detail_panel.mode_table.itemSelectionChanged.connect(self._sync_action_states)
        self.refresh_button.clicked.connect(self.load_configs)
        self.create_config_button.clicked.connect(self._create_config)
        self.edit_config_button.clicked.connect(self._edit_config)
        self.delete_config_button.clicked.connect(self._delete_config)
        self.add_item_button.clicked.connect(self._add_item)
        self.edit_item_button.clicked.connect(self._edit_item)
        self.refresh_item_detail_button.clicked.connect(self._refresh_item_detail)
        self.delete_item_button.clicked.connect(self._delete_item)
        self.edit_mode_button.clicked.connect(self._edit_mode_setting)
        self.start_runtime_button.clicked.connect(self._start_runtime)
        self.stop_runtime_button.clicked.connect(self._stop_runtime)

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
                selection-background-color: #2f6d62;
                selection-color: #fffdf8;
            }
            QHeaderView::section {
                background: #d7e5dd;
                color: #1f1b16;
                padding: 8px;
                border: none;
                font-weight: 600;
            }
            QPushButton {
                background: #2f6d62;
                color: #fffdf8;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #25574e;
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
        self.refresh_configs()

    def refresh_configs(self) -> None:
        self.config_table.set_rows(self.view_model.config_rows)
        if self.view_model.detail_config is None:
            self.detail_panel.clear_config()
        else:
            self.detail_panel.load_config(self.view_model.detail_config)
        self.runtime_panel.load_status(self.view_model.runtime_status)
        self._sync_action_states()
        self._sync_runtime_polling()

    def load_configs(self) -> None:
        self.controller.load_configs()

    def _handle_selection_changed(self) -> None:
        self.view_model.select_config(self.config_table.selected_config_id())
        self.refresh_configs()

    def _create_config(self) -> None:
        dialog = self.create_dialog_factory(self)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        self.controller.create_config(dialog.build_payload())

    def _edit_config(self) -> None:
        config = self.view_model.detail_config
        if config is None:
            return
        dialog = self.edit_config_dialog_factory(config, self)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        self.controller.update_selected_config(dialog.build_payload())

    def _delete_config(self) -> None:
        config = self.view_model.detail_config
        if config is None:
            return
        if not self.confirm_service.ask("确认删除", "确定要删除当前配置吗？"):
            self._publish_status("已取消删除配置")
            return
        self.controller.delete_selected_config()

    def _start_runtime(self) -> None:
        config = self.view_model.detail_config
        if config is None:
            return
        dialog = self.prepare_runtime_dialog_factory(
            str(config.get("config_id") or ""),
            str(config.get("name") or ""),
            self,
        )
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        self.controller.start_runtime_for_selected()

    def _stop_runtime(self) -> None:
        self.controller.stop_runtime()

    def _add_item(self) -> None:
        dialog = self.add_item_dialog_factory(self)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        self.controller.add_item_to_selected_config(dialog.build_payload())

    def _edit_item(self) -> None:
        item = self.detail_panel.selected_item()
        if item is None:
            return
        dialog = self.edit_item_dialog_factory(item, self)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        self.controller.update_selected_item(str(item.get("query_item_id") or ""), dialog.build_payload())

    def _delete_item(self) -> None:
        item = self.detail_panel.selected_item()
        if item is None:
            return
        if not self.confirm_service.ask("确认删除", "确定要删除当前商品吗？"):
            self._publish_status("已取消删除商品")
            return
        self.controller.delete_selected_item(str(item.get("query_item_id") or ""))

    def _refresh_item_detail(self) -> None:
        item = self.detail_panel.selected_item()
        if item is None:
            return
        self.controller.refresh_selected_item_detail(str(item.get("query_item_id") or ""))

    def _edit_mode_setting(self) -> None:
        mode_setting = self.detail_panel.selected_mode_setting()
        if mode_setting is None:
            return
        dialog = self.mode_settings_dialog_factory(mode_setting, self)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        self.controller.update_selected_mode_setting(str(mode_setting.get("mode_type") or ""), dialog.build_payload())

    def _sync_action_states(self) -> None:
        has_selection = self.view_model.detail_config is not None
        has_item_selection = self.detail_panel.selected_item() is not None
        has_mode_selection = self.detail_panel.selected_mode_setting() is not None
        backend_ready = self.backend_client is not None or self.controller is not None
        self.refresh_button.setEnabled(backend_ready)
        self.create_config_button.setEnabled(backend_ready)
        self.edit_config_button.setEnabled(backend_ready and has_selection)
        self.delete_config_button.setEnabled(backend_ready and has_selection)
        self.add_item_button.setEnabled(backend_ready and has_selection)
        self.edit_item_button.setEnabled(backend_ready and has_selection and has_item_selection)
        self.refresh_item_detail_button.setEnabled(backend_ready and has_selection and has_item_selection)
        self.delete_item_button.setEnabled(backend_ready and has_selection and has_item_selection)
        self.edit_mode_button.setEnabled(backend_ready and has_selection and has_mode_selection)
        self.start_runtime_button.setEnabled(backend_ready and has_selection)
        self.stop_runtime_button.setEnabled(backend_ready)

    def _sync_runtime_polling(self) -> None:
        if not self.view_model.runtime_status.get("running"):
            self._runtime_poll_timer.stop()
            return
        if self._runtime_refresh_in_flight:
            return
        if not self._runtime_poll_timer.isActive():
            self._runtime_poll_timer.start(self._runtime_poll_interval_ms)

    def _refresh_runtime_status(self) -> None:
        if self._runtime_refresh_in_flight or not self.view_model.runtime_status.get("running"):
            return
        refresh_runtime_status = getattr(self.controller, "refresh_runtime_status", None)
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
    if "冲突" in message or message.startswith("已取消"):
        return "warn"
    if message.startswith("已") or message.endswith("停止") or message.endswith("运行中"):
        return "ok"
    return "neutral"
