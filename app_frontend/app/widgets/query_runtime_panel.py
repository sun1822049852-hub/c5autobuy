from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_frontend.app.formatters.query_runtime_display import (
    build_event_rows,
    build_group_rows,
    build_mode_rows,
    format_runtime_summary,
)


def _readonly_line_edit() -> QLineEdit:
    field = QLineEdit()
    field.setReadOnly(True)
    return field


class QueryRuntimePanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._recent_events: list[dict[str, Any]] = []
        self.summary_label = QLabel("未运行")
        self.summary_label.setProperty("tone", "neutral")
        self.config_name_input = _readonly_line_edit()
        self.account_count_input = _readonly_line_edit()
        self.mode_table = QTableWidget(0, 6)
        self.mode_table.setHorizontalHeaderLabels(["模式", "状态", "活跃/可参与", "查询/命中", "时间窗", "最近错误"])
        self.mode_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.mode_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.mode_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mode_table.verticalHeader().setVisible(False)
        self.mode_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.group_table = QTableWidget(0, 8)
        self.group_table.setHorizontalHeaderLabels(
            ["账号", "模式", "状态", "时间窗", "冷却", "查询/命中", "最近成功", "最近错误"]
        )
        self.group_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.group_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.group_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.group_table.verticalHeader().setVisible(False)
        self.group_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.event_table = QTableWidget(0, 6)
        self.event_table.setHorizontalHeaderLabels(["时间", "模式", "账号", "查询项", "结果", "说明"])
        self.event_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.event_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.event_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.event_table.verticalHeader().setVisible(False)
        self.event_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.event_detail_status_label = QLabel("选择一条命中事件查看详情")
        self.event_detail_match_count_input = _readonly_line_edit()
        self.event_detail_total_price_input = _readonly_line_edit()
        self.event_detail_total_wear_input = _readonly_line_edit()
        self.event_detail_product_table = QTableWidget(0, 3)
        self.event_detail_product_table.setHorizontalHeaderLabels(["商品ID", "价格", "返利"])
        self.event_detail_product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.event_detail_product_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.event_detail_product_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.event_detail_product_table.verticalHeader().setVisible(False)
        self.event_detail_product_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        summary_group = QGroupBox("运行状态")
        summary_form = QFormLayout(summary_group)
        summary_form.addRow("摘要", self.summary_label)
        summary_form.addRow("当前配置", self.config_name_input)
        summary_form.addRow("账号数", self.account_count_input)

        modes_group = QGroupBox("模式统计")
        modes_layout = QVBoxLayout(modes_group)
        modes_layout.addWidget(self.mode_table)

        groups_group = QGroupBox("查询组明细")
        groups_layout = QVBoxLayout(groups_group)
        groups_layout.addWidget(self.group_table)

        events_group = QGroupBox("最近事件")
        events_layout = QVBoxLayout(events_group)
        events_layout.addWidget(self.event_table)

        detail_group = QGroupBox("命中详情")
        detail_layout = QVBoxLayout(detail_group)
        detail_form = QFormLayout()
        detail_form.addRow("状态", self.event_detail_status_label)
        detail_form.addRow("命中数量", self.event_detail_match_count_input)
        detail_form.addRow("总价", self.event_detail_total_price_input)
        detail_form.addRow("总磨损和", self.event_detail_total_wear_input)
        detail_layout.addLayout(detail_form)
        detail_layout.addWidget(self.event_detail_product_table)

        layout = QVBoxLayout(self)
        layout.addWidget(summary_group)
        layout.addWidget(modes_group)
        layout.addWidget(groups_group)
        layout.addWidget(events_group)
        layout.addWidget(detail_group)
        layout.addStretch(1)

        self.event_table.itemSelectionChanged.connect(self._sync_event_detail)

        self.load_status(
            {
                "running": False,
                "config_id": None,
                "config_name": None,
                "message": "未运行",
                "account_count": 0,
                "group_rows": [],
                "recent_events": [],
                "modes": {},
            }
        )

    def load_status(self, status: dict[str, Any]) -> None:
        self.summary_label.setText(format_runtime_summary(status))
        self.summary_label.setProperty("tone", "ok" if status.get("running") else "neutral")
        self.style().unpolish(self.summary_label)
        self.style().polish(self.summary_label)
        self.summary_label.update()

        self.config_name_input.setText(str(status.get("config_name") or ""))
        self.account_count_input.setText(str(status.get("account_count", 0)))

        rows = build_mode_rows(status)
        self.mode_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.mode_table.setItem(row_index, 0, QTableWidgetItem(row["mode_type"]))
            self.mode_table.setItem(row_index, 1, QTableWidgetItem(row["enabled"]))
            self.mode_table.setItem(row_index, 2, QTableWidgetItem(row["account_state"]))
            self.mode_table.setItem(row_index, 3, QTableWidgetItem(row["query_state"]))
            self.mode_table.setItem(row_index, 4, QTableWidgetItem(row["window_state"]))
            self.mode_table.setItem(row_index, 5, QTableWidgetItem(row["last_error"]))

        group_rows = build_group_rows(status)
        self.group_table.setRowCount(len(group_rows))
        for row_index, row in enumerate(group_rows):
            self.group_table.setItem(row_index, 0, QTableWidgetItem(row["account_display_name"]))
            self.group_table.setItem(row_index, 1, QTableWidgetItem(row["mode_type"]))
            self.group_table.setItem(row_index, 2, QTableWidgetItem(row["status"]))
            self.group_table.setItem(row_index, 3, QTableWidgetItem(row["window_state"]))
            self.group_table.setItem(row_index, 4, QTableWidgetItem(row["cooldown"]))
            self.group_table.setItem(row_index, 5, QTableWidgetItem(row["query_state"]))
            self.group_table.setItem(row_index, 6, QTableWidgetItem(row["last_success_at"]))
            self.group_table.setItem(row_index, 7, QTableWidgetItem(row["last_error"]))

        self._recent_events = [dict(event) for event in (status.get("recent_events") or []) if isinstance(event, dict)]
        event_rows = build_event_rows(status)
        self.event_table.setRowCount(len(event_rows))
        for row_index, row in enumerate(event_rows):
            self.event_table.setItem(row_index, 0, QTableWidgetItem(row["timestamp"]))
            self.event_table.setItem(row_index, 1, QTableWidgetItem(row["mode_type"]))
            self.event_table.setItem(row_index, 2, QTableWidgetItem(row["account_id"]))
            self.event_table.setItem(row_index, 3, QTableWidgetItem(row["query_item_name"]))
            self.event_table.setItem(row_index, 4, QTableWidgetItem(row["result"]))
            self.event_table.setItem(row_index, 5, QTableWidgetItem(row["message"]))
        self._select_default_event()

    def _select_default_event(self) -> None:
        if not self._recent_events:
            self.event_table.clearSelection()
            self._clear_event_detail("选择一条命中事件查看详情")
            return

        selected_row = 0
        for index, event in enumerate(self._recent_events):
            if event.get("product_list"):
                selected_row = index
                break
        self.event_table.selectRow(selected_row)
        self._sync_event_detail()

    def _sync_event_detail(self) -> None:
        selection_model = self.event_table.selectionModel()
        if selection_model is None:
            self._clear_event_detail("选择一条命中事件查看详情")
            return

        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            self._clear_event_detail("选择一条命中事件查看详情")
            return

        row_index = selected_rows[0].row()
        if row_index < 0 or row_index >= len(self._recent_events):
            self._clear_event_detail("选择一条命中事件查看详情")
            return

        event = self._recent_events[row_index]
        products = [dict(product) for product in (event.get("product_list") or []) if isinstance(product, dict)]
        if not products:
            self._clear_event_detail("当前事件没有命中商品明细")
            return

        account_name = str(event.get("account_display_name") or event.get("account_id") or "")
        query_item_name = str(event.get("query_item_name") or event.get("query_item_id") or "")
        self.event_detail_status_label.setText(f"{account_name} / {event.get('mode_type')} / {query_item_name}")
        self.event_detail_match_count_input.setText(str(event.get("match_count", 0)))
        self.event_detail_total_price_input.setText(_format_decimal(event.get("total_price"), digits=2))
        self.event_detail_total_wear_input.setText(_format_decimal(event.get("total_wear_sum"), digits=6))
        self.event_detail_product_table.setRowCount(len(products))
        for row_index, product in enumerate(products):
            self.event_detail_product_table.setItem(row_index, 0, QTableWidgetItem(str(product.get("productId") or "")))
            self.event_detail_product_table.setItem(
                row_index,
                1,
                QTableWidgetItem(_format_decimal(product.get("price"), digits=2)),
            )
            self.event_detail_product_table.setItem(
                row_index,
                2,
                QTableWidgetItem(_format_decimal(product.get("actRebateAmount"), digits=2)),
            )

    def _clear_event_detail(self, message: str) -> None:
        self.event_detail_status_label.setText(message)
        self.event_detail_match_count_input.clear()
        self.event_detail_total_price_input.clear()
        self.event_detail_total_wear_input.clear()
        self.event_detail_product_table.setRowCount(0)


def _format_decimal(value: Any, *, digits: int) -> str:
    if value is None or value == "":
        return ""
    return f"{float(value):.{digits}f}"
