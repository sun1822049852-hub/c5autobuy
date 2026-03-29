from app_backend.domain.models.account import Account


def test_display_name_prefers_remark_then_platform_then_default():
    account = Account(
        account_id="a1",
        default_name="默认账号",
        remark_name="备注名",
        browser_proxy_mode="direct",
        browser_proxy_url=None,
        api_proxy_mode="direct",
        api_proxy_url=None,
        api_key=None,
        c5_user_id=None,
        c5_nick_name="平台昵称",
        cookie_raw=None,
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        purchase_disabled=False,
        new_api_enabled=True,
        fast_api_enabled=True,
        token_enabled=True,
    )

    assert account.display_name == "备注名"
