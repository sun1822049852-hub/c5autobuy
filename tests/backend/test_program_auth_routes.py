from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app_backend.application.program_access import (
    ProgramAccessActionResult,
    ProgramAccessSummary,
)
from app_backend.main import create_app


async def test_program_auth_status_returns_local_pass_through_summary(client) -> None:
    response = await client.get("/program-auth/status")

    assert response.status_code == 200
    assert response.json() == {
        "mode": "local_pass_through",
        "stage": "prepackaging",
        "guard_enabled": False,
        "message": "当前为本地放行模式，远端程序会员控制面尚未接入正式链路",
        "username": None,
        "auth_state": None,
        "runtime_state": None,
        "grace_expires_at": None,
        "last_error_code": None,
    }


async def test_program_auth_login_returns_structured_not_ready_error(client) -> None:
    response = await client.post(
        "/program-auth/login",
        json={
            "username": "alice",
            "password": "Secret123!",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "program_auth_not_ready",
            "message": "当前为本地放行模式，远端程序会员控制面尚未接入正式链路",
            "action": "program-auth.login",
        }
    }


async def test_program_auth_register_and_password_routes_accept_with_stubbed_packaged_gateway(
    tmp_path: Path,
) -> None:
    gateway = _StubProgramAccessGateway()
    app = _create_packaged_release_app(tmp_path, gateway)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        send_register_code_response = await client.post(
            "/program-auth/register/send-code",
            json={"email": "alice@example.com"},
        )
        register_response = await client.post(
            "/program-auth/register",
            json={
                "email": "alice@example.com",
                "code": "123456",
                "username": "alice",
                "password": "Secret123!",
            },
        )
        send_reset_code_response = await client.post(
            "/program-auth/password/send-reset-code",
            json={"email": "alice@example.com"},
        )
        reset_password_response = await client.post(
            "/program-auth/password/reset",
            json={
                "email": "alice@example.com",
                "code": "654321",
                "new_password": "NewSecret456!",
            },
        )

    expected_summary = _summary_dict(gateway.summary)
    assert send_register_code_response.status_code == 200
    assert send_register_code_response.json() == {
        "ok": True,
        "message": "注册验证码已发送",
        "summary": expected_summary,
    }
    assert register_response.status_code == 200
    assert register_response.json() == {
        "ok": True,
        "message": "账号已创建，但当前未开通会员",
        "summary": expected_summary,
    }
    assert send_reset_code_response.status_code == 200
    assert send_reset_code_response.json() == {
        "ok": True,
        "message": "密码重置验证码已发送",
        "summary": expected_summary,
    }
    assert reset_password_response.status_code == 200
    assert reset_password_response.json() == {
        "ok": True,
        "message": "密码已重置",
        "summary": expected_summary,
    }


async def test_program_auth_register_returns_structured_conflict_error(tmp_path: Path) -> None:
    summary = ProgramAccessSummary(
        mode="remote_entitlement",
        stage="packaged_release",
        guard_enabled=True,
        message="请先登录程序会员",
        auth_state=None,
        runtime_state="stopped",
        grace_expires_at=None,
        last_error_code="program_auth_required",
    )
    gateway = _StubProgramAccessGateway(
        register_result=ProgramAccessActionResult.reject(
            summary=summary,
            code="user_already_exists",
            message="用户已存在",
        )
    )
    app = _create_packaged_release_app(tmp_path, gateway)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/program-auth/register",
            json={
                "email": "alice@example.com",
                "code": "123456",
                "username": "alice",
                "password": "Secret123!",
            },
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "user_already_exists",
            "message": "用户已存在",
            "action": "program-auth.register",
        }
    }


async def test_program_auth_login_and_logout_accept_with_stubbed_packaged_gateway(tmp_path: Path) -> None:
    gateway = _StubProgramAccessGateway()
    app = _create_packaged_release_app(tmp_path, gateway)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_response = await client.post(
            "/program-auth/login",
            json={
                "username": "alice",
                "password": "Secret123!",
            },
        )
        logout_response = await client.post("/program-auth/logout")

    expected_summary = _summary_dict(gateway.summary)
    assert login_response.status_code == 200
    assert login_response.json() == {
        "ok": True,
        "message": "登录成功",
        "summary": expected_summary,
    }
    assert logout_response.status_code == 200
    assert logout_response.json() == {
        "ok": True,
        "message": "已退出登录",
        "summary": expected_summary,
    }


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("rate_limited", 429),
        ("device_conflict", 409),
        ("refresh_credential_invalid", 401),
        ("unauthorized", 401),
        ("membership_expired", 403),
        ("membership_revoked", 403),
        ("service_unavailable", 503),
    ],
)
async def test_program_auth_logout_maps_extended_remote_status_codes(
    tmp_path: Path,
    code: str,
    status_code: int,
) -> None:
    gateway = _StubProgramAccessGateway(
        logout_result=ProgramAccessActionResult.reject(
            summary=_base_packaged_summary(),
            code=code,
            message="控制面拒绝退出",
        )
    )
    app = _create_packaged_release_app(tmp_path, gateway)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/program-auth/logout")

    assert response.status_code == status_code
    assert response.json() == {
        "detail": {
            "code": code,
            "message": "控制面拒绝退出",
            "action": "program-auth.logout",
        }
    }


def _create_packaged_release_app(
    tmp_path: Path,
    gateway: "_StubProgramAccessGateway",
):
    app = create_app(db_path=tmp_path / "app.db")
    app.state.program_access_stage = "packaged_release"
    app.state.program_access_gateway = gateway
    return app


def _summary_dict(summary: ProgramAccessSummary) -> dict[str, object]:
    return {
        "mode": summary.mode,
        "stage": summary.stage,
        "guard_enabled": summary.guard_enabled,
        "message": summary.message,
        "username": summary.username,
        "auth_state": summary.auth_state,
        "runtime_state": summary.runtime_state,
        "grace_expires_at": summary.grace_expires_at,
        "last_error_code": summary.last_error_code,
    }


@dataclass
class _StubProgramAccessGateway:
    login_result: ProgramAccessActionResult | None = None
    logout_result: ProgramAccessActionResult | None = None
    register_result: ProgramAccessActionResult | None = None

    def __post_init__(self) -> None:
        self.summary = _base_packaged_summary()

    def get_summary(self) -> ProgramAccessSummary:
        return self.summary

    def get_auth_status(self) -> ProgramAccessSummary:
        return self.summary

    def guard(self, action: str):  # pragma: no cover - route tests don't use guard here.
        _ = action
        raise AssertionError("guard should not be called in program-auth route tests")

    def login(self, *, username: str, password: str) -> ProgramAccessActionResult:
        _ = username
        _ = password
        if self.login_result is not None:
            return self.login_result
        return ProgramAccessActionResult(
            accepted=True,
            summary=self.summary,
            message="登录成功",
        )

    def logout(self) -> ProgramAccessActionResult:
        if self.logout_result is not None:
            return self.logout_result
        return ProgramAccessActionResult(
            accepted=True,
            summary=self.summary,
            message="已退出登录",
        )

    def send_register_code(self, email: str) -> ProgramAccessActionResult:
        _ = email
        return ProgramAccessActionResult(
            accepted=True,
            summary=self.summary,
            message="注册验证码已发送",
        )

    def register(
        self,
        *,
        email: str,
        code: str,
        username: str,
        password: str,
    ) -> ProgramAccessActionResult:
        _ = email
        _ = code
        _ = username
        _ = password
        if self.register_result is not None:
            return self.register_result
        return ProgramAccessActionResult(
            accepted=True,
            summary=self.summary,
            message="账号已创建，但当前未开通会员",
        )

    def send_reset_code(self, email: str) -> ProgramAccessActionResult:
        _ = email
        return ProgramAccessActionResult(
            accepted=True,
            summary=self.summary,
            message="密码重置验证码已发送",
        )

    def reset_password(
        self,
        *,
        email: str,
        code: str,
        new_password: str,
    ) -> ProgramAccessActionResult:
        _ = email
        _ = code
        _ = new_password
        return ProgramAccessActionResult(
            accepted=True,
            summary=self.summary,
            message="密码已重置",
        )


def _base_packaged_summary() -> ProgramAccessSummary:
    return ProgramAccessSummary(
        mode="remote_entitlement",
        stage="packaged_release",
        guard_enabled=True,
        message="请先登录程序会员",
        username=None,
        auth_state=None,
        runtime_state="stopped",
        grace_expires_at=None,
        last_error_code="program_auth_required",
    )
