from __future__ import annotations


async def test_login_adapter_returns_c5_payload():
    from app_backend.infrastructure.selenium.login_adapter import LegacySeleniumLoginAdapter

    captured: dict[str, str | None] = {}

    async def fake_runner(proxy_url, emit_state):
        captured["proxy_url"] = proxy_url
        await emit_state("waiting_for_scan")
        return {
            "c5_user_id": "10001",
            "c5_nick_name": "测试账号",
            "cookie_raw": "foo=bar",
        }

    adapter = LegacySeleniumLoginAdapter(login_runner=fake_runner)
    result = await adapter.run_login(proxy_url="http://127.0.0.1:8888")

    assert captured["proxy_url"] == "http://127.0.0.1:8888"
    assert result.c5_user_id == "10001"
    assert result.c5_nick_name == "测试账号"
    assert result.cookie_raw == "foo=bar"
