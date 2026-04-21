from __future__ import annotations

from typing import Protocol

from app_backend.application.program_access import (
    PROGRAM_AUTH_NOT_READY_CODE,
    ProgramAccessActionResult,
    ProgramAccessDecision,
    ProgramAccessSummary,
)

from .program_credential_bundle import ProgramCredentialBundle


PROGRAM_AUTH_REQUIRED_MESSAGE = "请先登录程序会员"
PROGRAM_AUTH_REMOTE_NOT_READY_MESSAGE = "程序会员远端登录尚未接入"
PROGRAM_MEMBERSHIP_EXPIRED_MESSAGE = "当前程序会员已过期"
PROGRAM_DEVICE_CONFLICT_MESSAGE = "当前程序会员已在另一台设备登录"
PROGRAM_GRACE_LIMITED_MESSAGE = "当前处于宽限期，暂不允许新的关键动作"
PROGRAM_FEATURE_NOT_ENABLED_MESSAGE = "当前套餐暂未开放该功能"
PROGRAM_PERMIT_DENIED_MESSAGE = "当前程序访问权限不足"
PROGRAM_ACCESS_REVOKED_MESSAGE = "当前程序会员不可用"
PROGRAM_ACCESS_UNLOCKED_MESSAGE = "当前程序会员权限有效"

_UNLOCKED_AUTH_STATES = {"active", "grace", "refresh_due"}
_MEMBERSHIP_STATUS_TO_AUTH_STATE = {
    "active": "active",
    "grace": "grace",
    "refresh_due": "refresh_due",
    "expired": "revoked",
    "revoked": "revoked",
}
_LOCKED_MESSAGES = {
    "program_auth_required": PROGRAM_AUTH_REQUIRED_MESSAGE,
    "program_membership_expired": PROGRAM_MEMBERSHIP_EXPIRED_MESSAGE,
    "program_device_conflict": PROGRAM_DEVICE_CONFLICT_MESSAGE,
    "program_grace_limited": PROGRAM_GRACE_LIMITED_MESSAGE,
    "program_feature_not_enabled": PROGRAM_FEATURE_NOT_ENABLED_MESSAGE,
    "program_permit_denied": PROGRAM_PERMIT_DENIED_MESSAGE,
}


class ProgramCredentialStore(Protocol):
    def load(self) -> ProgramCredentialBundle:
        ...

    def clear(self) -> None:
        ...


def _read_string(payload: dict[str, object] | None, key: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _resolve_auth_state(bundle: ProgramCredentialBundle) -> str | None:
    snapshot = bundle.entitlement_snapshot if isinstance(bundle.entitlement_snapshot, dict) else None
    explicit_auth_state = _read_string(snapshot, "auth_state")
    if explicit_auth_state:
        return explicit_auth_state

    membership_status = _read_string(snapshot, "membership_status")
    if membership_status:
        return _MEMBERSHIP_STATUS_TO_AUTH_STATE.get(membership_status, "revoked")

    return None


def _resolve_last_error_code(bundle: ProgramCredentialBundle, auth_state: str | None) -> str | None:
    if auth_state in _UNLOCKED_AUTH_STATES:
        return None
    if isinstance(bundle.last_error_code, str) and bundle.last_error_code:
        return bundle.last_error_code
    if auth_state == "revoked":
        return "program_feature_not_enabled"
    return "program_auth_required"


def _resolve_message(
    bundle: ProgramCredentialBundle,
    auth_state: str | None,
    last_error_code: str | None,
) -> str:
    snapshot = bundle.entitlement_snapshot if isinstance(bundle.entitlement_snapshot, dict) else None
    snapshot_message = _read_string(snapshot, "message")
    if snapshot_message:
        return snapshot_message
    if auth_state in _UNLOCKED_AUTH_STATES:
        return PROGRAM_ACCESS_UNLOCKED_MESSAGE
    if last_error_code:
        return _LOCKED_MESSAGES.get(last_error_code, PROGRAM_ACCESS_REVOKED_MESSAGE)
    return PROGRAM_AUTH_REQUIRED_MESSAGE


class CachedProgramAccessGateway:
    def __init__(
        self,
        credential_store: ProgramCredentialStore,
        *,
        stage: str = "packaged_release",
    ) -> None:
        self._credential_store = credential_store
        self._stage = stage

    def _build_summary(self, bundle: ProgramCredentialBundle) -> ProgramAccessSummary:
        auth_state = _resolve_auth_state(bundle)
        last_error_code = _resolve_last_error_code(bundle, auth_state)
        snapshot = bundle.entitlement_snapshot if isinstance(bundle.entitlement_snapshot, dict) else None

        return ProgramAccessSummary(
            mode="remote_entitlement",
            stage=self._stage,
            guard_enabled=True,
            message=_resolve_message(bundle, auth_state, last_error_code),
            username=_read_string(snapshot, "username"),
            auth_state=auth_state,
            runtime_state=_read_string(snapshot, "runtime_state") or "stopped",
            grace_expires_at=_read_string(snapshot, "grace_expires_at"),
            last_error_code=last_error_code,
        )

    def get_summary(self) -> ProgramAccessSummary:
        return self._build_summary(self._credential_store.load())

    def guard(self, action: str) -> ProgramAccessDecision:
        _ = action
        summary = self.get_summary()
        if summary.auth_state in _UNLOCKED_AUTH_STATES:
            return ProgramAccessDecision.allow()
        return ProgramAccessDecision.deny(
            code=str(summary.last_error_code or "program_auth_required"),
            message=str(summary.message or PROGRAM_AUTH_REQUIRED_MESSAGE),
        )

    def get_auth_status(self) -> ProgramAccessSummary:
        return self.get_summary()

    def login(self, *, username: str, password: str) -> ProgramAccessActionResult:
        _ = username
        _ = password
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=PROGRAM_AUTH_REMOTE_NOT_READY_MESSAGE,
        )

    def logout(self) -> ProgramAccessActionResult:
        self._credential_store.clear()
        return ProgramAccessActionResult.accept(summary=self.get_summary())
