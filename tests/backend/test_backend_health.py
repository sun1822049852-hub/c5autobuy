import time

from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient

from app_backend.main import create_app


async def test_health_endpoint():
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ready"] is True


def test_deferred_health_eventually_becomes_ready_without_init_error(tmp_path):
    app = create_app(
        db_path=tmp_path / "deferred.db",
        deferred_init=True,
        program_access_start_refresh_scheduler=False,
    )

    with TestClient(app) as client:
        deadline = time.monotonic() + 5
        payload = None

        while time.monotonic() < deadline:
            response = client.get("/health")
            payload = response.json()
            assert payload["status"] != "error"
            if payload["ready"] is True:
                break
            time.sleep(0.05)

        assert payload is not None
        assert payload["status"] == "ok"
        assert payload["ready"] is True

        bootstrap_response = client.get("/app/bootstrap")
        assert bootstrap_response.status_code == 200
