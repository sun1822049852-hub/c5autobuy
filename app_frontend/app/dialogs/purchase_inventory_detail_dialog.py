from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


def _readonly_line_edit() -> QLineEdit:
    field = QLineEdit()
    field.setReadOnly(True)
    return field


class PurchaseInventoryDetailDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("库存详情")
        self.resize(760, 480)

        self.error_label = QLabel("")
        self.error_label.setProperty("tone", "error")
        self.error_label.hide()
        self.account_name_input = _readonly_line_edit()
        self.selected_steam_id_input = _readonly_line_edit()
        self.refreshed_at_input = _readonly_line_edit()
        self.last_error_input = _readonly_line_edit()
        self.empty_state_label = QLabel("")
        self.inventory_table = QTableWidget(0, 6)
        self.inventory_table.setHorizontalHeaderLabels(
            ["仓库ID", "当前数量", "容量上限", "剩余容量", "是否当前目标", "是否可用"]
        )
        self.inventory_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.inventory_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.inventory_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inventory_table.verticalHeader().setVisible(False)
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        summary_group = QGroupBox("库存摘要")
        summary_form = QFormLayout(summary_group)
        summary_form.addRow("账号", self.account_name_input)
        summary_form.addRow("目标仓库", self.selected_steam_id_input)
        summary_form.addRow("快照时间", self.refreshed_at_input)
        summary_form.addRow("最近错误", self.last_error_input)

        inventories_group = QGroupBox("小仓库明细")
        inventories_layout = QVBoxLayout(inventories_group)
        inventories_layout.addWidget(self.empty_state_label)
        inventories_layout.addWidget(self.inventory_table)

        layout = QVBoxLayout(self)
        layout.addWidget(self.error_label)
        layout.addWidget(summary_group)
        layout.addWidget(inventories_group, 1)

    def load_detail(self, detail: dict[str, Any]) -> None:
        self.error_label.clear()
        self.error_label.hide()
        self.account_name_input.setText(str(detail.get("display_name") or detail.get("account_id") or ""))
        self.selected_steam_id_input.setText(str(detail.get("selected_steam_id") or "-"))
        self.refreshed_at_input.setText(str(detail.get("refreshed_at") or ""))
        self.last_error_input.setText(str(detail.get("last_error") or ""))

        inventories = [dict(row) for row in detail.get("inventories") or [] if isinstance(row, dict)]
        self.inventory_table.setRowCount(len(inventories))
        for row_index, inventory in enumerate(inventories):
            self.inventory_table.setItem(row_index, 0, QTableWidgetItem(str(inventory.get("steamId") or "")))
            self.inventory_table.setItem(row_index, 1, QTableWidgetItem(str(int(inventory.get("inventory_num", 0)))))
            self.inventory_table.setItem(row_index, 2, QTableWidgetItem(str(int(inventory.get("inventory_max", 0)))))
            self.inventory_table.setItem(
                row_index,
                3,
                QTableWidgetItem(str(int(inventory.get("remaining_capacity", 0)))),
            )
            self.inventory_table.setItem(
                row_index,
                4,
                QTableWidgetItem("是" if inventory.get("is_selected") else "否"),
            )
            self.inventory_table.setItem(
                row_index,
                5,
                QTableWidgetItem("是" if inventory.get("is_available") else "否"),
            )

        self.empty_state_label.setText("暂无库存快照" if not inventories else "")

    def show_error(self, message: str) -> None:
        self.error_label.setText(f"加载失败: {message}")
        self.error_label.show()
        self.account_name_input.clear()
        self.selected_steam_id_input.clear()
        self.refreshed_at_input.clear()
        self.last_error_input.clear()
        self.empty_state_label.clear()
        self.inventory_table.setRowCount(0)
