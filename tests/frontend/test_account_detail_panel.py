from __future__ import annotations

from PySide6.QtCore import Qt


def _account(
    account_id: str,
    *,
    display_name: str,
    api_key: str | None = "api-demo",
    purchase_capability_state: str = "bound",
    purchase_pool_state: str = "not_connected",
    last_error: str | None = None,
) -> dict:
    return {
        "account_id": account_id,
        "default_name": "默认名",
        "remark_name": "备注名",
        "display_name": display_name,
        "proxy_mode": "custom",
        "proxy_url": "http://127.0.0.1:9200",
        "api_key": api_key,
        "c5_user_id": "12345",
        "c5_nick_name": "平台昵称",
        "cookie_raw": "NC5_accessToken=token-1; foo=bar",
        "purchase_capability_state": purchase_capability_state,
        "purchase_pool_state": purchase_pool_state,
        "last_login_at": "2026-03-16T12:00:00",
        "last_error": last_error,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
        "purchase_disabled": False,
        "new_api_enabled": True,
        "fast_api_enabled": False,
        "token_enabled": True,
    }


def test_detail_panel_fields_are_readonly(qtbot):
    from app_frontend.app.widgets.account_detail_panel import AccountDetailPanel

    panel = AccountDetailPanel()
    qtbot.addWidget(panel)
    panel.load_account(_account("a-1", display_name="详情账号"))

    assert panel.display_name_input.isReadOnly()
    assert panel.remark_name_input.isReadOnly()
    assert panel.proxy_input.isReadOnly()
    assert panel.api_key_status_input.isReadOnly()
    assert panel.purchase_capability_input.isReadOnly()
    assert panel.purchase_pool_input.isReadOnly()
    assert panel.default_name_input.isReadOnly()
    assert panel.c5_nick_name_input.isReadOnly()
    assert panel.c5_user_id_input.isReadOnly()
    assert panel.new_api_mode_input.isReadOnly()
    assert panel.fast_api_mode_input.isReadOnly()
    assert panel.token_mode_input.isReadOnly()


def test_detail_panel_shows_all_account_identity_layers_and_actions(qtbot):
    from app_frontend.app.widgets.account_detail_panel import AccountDetailPanel

    panel = AccountDetailPanel()
    qtbot.addWidget(panel)
    panel.load_account(_account("a-1", display_name="详情账号"))

    assert panel.display_name_input.text() == "详情账号"
    assert panel.default_name_input.text() == "默认名"
    assert panel.remark_name_input.text() == "备注名"
    assert panel.c5_nick_name_input.text() == "平台昵称"
    assert panel.c5_user_id_input.text() == "12345"
    assert panel.last_login_input.text() == "2026-03-16 12:00:00"
    assert panel.last_error_input.text() == ""
    assert panel.new_api_mode_input.text() == "已启用"
    assert panel.fast_api_mode_input.text() == "已关闭"
    assert panel.token_mode_input.text() == "已启用"
    assert panel.edit_query_button.text() == "编辑账号"
    assert panel.start_login_button.text() == "发起登录"
    assert panel.clear_purchase_button.text() == "清除购买能力"
    assert panel.delete_account_button.text() == "删除账号"


def test_detail_panel_applies_semantic_tones_for_status_fields(qtbot):
    from app_frontend.app.widgets.account_detail_panel import AccountDetailPanel

    panel = AccountDetailPanel()
    qtbot.addWidget(panel)
    panel.load_account(_account("a-1", display_name="详情账号"))

    assert panel.api_key_status_input.property("tone") == "ok"
    assert panel.purchase_capability_input.property("tone") == "ok"
    assert panel.purchase_pool_input.property("tone") == "muted"
    assert panel.new_api_mode_input.property("tone") == "ok"
    assert panel.fast_api_mode_input.property("tone") == "muted"
    assert panel.token_mode_input.property("tone") == "ok"
    assert panel.last_error_input.property("tone") == "neutral"
    assert panel.last_error_input.toolTip() == ""


def test_detail_panel_highlights_recent_error_and_problem_states(qtbot):
    from app_frontend.app.widgets.account_detail_panel import AccountDetailPanel

    panel = AccountDetailPanel()
    qtbot.addWidget(panel)
    panel.load_account(
        _account(
            "a-2",
            display_name="异常账号",
            api_key=None,
            purchase_capability_state="expired",
            purchase_pool_state="paused_no_inventory",
            last_error="代理认证失败",
        )
    )

    assert panel.api_key_status_input.property("tone") == "muted"
    assert panel.purchase_capability_input.property("tone") == "error"
    assert panel.purchase_pool_input.property("tone") == "warn"
    assert panel.new_api_mode_input.text() == "缺少 API Key"
    assert panel.fast_api_mode_input.text() == "缺少 API Key"
    assert panel.token_mode_input.text() == "已启用"
    assert panel.last_error_input.property("tone") == "error"
    assert panel.last_error_input.toolTip() == "代理认证失败"


def test_detail_panel_supports_active_and_auth_invalid_pool_states(qtbot):
    from app_frontend.app.widgets.account_detail_panel import AccountDetailPanel

    active_panel = AccountDetailPanel()
    qtbot.addWidget(active_panel)
    active_panel.load_account(
        _account(
            "a-3",
            display_name="运行账号",
            purchase_capability_state="bound",
            purchase_pool_state="active",
        )
    )

    assert active_panel.purchase_pool_input.text() == "运行中"
    assert active_panel.purchase_pool_input.property("tone") == "ok"

    invalid_panel = AccountDetailPanel()
    qtbot.addWidget(invalid_panel)
    invalid_panel.load_account(
        _account(
            "a-4",
            display_name="失效账号",
            purchase_capability_state="expired",
            purchase_pool_state="paused_auth_invalid",
        )
    )

    assert invalid_panel.purchase_pool_input.text() == "鉴权失效暂停"
    assert invalid_panel.purchase_pool_input.property("tone") == "error"


def test_clicking_view_detail_loads_detail_panel(qtbot):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            _account("a-1", display_name="第一账号"),
            _account("a-2", display_name="第二账号"),
        ]
    )
    window = AccountCenterWindow(view_model=vm)
    qtbot.addWidget(window)

    window.account_table.selectRow(0)
    qtbot.wait(20)

    assert window.detail_panel.account_id_input.text() == ""

    qtbot.mouseClick(window.view_detail_button, Qt.LeftButton)

    assert window.detail_panel.account_id_input.text() == "a-1"
    assert window.detail_panel.display_name_input.text() == "第一账号"
