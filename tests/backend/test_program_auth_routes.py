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
        "registration_flow_version": 2,
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
        verify_register_code_response = await client.post(
            "/program-auth/register/verify-code",
            json={
                "email": "alice@example.com",
                "code": "123456",
                "register_session_id": "register_session_1",
            },
        )
        complete_register_response = await client.post(
            "/program-auth/register/complete",
            json={
                "email": "alice@example.com",
                "verification_ticket": "ticket_1",
                "username": "alice",
                "password": "Secret123!",
            },
        )
        legacy_register_response = await client.post(
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
    assert verify_register_code_response.status_code == 200
    assert verify_register_code_response.json() == {
        "ok": True,
        "message": "验证码已验证",
        "summary": expected_summary,
    }
    assert complete_register_response.status_code == 200
    assert complete_register_response.json() == {
        "ok": True,
        "message": "账号已创建，但当前未开通会员",
        "summary": expected_summary,
    }
    assert legacy_register_response.status_code in {404, 405}
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


@pytest.mark.parametrize(
    ("stub_field", "path", "request_payload", "error_code", "error_message", "status_code", "action"),
    [
        (
            "complete_register_result",
            "/program-auth/register/complete",
            {
                "email": "alice@example.com",
                "verification_ticket": "ticket_1",
                "username": "alice",
                "password": "Secret123!",
            },
            "REGISTER_USERNAME_TAKEN",
            "用户名已被占用",
            409,
            "program-auth.register.complete",
        ),
        (
            "complete_register_result",
            "/program-auth/register/complete",
            {
                "email": "alice@example.com",
                "verification_ticket": "ticket_1",
                "username": "alice",
                "password": "Secret123!",
            },
            "REGISTER_EMAIL_UNAVAILABLE",
            "邮箱暂不可用",
            409,
            "program-auth.register.complete",
        ),
        (
            "login_result",
            "/program-auth/login",
            {
                "username": "alice",
                "password": "Secret123!",
            },
            "login_locked",
            "登录尝试过多，请稍后重试",
            429,
            "program-auth.login",
        ),
        (
            "reset_password_result",
            "/program-auth/password/reset",
            {
                "email": "alice@example.com",
                "code": "654321",
                "new_password": "NewSecret456!",
            },
            "code_verify_locked",
            "验证码校验已锁定",
            429,
            "program-auth.password.reset",
        ),
        (
            "complete_register_result",
            "/program-auth/register/complete",
            {
                "email": "alice@example.com",
                "verification_ticket": "ticket_1",
                "username": "alice",
                "password": "Secret123!",
            },
            "device_mismatch",
            "设备不匹配",
            409,
            "program-auth.register.complete",
        ),
    ],
)
async def test_program_auth_routes_map_focused_register_v3_error_statuses(
    tmp_path: Path,
    stub_field: str,
    path: str,
    request_payload: dict[str, str],
    error_code: str,
    error_message: str,
    status_code: int,
    action: str,
) -> None:
    reject_result = ProgramAccessActionResult.reject(
        summary=_base_packaged_summary(),
        code=error_code,
        message=error_message,
    )
    gateway = _StubProgramAccessGateway(**{stub_field: reject_result})
    app = _create_packaged_release_app(tmp_path, gateway)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json=request_payload)

    assert response.status_code == status_code
    assert response.json() == {
        "detail": {
            "code": error_code,
            "message": error_message,
            "action": action,
        }
    }


async def test_program_auth_send_register_code_returns_retry_after_seconds_error_detail(tmp_path: Path) -> None:
    gateway = _StubProgramAccessGateway(
        send_register_code_result=ProgramAccessActionResult.reject(
            summary=_base_packaged_summary(),
            code="REGISTER_SEND_RETRY_LATER",
            message="register send is cooling down",
            payload={"retry_after_seconds": 52},
        )
    )
    app = _create_packaged_release_app(tmp_path, gateway)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/program-auth/register/send-code",
            json={"email": "alice@example.com"},
        )

    assert response.status_code == 429
    assert response.json() == {
        "detail": {
            "code": "REGISTER_SEND_RETRY_LATER",
            "message": "register send is cooling down",
            "action": "program-auth.register.send-code",
            "retry_after_seconds": 52,
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
    payload = {
        "mode": summary.mode,
        "stage": summary.stage,
        "guard_enabled": summary.guard_enabled,
        "message": summary.message,
        "registration_flow_version": summary.registration_flow_version,
        "username": summary.username,
        "auth_state": summary.auth_state,
        "runtime_state": summary.runtime_state,
        "grace_expires_at": summary.grace_expires_at,
        "last_error_code": summary.last_error_code,
    }
    return {key: value for key, value in payload.items() if value is not None}


@dataclass
class _StubProgramAccessGateway:
    login_result: ProgramAccessActionResult | None = None
    logout_result: ProgramAccessActionResult | None = None
    send_register_code_result: ProgramAccessActionResult | None = None
    register_result: ProgramAccessActionResult | None = None
    verify_register_code_result: ProgramAccessActionResult | None = None
    complete_register_result: ProgramAccessActionResult | None = None
    reset_password_result: ProgramAccessActionResult | None = None

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
        if self.send_register_code_result is not None:
            return self.send_register_code_result
        return ProgramAccessActionResult(
            accepted=True,
            summary=self.summary,
            message="注册验证码已发送",
        )

    def verify_register_code(
        self,
        *,
        email: str,
        code: str,
        register_session_id: str,
    ) -> ProgramAccessActionResult:
        _ = email
        _ = code
        _ = register_session_id
        if self.verify_register_code_result is not None:
            return self.verify_register_code_result
        return ProgramAccessActionResult(
            accepted=True,
            summary=self.summary,
            message="验证码已验证",
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

    def complete_register(
        self,
        *,
        email: str,
        verification_ticket: str,
        username: str,
        password: str,
    ) -> ProgramAccessActionResult:
        _ = email
        _ = verification_ticket
        _ = username
        _ = password
        if self.complete_register_result is not None:
            return self.complete_register_result
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
        if self.reset_password_result is not None:
            return self.reset_password_result
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
        registration_flow_version=3,
        username=None,
        auth_state=None,
        runtime_state="stopped",
        grace_expires_at=None,
        last_error_code="program_auth_required",
    )
