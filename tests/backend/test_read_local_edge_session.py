from __future__ import annotations

import json


def test_main_reads_local_edge_session_and_prints_summary(monkeypatch, capsys):
    import app_backend.debug.read_local_edge_session as module

    captured: dict[str, object] = {}

    class FakeAdapter:
        async def run_login(self, *, proxy_url, emit_state=None):
            captured["proxy_url"] = proxy_url
            if emit_state is not None:
                await emit_state("captured_login_info")
            return {
                "c5_user_id": "10001",
                "c5_nick_name": "本地已登录账号",
                "cookie_raw": "foo=bar; NC5_accessToken=token-1",
            }

    monkeypatch.setattr(module, "_build_local_edge_adapter", lambda debugger_address: (
        captured.setdefault("debugger_address", debugger_address),
        FakeAdapter(),
    )[1])

    exit_code = module.main(["--debugger-address", "127.0.0.1:9333"])

    assert exit_code == 0
    assert captured["debugger_address"] == "127.0.0.1:9333"
    assert captured["proxy_url"] is None

    payload = json.loads(capsys.readouterr().out)
    assert payload["debugger_address"] == "127.0.0.1:9333"
    assert payload["c5_user_id"] == "10001"
    assert payload["c5_nick_name"] == "本地已登录账号"
    assert payload["has_cookie_raw"] is True
    assert payload["cookie_raw_preview"] == "foo=bar; NC5_accessToken=token-1"


def test_main_prefers_env_debugger_address(monkeypatch, capsys):
    import app_backend.debug.read_local_edge_session as module

    monkeypatch.setenv("C5_EDGE_DEBUGGER_ADDRESS", "127.0.0.1:9222")
    monkeypatch.setattr(
        module,
        "_build_local_edge_adapter",
        lambda debugger_address: type(
            "Adapter",
            (),
            {
                "run_login": staticmethod(
                    lambda **_kwargs: {
                        "c5_user_id": "10002",
                        "c5_nick_name": "环境变量账号",
                        "cookie_raw": "NC5_accessToken=token-2",
                    }
                )
            },
        )(),
    )

    exit_code = module.main([])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["debugger_address"] == "127.0.0.1:9222"


def test_main_requires_debugger_address(capsys):
    import app_backend.debug.read_local_edge_session as module

    exit_code = module.main([])

    assert exit_code == 2
    assert "缺少 Edge 调试地址" in capsys.readouterr().err
