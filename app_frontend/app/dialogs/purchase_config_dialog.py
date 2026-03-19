from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
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


class PurchaseConfigDialog(QDialog):
    def __init__(
        self,
        *,
        account: dict[str, Any],
        inventory_detail: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("购买配置")
        self.resize(760, 460)
        self._available_inventory_ids: set[str] = set()

        self.disabled_checkbox = QCheckBox("禁用该账号购买")
        self.disabled_checkbox.setChecked(bool(account.get("disabled", False)))
        self.current_selected_input = _readonly_line_edit()
        self.refreshed_at_input = _readonly_line_edit()
        self.last_error_input = _readonly_line_edit()
        self.hint_label = QLabel("")
        self.inventory_table = QTableWidget(0, 5)
        self.inventory_table.setHorizontalHeaderLabels(["仓库ID", "当前数量", "容量上限", "剩余容量", "状态"])
        self.inventory_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.inventory_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.inventory_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inventory_table.verticalHeader().setVisible(False)
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        summary_group = QGroupBox("当前配置")
        summary_form = QFormLayout(summary_group)
        summary_form.addRow("", self.disabled_checkbox)
        summary_form.addRow("当前仓库", self.current_selected_input)
        summary_form.addRow("快照时间", self.refreshed_at_input)
        summary_form.addRow("最近错误", self.last_error_input)

        inventory_group = QGroupBox("可选仓库")
        inventory_layout = QVBoxLayout(inventory_group)
        inventory_layout.addWidget(self.hint_label)
        inventory_layout.addWidget(self.inventory_table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(summary_group)
        layout.addWidget(inventory_group, 1)
        layout.addWidget(buttons)

        self._load_inventory_detail(account=account, inventory_detail=inventory_detail)

    def build_payload(self) -> dict[str, str | bool | None]:
        return {
            "disabled": self.disabled_checkbox.isChecked(),
            "selected_steam_id": self._selected_available_steam_id(),
        }

    def _load_inventory_detail(
        self,
        *,
        account: dict[str, Any],
        inventory_detail: dict[str, Any] | None,
    ) -> None:
        detail = inventory_detail or {}
        current_selected_steam_id = (
            str(detail.get("selected_steam_id") or "")
            or str(account.get("selected_steam_id") or "")
        )
        inventories = [dict(row) for row in detail.get("inventories") or [] if isinstance(row, dict)]

        self.current_selected_input.setText(current_selected_steam_id or "-")
        self.refreshed_at_input.setText(str(detail.get("refreshed_at") or ""))
        self.last_error_input.setText(str(detail.get("last_error") or ""))

        self._available_inventory_ids.clear()
        self.inventory_table.setRowCount(len(inventories))
        initial_selected_row = -1
        for row_index, inventory in enumerate(inventories):
            steam_id = str(inventory.get("steamId") or "")
            is_available = bool(inventory.get("is_available"))
            is_selected = bool(inventory.get("is_selected"))
            if is_available:
                self._available_inventory_ids.add(steam_id)
                if is_selected:
                    initial_selected_row = row_index

            values = [
                steam_id,
                str(int(inventory.get("inventory_num", 0))),
                str(int(inventory.get("inventory_max", 0))),
                str(int(inventory.get("remaining_capacity", 0))),
                self._status_text(is_selected=is_selected, is_available=is_available),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, steam_id)
                if not is_available:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    item.setForeground(Qt.GlobalColor.darkGray)
                self.inventory_table.setItem(row_index, column_index, item)

        if initial_selected_row >= 0:
            self.inventory_table.selectRow(initial_selected_row)
        else:
            self.inventory_table.clearSelection()

        self.hint_label.setText(self._build_hint(current_selected_steam_id=current_selected_steam_id, inventories=inventories))

    @staticmethod
    def _status_text(*, is_selected: bool, is_available: bool) -> str:
        if is_selected and is_available:
            return "当前已选"
        if is_selected and not is_available:
            return "当前仓库（库存已满）"
        if is_available:
            return "可切换"
        return "库存已满"

    @staticmethod
    def _build_hint(*, current_selected_steam_id: str, inventories: list[dict[str, Any]]) -> str:
        if not inventories:
            return "暂无仓库快照，当前只能修改是否参与购买。"
        if any(bool(row.get("is_selected")) and not bool(row.get("is_available")) for row in inventories):
            return f"当前仓库 {current_selected_steam_id or '-'} 已满，请切到可用仓库，或先禁用该账号购买。"
        if any(bool(row.get("is_available")) for row in inventories):
            return "请选择一个可用仓库；库存已满的仓库不会参与选择。"
        return "当前没有可用仓库，可以先禁用该账号购买。"

    def _selected_available_steam_id(self) -> str | None:
        row_index = self.inventory_table.currentRow()
        if row_index < 0:
            return None
        item = self.inventory_table.item(row_index, 0)
        if item is None:
            return None
        steam_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if steam_id not in self._available_inventory_ids:
            return None
        return steam_id or None
