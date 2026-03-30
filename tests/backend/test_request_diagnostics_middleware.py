from __future__ import annotations

import asyncio
import json
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app_backend.main import create_app


async def test_request_diagnostics_logs_slow_requests(tmp_path: Path):
    log_path = tmp_path / "runtime" / "request_diagnostics.runtime.jsonl"
    app = create_app(
        db_path=tmp_path / "slow.db",
        request_diagnostics_log_path=log_path,
        request_diagnostics_slow_ms=0,
    )

    @app.get("/_slow-request")
    async def slow_request() -> dict[str, bool]:
        await asyncio.sleep(0.01)
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_slow-request")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert log_path.exists()

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records
    assert records[-1]["event"] == "slow_request"
    assert records[-1]["method"] == "GET"
    assert records[-1]["path"] == "/_slow-request"
    assert records[-1]["status_code"] == 200
    assert records[-1]["duration_ms"] >= 0


async def test_request_diagnostics_logs_exceptions(tmp_path: Path):
    log_path = tmp_path / "runtime" / "request_diagnostics.runtime.jsonl"
    app = create_app(
        db_path=tmp_path / "boom.db",
        request_diagnostics_log_path=log_path,
        request_diagnostics_slow_ms=60_000,
    )

    @app.get("/_boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_boom")

    assert response.status_code == 500
    assert log_path.exists()

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records
    assert records[-1]["event"] == "request_exception"
    assert records[-1]["method"] == "GET"
    assert records[-1]["path"] == "/_boom"
    assert records[-1]["error_type"] == "RuntimeError"
    assert records[-1]["error_message"] == "boom"
