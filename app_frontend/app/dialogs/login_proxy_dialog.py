from __future__ import annotations

from PySide6.QtWidgets import QDialogButtonBox

from app_frontend.app.dialogs.create_account_dialog import _AccountDialogBase


class LoginProxyDialog(_AccountDialogBase):
    def __init__(self, *, account: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录代理设置")
        self.set_basic_row_visible(self.remark_name_input, False)
        self.set_basic_row_visible(self.api_key_input, False)
        self.query_mode_group.hide()
        self.set_proxy_inputs(
            proxy_mode=account.get("proxy_mode") or "direct",
            proxy_url=account.get("proxy_url"),
        )

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.root_layout.addWidget(button_box)
