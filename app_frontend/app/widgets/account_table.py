from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


class AccountTableWidget(QTableWidget):
    HEADERS = ["显示名", "查询能力", "购买能力", "购买池", "代理"]

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["display_name"],
                row["query_capability"],
                row["purchase_capability"],
                row["purchase_pool_state"],
                row["proxy"],
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row["account_id"])
                self.setItem(row_index, column_index, item)

    def selected_account_id(self) -> str | None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return None
        item = self.item(indexes[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

