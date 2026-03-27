from __future__ import annotations

import pytest


async def test_login_adapter_returns_c5_payload():
    from app_backend.infrastructure.browser_runtime.login_adapter import BrowserLoginAdapter

    captured: dict[str, str | None] = {}

    async def fake_runner(proxy_url, account_id=None, emit_state=None):
        captured["proxy_url"] = proxy_url
        captured["account_id"] = account_id
        await emit_state("waiting_for_scan")
        return {
            "c5_user_id": "10001",
            "c5_nick_name": "测试账号",
            "cookie_raw": "foo=bar",
        }

    adapter = BrowserLoginAdapter(login_runner=fake_runner)
    result = await adapter.run_login(proxy_url="http://127.0.0.1:8888")

    assert captured["proxy_url"] == "http://127.0.0.1:8888"
    assert captured["account_id"] is None
    assert result.captured_login.c5_user_id == "10001"
    assert result.captured_login.c5_nick_name == "测试账号"
    assert result.captured_login.cookie_raw == "foo=bar"
    assert result.c5_user_id == "10001"
    assert result.c5_nick_name == "测试账号"
    assert result.cookie_raw == "foo=bar"
    assert result.session_payload["cookie_raw"] == "foo=bar"


def test_login_adapter_requires_explicit_login_runner():
    from app_backend.infrastructure.browser_runtime.login_adapter import BrowserLoginAdapter

    with pytest.raises(TypeError):
        BrowserLoginAdapter()

