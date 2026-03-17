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


def test_create_app_wires_selenium_login_adapter(tmp_path: Path):
    from app_backend.main import create_app
    from app_backend.infrastructure.selenium.login_adapter import SeleniumLoginAdapter

    app = create_app(db_path=tmp_path / "entry.db")

    assert isinstance(app.state.login_adapter, SeleniumLoginAdapter)


def test_create_app_wires_real_product_detail_fetcher(tmp_path: Path):
    from app_backend.main import create_app
    from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetailCollector, _missing_fetcher
    from app_backend.infrastructure.query.collectors.product_detail_fetcher import ProductDetailFetcher

    app = create_app(db_path=tmp_path / "entry.db")
    collector = app.state.product_detail_collector

    assert isinstance(collector, ProductDetailCollector)
    assert collector._fetcher is not _missing_fetcher
    assert isinstance(getattr(collector._fetcher, "__self__", None), ProductDetailFetcher)


def test_create_app_wires_prepare_service_with_shared_product_detail_collector(tmp_path: Path):
    from app_backend.main import create_app

    app = create_app(db_path=tmp_path / "entry.db")

    assert app.state.query_item_detail_refresh_service._collector is app.state.product_detail_collector
