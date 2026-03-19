from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout


class RemarkEditDialog(QDialog):
    def __init__(self, *, account: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑备注")
        self.remark_name_input = QLineEdit()
        self.remark_name_input.setText(account.get("remark_name") or account.get("display_name") or "")

        form = QFormLayout()
        form.addRow("备注", self.remark_name_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def build_payload(self) -> dict[str, str | None]:
        return {"remark_name": self.remark_name_input.text().strip() or None}
