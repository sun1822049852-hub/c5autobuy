from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app_backend.main import create_app


@pytest.fixture
def app(tmp_path: Path):
    return create_app(db_path=tmp_path / "app.db")


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
