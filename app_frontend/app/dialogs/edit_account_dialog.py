from __future__ import annotations

from app_frontend.app.dialogs.create_account_dialog import _AccountDialogBase


class EditAccountDialog(_AccountDialogBase):
    def __init__(self, *, account: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑账号")
        self.remark_name_input.setText(account.get("remark_name") or "")
        self.api_key_input.setText(account.get("api_key") or "")
        proxy_url = account.get("proxy_url") or ""
        proxy_mode = account.get("proxy_mode") or "direct"
        self.proxy_mode_combo.setCurrentText(proxy_mode)
        self.proxy_url_input.setText(proxy_url)
