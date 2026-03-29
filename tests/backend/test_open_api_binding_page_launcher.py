from __future__ import annotations

from pathlib import Path


class _RelativeRuntime:
    def resolve_browser_executable(self) -> Path:
        return Path("data/app-private/browser-runtime/Application/msedge.exe")


class _FakeProcess:
    def __init__(self) -> None:
        self._poll_result = None

    def poll(self):
        return self._poll_result

    def kill(self):
        self._poll_result = 0


class _FakeProfileStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.clone_calls: list[str] = []
        self.persist_calls: list[tuple[str, str]] = []

    def clone_session(self, account_id: str) -> Path:
        self.clone_calls.append(account_id)
        session_root = self.root / f"account-{account_id}"
        session_root.mkdir(parents=True, exist_ok=True)
        return session_root

    def persist_session(self, account_id: str, session_root: Path) -> Path:
        self.persist_calls.append((account_id, str(session_root)))
        return self.root / f"profile-{account_id}"


class _ImmediateThread:
    def __init__(self, *, target, name=None, daemon=None) -> None:
        self._target = target

    def start(self) -> None:
        self._target()


class _SequenceProcess:
    def __init__(self, poll_results: list[int | None]) -> None:
        self._poll_results = list(poll_results)

    def poll(self):
        if len(self._poll_results) > 1:
            return self._poll_results.pop(0)
        return self._poll_results[0]

    def kill(self):
        self._poll_results = [0]


def test_open_api_binding_page_launcher_uses_absolute_launch_paths(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher import (
        OpenApiBindingPageLauncher,
    )

    monkeypatch.chdir(tmp_path)
    launcher = OpenApiBindingPageLauncher(runtime=_RelativeRuntime())
    process = _FakeProcess()
    captured_commands: list[list[str]] = []

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.reserve_debug_port",
        lambda: 9771,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.subprocess.Popen",
        lambda command: captured_commands.append(command) or process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.OpenApiBindingPageLauncher._schedule_cleanup",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.OpenApiBindingPageLauncher._schedule_watch",
        lambda *args, **kwargs: None,
    )

    launcher.launch(
        profile_root="data/app-private/browser-sessions/account-1",
        profile_directory="Default",
        proxy_url=None,
    )

    command = captured_commands[0]
    assert command[0] == str(
        (tmp_path / "data" / "app-private" / "browser-runtime" / "Application" / "msedge.exe").resolve()
    )
    assert f"--user-data-dir={(tmp_path / 'data' / 'app-private' / 'browser-sessions' / 'account-1').resolve()}" in command


def test_open_api_binding_page_launcher_reuses_existing_live_launch_for_same_account(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher import (
        OpenApiBindingPageLauncher,
    )

    monkeypatch.chdir(tmp_path)
    profile_store = _FakeProfileStore(tmp_path / "profiles")
    launcher = OpenApiBindingPageLauncher(runtime=_RelativeRuntime(), profile_store=profile_store)
    process = _FakeProcess()
    captured_commands: list[list[str]] = []

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.reserve_debug_port",
        lambda: 9771,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.subprocess.Popen",
        lambda command: captured_commands.append(command) or process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.OpenApiBindingPageLauncher._schedule_cleanup",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.OpenApiBindingPageLauncher._schedule_watch",
        lambda *args, **kwargs: None,
    )

    first = launcher.launch(
        account_id="a-1",
        profile_root="data/app-private/browser-sessions/account-1",
        profile_directory="Default",
        proxy_url=None,
    )
    second = launcher.launch(
        account_id="a-1",
        profile_root="data/app-private/browser-sessions/account-1",
        profile_directory="Default",
        proxy_url=None,
    )

    assert first == second
    assert len(captured_commands) == 1
    assert profile_store.clone_calls == ["a-1"]


def test_open_api_binding_page_launcher_relaunches_after_previous_process_exits(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher import (
        OpenApiBindingPageLauncher,
    )

    monkeypatch.chdir(tmp_path)
    profile_store = _FakeProfileStore(tmp_path / "profiles")
    launcher = OpenApiBindingPageLauncher(runtime=_RelativeRuntime(), profile_store=profile_store)
    processes = [_FakeProcess(), _FakeProcess()]
    captured_commands: list[list[str]] = []
    ports = iter([9771, 9772])

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.reserve_debug_port",
        lambda: next(ports),
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.subprocess.Popen",
        lambda command: captured_commands.append(command) or processes[len(captured_commands) - 1],
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.OpenApiBindingPageLauncher._schedule_cleanup",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.OpenApiBindingPageLauncher._schedule_watch",
        lambda *args, **kwargs: None,
    )

    first = launcher.launch(
        account_id="a-1",
        profile_root="data/app-private/browser-sessions/account-1",
        profile_directory="Default",
        proxy_url=None,
    )
    processes[0].kill()
    second = launcher.launch(
        account_id="a-1",
        profile_root="data/app-private/browser-sessions/account-1",
        profile_directory="Default",
        proxy_url=None,
    )

    assert first["debugger_address"] == "127.0.0.1:9771"
    assert second["debugger_address"] == "127.0.0.1:9772"
    assert len(captured_commands) == 2
    assert profile_store.clone_calls == ["a-1", "a-1"]


def test_open_api_binding_page_launcher_skips_persist_for_login_redirected_session(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher import (
        OpenApiBindingPageLauncher,
    )

    monkeypatch.chdir(tmp_path)
    profile_store = _FakeProfileStore(tmp_path / "profiles")
    launcher = OpenApiBindingPageLauncher(runtime=_RelativeRuntime(), profile_store=profile_store)
    process = _SequenceProcess([None, 0])

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.reserve_debug_port",
        lambda: 9771,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.wait_for_debugger_port",
        lambda port, process: None,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.subprocess.Popen",
        lambda command: process,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.threading.Thread",
        _ImmediateThread,
    )
    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher.read_attached_session",
        lambda debugger_address: {
            "target_url": "https://www.c5game.com/login",
            "cookie_raw": "",
        },
        raising=False,
    )

    launcher.launch(
        account_id="a-1",
        profile_root="data/app-private/browser-sessions/account-1",
        profile_directory="Default",
        proxy_url=None,
    )

    assert profile_store.persist_calls == []
