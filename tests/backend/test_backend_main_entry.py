from __future__ import annotations

from pathlib import Path
import sys


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


def test_backend_main_default_app_is_built_lazily(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("app_backend.main", None)

    import app_backend.main as backend_main

    fake_app = object()
    called: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_create_app(*args, **kwargs):
        called.append((args, kwargs))
        return fake_app

    monkeypatch.setattr(backend_main, "create_app", fake_create_app)

    assert called == []
    assert backend_main.app is fake_app
    assert called == [((), {})]
    assert backend_main.app is fake_app
    assert called == [((), {})]


def test_create_app_wires_browser_login_adapter(tmp_path: Path):
    from app_backend.main import create_app
    from app_backend.infrastructure.repositories.account_session_bundle_repository import (
        SqliteAccountSessionBundleRepository,
    )
    from app_backend.infrastructure.browser_runtime.login_adapter import (
        ManagedEdgeCdpLoginRunner,
        BrowserLoginAdapter,
    )

    app = create_app(db_path=tmp_path / "entry.db")

    assert isinstance(app.state.login_adapter, BrowserLoginAdapter)
    assert isinstance(getattr(app.state.login_adapter._login_runner, "__self__", None), ManagedEdgeCdpLoginRunner)
    assert isinstance(app.state.account_session_bundle_repository, SqliteAccountSessionBundleRepository)


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

def test_managed_browser_runtime_uses_app_private_env_layout(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    app_private_dir = tmp_path / "app-private"
    monkeypatch.setenv("C5_APP_PRIVATE_DIR", str(app_private_dir))

    runtime = ManagedBrowserRuntime.from_environment()

    assert runtime.app_private_dir == app_private_dir
    assert runtime.bundle_root == app_private_dir / "account-session-bundles"
    assert runtime.runtime_root == app_private_dir / "browser-runtime"
    assert runtime.session_root == app_private_dir / "browser-sessions"

