from __future__ import annotations

from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect

from app_backend.main import create_app
from app_backend.infrastructure.db.base import build_engine


async def test_health_endpoint_allows_localhost_vite_origin(tmp_path: Path):
    app = create_app(db_path=tmp_path / "desktop-web.db")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["vary"] == "Origin"


async def test_health_endpoint_allows_null_origin_for_file_scheme(tmp_path: Path):
    app = create_app(db_path=tmp_path / "desktop-web.db")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={"Origin": "null"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "null"
    assert response.headers["vary"] == "Origin"


async def test_health_preflight_allows_local_127_origin(tmp_path: Path):
    app = create_app(db_path=tmp_path / "desktop-web.db")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:4173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_create_app_keeps_account_center_services_wired(tmp_path: Path):
    app = create_app(db_path=tmp_path / "desktop-web.db")

    assert app.state.account_repository is not None
    assert app.state.program_access_gateway is not None
    assert app.state.purchase_runtime_service is not None
    assert app.state.query_runtime_service is not None
    assert app.state.purchase_ui_preferences_repository is not None
    assert app.state.stats_repository is not None
    assert app.state.stats_pipeline is not None
    assert getattr(app.state.purchase_runtime_service._stats_sink, "__self__", None) is app.state.stats_pipeline
    assert getattr(app.state.purchase_runtime_service._stats_sink, "__name__", "") == "enqueue"
    assert app.state.purchase_runtime_service._settings_repository is app.state.runtime_settings_repository
    assert getattr(app.state.query_runtime_service._stats_sink, "__self__", None) is app.state.stats_pipeline
    assert getattr(app.state.query_runtime_service._stats_sink, "__name__", "") == "enqueue"


def test_create_app_packaged_release_wires_remote_program_access_services(tmp_path: Path):
    app = create_app(
        db_path=tmp_path / "desktop-web.db",
        program_access_stage="packaged_release",
        program_access_app_data_root=tmp_path / "program-access-data",
        program_access_secret_stage="local_dev",
        program_access_control_plane_base_url="http://8.138.39.139:18787",
        program_access_start_refresh_scheduler=False,
    )

    summary = app.state.program_access_gateway.get_summary()

    assert summary.mode == "remote_entitlement"
    assert summary.stage == "packaged_release"
    assert summary.guard_enabled is True
    assert summary.last_error_code == "program_auth_required"
    assert app.state.program_access_credential_store is not None
    assert app.state.program_access_secret_store is not None
    assert app.state.program_access_device_id_store is not None
    assert app.state.program_access_refresh_scheduler is not None


def test_create_app_creates_stats_and_ui_preference_tables(tmp_path: Path):
    db_path = tmp_path / "desktop-web.db"
    create_app(db_path=db_path)
    engine = build_engine(db_path)
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())

    assert "purchase_ui_preferences" in table_names
    assert "runtime_settings" in table_names
    assert "query_item_stats_total" in table_names
    assert "query_item_stats_daily" in table_names
    assert "query_matched_products" in table_names
    assert "query_item_rule_stats_total" in table_names
    assert "query_item_rule_stats_daily" in table_names
    assert "account_capability_stats_total" in table_names
    assert "account_capability_stats_daily" in table_names
