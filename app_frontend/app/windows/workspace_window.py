from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget


class WorkspaceWindow(QWidget):
    def __init__(
        self,
        *,
        account_center_window: QWidget,
        query_system_window: QWidget,
        purchase_runtime_window: QWidget,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.account_center_window = account_center_window
        self.query_system_window = query_system_window
        self.purchase_runtime_window = purchase_runtime_window

        self.setWindowTitle("C5 工作台")
        self.account_center_button = QPushButton("账号中心")
        self.query_system_button = QPushButton("查询系统")
        self.purchase_runtime_button = QPushButton("购买运行")
        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self.account_center_window)
        self.page_stack.addWidget(self.query_system_window)
        self.page_stack.addWidget(self.purchase_runtime_window)

        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.account_center_button)
        nav_layout.addWidget(self.query_system_button)
        nav_layout.addWidget(self.purchase_runtime_button)
        nav_layout.addStretch(1)

        root_layout = QVBoxLayout(self)
        root_layout.addLayout(nav_layout)
        root_layout.addWidget(self.page_stack, 1)

        self.account_center_button.clicked.connect(self.show_account_center)
        self.query_system_button.clicked.connect(self.show_query_system)
        self.purchase_runtime_button.clicked.connect(self.show_purchase_runtime)

        self.setStyleSheet(
            """
            QWidget {
                background: #efe8db;
                color: #1f1b16;
                font-family: "Microsoft YaHei UI";
                font-size: 13px;
            }
            QPushButton {
                background: #c85c36;
                color: #fffdf8;
                border: none;
                border-radius: 10px;
                padding: 10px 18px;
                font-weight: 700;
                min-width: 112px;
            }
            QPushButton:hover {
                background: #a84c2c;
            }
            QPushButton[active="true"] {
                background: #1f5f4a;
            }
            """
        )

        self.show_account_center()

    def show_account_center(self) -> None:
        self.page_stack.setCurrentWidget(self.account_center_window)
        self._sync_nav_state()

    def show_query_system(self) -> None:
        self.page_stack.setCurrentWidget(self.query_system_window)
        self._sync_nav_state()

    def current_page_name(self) -> str:
        if self.page_stack.currentWidget() is self.purchase_runtime_window:
            return "purchase"
        if self.page_stack.currentWidget() is self.query_system_window:
            return "query"
        return "account"

    def _sync_nav_state(self) -> None:
        current_page = self.current_page_name()
        self.account_center_button.setProperty("active", current_page == "account")
        self.query_system_button.setProperty("active", current_page == "query")
        self.purchase_runtime_button.setProperty("active", current_page == "purchase")
        for button in (self.account_center_button, self.query_system_button, self.purchase_runtime_button):
            self.style().unpolish(button)
            self.style().polish(button)
            button.update()

    def show_purchase_runtime(self) -> None:
        self.page_stack.setCurrentWidget(self.purchase_runtime_window)
        self._sync_nav_state()
