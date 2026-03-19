from __future__ import annotations


def _account(
    account_id: str,
    *,
    default_name: str,
    remark_name: str | None = None,
    c5_nick_name: str | None = None,
) -> dict:
    return {
        "account_id": account_id,
        "default_name": default_name,
        "remark_name": remark_name,
        "display_name": remark_name or c5_nick_name or default_name,
        "proxy_mode": "direct",
        "proxy_url": None,
        "api_key": None,
        "c5_user_id": None,
        "c5_nick_name": c5_nick_name,
        "cookie_raw": None,
        "purchase_capability_state": "unbound",
        "purchase_pool_state": "not_connected",
        "last_login_at": None,
        "last_error": None,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
        "disabled": False,
    }


def _account_center_row(
    account_id: str,
    *,
    display_name: str,
    api_key_present: bool = False,
    purchase_status_code: str = "not_logged_in",
    purchase_status_text: str = "未登录",
    proxy_display: str = "直连",
) -> dict:
    return {
        "account_id": account_id,
        "display_name": display_name,
        "remark_name": display_name,
        "c5_nick_name": None,
        "default_name": f"默认-{account_id}",
        "api_key_present": api_key_present,
        "api_key": "api-key" if api_key_present else None,
        "proxy_mode": "direct",
        "proxy_url": None if proxy_display == "直连" else proxy_display,
        "proxy_display": proxy_display,
        "purchase_capability_state": "bound",
        "purchase_pool_state": "not_connected",
        "disabled": purchase_status_code == "disabled",
        "selected_steam_id": purchase_status_text if purchase_status_code == "selected_warehouse" else None,
        "selected_warehouse_text": purchase_status_text if purchase_status_code == "selected_warehouse" else None,
        "purchase_status_code": purchase_status_code,
        "purchase_status_text": purchase_status_text,
    }


def test_selected_row_does_not_auto_open_detail():
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            _account("a-1", default_name="默认A"),
            _account("a-2", default_name="默认B"),
        ]
    )

    vm.select_account("a-1")

    assert vm.selected_account_id == "a-1"
    assert vm.detail_account is None


def test_open_selected_detail_loads_current_account():
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel

    vm = AccountCenterViewModel()
    vm.set_accounts([_account("a-1", default_name="默认A")])
    vm.select_account("a-1")

    detail = vm.open_selected_account_detail()

    assert detail is not None
    assert detail["account_id"] == "a-1"
    assert vm.detail_account["account_id"] == "a-1"


def test_display_name_priority_is_reflected_in_table_rows():
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            _account("a-1", default_name="默认A", remark_name="备注A", c5_nick_name="平台A"),
            _account("a-2", default_name="默认B", c5_nick_name="平台B"),
            _account("a-3", default_name="默认C"),
        ]
    )

    rows = vm.table_rows

    assert [row["display_name"] for row in rows] == ["备注A", "平台B", "默认C"]


def test_table_rows_render_capability_states_in_chinese():
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            {
                **_account("a-1", default_name="默认A"),
                "api_key": "api-key",
                "purchase_capability_state": "bound",
                "purchase_pool_state": "not_connected",
                "proxy_url": "http://127.0.0.1:9900",
            }
        ]
    )

    row = vm.table_rows[0]

    assert row["query_capability"] == "已配置"
    assert row["purchase_capability"] == "已绑定"
    assert row["purchase_pool_state"] == "未接入"
    assert row["proxy"] == "http://127.0.0.1:9900"


def test_table_rows_render_new_account_center_columns():
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            _account_center_row(
                "a-1",
                display_name="备注A",
                api_key_present=True,
                purchase_status_code="selected_warehouse",
                purchase_status_text="steam-1",
                proxy_display="http://127.0.0.1:9900",
            )
        ]
    )

    row = vm.table_rows[0]

    assert row["account_id"] == "a-1"
    assert row["c5_nickname"] == "备注A"
    assert row["api_key"] == "有"
    assert row["purchase_status"] == "steam-1"
    assert row["purchase_status_code"] == "selected_warehouse"
    assert row["proxy"] == "http://127.0.0.1:9900"


def test_selected_account_uses_account_center_row_shape():
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel

    vm = AccountCenterViewModel()
    vm.set_accounts(
        [
            _account_center_row(
                "a-1",
                display_name="备注A",
                api_key_present=False,
                purchase_status_code="disabled",
                purchase_status_text="禁用",
            )
        ]
    )

    vm.select_account("a-1")

    assert vm.selected_account is not None
    assert vm.selected_account["display_name"] == "备注A"
    assert vm.selected_account["purchase_status_text"] == "禁用"
    assert vm.selected_account["purchase_status_code"] == "disabled"
