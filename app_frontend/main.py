from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app_frontend.app.services.async_runner import QtAsyncRunner
from app_frontend.app.services.backend_client import BackendClient
from app_frontend.app.services.local_backend_server import LocalBackendServer
from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
from app_frontend.app.viewmodels.purchase_runtime_vm import PurchaseRuntimeViewModel
from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
from app_frontend.app.windows.account_center_window import AccountCenterWindow
from app_frontend.app.windows.purchase_runtime_window import PurchaseRuntimeWindow
from app_frontend.app.windows.query_system_window import QuerySystemWindow
from app_frontend.app.windows.workspace_window import WorkspaceWindow


def build_window(*, backend_client=None, task_runner=None) -> WorkspaceWindow:
    account_center_window = AccountCenterWindow(
        view_model=AccountCenterViewModel(),
        backend_client=backend_client,
        task_runner=task_runner,
    )
    query_system_window = QuerySystemWindow(
        view_model=QuerySystemViewModel(),
        backend_client=backend_client,
        task_runner=task_runner,
    )
    purchase_runtime_window = PurchaseRuntimeWindow(
        view_model=PurchaseRuntimeViewModel(),
        backend_client=backend_client,
        task_runner=task_runner,
    )
    window = WorkspaceWindow(
        account_center_window=account_center_window,
        query_system_window=query_system_window,
        purchase_runtime_window=purchase_runtime_window,
    )
    window.resize(1320, 780)
    return window


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    server = LocalBackendServer(db_path=Path("data/app.db"))
    server.start()

    backend_client = BackendClient(base_url=server.base_url)
    task_runner = QtAsyncRunner()
    window = build_window(backend_client=backend_client, task_runner=task_runner)
    window.account_center_window.load_accounts()
    window.show()
    app.aboutToQuit.connect(task_runner.shutdown)
    app.aboutToQuit.connect(server.stop)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
