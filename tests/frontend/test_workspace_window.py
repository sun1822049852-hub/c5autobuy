from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


def test_workspace_window_switches_between_account_and_query_pages(qtbot):
    from app_frontend.app.windows.workspace_window import WorkspaceWindow

    account_page = QWidget()
    query_page = QWidget()
    purchase_page = QWidget()
    window = WorkspaceWindow(
        account_center_window=account_page,
        query_system_window=query_page,
        purchase_runtime_window=purchase_page,
    )
    qtbot.addWidget(window)

    assert window.current_page_name() == "account"

    qtbot.mouseClick(window.query_system_button, Qt.LeftButton)
    assert window.current_page_name() == "query"

    qtbot.mouseClick(window.purchase_runtime_button, Qt.LeftButton)
    assert window.current_page_name() == "purchase"

    qtbot.mouseClick(window.account_center_button, Qt.LeftButton)
    assert window.current_page_name() == "account"


def test_frontend_build_window_returns_workspace_shell(qtbot):
    import app_frontend.main as frontend_main
    from app_frontend.app.windows.workspace_window import WorkspaceWindow

    window = frontend_main.build_window()
    qtbot.addWidget(window)

    assert isinstance(window, WorkspaceWindow)
    assert window.current_page_name() == "account"
    assert window.purchase_runtime_button.text() == "购买运行"
