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
