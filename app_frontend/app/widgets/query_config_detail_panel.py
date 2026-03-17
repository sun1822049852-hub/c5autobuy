from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _readonly_line_edit() -> QLineEdit:
    field = QLineEdit()
    field.setReadOnly(True)
    return field


def _format_wear_range(min_wear: object, detail_max_wear: object) -> str:
    if min_wear is None or detail_max_wear is None:
        return ""
    return f"{min_wear} ~ {detail_max_wear}"


def _format_detail_sync_time(last_detail_sync_at: object) -> str:
    if not last_detail_sync_at:
        return "未同步"
    raw_value = str(last_detail_sync_at)
    try:
        return datetime.fromisoformat(raw_value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw_value


class QueryConfigDetailPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.config_id_input = _readonly_line_edit()
        self.name_input = _readonly_line_edit()
        self.description_input = _readonly_line_edit()
        self.item_count_input = _readonly_line_edit()
        self.mode_summary_input = _readonly_line_edit()
        self.mode_table = QTableWidget(0, 3)
        self.mode_table.setHorizontalHeaderLabels(["模式", "状态", "冷却"])
        self.mode_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.mode_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.mode_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mode_table.verticalHeader().setVisible(False)
        self.mode_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.item_table = QTableWidget(0, 6)
        self.item_table.setHorizontalHeaderLabels(["商品", "完整磨损范围", "用户阈值", "价格上限", "市场名", "详情同步"])
        self.item_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.item_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.item_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        summary_group = QGroupBox("配置详情")
        summary_form = QFormLayout(summary_group)
        summary_form.addRow("配置ID", self.config_id_input)
        summary_form.addRow("配置名", self.name_input)
        summary_form.addRow("描述", self.description_input)
        summary_form.addRow("商品数", self.item_count_input)
        summary_form.addRow("商品列表", self.item_table)
        summary_form.addRow("模式", self.mode_summary_input)
        summary_form.addRow("模式列表", self.mode_table)

        layout = QVBoxLayout(self)
        layout.addWidget(summary_group)
        layout.addStretch(1)

        self.clear_config()

    def clear_config(self) -> None:
        for field in (
            self.config_id_input,
            self.name_input,
            self.description_input,
            self.item_count_input,
            self.mode_summary_input,
        ):
            field.clear()
        self.item_table.setRowCount(0)
        self.mode_table.setRowCount(0)

    def load_config(self, config: dict) -> None:
        self.config_id_input.setText(config.get("config_id", ""))
        self.name_input.setText(config.get("name", ""))
        self.description_input.setText(config.get("description") or "")
        mode_settings = list(config.get("mode_settings") or [])
        items = list(config.get("items") or [])
        self.item_count_input.setText(str(len(items)))
        mode_summary = " / ".join(
            [setting.get("mode_type") if setting.get("enabled", False) else f"{setting.get('mode_type')}(关)" for setting in mode_settings]
        )
        self.mode_summary_input.setText(mode_summary)
        self.item_table.setRowCount(len(items))
        for row_index, item in enumerate(items):
            wear_range_text = _format_wear_range(item.get("min_wear"), item.get("detail_max_wear"))
            self.item_table.setItem(row_index, 0, QTableWidgetItem(str(item.get("item_name") or item.get("external_item_id") or "")))
            self.item_table.setItem(row_index, 1, QTableWidgetItem(wear_range_text))
            self.item_table.setItem(row_index, 2, QTableWidgetItem("" if item.get("max_wear") is None else str(item.get("max_wear"))))
            self.item_table.setItem(row_index, 3, QTableWidgetItem("" if item.get("max_price") is None else str(item.get("max_price"))))
            self.item_table.setItem(row_index, 4, QTableWidgetItem(str(item.get("market_hash_name") or "")))
            self.item_table.setItem(row_index, 5, QTableWidgetItem(_format_detail_sync_time(item.get("last_detail_sync_at"))))
            item_cell = self.item_table.item(row_index, 0)
            if item_cell is not None:
                item_cell.setData(Qt.ItemDataRole.UserRole, dict(item))
        if items:
            self.item_table.selectRow(0)
        self.mode_table.setRowCount(len(mode_settings))
        for row_index, setting in enumerate(mode_settings):
            self.mode_table.setItem(row_index, 0, QTableWidgetItem(str(setting.get("mode_type") or "")))
            self.mode_table.setItem(row_index, 1, QTableWidgetItem("启用" if setting.get("enabled") else "关闭"))
            cooldown_text = f"{setting.get('base_cooldown_min', 0)} - {setting.get('base_cooldown_max', 0)}"
            self.mode_table.setItem(row_index, 2, QTableWidgetItem(cooldown_text))
            mode_item = self.mode_table.item(row_index, 0)
            if mode_item is not None:
                mode_item.setData(Qt.ItemDataRole.UserRole, dict(setting))
        if mode_settings:
            self.mode_table.selectRow(0)

    def selected_mode_setting(self) -> dict | None:
        indexes = self.mode_table.selectionModel().selectedRows()
        if not indexes:
            return None
        item = self.mode_table.item(indexes[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def selected_item(self) -> dict | None:
        indexes = self.item_table.selectionModel().selectedRows()
        if not indexes:
            return None
        item = self.item_table.item(indexes[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)
