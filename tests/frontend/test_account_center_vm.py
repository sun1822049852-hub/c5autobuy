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
