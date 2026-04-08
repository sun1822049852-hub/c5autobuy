from __future__ import annotations

import asyncio
from pathlib import Path
import threading


class _DummyRuntime:
    def __init__(self, root: Path) -> None:
        self.session_root = root / "browser-sessions"
        self.session_root.mkdir(parents=True, exist_ok=True)

    def resolve_browser_executable(self) -> Path:
        return Path("C:/Edge/msedge.exe")


class _DummyProfileStore:
    def __init__(self, root: Path) -> None:
        self.root = root / "browser-profiles"
        self.root.mkdir(parents=True, exist_ok=True)
        self.clone_calls: list[str] = []
        self.persist_calls: list[tuple[str, str]] = []

    def ensure_account_profile(self, account_id: str) -> Path:
        profile_root = self.root / account_id
        profile_root.mkdir(parents=True, exist_ok=True)
        return profile_root

    def clone_session(self, account_id: str, *, session_name: str | None = None) -> Path:
        self.clone_calls.append(account_id)
        session_root = self.root.parent / "browser-sessions" / str(session_name or account_id)
        session_root.mkdir(parents=True, exist_ok=True)
        return session_root

    def persist_session(self, account_id: str, session_root: Path) -> Path:
        self.persist_calls.append((account_id, str(session_root)))
        return self.ensure_account_profile(account_id)


class _FakeProcess:
    def __init__(self, *, poll_result=None) -> None:
        self._poll_result = poll_result
        self.terminated = False

    def poll(self):
        return self._poll_result

    def terminate(self):
        self.terminated = True
        self._poll_result = 0

    def wait(self, timeout=None):
        return 0


class _RelativeRuntime:
    session_root = Path("data/app-private/browser-sessions")

    def resolve_browser_executable(self) -> Path:
        return Path("data/app-private/browser-runtime/Application/msedge.exe")


async def test_managed_edge_cdp_login_runner_returns_capture_after_token_detected(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(runtime=runtime, login_timeout_seconds=1.0, poll_interval_seconds=0.0)
    process = _FakeProcess()
    captured_commands: list[list[str]] = []
    emitted_states: list[str] = []

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: captured_commands.append(command) or process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9555,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: {
            "c5_user_id": "10001",
            "c5_nick_name": "纯净账号",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        },
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._schedule_delayed_cleanup",
        lambda self, process, session_root, cleanup_callbacks, remove_session_root=True: None,
    )
    payload = await runner.run(
        proxy_url=None,
        emit_state=lambda state: emitted_states.append(state),
    )

    assert payload["c5_user_id"] == "10001"
    assert payload["c5_nick_name"] == "纯净账号"
    assert payload["debugger_address"] == "127.0.0.1:9555"
    assert emitted_states == ["waiting_for_scan", "captured_login_info"]
    assert any("--disable-extensions" in item for item in captured_commands[0])
    assert process.terminated is False


async def test_managed_edge_cdp_login_runner_waits_until_account_center_fields_are_complete(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(runtime=runtime, login_timeout_seconds=1.0, poll_interval_seconds=0.0)
    process = _FakeProcess()
    payloads = iter([
        {
            "c5_user_id": "10001",
            "c5_nick_name": "",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        },
        {
            "c5_user_id": "10001",
            "c5_nick_name": "纯净账号",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        },
    ])

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9557,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: next(payloads),
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._schedule_delayed_cleanup",
        lambda self, process, session_root, cleanup_callbacks, remove_session_root=True: None,
    )
    payload = await runner.run(proxy_url=None)

    assert payload["c5_nick_name"] == "纯净账号"
    assert process.terminated is False


async def test_managed_edge_cdp_login_runner_offloads_blocking_debugger_calls_from_event_loop(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(runtime=runtime, login_timeout_seconds=1.0, poll_interval_seconds=0.0)
    process = _FakeProcess()
    main_thread_id = threading.get_ident()
    wait_thread_ids: list[int] = []
    read_thread_ids: list[int] = []

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9559,
    )

    def _wait_for_debugger_port(port, process):
        wait_thread_ids.append(threading.get_ident())

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        _wait_for_debugger_port,
    )

    def _read_attached_session(debugger_address):
        read_thread_ids.append(threading.get_ident())
        return {
            "c5_user_id": "10001",
            "c5_nick_name": "纯净账号",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        }

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        _read_attached_session,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._schedule_delayed_cleanup",
        lambda self, process, session_root, cleanup_callbacks, remove_session_root=True: None,
    )

    payload = await runner.run(proxy_url=None)

    assert payload["c5_user_id"] == "10001"
    assert wait_thread_ids
    assert read_thread_ids
    assert all(thread_id != main_thread_id for thread_id in wait_thread_ids)
    assert all(thread_id != main_thread_id for thread_id in read_thread_ids)


async def test_managed_edge_cdp_login_runner_delays_close_after_capture(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(
        runtime=runtime,
        login_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
        close_delay_seconds=600.0,
    )
    process = _FakeProcess()
    wait_calls: list[float] = []

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9558,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: {
            "c5_user_id": "10001",
            "c5_nick_name": "纯净账号",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        },
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._wait_for_process_exit",
        lambda self, process, timeout_seconds: wait_calls.append(timeout_seconds),
    )

    class _ImmediateThread:
        def __init__(self, *, target, name=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr("app_backend.infrastructure.browser_runtime.login_adapter.threading.Thread", _ImmediateThread)

    await runner.run(proxy_url=None)

    assert wait_calls == [600.0]
    assert process.terminated is True


async def test_managed_edge_cdp_login_runner_times_out_when_token_never_appears(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(runtime=runtime, login_timeout_seconds=0.01, poll_interval_seconds=0.0)
    process = _FakeProcess()

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9556,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: {
            "c5_user_id": "",
            "c5_nick_name": "",
            "cookie_raw": "NC5_deviceId=device-1",
        },
    )

    try:
        await runner.run(proxy_url=None)
    except RuntimeError as exc:
        assert "登录失败或超时" in str(exc)
    else:
        raise AssertionError("expected timeout")
    assert process.terminated is True


async def test_managed_edge_cdp_login_runner_ignores_open_api_navigation_failure(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(runtime=runtime, login_timeout_seconds=1.0, poll_interval_seconds=0.0)
    process = _FakeProcess()

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9560,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: {
            "c5_user_id": "10001",
            "c5_nick_name": "纯净账号",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        },
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._schedule_delayed_cleanup",
        lambda self, process, session_root, cleanup_callbacks, remove_session_root=True: None,
    )

    payload = await runner.run(proxy_url=None)

    assert payload["c5_user_id"] == "10001"
    assert payload["c5_nick_name"] == "纯净账号"
    assert process.terminated is False


async def test_managed_edge_cdp_login_runner_uses_account_profile_store(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    profile_store = _DummyProfileStore(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(
        runtime=runtime,
        profile_store=profile_store,
        login_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
        close_delay_seconds=0.0,
    )
    process = _FakeProcess()
    captured_commands: list[list[str]] = []

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: captured_commands.append(command) or process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9561,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: {
            "c5_user_id": "10001",
            "c5_nick_name": "纯净账号",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        },
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._wait_for_process_exit",
        lambda self, process, timeout_seconds: None,
    )

    class _ImmediateThread:
        def __init__(self, *, target, name=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr("app_backend.infrastructure.browser_runtime.login_adapter.threading.Thread", _ImmediateThread)

    payload = await runner.run(proxy_url=None, account_id="account-1")

    assert payload["profile_root"] == str(tmp_path / "browser-profiles" / "account-1")
    assert payload["profile_directory"] == "Default"
    assert payload["profile_kind"] == "account"
    assert profile_store.clone_calls == ["account-1"]
    assert len(profile_store.persist_calls) == 1
    persisted_session_root = Path(profile_store.persist_calls[0][1])
    assert profile_store.persist_calls[0][0] == "account-1"
    assert persisted_session_root.parent == tmp_path / "browser-sessions"
    assert persisted_session_root.name.startswith("login-account-1-")
    assert any(str(persisted_session_root) in item for item in captured_commands[0])


def test_managed_edge_cdp_login_runner_launches_with_absolute_edge_and_session_paths(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    monkeypatch.chdir(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(runtime=_RelativeRuntime())
    process = _FakeProcess()
    captured_commands: list[list[str]] = []

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: captured_commands.append(command) or process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9661,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )

    runner._launch_browser(
        session_root=Path("data/app-private/browser-sessions/session-fixed"),
        proxy_url=None,
        cleanup_callbacks=[],
    )

    command = captured_commands[0]
    assert command[0] == str(
        (tmp_path / "data" / "app-private" / "browser-runtime" / "Application" / "msedge.exe").resolve()
    )
    assert f"--user-data-dir={(tmp_path / 'data' / 'app-private' / 'browser-sessions' / 'session-fixed').resolve()}" in command


async def test_managed_edge_cdp_login_runner_persists_profile_before_browser_exit(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    profile_store = _DummyProfileStore(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(
        runtime=runtime,
        profile_store=profile_store,
        login_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
        close_delay_seconds=0.0,
    )
    process = _FakeProcess()
    persist_poll_results: list[int | None] = []

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9562,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: {
            "c5_user_id": "10001",
            "c5_nick_name": "纯净账号",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        },
    )

    original_persist_session = profile_store.persist_session

    def _persist_session(account_id: str, session_root: Path) -> Path:
        persist_poll_results.append(process.poll())
        return original_persist_session(account_id, session_root)

    monkeypatch.setattr(profile_store, "persist_session", _persist_session)
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._wait_for_process_exit",
        lambda self, process, timeout_seconds: setattr(process, "_poll_result", 0),
    )

    class _ImmediateThread:
        def __init__(self, *, target, name=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr("app_backend.infrastructure.browser_runtime.login_adapter.threading.Thread", _ImmediateThread)

    payload = await runner.run(proxy_url=None, account_id="account-2")

    assert payload["profile_root"] == str(tmp_path / "browser-profiles" / "account-2")
    assert persist_poll_results == [None]
    assert process.terminated is False


async def test_managed_edge_cdp_login_runner_persists_profile_immediately_after_capture(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    profile_store = _DummyProfileStore(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(
        runtime=runtime,
        profile_store=profile_store,
        login_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )
    process = _FakeProcess()

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9563,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: {
            "c5_user_id": "10001",
            "c5_nick_name": "纯净账号",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        },
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._schedule_delayed_cleanup",
        lambda self, process, session_root, cleanup_callbacks, remove_session_root=True: None,
    )

    await runner.run(proxy_url=None, account_id="account-3")

    assert len(profile_store.persist_calls) == 1
    assert profile_store.persist_calls[0][0] == "account-3"
    assert Path(profile_store.persist_calls[0][1]).name.startswith("login-account-3-")


async def test_managed_edge_cdp_login_runner_skips_invalid_profile_persist_after_browser_exit(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    profile_store = _DummyProfileStore(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(
        runtime=runtime,
        profile_store=profile_store,
        login_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
        close_delay_seconds=0.0,
    )
    process = _FakeProcess()
    read_payloads = iter(
        [
            {
                "c5_user_id": "10001",
                "c5_nick_name": "纯净账号",
                "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
                "target_url": "https://www.c5game.com/user/user/",
            },
            {
                "c5_user_id": "10001",
                "c5_nick_name": "",
                "cookie_raw": "",
                "target_url": "https://www.c5game.com/login",
            },
        ]
    )

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9564,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: next(read_payloads),
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._wait_for_process_exit",
        lambda self, process, timeout_seconds: setattr(process, "_poll_result", 0),
    )

    class _ImmediateThread:
        def __init__(self, *, target, name=None, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr("app_backend.infrastructure.browser_runtime.login_adapter.threading.Thread", _ImmediateThread)

    await runner.run(proxy_url=None, account_id="account-4")

    assert len(profile_store.persist_calls) == 1
    assert profile_store.persist_calls[0][0] == "account-4"
    assert Path(profile_store.persist_calls[0][1]).name.startswith("login-account-4-")


async def test_managed_edge_cdp_login_runner_uses_dedicated_login_session_directory(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.login_adapter import ManagedEdgeCdpLoginRunner

    runtime = _DummyRuntime(tmp_path)
    profile_store = _DummyProfileStore(tmp_path)
    runner = ManagedEdgeCdpLoginRunner(
        runtime=runtime,
        profile_store=profile_store,
        login_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )
    process = _FakeProcess()
    captured_commands: list[list[str]] = []

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.subprocess.Popen",
        lambda command: captured_commands.append(command) or process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.reserve_debug_port",
        lambda: 9565,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.read_attached_session",
        lambda debugger_address: {
            "c5_user_id": "10001",
            "c5_nick_name": "纯净账号",
            "cookie_raw": "NC5_accessToken=token-1; NC5_deviceId=device-1",
            "target_url": "https://www.c5game.com/user/user/",
        },
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.login_adapter.ManagedEdgeCdpLoginRunner._schedule_delayed_cleanup",
        lambda self, process, session_root, cleanup_callbacks, remove_session_root=True: None,
    )

    await runner.run(proxy_url=None, account_id="account-5")

    command = captured_commands[0]
    fixed_session_arg = f"--user-data-dir={tmp_path / 'browser-sessions' / 'account-5'}"
    assert fixed_session_arg not in command

