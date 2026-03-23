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
    assert app.state.purchase_runtime_service is not None
    assert app.state.query_runtime_service is not None


def test_create_app_bootstraps_runtime_settings_table(tmp_path: Path):
    db_path = tmp_path / "desktop-web.db"

    create_app(db_path=db_path)
    inspector = inspect(build_engine(db_path))

    assert "runtime_settings" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns("runtime_settings")} == {
        "settings_id",
        "query_settings_json",
        "purchase_settings_json",
        "updated_at",
    }
