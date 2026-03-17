from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QPlainTextEdit, QVBoxLayout


class QueryConfigDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建查询配置")

        self.name_input = QLineEdit()
        self.description_input = QPlainTextEdit()
        self.description_input.setFixedHeight(100)

        form_layout = QFormLayout()
        form_layout.addRow("配置名", self.name_input)
        form_layout.addRow("描述", self.description_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

    def build_payload(self) -> dict[str, str]:
        return {
            "name": self.name_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
        }
