from __future__ import annotations

from PySide6.QtWidgets import QDialog


def test_window_status_label_applies_semantic_tones(qtbot, monkeypatch):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    warning_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app_frontend.app.windows.account_center_window.QMessageBox.warning",
        lambda _parent, title, message: warning_calls.append((title, message)),
    )

    window = AccountCenterWindow(view_model=AccountCenterViewModel())
    qtbot.addWidget(window)

    assert window.status_label.property("tone") == "neutral"

    window._publish_status("已加载 1 个账号")
    assert window.status_label.text() == "已加载 1 个账号"
    assert window.status_label.property("tone") == "ok"

    window._publish_status("登录任务状态: 检测到账号冲突")
    assert window.status_label.property("tone") == "warn"

    window._publish_status("冲突处理完成: 登录完成")
    assert window.status_label.property("tone") == "ok"

    window._publish_status("已取消删除账号")
    assert window.status_label.property("tone") == "warn"

    window._handle_error("代理连接失败")
    assert window.status_label.text() == "操作失败: 代理连接失败"
    assert window.status_label.property("tone") == "error"
    assert warning_calls == [("操作失败", "代理连接失败")]


def test_window_start_login_submits_proxy_payload_after_dialog_accepts(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    submitted_payloads: list[dict] = []

    class FakeLoginProxyDialog:
        def exec(self) -> int:
            return int(QDialog.DialogCode.Accepted)

        def build_proxy_payload(self) -> dict:
            return {"proxy_mode": "custom", "proxy_url": "http://127.0.0.1:9600"}

    class SpyController:
        def submit_login_proxy_for_detail(self, payload):
            submitted_payloads.append(payload)

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                "account_id": "a-1",
                "default_name": "默认名",
                "remark_name": "备注名",
                "display_name": "备注名",
                "proxy_mode": "direct",
                "proxy_url": None,
                "api_key": None,
                "c5_user_id": None,
                "c5_nick_name": None,
                "cookie_raw": None,
                "purchase_capability_state": "unbound",
                "purchase_pool_state": "not_connected",
                "last_login_at": None,
                "last_error": None,
                "created_at": "2026-03-16T12:00:00",
                "updated_at": "2026-03-16T12:00:00",
                "disabled": False,
                "new_api_enabled": False,
                "fast_api_enabled": False,
                "token_enabled": False,
            }
        ]
    )
    vm.select_account("a-1")
    vm.open_selected_account_detail()
    window = AccountCenterWindow(
        view_model=vm,
        backend_client=object(),
        login_proxy_dialog_factory=lambda account, parent=None: FakeLoginProxyDialog(),
    )
    qtbot.addWidget(window)
    window.controller = SpyController()

    window._start_login()

    assert submitted_payloads == [{"proxy_mode": "custom", "proxy_url": "http://127.0.0.1:9600"}]


def test_window_start_login_does_not_submit_when_dialog_is_cancelled(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    submitted_payloads: list[dict] = []

    class FakeLoginProxyDialog:
        def exec(self) -> int:
            return int(QDialog.DialogCode.Rejected)

        def build_proxy_payload(self) -> dict:
            raise AssertionError("cancelled dialog should not build payload")

    class SpyController:
        def submit_login_proxy_for_detail(self, payload):
            submitted_payloads.append(payload)

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                "account_id": "a-1",
                "default_name": "默认名",
                "remark_name": "备注名",
                "display_name": "备注名",
                "proxy_mode": "direct",
                "proxy_url": None,
                "api_key": None,
                "c5_user_id": None,
                "c5_nick_name": None,
                "cookie_raw": None,
                "purchase_capability_state": "unbound",
                "purchase_pool_state": "not_connected",
                "last_login_at": None,
                "last_error": None,
                "created_at": "2026-03-16T12:00:00",
                "updated_at": "2026-03-16T12:00:00",
                "disabled": False,
                "new_api_enabled": False,
                "fast_api_enabled": False,
                "token_enabled": False,
            }
        ]
    )
    vm.select_account("a-1")
    vm.open_selected_account_detail()
    window = AccountCenterWindow(
        view_model=vm,
        backend_client=object(),
        login_proxy_dialog_factory=lambda account, parent=None: FakeLoginProxyDialog(),
    )
    qtbot.addWidget(window)
    window.controller = SpyController()

    window._start_login()

    assert submitted_payloads == []


def test_window_start_login_uses_top_level_workspace_as_dialog_parent(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.viewmodels.purchase_runtime_vm import PurchaseRuntimeViewModel
    from app_frontend.app.viewmodels.query_system_vm import QuerySystemViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow
    from app_frontend.app.windows.purchase_runtime_window import PurchaseRuntimeWindow
    from app_frontend.app.windows.query_system_window import QuerySystemWindow
    from app_frontend.app.windows.workspace_window import WorkspaceWindow

    captured_parents = []

    class FakeLoginProxyDialog:
        def exec(self) -> int:
            return int(QDialog.DialogCode.Rejected)

    def dialog_factory(account, parent=None):
        captured_parents.append(parent)
        return FakeLoginProxyDialog()

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                "account_id": "a-1",
                "default_name": "默认名",
                "remark_name": "备注名",
                "display_name": "备注名",
                "proxy_mode": "direct",
                "proxy_url": None,
                "api_key": None,
                "c5_user_id": None,
                "c5_nick_name": None,
                "cookie_raw": None,
                "purchase_capability_state": "unbound",
                "purchase_pool_state": "not_connected",
                "last_login_at": None,
                "last_error": None,
                "created_at": "2026-03-16T12:00:00",
                "updated_at": "2026-03-16T12:00:00",
                "disabled": False,
                "new_api_enabled": False,
                "fast_api_enabled": False,
                "token_enabled": False,
            }
        ]
    )
    vm.select_account("a-1")
    vm.open_selected_account_detail()
    account_window = AccountCenterWindow(
        view_model=vm,
        backend_client=object(),
        login_proxy_dialog_factory=dialog_factory,
    )
    workspace = WorkspaceWindow(
        account_center_window=account_window,
        query_system_window=QuerySystemWindow(view_model=QuerySystemViewModel()),
        purchase_runtime_window=PurchaseRuntimeWindow(view_model=PurchaseRuntimeViewModel()),
    )
    qtbot.addWidget(workspace)

    account_window._start_login()

    assert captured_parents == [workspace]


def test_window_account_table_uses_new_main_list_columns(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    window = AccountCenterWindow(view_model=AccountCenterViewModel())
    qtbot.addWidget(window)

    headers = [window.account_table.horizontalHeaderItem(index).text() for index in range(window.account_table.columnCount())]

    assert headers == ["C5昵称", "API Key", "购买状态", "代理"]


def test_window_uses_add_account_button_label(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    window = AccountCenterWindow(view_model=AccountCenterViewModel())
    qtbot.addWidget(window)

    assert window.create_account_button.text() == "添加账号"


def test_window_clicking_c5_nickname_opens_remark_editor(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    submitted_payloads: list[tuple[str, dict]] = []

    class FakeRemarkDialog:
        def exec(self) -> int:
            return int(QDialog.DialogCode.Accepted)

        def build_payload(self) -> dict:
            return {"remark_name": "新备注"}

    class SpyController:
        def edit_account_remark(self, account_id: str, payload: dict) -> None:
            submitted_payloads.append((account_id, payload))

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                "account_id": "a-1",
                "display_name": "旧备注",
                "remark_name": "旧备注",
                "c5_nick_name": "平台昵称",
                "default_name": "默认名",
                "api_key_present": True,
                "api_key": "api-key",
                "proxy_mode": "direct",
                "proxy_url": None,
                "proxy_display": "直连",
                "purchase_capability_state": "bound",
                "purchase_pool_state": "not_connected",
                "disabled": False,
                "selected_steam_id": "steam-1",
                "selected_warehouse_text": "steam-1",
                "purchase_status_code": "selected_warehouse",
                "purchase_status_text": "steam-1",
            }
        ]
    )
    window = AccountCenterWindow(
        view_model=vm,
        backend_client=object(),
        remark_dialog_factory=lambda account, parent=None: FakeRemarkDialog(),
    )
    qtbot.addWidget(window)
    window.controller = SpyController()

    window.account_table.cellClicked.emit(0, 0)

    assert submitted_payloads == [("a-1", {"remark_name": "新备注"})]


def test_window_clicking_api_key_opens_editor(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    submitted_payloads: list[tuple[str, dict]] = []

    class FakeApiKeyDialog:
        def exec(self) -> int:
            return int(QDialog.DialogCode.Accepted)

        def build_payload(self) -> dict:
            return {"api_key": "api-new"}

    class SpyController:
        def edit_account_api_key(self, account_id: str, payload: dict) -> None:
            submitted_payloads.append((account_id, payload))

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                "account_id": "a-1",
                "display_name": "旧备注",
                "remark_name": "旧备注",
                "c5_nick_name": "平台昵称",
                "default_name": "默认名",
                "api_key_present": True,
                "api_key": "api-key",
                "proxy_mode": "direct",
                "proxy_url": None,
                "proxy_display": "直连",
                "purchase_capability_state": "bound",
                "purchase_pool_state": "not_connected",
                "disabled": False,
                "selected_steam_id": "steam-1",
                "selected_warehouse_text": "steam-1",
                "purchase_status_code": "selected_warehouse",
                "purchase_status_text": "steam-1",
            }
        ]
    )
    window = AccountCenterWindow(
        view_model=vm,
        backend_client=object(),
        api_key_dialog_factory=lambda account, parent=None: FakeApiKeyDialog(),
    )
    qtbot.addWidget(window)
    window.controller = SpyController()

    window.account_table.cellClicked.emit(0, 1)

    assert submitted_payloads == [("a-1", {"api_key": "api-new"})]


def test_window_clicking_proxy_opens_editor(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    submitted_payloads: list[tuple[str, dict]] = []

    class FakeProxyDialog:
        def exec(self) -> int:
            return int(QDialog.DialogCode.Accepted)

        def build_proxy_payload(self) -> dict:
            return {"proxy_mode": "custom", "proxy_url": "http://127.0.0.1:9500"}

    class SpyController:
        def edit_account_proxy(self, account_id: str, payload: dict) -> None:
            submitted_payloads.append((account_id, payload))

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                "account_id": "a-1",
                "display_name": "旧备注",
                "remark_name": "旧备注",
                "c5_nick_name": "平台昵称",
                "default_name": "默认名",
                "api_key_present": True,
                "api_key": "api-key",
                "proxy_mode": "direct",
                "proxy_url": None,
                "proxy_display": "直连",
                "purchase_capability_state": "bound",
                "purchase_pool_state": "not_connected",
                "disabled": False,
                "selected_steam_id": "steam-1",
                "selected_warehouse_text": "steam-1",
                "purchase_status_code": "selected_warehouse",
                "purchase_status_text": "steam-1",
            }
        ]
    )
    window = AccountCenterWindow(
        view_model=vm,
        backend_client=object(),
        login_proxy_dialog_factory=lambda account, parent=None: FakeProxyDialog(),
    )
    qtbot.addWidget(window)
    window.controller = SpyController()

    window.account_table.cellClicked.emit(0, 3)

    assert submitted_payloads == [("a-1", {"proxy_mode": "custom", "proxy_url": "http://127.0.0.1:9500"})]


def test_window_clicking_purchase_status_for_unlogged_account_starts_login_flow(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    submitted_payloads: list[tuple[str, dict]] = []

    class FakeLoginDialog:
        def exec(self) -> int:
            return int(QDialog.DialogCode.Accepted)

        def build_proxy_payload(self) -> dict:
            return {"proxy_mode": "direct", "proxy_url": None}

    class SpyController:
        def submit_login_proxy_for_account(self, account_id: str, payload: dict) -> None:
            submitted_payloads.append((account_id, payload))

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                "account_id": "a-1",
                "display_name": "未登录账号",
                "remark_name": "未登录账号",
                "c5_nick_name": None,
                "default_name": "默认名",
                "api_key_present": False,
                "api_key": None,
                "proxy_mode": "direct",
                "proxy_url": None,
                "proxy_display": "直连",
                "purchase_capability_state": "unbound",
                "purchase_pool_state": "not_connected",
                "disabled": False,
                "selected_steam_id": None,
                "selected_warehouse_text": None,
                "purchase_status_code": "not_logged_in",
                "purchase_status_text": "未登录",
            }
        ]
    )
    window = AccountCenterWindow(
        view_model=vm,
        backend_client=object(),
        login_proxy_dialog_factory=lambda account, parent=None: FakeLoginDialog(),
    )
    qtbot.addWidget(window)
    window.controller = SpyController()

    window.account_table.cellClicked.emit(0, 2)

    assert submitted_payloads == [("a-1", {"proxy_mode": "direct", "proxy_url": None})]


def test_window_clicking_purchase_status_loads_inventory_detail_then_opens_purchase_config_dialog(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    loaded_account_ids: list[str] = []
    captured_inventory_details: list[dict] = []
    submitted_payloads: list[tuple[str, dict]] = []

    class FakePurchaseConfigDialog:
        def exec(self) -> int:
            return int(QDialog.DialogCode.Accepted)

        def build_payload(self) -> dict:
            return {"disabled": True, "selected_steam_id": "steam-2"}

    class SpyController:
        def load_purchase_inventory_detail(self, account_id: str, on_loaded) -> None:
            loaded_account_ids.append(account_id)
            on_loaded(
                {
                    "account_id": account_id,
                    "display_name": "可买账号",
                    "selected_steam_id": "steam-1",
                    "refreshed_at": "2026-03-18T10:00:00",
                    "last_error": None,
                    "inventories": [
                        {
                            "steamId": "steam-1",
                            "inventory_num": 900,
                            "inventory_max": 1000,
                            "remaining_capacity": 100,
                            "is_selected": True,
                            "is_available": True,
                        },
                        {
                            "steamId": "steam-2",
                            "inventory_num": 1000,
                            "inventory_max": 1000,
                            "remaining_capacity": 0,
                            "is_selected": False,
                            "is_available": False,
                        },
                    ],
                }
            )

        def update_account_purchase_config(self, account_id: str, payload: dict) -> None:
            submitted_payloads.append((account_id, payload))

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                "account_id": "a-1",
                "display_name": "可买账号",
                "remark_name": "可买账号",
                "c5_nick_name": None,
                "default_name": "默认名",
                "api_key_present": True,
                "api_key": "api-key",
                "proxy_mode": "direct",
                "proxy_url": None,
                "proxy_display": "直连",
                "purchase_capability_state": "bound",
                "purchase_pool_state": "not_connected",
                "disabled": False,
                "selected_steam_id": "steam-1",
                "selected_warehouse_text": "steam-1",
                "purchase_status_code": "selected_warehouse",
                "purchase_status_text": "steam-1",
            }
        ]
    )
    window = AccountCenterWindow(
        view_model=vm,
        backend_client=object(),
        purchase_config_dialog_factory=lambda account, inventory_detail, parent=None: (
            captured_inventory_details.append(inventory_detail),
            FakePurchaseConfigDialog(),
        )[1],
    )
    qtbot.addWidget(window)
    window.controller = SpyController()

    window.account_table.cellClicked.emit(0, 2)

    assert loaded_account_ids == ["a-1"]
    assert captured_inventory_details == [
        {
            "account_id": "a-1",
            "display_name": "可买账号",
            "selected_steam_id": "steam-1",
            "refreshed_at": "2026-03-18T10:00:00",
            "last_error": None,
            "inventories": [
                {
                    "steamId": "steam-1",
                    "inventory_num": 900,
                    "inventory_max": 1000,
                    "remaining_capacity": 100,
                    "is_selected": True,
                    "is_available": True,
                },
                {
                    "steamId": "steam-2",
                    "inventory_num": 1000,
                    "inventory_max": 1000,
                    "remaining_capacity": 0,
                    "is_selected": False,
                    "is_available": False,
                },
            ],
        }
    ]
    assert submitted_payloads == [("a-1", {"disabled": True, "selected_steam_id": "steam-2"})]


def test_window_delete_account_requires_confirmation(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    deleted_account_ids: list[str] = []

    class FakeConfirmService:
        def __init__(self, result: bool) -> None:
            self._result = result

        def ask(self, title: str, message: str) -> bool:
            return self._result

    class SpyController:
        def delete_account(self, account_id: str) -> None:
            deleted_account_ids.append(account_id)

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                "account_id": "a-1",
                "display_name": "可删账号",
                "remark_name": "可删账号",
                "c5_nick_name": None,
                "default_name": "默认名",
                "api_key_present": True,
                "api_key": "api-key",
                "proxy_mode": "direct",
                "proxy_url": None,
                "proxy_display": "直连",
                "purchase_capability_state": "bound",
                "purchase_pool_state": "not_connected",
                "disabled": False,
                "selected_steam_id": "steam-1",
                "selected_warehouse_text": "steam-1",
                "purchase_status_code": "selected_warehouse",
                "purchase_status_text": "steam-1",
            }
        ]
    )
    window = AccountCenterWindow(
        view_model=vm,
        backend_client=object(),
        confirm_service=FakeConfirmService(True),
    )
    qtbot.addWidget(window)
    window.controller = SpyController()

    window._delete_account_by_id("a-1")

    assert deleted_account_ids == ["a-1"]
