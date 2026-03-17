from __future__ import annotations

from app_frontend.app.formatters.account_display import (
    format_last_login,
    purchase_capability_label,
    purchase_pool_label,
)
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _readonly_line_edit() -> QLineEdit:
    field = QLineEdit()
    field.setReadOnly(True)
    return field


def _set_tone(field: QLineEdit, tone: str, *, tooltip: str = "") -> None:
    field.setProperty("tone", tone)
    field.setToolTip(tooltip)
    field.style().unpolish(field)
    field.style().polish(field)
    field.update()


def _api_key_tone(api_key: str | None) -> str:
    return "ok" if api_key else "muted"


def _purchase_capability_tone(state: str | None) -> str:
    mapping = {
        "bound": "ok",
        "expired": "error",
        "unbound": "muted",
    }
    return mapping.get(state or "", "neutral")


def _purchase_pool_tone(state: str | None) -> str:
    mapping = {
        "active": "ok",
        "available": "ok",
        "paused_no_inventory": "warn",
        "paused_not_login": "error",
        "paused_auth_invalid": "error",
        "not_connected": "muted",
    }
    return mapping.get(state or "", "neutral")


def _query_mode_status(*, enabled: bool, available: bool, unavailable_reason: str) -> tuple[str, str]:
    if not available:
        return unavailable_reason, "warn"
    if enabled:
        return "已启用", "ok"
    return "已关闭", "muted"


class AccountDetailPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.account_id_input = _readonly_line_edit()
        self.display_name_input = _readonly_line_edit()
        self.default_name_input = _readonly_line_edit()
        self.remark_name_input = _readonly_line_edit()
        self.c5_nick_name_input = _readonly_line_edit()
        self.c5_user_id_input = _readonly_line_edit()
        self.last_login_input = _readonly_line_edit()
        self.last_error_input = _readonly_line_edit()
        self.proxy_input = _readonly_line_edit()
        self.api_key_status_input = _readonly_line_edit()
        self.new_api_mode_input = _readonly_line_edit()
        self.fast_api_mode_input = _readonly_line_edit()
        self.token_mode_input = _readonly_line_edit()
        self.purchase_capability_input = _readonly_line_edit()
        self.purchase_pool_input = _readonly_line_edit()

        base_group = QGroupBox("基础信息")
        base_form = QFormLayout(base_group)
        base_form.addRow("账号ID", self.account_id_input)
        base_form.addRow("显示名", self.display_name_input)
        base_form.addRow("默认名", self.default_name_input)
        base_form.addRow("备注名", self.remark_name_input)
        base_form.addRow("C5昵称", self.c5_nick_name_input)
        base_form.addRow("C5用户ID", self.c5_user_id_input)
        base_form.addRow("最近登录", self.last_login_input)
        base_form.addRow("最近错误", self.last_error_input)
        base_form.addRow("代理", self.proxy_input)

        query_group = QGroupBox("查询能力")
        query_form = QFormLayout(query_group)
        self.edit_query_button = QPushButton("编辑账号")
        query_form.addRow("API Key", self.api_key_status_input)
        query_form.addRow("new_api", self.new_api_mode_input)
        query_form.addRow("fast_api", self.fast_api_mode_input)
        query_form.addRow("token", self.token_mode_input)
        query_form.addRow("", self.edit_query_button)

        capability_group = QGroupBox("购买能力")
        capability_form = QFormLayout(capability_group)
        self.start_login_button = QPushButton("发起登录")
        capability_form.addRow("购买能力", self.purchase_capability_input)
        capability_form.addRow("购买池", self.purchase_pool_input)
        capability_form.addRow("", self.start_login_button)

        risk_group = QGroupBox("风险操作")
        risk_layout = QHBoxLayout(risk_group)
        self.clear_purchase_button = QPushButton("清除购买能力")
        self.delete_account_button = QPushButton("删除账号")
        risk_layout.addWidget(self.clear_purchase_button)
        risk_layout.addWidget(self.delete_account_button)

        layout = QVBoxLayout(self)
        layout.addWidget(base_group)
        layout.addWidget(query_group)
        layout.addWidget(capability_group)
        layout.addWidget(risk_group)
        layout.addStretch(1)

        self.setStyleSheet(
            """
            QLineEdit[tone="ok"] {
                background: #e7f6ee;
                border: 1px solid #7dbb91;
                color: #174a2f;
            }
            QLineEdit[tone="warn"] {
                background: #fff1db;
                border: 1px solid #d9a14a;
                color: #8a4b10;
            }
            QLineEdit[tone="error"] {
                background: #fde8e4;
                border: 1px solid #cf6f5b;
                color: #8f2416;
            }
            QLineEdit[tone="muted"] {
                background: #f2eee8;
                border: 1px solid #cbbfaa;
                color: #706458;
            }
            QLineEdit[tone="neutral"] {
                background: #fffdf8;
                border: 1px solid #d8ccb9;
                color: #1f1b16;
            }
            """
        )

        self.clear_account()

    def clear_account(self) -> None:
        for field in (
            self.account_id_input,
            self.display_name_input,
            self.default_name_input,
            self.remark_name_input,
            self.c5_nick_name_input,
            self.c5_user_id_input,
            self.last_login_input,
            self.last_error_input,
            self.proxy_input,
            self.api_key_status_input,
            self.new_api_mode_input,
            self.fast_api_mode_input,
            self.token_mode_input,
            self.purchase_capability_input,
            self.purchase_pool_input,
        ):
            field.clear()
            _set_tone(field, "neutral")

        for button in (
            self.edit_query_button,
            self.start_login_button,
            self.clear_purchase_button,
            self.delete_account_button,
        ):
            button.setEnabled(False)

    def load_account(self, account: dict) -> None:
        self.account_id_input.setText(account.get("account_id", ""))
        self.display_name_input.setText(account.get("display_name", ""))
        self.default_name_input.setText(account.get("default_name") or "")
        self.remark_name_input.setText(account.get("remark_name") or "")
        self.c5_nick_name_input.setText(account.get("c5_nick_name") or "")
        self.c5_user_id_input.setText(account.get("c5_user_id") or "")
        self.last_login_input.setText(format_last_login(account.get("last_login_at")))
        last_error = account.get("last_error") or ""
        self.last_error_input.setText(last_error)
        self.proxy_input.setText(account.get("proxy_url") or "直连")
        api_key = account.get("api_key")
        purchase_capability_state = account.get("purchase_capability_state")
        purchase_pool_state = account.get("purchase_pool_state")
        has_token = "NC5_accessToken=" in str(account.get("cookie_raw") or "")
        new_api_text, new_api_tone = _query_mode_status(
            enabled=bool(account.get("new_api_enabled", False)),
            available=bool(api_key),
            unavailable_reason="缺少 API Key",
        )
        fast_api_text, fast_api_tone = _query_mode_status(
            enabled=bool(account.get("fast_api_enabled", False)),
            available=bool(api_key),
            unavailable_reason="缺少 API Key",
        )
        token_text, token_tone = _query_mode_status(
            enabled=bool(account.get("token_enabled", False)),
            available=has_token,
            unavailable_reason="缺少 Token",
        )
        self.api_key_status_input.setText("已配置" if api_key else "未配置")
        self.new_api_mode_input.setText(new_api_text)
        self.fast_api_mode_input.setText(fast_api_text)
        self.token_mode_input.setText(token_text)
        self.purchase_capability_input.setText(purchase_capability_label(purchase_capability_state))
        self.purchase_pool_input.setText(purchase_pool_label(purchase_pool_state))
        _set_tone(self.api_key_status_input, _api_key_tone(api_key))
        _set_tone(self.new_api_mode_input, new_api_tone)
        _set_tone(self.fast_api_mode_input, fast_api_tone)
        _set_tone(self.token_mode_input, token_tone)
        _set_tone(self.purchase_capability_input, _purchase_capability_tone(purchase_capability_state))
        _set_tone(self.purchase_pool_input, _purchase_pool_tone(purchase_pool_state))
        _set_tone(self.last_error_input, "error" if last_error else "neutral", tooltip=last_error)

        for button in (
            self.edit_query_button,
            self.start_login_button,
            self.clear_purchase_button,
            self.delete_account_button,
        ):
            button.setEnabled(True)
