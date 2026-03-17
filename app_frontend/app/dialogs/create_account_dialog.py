from __future__ import annotations

from PySide6.QtWidgets import (
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

        basic_group = QGroupBox("基础配置")
        basic_form = QFormLayout(basic_group)
        basic_form.addRow("备注名", self.remark_name_input)
        basic_form.addRow("代理模式", self.proxy_mode_combo)
        basic_form.addRow("完整代理", self.proxy_url_input)
        basic_form.addRow("API Key", self.api_key_input)

        split_group = QGroupBox("拆分代理")
        split_layout = QFormLayout(split_group)
        split_layout.addRow("协议", self.proxy_scheme_combo)
        split_layout.addRow("主机", self.proxy_host_input)
        split_layout.addRow("端口", self.proxy_port_input)
        split_layout.addRow("用户名", self.proxy_username_input)
        split_layout.addRow("密码", self.proxy_password_input)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(basic_group)
        root_layout.addWidget(split_group)

        self.proxy_mode_combo.currentTextChanged.connect(self._sync_proxy_mode_ui)
        self._sync_proxy_mode_ui(self.proxy_mode_combo.currentText())

    def build_payload(self) -> dict:
        proxy_mode, proxy_url = self._build_proxy_payload()
        return {
            "remark_name": self.remark_name_input.text().strip() or None,
            "proxy_mode": proxy_mode,
            "proxy_url": proxy_url,
            "api_key": self.api_key_input.text().strip() or None,
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


class CreateAccountDialog(_AccountDialogBase):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建账号")

