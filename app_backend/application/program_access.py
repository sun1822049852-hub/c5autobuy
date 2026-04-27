from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

LOCAL_PASS_THROUGH_MESSAGE = "当前为本地放行模式，远端程序会员控制面尚未接入正式链路"
PROGRAM_ACCESS_UNLOCKED_MESSAGE = "当前程序会员权限有效"
PROGRAM_AUTH_REQUIRED_MESSAGE = "请先登录程序会员"
PROGRAM_FEATURE_NOT_ENABLED_MESSAGE = "当前套餐暂未开放该功能"
ACCOUNT_BROWSER_QUERY_ENABLE_ACTION = "account.browser_query.enable"
PROGRAM_BROWSER_QUERY_ENABLE_NOT_OPEN_MESSAGE = "当前此功能未开放"
PROGRAM_PERMIT_DENIED_MESSAGE = "当前程序访问权限不足"
PROGRAM_REMOTE_UNAVAILABLE_MESSAGE = "程序会员服务暂不可用"
PROGRAM_SNAPSHOT_INVALID_MESSAGE = "程序会员授权已失效，请重新登录"
PROGRAM_REFRESH_FAILED_MESSAGE = "程序会员刷新失败"
PROGRAM_REGISTERED_BUT_NOT_MEMBER_MESSAGE = "账号已创建，但当前未开通会员"

PROGRAM_AUTH_NOT_READY_CODE = "program_auth_not_ready"
PROGRAM_AUTH_REQUIRED_CODE = "program_auth_required"
PROGRAM_FEATURE_NOT_ENABLED_CODE = "program_feature_not_enabled"
PROGRAM_PERMIT_DENIED_CODE = "program_permit_denied"
PROGRAM_REMOTE_UNAVAILABLE_CODE = "program_remote_unavailable"
PROGRAM_SNAPSHOT_INVALID_CODE = "program_snapshot_invalid"
PROGRAM_REFRESH_FAILED_CODE = "program_refresh_failed"


@dataclass(frozen=True)
class ProgramAccessSummary:
    mode: str
    stage: str
    guard_enabled: bool
    message: str
    registration_flow_version: int = 2
    username: str | None = None
    auth_state: str | None = None
    runtime_state: str | None = None
    grace_expires_at: str | None = None
    last_error_code: str | None = None


@dataclass(frozen=True)
class ProgramAccessDecision:
    allowed: bool
    code: str | None = None
    message: str | None = None

    @classmethod
    def allow(cls) -> ProgramAccessDecision:
        return cls(allowed=True)

    @classmethod
    def deny(cls, *, code: str, message: str) -> ProgramAccessDecision:
        return cls(allowed=False, code=code, message=message)


@dataclass(frozen=True)
class ProgramAccessActionResult:
    accepted: bool
    summary: ProgramAccessSummary
    code: str | None = None
    message: str | None = None
    payload: dict[str, object] | None = None

    @classmethod
    def accept(
        cls,
        *,
        summary: ProgramAccessSummary,
        message: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> ProgramAccessActionResult:
        return cls(accepted=True, summary=summary, message=message, payload=payload)

    @classmethod
    def reject(
        cls,
        *,
        summary: ProgramAccessSummary,
        code: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> ProgramAccessActionResult:
        return cls(accepted=False, summary=summary, code=code, message=message, payload=payload)


class ProgramAccessGateway(Protocol):
    def get_summary(self) -> ProgramAccessSummary: ...

    def get_auth_status(self) -> ProgramAccessSummary: ...

    def guard(self, action: str) -> ProgramAccessDecision: ...

    def login(self, *, username: str, password: str) -> ProgramAccessActionResult: ...

    def logout(self) -> ProgramAccessActionResult: ...

    def send_register_code(self, email: str) -> ProgramAccessActionResult: ...

    def verify_register_code(
        self,
        *,
        email: str,
        code: str,
        register_session_id: str,
    ) -> ProgramAccessActionResult: ...

    def complete_register(
        self,
        *,
        email: str,
        verification_ticket: str,
        username: str,
        password: str,
    ) -> ProgramAccessActionResult: ...

    def send_reset_code(self, email: str) -> ProgramAccessActionResult: ...

    def reset_password(
        self,
        *,
        email: str,
        code: str,
        new_password: str,
    ) -> ProgramAccessActionResult: ...

    def refresh(self, *, reason: str) -> ProgramAccessActionResult: ...
