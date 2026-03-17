from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout


_EMPTY_VALUE = -1.0


class QueryItemDialog(QDialog):
    def __init__(self, *, item: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self._item = dict(item) if item is not None else None
        self.setWindowTitle("编辑商品" if item is not None else "新增商品")

        self.product_url_input = QLineEdit()
        self.max_wear_input = self._build_spin()
        self.max_price_input = self._build_spin()
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #8f2416;")

        if self._item is not None:
            self.product_url_input.setText(str(self._item.get("product_url") or ""))
            self.product_url_input.setReadOnly(True)
            if self._item.get("max_wear") is not None:
                self.max_wear_input.setValue(float(self._item["max_wear"]))
            if self._item.get("max_price") is not None:
                self.max_price_input.setValue(float(self._item["max_price"]))

        form_layout = QFormLayout()
        form_layout.addRow("商品 URL", self.product_url_input)
        form_layout.addRow("最大磨损", self.max_wear_input)
        form_layout.addRow("最高价格", self.max_price_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def accept(self) -> None:
        error_message = self._validate()
        self.error_label.setText(error_message or "")
        if error_message:
            return
        super().accept()

    def build_payload(self) -> dict[str, float | str | None]:
        payload: dict[str, float | str | None] = {
            "max_wear": self._spin_value_or_none(self.max_wear_input),
            "max_price": self._spin_value_or_none(self.max_price_input),
        }
        if self._item is None:
            payload["product_url"] = self.product_url_input.text().strip()
        return payload

    def _validate(self) -> str | None:
        if self._item is None and not self.product_url_input.text().strip():
            return "商品 URL 不能为空"

        max_wear = self._spin_value_or_none(self.max_wear_input)
        if max_wear is not None and not 0.0 <= max_wear <= 1.0:
            return "最大磨损必须在 0 到 1 之间"

        max_price = self._spin_value_or_none(self.max_price_input)
        if max_price is not None and max_price <= 0.0:
            return "最高价格必须大于 0"

        return None

    @staticmethod
    def _spin_value_or_none(field: QDoubleSpinBox) -> float | None:
        value = field.value()
        if abs(value - field.minimum()) < 1e-9:
            return None
        return value

    @staticmethod
    def _build_spin() -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setDecimals(4)
        field.setRange(_EMPTY_VALUE, 9999999.0)
        field.setSingleStep(0.1)
        field.setValue(_EMPTY_VALUE)
        field.setSpecialValueText("未设置")
        return field
