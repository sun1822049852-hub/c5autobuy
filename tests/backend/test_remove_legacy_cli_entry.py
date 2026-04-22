from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_python_wrapper_entrypoints_are_removed():
    assert not (PROJECT_ROOT / "run_app.py").exists()
    assert not (PROJECT_ROOT / "run_app_local_debug.py").exists()


def test_readme_only_documents_js_entrypoints():
    content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "python run_app.py" not in content
    assert "python run_app_local_debug.py" not in content
    assert "python -m app_backend.main" not in content
    assert "node main_ui_node_desktop.js" in content
    assert "node main_ui_node_desktop_local_debug.js" in content


def test_backend_main_has_no_direct_python_cli_guard():
    content = (PROJECT_ROOT / "app_backend/main.py").read_text(encoding="utf-8")

    assert 'if __name__ == "__main__"' not in content


def test_superpowers_readme_describes_js_only_public_entry():
    content = (PROJECT_ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")

    assert "run_app.py" not in content
    assert "run_app_local_debug.py" not in content
    assert "main_ui_node_desktop.js" in content
