from __future__ import annotations

from pathlib import Path
import shutil

import certifi
import pytest
from httpx import ASGITransport, AsyncClient

from app_backend.main import create_app


class DenyGateway:
    def __init__(self, *, code: str, message: str) -> None:
        self._code = code
        self._message = message

    def guard(self, action: str):
        _ = action
        return type(
            "Decision",
            (),
            {
                "allowed": False,
                "code": self._code,
                "message": self._message,
            },
        )()


async def _create_query_config(client: AsyncClient, *, name: str) -> str:
    response = await client.post(
        "/query-configs",
        json={
            "name": name,
            "description": f"{name} 描述",
        },
    )
    assert response.status_code == 201
    return response.json()["config_id"]


@pytest.mark.parametrize(
    ("path", "action"),
    [
        ("/query-runtime/start", "runtime.start"),
        ("/purchase-runtime/start", "runtime.start"),
    ],
)
async def test_runtime_start_routes_return_guard_error_when_program_access_denies(client, app, path: str, action: str):
    app.state.program_access_gateway = DenyGateway(
        code="program_auth_required",
        message="请先登录程序会员",
    )
    config_id = await _create_query_config(client, name="受控配置")

    response = await client.post(path, json={"config_id": config_id})

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "code": "program_auth_required",
        "message": "请先登录程序会员",
        "action": action,
    }


async def test_packaged_release_runtime_start_routes_require_cached_program_auth(tmp_path: Path):
    control_plane_ca_cert_path = tmp_path / "control_plane_ca.pem"
    shutil.copyfile(certifi.where(), control_plane_ca_cert_path)
    app = create_app(
        db_path=tmp_path / "desktop-web.db",
        program_access_stage="packaged_release",
        program_access_app_data_root=tmp_path / "program-access-data",
        program_access_secret_stage="local_dev",
        program_access_control_plane_base_url="https://8.138.39.139",
        program_access_control_plane_ca_cert_path=control_plane_ca_cert_path,
        program_access_start_refresh_scheduler=False,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        config_id = await _create_query_config(client, name="受控配置")
        query_response = await client.post("/query-runtime/start", json={"config_id": config_id})
        purchase_response = await client.post("/purchase-runtime/start", json={"config_id": config_id})

    expected_detail = {
        "code": "program_auth_required",
        "message": "请先登录程序会员",
        "action": "runtime.start",
    }
    assert query_response.status_code == 401
    assert query_response.json()["detail"] == expected_detail
    assert purchase_response.status_code == 401
    assert purchase_response.json()["detail"] == expected_detail
