from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_run_app_delegates_to_desktop_launcher(monkeypatch, tmp_path):
    import run_app

    captured: dict[str, object] = {}
    launcher_path = tmp_path / "main_ui_account_center_desktop.js"
    launcher_path.write_text("// launcher", encoding="utf-8")

    def _fake_resolve_node_executable() -> str:
        captured["resolved"] = True
        return "node.exe"

    def _fake_launch_desktop(node_executable: str, launcher_path: Path | None = None) -> int:
        captured["node_executable"] = node_executable
        captured["launcher_path"] = launcher_path
        return 7

    monkeypatch.setattr(run_app, "DESKTOP_LAUNCHER", launcher_path)
    monkeypatch.setattr(run_app, "resolve_node_executable", _fake_resolve_node_executable)
    monkeypatch.setattr(run_app, "launch_desktop", _fake_launch_desktop)

    assert run_app.main() == 7
    assert captured == {
        "resolved": True,
        "node_executable": "node.exe",
        "launcher_path": None,
    }


def test_run_app_source_has_no_c5_layered_reference():
    content = (PROJECT_ROOT / "run_app.py").read_text(encoding="utf-8")

    assert "c5_layered" not in content
