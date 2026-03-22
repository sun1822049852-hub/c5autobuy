from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_run_app_delegates_to_desktop_launcher(monkeypatch, tmp_path):
    import run_app

    launcher = tmp_path / "main_ui_account_center_desktop.js"
    launcher.write_text("// stub", encoding="utf-8")
    captured: dict[str, object] = {}

    def _fake_launch_desktop(node_executable: str) -> int:
        captured["node_executable"] = node_executable
        return 7

    monkeypatch.setattr(run_app, "DESKTOP_LAUNCHER", launcher)
    monkeypatch.setattr(run_app, "resolve_node_executable", lambda: "node.exe")
    monkeypatch.setattr(run_app, "launch_desktop", _fake_launch_desktop)

    assert run_app.main() == 7
    assert captured == {"node_executable": "node.exe"}


def test_run_app_source_has_no_c5_layered_reference():
    content = (PROJECT_ROOT / "run_app.py").read_text(encoding="utf-8")

    assert "c5_layered" not in content
    assert "app_frontend" not in content


def test_run_app_returns_error_when_node_is_missing(monkeypatch, tmp_path, capsys):
    import run_app

    launcher = tmp_path / "main_ui_account_center_desktop.js"
    launcher.write_text("// stub", encoding="utf-8")

    monkeypatch.setattr(run_app, "DESKTOP_LAUNCHER", launcher)
    monkeypatch.setattr(run_app, "resolve_node_executable", lambda: None)

    assert run_app.main() == 1
    assert "Node.js" in capsys.readouterr().err
