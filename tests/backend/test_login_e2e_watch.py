from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app_backend.infrastructure.browser_runtime.login_adapter import LoginCapture
from app_backend.main import create_app
from app_backend.debug.login_e2e_watch import run_login_watch


class _FastFakeLoginAdapter:
    async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
        for state in ("waiting_for_scan", "captured_login_info", "waiting_for_browser_close"):
            if emit_state is not None:
                await emit_state(state)
        return LoginCapture(
            c5_user_id="70007",
            c5_nick_name="烟测账号",
            cookie_raw="smoke=cookie",
        )


class _SlowFakeLoginAdapter:
    async def run_login(self, *, proxy_url: str | None, emit_state=None) -> LoginCapture:
        if emit_state is not None:
            await emit_state("waiting_for_scan")
        await asyncio.sleep(0.05)
        if emit_state is not None:
            await emit_state("captured_login_info")
            await emit_state("waiting_for_browser_close")
        return LoginCapture(
            c5_user_id="80008",
            c5_nick_name="慢速烟测",
            cookie_raw="slow=cookie",
        )


def _read_log_lines(log_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def test_run_login_watch_writes_task_events_and_db_summary(tmp_path: Path):
    db_path = tmp_path / "watch.db"
    log_path = tmp_path / "watch.jsonl"
    app = create_app(db_path=db_path)
    app.state.login_adapter = _FastFakeLoginAdapter()

    summary = await run_login_watch(
        app=app,
        db_path=db_path,
        log_path=log_path,
        poll_interval_seconds=0.01,
        heartbeat_interval_seconds=10.0,
        timeout_seconds=2.0,
    )

    assert summary["task_state"] == "succeeded"
    assert summary["account_id"]
    assert summary["task_id"]
    assert summary["log_path"] == str(log_path)

    lines = _read_log_lines(log_path)
    event_states = [line["state"] for line in lines if line["phase"] == "task_event"]
    assert event_states == [
        "pending",
        "starting_browser",
        "waiting_for_scan",
        "captured_login_info",
        "waiting_for_browser_close",
        "saving_account",
        "succeeded",
    ]

    account_line = next(line for line in lines if line["phase"] == "account_detail")
    assert account_line["account"]["c5_user_id"] == "70007"
    assert account_line["account"]["c5_nick_name"] == "烟测账号"
    assert account_line["account"]["purchase_capability_state"] == "bound"
    assert account_line["account"]["has_cookie_raw"] is True
    assert "cookie_raw" not in account_line["account"]

    sqlite_line = next(line for line in lines if line["phase"] == "sqlite_row")
    assert sqlite_line["row"]["exists"] is True
    assert sqlite_line["row"]["c5_user_id"] == "70007"
    assert sqlite_line["row"]["purchase_capability_state"] == "bound"
    assert sqlite_line["row"]["has_cookie_raw"] is True
    assert "cookie_raw" not in sqlite_line["row"]


async def test_run_login_watch_emits_heartbeat_when_state_lingers(tmp_path: Path):
    db_path = tmp_path / "heartbeat.db"
    log_path = tmp_path / "heartbeat.jsonl"
    app = create_app(db_path=db_path)
    app.state.login_adapter = _SlowFakeLoginAdapter()

    summary = await run_login_watch(
        app=app,
        db_path=db_path,
        log_path=log_path,
        poll_interval_seconds=0.01,
        heartbeat_interval_seconds=0.01,
        timeout_seconds=2.0,
    )

    assert summary["task_state"] == "succeeded"

    lines = _read_log_lines(log_path)
    heartbeats = [line for line in lines if line["phase"] == "task_heartbeat"]
    assert heartbeats
    assert any(line["state"] == "waiting_for_scan" for line in heartbeats)


def test_login_e2e_watch_main_prints_attach_mode_instructions(monkeypatch, capsys, tmp_path: Path):
    import app_backend.debug.login_e2e_watch as module

    db_path = tmp_path / "attach.db"
    log_path = tmp_path / "attach.jsonl"

    monkeypatch.setenv("C5_EDGE_DEBUGGER_ADDRESS", "127.0.0.1:9222")
    monkeypatch.setattr(module, "_default_paths", lambda: (db_path, log_path))

    async def fake_run_login_watch(**kwargs):
        return {
            "account_id": "acc-1",
            "task_id": "task-1",
            "task_state": "succeeded",
            "db_path": str(kwargs["db_path"]),
            "log_path": str(kwargs["log_path"]),
        }

    monkeypatch.setattr(module, "run_login_watch", fake_run_login_watch)

    exit_code = module.main(["--remark-name", "登录验真-attach"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "attach 模式" in captured
    assert "无需关闭浏览器窗口" in captured
    assert "关闭临时浏览器窗口" not in captured


def test_attach_helper_script_targets_default_profile():
    script_path = Path("app_backend/debug/start_default_profile_attach_login_watch.ps1")

    content = script_path.read_text(encoding="utf-8")

    assert '[int]$Port = 9222' in content
    assert '[string]$ProfileDirectory = "Default"' in content
    assert '"--remote-debugging-port=$Port"' in content
    assert '"--profile-directory=$ProfileDirectory"' in content
    assert "C5_EDGE_DEBUGGER_ADDRESS" in content
    assert "login_e2e_watch" in content
    assert "Microsoft\\Edge\\User Data" in content


def test_shortcut_attach_helper_script_invokes_backend_helper():
    script_path = Path("调试/默认配置附着登录验真.ps1")

    content = script_path.read_text(encoding="utf-8")

    assert "start_default_profile_attach_login_watch.ps1" in content
    assert "app_backend\\debug" in content

