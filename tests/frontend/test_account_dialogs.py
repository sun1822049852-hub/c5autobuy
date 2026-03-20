from __future__ import annotations

from PySide6.QtCore import Qt


def _account() -> dict:
    return {
        "account_id": "a-1",
        "default_name": "默认名",
        "remark_name": "旧备注",
        "display_name": "旧备注",
        "proxy_mode": "direct",
        "proxy_url": None,
        "api_key": None,
        "c5_user_id": "12345",
        "c5_nick_name": "平台昵称",
        "cookie_raw": "NC5_accessToken=token-1; foo=bar",
        "purchase_capability_state": "bound",
        "purchase_pool_state": "not_connected",
        "last_login_at": "2026-03-16T12:00:00",
        "last_error": None,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
        "purchase_disabled": False,
        "new_api_enabled": True,
        "fast_api_enabled": False,
        "token_enabled": True,
    }


def test_create_dialog_accepts_empty_proxy_as_direct(qtbot):
    from app_frontend.app.dialogs.create_account_dialog import CreateAccountDialog

    dialog = CreateAccountDialog()
    qtbot.addWidget(dialog)
    dialog.remark_name_input.setText("新账号")
    dialog.proxy_mode_combo.setCurrentText("direct")
    dialog.proxy_url_input.clear()
    dialog.api_key_input.clear()

    payload = dialog.build_payload()

    assert payload == {
        "remark_name": "新账号",
        "proxy_mode": "direct",
        "proxy_url": None,
        "api_key": None,
    }


def test_edit_dialog_updates_allowed_fields(qtbot):
    from app_frontend.app.dialogs.edit_account_dialog import EditAccountDialog

    dialog = EditAccountDialog(account=_account())
    qtbot.addWidget(dialog)
    dialog.remark_name_input.setText("新备注")
    dialog.proxy_mode_combo.setCurrentText("custom")
    dialog.proxy_url_input.setText("http://127.0.0.1:9300")
    dialog.api_key_input.setText("new-api")

    payload = dialog.build_payload()

    assert payload == {
        "remark_name": "新备注",
        "proxy_mode": "custom",
        "proxy_url": "http://127.0.0.1:9300",
        "api_key": "new-api",
    }
    assert dialog.build_query_mode_payload() == {
        "new_api_enabled": True,
        "fast_api_enabled": False,
        "token_enabled": True,
    }


def test_edit_dialog_disables_query_modes_without_api_key_or_token(qtbot):
    from app_frontend.app.dialogs.edit_account_dialog import EditAccountDialog

    account = _account()
    account["api_key"] = None
    account["cookie_raw"] = None
    account["new_api_enabled"] = True
    account["fast_api_enabled"] = True
    account["token_enabled"] = True

    dialog = EditAccountDialog(account=account)
    qtbot.addWidget(dialog)

    assert dialog.new_api_enabled_checkbox.isEnabled() is False
    assert dialog.fast_api_enabled_checkbox.isEnabled() is False
    assert dialog.token_enabled_checkbox.isEnabled() is False
    assert dialog.build_query_mode_payload() == {
        "new_api_enabled": False,
        "fast_api_enabled": False,
        "token_enabled": False,
    }


def test_edit_dialog_enables_api_modes_when_api_key_is_present(qtbot):
    from app_frontend.app.dialogs.edit_account_dialog import EditAccountDialog

    account = _account()
    account["api_key"] = None
    account["cookie_raw"] = "foo=bar"
    account["token_enabled"] = False

    dialog = EditAccountDialog(account=account)
    qtbot.addWidget(dialog)
    dialog.api_key_input.setText("api-new")

    assert dialog.new_api_enabled_checkbox.isEnabled() is True
    assert dialog.fast_api_enabled_checkbox.isEnabled() is True
    assert dialog.token_enabled_checkbox.isEnabled() is False


def test_account_dialogs_do_not_expose_purchase_capability_editing(qtbot):
    from app_frontend.app.dialogs.create_account_dialog import CreateAccountDialog
    from app_frontend.app.dialogs.edit_account_dialog import EditAccountDialog

    create_dialog = CreateAccountDialog()
    edit_dialog = EditAccountDialog(account=_account())
    qtbot.addWidget(create_dialog)
    qtbot.addWidget(edit_dialog)

    for dialog in (create_dialog, edit_dialog):
        assert not hasattr(dialog, "cookie_input")
        assert not hasattr(dialog, "c5_user_id_input")
        assert not hasattr(dialog, "purchase_capability_input")


def test_login_proxy_dialog_prefills_current_proxy(qtbot):
    from app_frontend.app.dialogs.login_proxy_dialog import LoginProxyDialog

    account = _account()
    account["proxy_mode"] = "custom"
    account["proxy_url"] = "http://127.0.0.1:9400"

    dialog = LoginProxyDialog(account=account)
    qtbot.addWidget(dialog)

    assert dialog.proxy_mode_combo.currentText() == "custom"
    assert dialog.proxy_url_input.text() == "http://127.0.0.1:9400"
    assert dialog.build_proxy_payload() == {
        "proxy_mode": "custom",
        "proxy_url": "http://127.0.0.1:9400",
    }


def test_login_proxy_dialog_builds_split_proxy_payload(qtbot):
    from app_frontend.app.dialogs.login_proxy_dialog import LoginProxyDialog

    dialog = LoginProxyDialog(account=_account())
    qtbot.addWidget(dialog)
    dialog.proxy_mode_combo.setCurrentText("custom")
    dialog.proxy_url_input.clear()
    dialog.proxy_scheme_combo.setCurrentText("https")
    dialog.proxy_host_input.setText("127.0.0.1")
    dialog.proxy_port_input.setText("9900")
    dialog.proxy_username_input.setText("demo")
    dialog.proxy_password_input.setText("secret")

    assert dialog.build_proxy_payload() == {
        "proxy_mode": "custom",
        "proxy_url": "https://demo:secret@127.0.0.1:9900",
    }


def test_purchase_config_dialog_lists_warehouses_and_only_allows_available_selection(qtbot):
    from app_frontend.app.dialogs.purchase_config_dialog import PurchaseConfigDialog

    dialog = PurchaseConfigDialog(
        account=_account() | {"purchase_disabled": False, "selected_steam_id": "steam-1"},
        inventory_detail={
            "account_id": "a-1",
            "display_name": "旧备注",
            "selected_steam_id": "steam-1",
            "refreshed_at": "2026-03-18T10:00:00",
            "last_error": None,
            "inventories": [
                {
                    "steamId": "steam-1",
                    "inventory_num": 910,
                    "inventory_max": 1000,
                    "remaining_capacity": 90,
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
        },
    )
    qtbot.addWidget(dialog)

    assert dialog.inventory_table.rowCount() == 2
    assert dialog.inventory_table.item(0, 0).text() == "steam-1"
    assert dialog.inventory_table.item(1, 4).text() == "库存已满"
    assert bool(dialog.inventory_table.item(1, 0).flags() & Qt.ItemFlag.ItemIsSelectable) is False

    dialog.inventory_table.selectRow(0)

    assert dialog.build_payload() == {
        "purchase_disabled": False,
        "selected_steam_id": "steam-1",
    }


def test_purchase_config_dialog_keeps_full_current_warehouse_as_display_only(qtbot):
    from app_frontend.app.dialogs.purchase_config_dialog import PurchaseConfigDialog

    dialog = PurchaseConfigDialog(
        account=_account() | {"purchase_disabled": False, "selected_steam_id": "steam-2"},
        inventory_detail={
            "account_id": "a-1",
            "display_name": "旧备注",
            "selected_steam_id": "steam-2",
            "refreshed_at": "2026-03-18T10:00:00",
            "last_error": None,
            "inventories": [
                {
                    "steamId": "steam-2",
                    "inventory_num": 1000,
                    "inventory_max": 1000,
                    "remaining_capacity": 0,
                    "is_selected": True,
                    "is_available": False,
                }
            ],
        },
    )
    qtbot.addWidget(dialog)

    assert dialog.current_selected_input.text() == "steam-2"
    assert dialog.inventory_table.currentRow() == -1
    assert dialog.build_payload() == {
        "purchase_disabled": False,
        "selected_steam_id": None,
    }
