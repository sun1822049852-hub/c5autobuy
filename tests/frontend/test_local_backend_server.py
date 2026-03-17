from __future__ import annotations

import httpx


def test_local_backend_server_exposes_health_endpoint(tmp_path):
    from app_frontend.app.services.local_backend_server import LocalBackendServer

    server = LocalBackendServer(db_path=tmp_path / "app.db")
    server.start()

    try:
        response = httpx.get(f"{server.base_url}/health", timeout=5.0)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        server.stop()
