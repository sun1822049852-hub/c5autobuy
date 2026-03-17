from __future__ import annotations

from pathlib import Path


def test_backend_main_runs_uvicorn(monkeypatch, tmp_path: Path):
    import app_backend.main as backend_main

    called: dict[str, object] = {}

    def fake_run(app, host: str, port: int, log_level: str):
        called["app"] = app
        called["host"] = host
        called["port"] = port
        called["log_level"] = log_level

    monkeypatch.setattr(backend_main.uvicorn, "run", fake_run)

    backend_main.main(db_path=tmp_path / "entry.db", host="127.0.0.1", port=8133)

    assert called["host"] == "127.0.0.1"
    assert called["port"] == 8133
    assert called["log_level"] == "info"
