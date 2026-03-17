from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
)


class _AccountDialogBase(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.remark_name_input = QLineEdit()
        self.proxy_mode_combo = QComboBox()
        self.proxy_mode_combo.addItems(["direct", "custom"])
        self.proxy_url_input = QLineEdit()
        self.proxy_url_input.setPlaceholderText("http://user:pass@host:port")
        self.api_key_input = QLineEdit()

        self.proxy_scheme_combo = QComboBox()
        self.proxy_scheme_combo.addItems(["http", "https"])
        self.proxy_host_input = QLineEdit()
        self.proxy_port_input = QLineEdit()
        self.proxy_username_input = QLineEdit()
        self.proxy_password_input = QLineEdit()
        self.proxy_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_api_enabled_checkbox = QCheckBox("new_api")
        self.fast_api_enabled_checkbox = QCheckBox("fast_api")
        self.token_enabled_checkbox = QCheckBox("token")
        self._token_available = False
        self._desired_new_api_enabled = False
        self._desired_fast_api_enabled = False
        self._desired_token_enabled = False
        self._syncing_query_mode_ui = False

        basic_group = QGroupBox("基础配置")
        basic_form = QFormLayout(basic_group)
        basic_form.addRow("备注名", self.remark_name_input)
        basic_form.addRow("代理模式", self.proxy_mode_combo)
        basic_form.addRow("完整代理", self.proxy_url_input)
        basic_form.addRow("API Key", self.api_key_input)

        query_mode_group = QGroupBox("查询开关")
        query_mode_layout = QVBoxLayout(query_mode_group)
        query_mode_layout.addWidget(self.new_api_enabled_checkbox)
        query_mode_layout.addWidget(self.fast_api_enabled_checkbox)
        query_mode_layout.addWidget(self.token_enabled_checkbox)
        self.query_mode_group = query_mode_group

        split_group = QGroupBox("拆分代理")
        split_layout = QFormLayout(split_group)
        split_layout.addRow("协议", self.proxy_scheme_combo)
        split_layout.addRow("主机", self.proxy_host_input)
        split_layout.addRow("端口", self.proxy_port_input)
        split_layout.addRow("用户名", self.proxy_username_input)
        split_layout.addRow("密码", self.proxy_password_input)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(basic_group)
        root_layout.addWidget(query_mode_group)
        root_layout.addWidget(split_group)

        self.proxy_mode_combo.currentTextChanged.connect(self._sync_proxy_mode_ui)
        self.api_key_input.textChanged.connect(lambda _text: self._sync_query_mode_ui())
        self.new_api_enabled_checkbox.stateChanged.connect(lambda _state: self._remember_query_mode_preferences())
        self.fast_api_enabled_checkbox.stateChanged.connect(lambda _state: self._remember_query_mode_preferences())
        self.token_enabled_checkbox.stateChanged.connect(lambda _state: self._remember_query_mode_preferences())
        self._sync_proxy_mode_ui(self.proxy_mode_combo.currentText())
        self._sync_query_mode_ui()

    def build_payload(self) -> dict:
        proxy_mode, proxy_url = self._build_proxy_payload()
        return {
            "remark_name": self.remark_name_input.text().strip() or None,
            "proxy_mode": proxy_mode,
            "proxy_url": proxy_url,
            "api_key": self.api_key_input.text().strip() or None,
        }

    def build_query_mode_payload(self) -> dict[str, bool]:
        api_key_available = self._has_api_key()
        token_available = self._has_token()
        return {
            "new_api_enabled": api_key_available and self.new_api_enabled_checkbox.isChecked(),
            "fast_api_enabled": api_key_available and self.fast_api_enabled_checkbox.isChecked(),
            "token_enabled": token_available and self.token_enabled_checkbox.isChecked(),
        }

    def _build_proxy_payload(self) -> tuple[str, str | None]:
        if self.proxy_mode_combo.currentText() == "direct":
            return "direct", None

        full_proxy = self.proxy_url_input.text().strip()
        if full_proxy:
            return "custom", full_proxy

        host = self.proxy_host_input.text().strip()
        if not host:
            return "direct", None

        scheme = self.proxy_scheme_combo.currentText()
        port = self.proxy_port_input.text().strip()
        username = self.proxy_username_input.text().strip()
        password = self.proxy_password_input.text().strip()

        auth = ""
        if username and password:
            auth = f"{username}:{password}@"

        host_and_port = host
        if port:
            host_and_port = f"{host}:{port}"

        return "custom", f"{scheme}://{auth}{host_and_port}"

    def _sync_proxy_mode_ui(self, proxy_mode: str) -> None:
        enabled = proxy_mode == "custom"
        for widget in (
            self.proxy_url_input,
            self.proxy_scheme_combo,
            self.proxy_host_input,
            self.proxy_port_input,
            self.proxy_username_input,
            self.proxy_password_input,
        ):
            widget.setEnabled(enabled)

    def _sync_query_mode_ui(self) -> None:
        api_key_available = self._has_api_key()
        token_available = self._has_token()
        self._syncing_query_mode_ui = True
        self.new_api_enabled_checkbox.setEnabled(api_key_available)
        self.fast_api_enabled_checkbox.setEnabled(api_key_available)
        self.token_enabled_checkbox.setEnabled(token_available)

        self.new_api_enabled_checkbox.setChecked(self._desired_new_api_enabled if api_key_available else False)
        self.fast_api_enabled_checkbox.setChecked(self._desired_fast_api_enabled if api_key_available else False)
        self.token_enabled_checkbox.setChecked(self._desired_token_enabled if token_available else False)
        self._syncing_query_mode_ui = False

    def _has_api_key(self) -> bool:
        return bool(self.api_key_input.text().strip())

    def _has_token(self) -> bool:
        return self._token_available

    def _set_query_mode_state(
        self,
        *,
        new_api_enabled: bool,
        fast_api_enabled: bool,
        token_enabled: bool,
        token_available: bool,
    ) -> None:
        self._token_available = bool(token_available)
        self._desired_new_api_enabled = bool(new_api_enabled)
        self._desired_fast_api_enabled = bool(fast_api_enabled)
        self._desired_token_enabled = bool(token_enabled)
        self._sync_query_mode_ui()

    def _remember_query_mode_preferences(self) -> None:
        if self._syncing_query_mode_ui:
            return
        self._desired_new_api_enabled = self.new_api_enabled_checkbox.isChecked()
        self._desired_fast_api_enabled = self.fast_api_enabled_checkbox.isChecked()
        self._desired_token_enabled = self.token_enabled_checkbox.isChecked()


class CreateAccountDialog(_AccountDialogBase):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建账号")
        self._set_query_mode_state(
            new_api_enabled=False,
            fast_api_enabled=False,
            token_enabled=False,
            token_available=False,
        )
        self.query_mode_group.hide()

