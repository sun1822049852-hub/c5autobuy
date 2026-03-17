from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout


def _format_wear_range(min_wear: object, detail_max_wear: object) -> str:
    if min_wear is None or detail_max_wear is None:
        return ""
    return f"{min_wear} ~ {detail_max_wear}"


class QueryRuntimePrepareDialog(QDialog):
    def __init__(
        self,
        *,
        config_id: str,
        config_name: str,
        backend_client,
        task_runner,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config_id = config_id
        self._config_name = config_name
        self._backend_client = backend_client
        self._task_runner = task_runner
        self._has_auto_refreshed = False

        self.setWindowTitle(f"启动前准备 - {config_name}")
        self.summary_label = QLabel("正在准备...")
        self.summary_label.setWordWrap(True)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #8f2416;")

        self.item_table = QTableWidget(0, 5)
        self.item_table.setHorizontalHeaderLabels(["商品", "状态", "最低价", "完整磨损范围", "说明"])
        self.item_table.horizontalHeader().setStretchLastSection(True)
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.item_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        self.refresh_button = QPushButton("重新刷新价格")
        self.start_button = QPushButton("确认启动查询")
        self.cancel_button = QPushButton("取消")
        self.start_button.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.start_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.error_label)
        layout.addWidget(self.item_table)
        layout.addLayout(button_row)

        self.refresh_button.clicked.connect(lambda: self._request_prepare(force_refresh=True))
        self.start_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._has_auto_refreshed:
            return
        self._has_auto_refreshed = True
        self._request_prepare(force_refresh=False)

    def _request_prepare(self, *, force_refresh: bool) -> None:
        self.summary_label.setText(f"正在检查 {self._config_name} 的商品详情...")
        self.error_label.setText("")
        self.start_button.setEnabled(False)
        self._task_runner.submit(
            lambda: self._backend_client.prepare_query_runtime(self._config_id, force_refresh=force_refresh),
            on_success=self._handle_prepare_success,
            on_error=self._handle_prepare_error,
        )

    def _handle_prepare_success(self, summary: dict) -> None:
        self.summary_label.setText(
            f"{summary.get('config_name') or self._config_name}：已更新 {summary.get('updated_count', 0)}，"
            f"已跳过 {summary.get('skipped_count', 0)}，失败 {summary.get('failed_count', 0)}"
        )
        self._load_items(summary.get("items") or [])
        self.start_button.setEnabled(True)

    def _handle_prepare_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.summary_label.setText(f"{self._config_name}：启动前准备失败")

    def _load_items(self, items: list[dict]) -> None:
        self.item_table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.item_table.setItem(row, 0, QTableWidgetItem(str(item.get("item_name") or item.get("external_item_id") or "")))
            self.item_table.setItem(row, 1, QTableWidgetItem(str(item.get("status") or "")))
            price = item.get("last_market_price")
            self.item_table.setItem(row, 2, QTableWidgetItem("" if price is None else str(price)))
            self.item_table.setItem(row, 3, QTableWidgetItem(_format_wear_range(item.get("min_wear"), item.get("detail_max_wear"))))
            self.item_table.setItem(row, 4, QTableWidgetItem(str(item.get("message") or "")))
