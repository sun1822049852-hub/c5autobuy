from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout


class QueryConfigDialog(QDialog):
    def __init__(self, *, config: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self._config = dict(config) if config is not None else None
        self.setWindowTitle("编辑查询配置" if self._config is not None else "新建查询配置")

        self.name_input = QLineEdit()
        self.description_input = QPlainTextEdit()
        self.description_input.setFixedHeight(100)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #8f2416;")
        self.error_label.setWordWrap(True)

        if self._config is not None:
            self.name_input.setText(str(self._config.get("name") or ""))
            self.description_input.setPlainText(str(self._config.get("description") or ""))

        form_layout = QFormLayout()
        form_layout.addRow("配置名", self.name_input)
        form_layout.addRow("描述", self.description_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def accept(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            self.error_label.setText("配置名不能为空")
            return
        self.error_label.clear()
        super().accept()

    def build_payload(self) -> dict[str, str]:
        return {
            "name": self.name_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
        }
