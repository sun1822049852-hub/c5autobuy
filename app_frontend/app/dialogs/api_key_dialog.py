from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout


class ApiKeyDialog(QDialog):
    def __init__(self, *, account: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑 API Key")
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(account.get("api_key") or "")

        form = QFormLayout()
        form.addRow("API Key", self.api_key_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def build_payload(self) -> dict[str, str | None]:
        return {"api_key": self.api_key_input.text().strip() or None}
