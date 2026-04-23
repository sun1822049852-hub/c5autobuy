from __future__ import annotations

from app_backend.application.program_access import (
    LOCAL_PASS_THROUGH_MESSAGE,
    PROGRAM_AUTH_NOT_READY_CODE,
    ProgramAccessActionResult,
    ProgramAccessDecision,
    ProgramAccessSummary,
)


class LocalPassThroughGateway:
    def get_summary(self) -> ProgramAccessSummary:
        return ProgramAccessSummary(
            mode="local_pass_through",
            stage="prepackaging",
            guard_enabled=False,
            message=LOCAL_PASS_THROUGH_MESSAGE,
        )

    def get_auth_status(self) -> ProgramAccessSummary:
        return self.get_summary()

    def guard(self, action: str) -> ProgramAccessDecision:
        _ = action
        return ProgramAccessDecision.allow()

    def login(self, *, username: str, password: str) -> ProgramAccessActionResult:
        _ = username
        _ = password
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=LOCAL_PASS_THROUGH_MESSAGE,
        )

    def logout(self) -> ProgramAccessActionResult:
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=LOCAL_PASS_THROUGH_MESSAGE,
        )

    def send_register_code(self, email: str) -> ProgramAccessActionResult:
        _ = email
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=LOCAL_PASS_THROUGH_MESSAGE,
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
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=LOCAL_PASS_THROUGH_MESSAGE,
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
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=LOCAL_PASS_THROUGH_MESSAGE,
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
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=LOCAL_PASS_THROUGH_MESSAGE,
        )

    def send_reset_code(self, email: str) -> ProgramAccessActionResult:
        _ = email
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=LOCAL_PASS_THROUGH_MESSAGE,
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
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=LOCAL_PASS_THROUGH_MESSAGE,
        )

    def refresh(self, *, reason: str) -> ProgramAccessActionResult:
        _ = reason
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=PROGRAM_AUTH_NOT_READY_CODE,
            message=LOCAL_PASS_THROUGH_MESSAGE,
        )
