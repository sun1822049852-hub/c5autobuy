from __future__ import annotations


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
        "cookie_raw": "foo=bar",
        "purchase_capability_state": "bound",
        "purchase_pool_state": "not_connected",
        "last_login_at": "2026-03-16T12:00:00",
        "last_error": None,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
        "disabled": False,
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
