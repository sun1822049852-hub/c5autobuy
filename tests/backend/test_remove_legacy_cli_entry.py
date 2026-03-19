from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_run_app_delegates_to_frontend_main(monkeypatch):
    import run_app

    captured: dict[str, object] = {}

    def _fake_frontend_main() -> int:
        captured["called"] = True
        return 7

    monkeypatch.setattr(run_app, "run_frontend_main", _fake_frontend_main)

    assert run_app.main() == 7
    assert captured == {"called": True}


def test_run_app_source_has_no_c5_layered_reference():
    content = (PROJECT_ROOT / "run_app.py").read_text(encoding="utf-8")

    assert "c5_layered" not in content
