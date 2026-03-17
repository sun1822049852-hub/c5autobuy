from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


_EMPTY_VALUE = -1.0


class QueryItemDialog(QDialog):
    def __init__(
        self,
        *,
        item: dict | None = None,
        backend_client=None,
        task_runner=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._item = dict(item) if item is not None else None
        self._backend_client = backend_client
        self._task_runner = task_runner
        self._fetched_detail: dict | None = None
        self.setWindowTitle("编辑商品" if item is not None else "新增商品")

        self.product_url_input = QLineEdit()
        self.fetch_detail_button = QPushButton("获取商品详情")
        self.item_name_input = self._build_readonly_input()
        self.market_hash_name_input = self._build_readonly_input()
        self.wear_range_input = self._build_readonly_input()
        self.last_market_price_input = self._build_readonly_input()
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
            self.fetch_detail_button.hide()
            self._load_detail_preview(
                {
                    "item_name": self._item.get("item_name"),
                    "market_hash_name": self._item.get("market_hash_name"),
                    "min_wear": self._item.get("min_wear"),
                    "detail_max_wear": self._item.get("detail_max_wear"),
                    "last_market_price": self._item.get("last_market_price"),
                    "product_url": self._item.get("product_url"),
                }
            )
        else:
            self.product_url_input.textChanged.connect(self._handle_product_url_changed)
            if self._backend_client is None or self._task_runner is None:
                self.fetch_detail_button.setEnabled(False)
            self.fetch_detail_button.clicked.connect(self._request_detail)

        form_layout = QFormLayout()
        url_row = QHBoxLayout()
        url_row.addWidget(self.product_url_input, 1)
        url_row.addWidget(self.fetch_detail_button)
        form_layout.addRow("商品 URL", url_row)
        form_layout.addRow("商品名称", self.item_name_input)
        form_layout.addRow("市场名称", self.market_hash_name_input)
        form_layout.addRow("完整磨损范围", self.wear_range_input)
        form_layout.addRow("市场价格", self.last_market_price_input)
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
        wear_error = self._validate_max_wear_against_detail(max_wear)
        if wear_error is not None:
            return wear_error

        max_price = self._spin_value_or_none(self.max_price_input)
        if max_price is not None and max_price <= 0.0:
            return "最高价格必须大于 0"

        if self._item is None and not self._has_fetched_detail():
            return "请先获取商品详情"

        return None

    def _request_detail(self) -> None:
        product_url = self.product_url_input.text().strip()
        if not product_url:
            self.error_label.setText("商品 URL 不能为空")
            return
        if self._backend_client is None or self._task_runner is None:
            self.error_label.setText("当前未连接后端，无法获取商品详情")
            return
        self.error_label.clear()
        self.fetch_detail_button.setEnabled(False)
        self._task_runner.submit(
            lambda: self._backend_client.parse_query_item_url({"product_url": product_url}),
            on_success=self._handle_url_parsed,
            on_error=self._handle_detail_error,
        )

    def _handle_url_parsed(self, parsed: dict) -> None:
        self._task_runner.submit(
            lambda: self._backend_client.fetch_query_item_detail(parsed),
            on_success=self._handle_detail_loaded,
            on_error=self._handle_detail_error,
        )

    def _handle_detail_loaded(self, detail: dict) -> None:
        self._fetched_detail = dict(detail)
        self.fetch_detail_button.setEnabled(True)
        self.error_label.clear()
        self._load_detail_preview(detail)

    def _handle_detail_error(self, message: str) -> None:
        self._fetched_detail = None
        self.fetch_detail_button.setEnabled(True)
        self._load_detail_preview(None)
        self.error_label.setText(message)

    def _handle_product_url_changed(self, text: str) -> None:
        current_url = text.strip()
        if self._fetched_detail is None:
            return
        if current_url == str(self._fetched_detail.get("product_url") or ""):
            return
        self._fetched_detail = None
        self._load_detail_preview(None)

    def _has_fetched_detail(self) -> bool:
        if self._fetched_detail is None:
            return False
        return self.product_url_input.text().strip() == str(self._fetched_detail.get("product_url") or "")

    def _load_detail_preview(self, detail: dict | None) -> None:
        if detail is None:
            self.item_name_input.clear()
            self.market_hash_name_input.clear()
            self.wear_range_input.clear()
            self.last_market_price_input.clear()
            return
        self.item_name_input.setText(str(detail.get("item_name") or ""))
        self.market_hash_name_input.setText(str(detail.get("market_hash_name") or ""))
        self.wear_range_input.setText(self._format_wear_range(detail.get("min_wear"), detail.get("detail_max_wear")))
        price = detail.get("last_market_price")
        self.last_market_price_input.setText("" if price is None else str(price))

    def _validate_max_wear_against_detail(self, max_wear: float | None) -> str | None:
        if max_wear is None:
            return None
        min_wear, detail_max_wear = self._current_wear_bounds()
        if min_wear is None or detail_max_wear is None:
            return None
        if min_wear < max_wear <= detail_max_wear:
            return None
        return f"最大磨损值必须在范围 ({self._format_wear_number(min_wear)}, {self._format_wear_number(detail_max_wear)}] 内"

    def _current_wear_bounds(self) -> tuple[float | None, float | None]:
        detail = self._item
        if self._item is None:
            detail = self._fetched_detail if self._has_fetched_detail() else None
        if detail is None:
            return None, None
        return detail.get("min_wear"), detail.get("detail_max_wear")

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

    @staticmethod
    def _build_readonly_input() -> QLineEdit:
        field = QLineEdit()
        field.setReadOnly(True)
        return field

    @staticmethod
    def _format_wear_range(min_wear: object, detail_max_wear: object) -> str:
        if min_wear is None or detail_max_wear is None:
            return ""
        return f"{min_wear} ~ {detail_max_wear}"

    @staticmethod
    def _format_wear_number(value: float) -> str:
        return f"{value:g}"
