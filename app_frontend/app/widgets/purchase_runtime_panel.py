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

from app_frontend.app.viewmodels.purchase_runtime_vm import PurchaseRuntimeViewModel


def _readonly_line_edit() -> QLineEdit:
    field = QLineEdit()
    field.setReadOnly(True)
    return field


class PurchaseRuntimePanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.summary_label = QLabel("未运行")
        self.summary_label.setProperty("tone", "neutral")
        self.queue_size_input = _readonly_line_edit()
        self.active_account_count_input = _readonly_line_edit()
        self.total_account_count_input = _readonly_line_edit()
        self.recovery_waiting_count_input = _readonly_line_edit()
        self.total_purchased_count_input = _readonly_line_edit()
        self.account_table = QTableWidget(0, 7)
        self.account_table.setHorizontalHeaderLabels(
            ["显示名", "购买能力", "购买池", "目标仓库", "容量", "恢复状态", "已购"]
        )
        self.account_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.account_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.account_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.account_table.verticalHeader().setVisible(False)
        self.account_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.event_table = QTableWidget(0, 5)
        self.event_table.setHorizontalHeaderLabels(["时间", "状态", "账号", "商品/事件", "说明"])
        self.event_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.event_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.event_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.event_table.verticalHeader().setVisible(False)
        self.event_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        summary_group = QGroupBox("运行摘要")
        summary_form = QFormLayout(summary_group)
        summary_form.addRow("状态", self.summary_label)
        summary_form.addRow("队列数量", self.queue_size_input)
        summary_form.addRow("活跃账号", self.active_account_count_input)
        summary_form.addRow("账号总数", self.total_account_count_input)
        summary_form.addRow("等待恢复", self.recovery_waiting_count_input)
        summary_form.addRow("累计购买", self.total_purchased_count_input)

        accounts_group = QGroupBox("购买账号")
        accounts_layout = QVBoxLayout(accounts_group)
        accounts_layout.addWidget(self.account_table)

        events_group = QGroupBox("最近事件")
        events_layout = QVBoxLayout(events_group)
        events_layout.addWidget(self.event_table)

        layout = QVBoxLayout(self)
        layout.addWidget(summary_group)
        layout.addWidget(accounts_group)
        layout.addWidget(events_group)
        layout.addStretch(1)

        self.load_status(
            {
                "running": False,
                "message": "未运行",
                "queue_size": 0,
                "active_account_count": 0,
                "total_account_count": 0,
                "total_purchased_count": 0,
                "accounts": [],
                "recent_events": [],
            }
        )

    def load_status(self, status: dict[str, Any]) -> None:
        view_model = PurchaseRuntimeViewModel()
        view_model.load_status(status)
        summary = view_model.summary
        self.summary_label.setText(summary["message"])
        self.summary_label.setProperty("tone", "ok" if status.get("running") else "neutral")
        self.style().unpolish(self.summary_label)
        self.style().polish(self.summary_label)
        self.summary_label.update()

        self.queue_size_input.setText(summary["queue_size"])
        self.active_account_count_input.setText(summary["active_account_count"])
        self.total_account_count_input.setText(summary["total_account_count"])
        self.recovery_waiting_count_input.setText(summary["recovery_waiting_count"])
        self.total_purchased_count_input.setText(summary["total_purchased_count"])

        accounts = view_model.account_rows
        self.account_table.setRowCount(len(accounts))
        for row_index, account in enumerate(accounts):
            self.account_table.setItem(
                row_index,
                0,
                QTableWidgetItem(str(account.get("display_name") or account.get("account_id") or "")),
            )
            self.account_table.setItem(row_index, 1, QTableWidgetItem(str(account.get("purchase_capability_state") or "")))
            self.account_table.setItem(row_index, 2, QTableWidgetItem(str(account.get("purchase_pool_state") or "")))
            self.account_table.setItem(
                row_index,
                3,
                QTableWidgetItem(str(account.get("selected_steam_id") or "-")),
            )
            self.account_table.setItem(row_index, 4, QTableWidgetItem(str(account.get("capacity_text") or "-")))
            self.account_table.setItem(row_index, 5, QTableWidgetItem(str(account.get("recovery_status") or "")))
            self.account_table.setItem(
                row_index,
                6,
                QTableWidgetItem(str(int(account.get("total_purchased_count", 0) or 0))),
            )

        events = view_model.recent_event_rows
        self.event_table.setRowCount(len(events))
        for row_index, event in enumerate(events):
            self.event_table.setItem(row_index, 0, QTableWidgetItem(str(event.get("occurred_at") or "")))
            self.event_table.setItem(row_index, 1, QTableWidgetItem(str(event.get("status") or "")))
            self.event_table.setItem(row_index, 2, QTableWidgetItem(str(event.get("account_display_name") or "")))
            self.event_table.setItem(
                row_index,
                3,
                QTableWidgetItem(str(event.get("query_item_name") or event.get("status_text") or "")),
            )
            self.event_table.setItem(row_index, 4, QTableWidgetItem(str(event.get("message") or "")))
