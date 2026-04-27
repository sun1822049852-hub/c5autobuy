from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.program_auth import (
    ProgramAuthActionResponse,
    ProgramAuthRegisterCompleteRequest,
    ProgramAuthLoginRequest,
    ProgramAuthPasswordResetRequest,
    ProgramAuthPasswordSendResetCodeRequest,
    ProgramAuthRegisterSendCodeRequest,
    ProgramAuthRegisterVerifyCodeRequest,
    ProgramAuthStatusResponse,
)
from app_backend.application.program_access import (
    PROGRAM_REMOTE_UNAVAILABLE_CODE,
    PROGRAM_REMOTE_UNAVAILABLE_MESSAGE,
    ProgramAccessActionResult,
    ProgramAccessSummary,
)

router = APIRouter(prefix="/program-auth", tags=["program-auth"])

_PROGRAM_AUTH_HTTP_STATUS = {
    "program_auth_not_ready": status.HTTP_503_SERVICE_UNAVAILABLE,
    "program_remote_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "service_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "program_auth_required": status.HTTP_401_UNAUTHORIZED,
    "program_snapshot_invalid": status.HTTP_401_UNAUTHORIZED,
    "program_feature_not_enabled": status.HTTP_403_FORBIDDEN,
    "program_permit_denied": status.HTTP_403_FORBIDDEN,
    "unauthorized": status.HTTP_401_UNAUTHORIZED,
    "invalid_credentials": status.HTTP_401_UNAUTHORIZED,
    "invalid_refresh_token": status.HTTP_401_UNAUTHORIZED,
    "refresh_token_invalid": status.HTTP_401_UNAUTHORIZED,
    "refresh_token_missing": status.HTTP_401_UNAUTHORIZED,
    "refresh_credential_invalid": status.HTTP_401_UNAUTHORIZED,
    "device_session_revoked": status.HTTP_401_UNAUTHORIZED,
    "refresh_token_not_found": status.HTTP_401_UNAUTHORIZED,
    "user_not_found": status.HTTP_404_NOT_FOUND,
    "user_already_exists": status.HTTP_409_CONFLICT,
    "device_conflict": status.HTTP_409_CONFLICT,
    "membership_expired": status.HTTP_403_FORBIDDEN,
    "membership_revoked": status.HTTP_403_FORBIDDEN,
    "membership_not_enabled": status.HTTP_403_FORBIDDEN,
    "feature_not_enabled": status.HTTP_403_FORBIDDEN,
    "rate_limited": status.HTTP_429_TOO_MANY_REQUESTS,
    "login_locked": status.HTTP_429_TOO_MANY_REQUESTS,
    "code_verify_locked": status.HTTP_429_TOO_MANY_REQUESTS,
    "device_mismatch": status.HTTP_409_CONFLICT,
    "REGISTER_INPUT_INVALID": status.HTTP_400_BAD_REQUEST,
    "REGISTER_SEND_RETRY_LATER": status.HTTP_429_TOO_MANY_REQUESTS,
    "REGISTER_SEND_DENIED": status.HTTP_403_FORBIDDEN,
    "REGISTER_SERVICE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "REGISTER_SESSION_EMAIL_MISMATCH": status.HTTP_409_CONFLICT,
    "REGISTER_SESSION_INVALID": status.HTTP_410_GONE,
    "REGISTER_CODE_INVALID_OR_EXPIRED": status.HTTP_400_BAD_REQUEST,
    "REGISTER_CODE_ATTEMPTS_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
    "REGISTER_TICKET_INVALID_OR_EXPIRED": status.HTTP_410_GONE,
    "REGISTER_USERNAME_INVALID": status.HTTP_400_BAD_REQUEST,
    "REGISTER_USERNAME_TAKEN": status.HTTP_409_CONFLICT,
    "REGISTER_PASSWORD_WEAK": status.HTTP_400_BAD_REQUEST,
    "REGISTER_EMAIL_UNAVAILABLE": status.HTTP_409_CONFLICT,
}


def _gateway(request: Request):
    return request.app.state.program_access_gateway


def _serialize_summary(summary: ProgramAccessSummary) -> ProgramAuthStatusResponse:
    return ProgramAuthStatusResponse.model_validate(asdict(summary))


def _raise_structured_error(
    *,
    action: str,
    code: str,
    message: str,
    payload: dict[str, object] | None = None,
) -> None:
    detail_payload = {
        "code": code,
        "message": message,
        "action": action,
    }
    if isinstance(payload, dict):
        detail_payload.update({
            key: value
            for key, value in payload.items()
            if key not in {"code", "message", "action"} and value is not None
        })
    raise HTTPException(
        status_code=_status_code_for_program_auth_error(code),
        detail=detail_payload,
    )


def _handle_action_result(
    *,
    action: str,
    result: ProgramAccessActionResult,
) -> ProgramAuthActionResponse:
    if result.accepted:
        payload = result.payload if isinstance(result.payload, dict) else {}
        return ProgramAuthActionResponse.model_validate({
            "ok": True,
            "message": str(result.message or result.summary.message),
            "summary": _serialize_summary(result.summary),
            **payload,
        })
    _raise_structured_error(
        action=action,
        code=str(result.code or PROGRAM_REMOTE_UNAVAILABLE_CODE),
        message=str(result.message or PROGRAM_REMOTE_UNAVAILABLE_MESSAGE),
        payload=result.payload if isinstance(result.payload, dict) else None,
    )


def _execute_action(
    *,
    action: str,
    invoke: Callable[[], ProgramAccessActionResult],
) -> ProgramAuthActionResponse:
    try:
        return _handle_action_result(action=action, result=invoke())
    except HTTPException:
        raise
    except Exception:
        _raise_structured_error(
            action=action,
            code=PROGRAM_REMOTE_UNAVAILABLE_CODE,
            message=PROGRAM_REMOTE_UNAVAILABLE_MESSAGE,
        )


def _status_code_for_program_auth_error(code: str) -> int:
    normalized_code = str(code or "").strip()
    if normalized_code in _PROGRAM_AUTH_HTTP_STATUS:
        return _PROGRAM_AUTH_HTTP_STATUS[normalized_code]
    if normalized_code in {
        "email_invalid",
        "email_code_invalid",
        "register_payload_invalid",
        "reset_payload_invalid",
    }:
        return status.HTTP_400_BAD_REQUEST
    if normalized_code == "invalid_response":
        return status.HTTP_502_BAD_GATEWAY
    return status.HTTP_400_BAD_REQUEST


@router.get("/status", response_model=ProgramAuthStatusResponse)
def get_program_auth_status(request: Request) -> ProgramAuthStatusResponse:
    try:
        return _serialize_summary(_gateway(request).get_auth_status())
    except Exception:
        _raise_structured_error(
            action="program-auth.status",
            code=PROGRAM_REMOTE_UNAVAILABLE_CODE,
            message=PROGRAM_REMOTE_UNAVAILABLE_MESSAGE,
        )


@router.post("/login", response_model=ProgramAuthActionResponse, response_model_exclude_none=True)
def login_program_auth(payload: ProgramAuthLoginRequest, request: Request) -> ProgramAuthActionResponse:
    return _execute_action(
        action="program-auth.login",
        invoke=lambda: _gateway(request).login(
            username=payload.username,
            password=payload.password,
        ),
    )


@router.post("/logout", response_model=ProgramAuthActionResponse, response_model_exclude_none=True)
def logout_program_auth(request: Request) -> ProgramAuthActionResponse:
    return _execute_action(
        action="program-auth.logout",
        invoke=lambda: _gateway(request).logout(),
    )


@router.post("/register/send-code", response_model=ProgramAuthActionResponse, response_model_exclude_none=True)
def send_register_code(
    payload: ProgramAuthRegisterSendCodeRequest,
    request: Request,
) -> ProgramAuthActionResponse:
    return _execute_action(
        action="program-auth.register.send-code",
        invoke=lambda: _gateway(request).send_register_code(payload.email),
    )


@router.post("/register/verify-code", response_model=ProgramAuthActionResponse, response_model_exclude_none=True)
def verify_register_code(
    payload: ProgramAuthRegisterVerifyCodeRequest,
    request: Request,
) -> ProgramAuthActionResponse:
    return _execute_action(
        action="program-auth.register.verify-code",
        invoke=lambda: _gateway(request).verify_register_code(
            email=payload.email,
            code=payload.code,
            register_session_id=payload.register_session_id,
        ),
    )


@router.post("/register/complete", response_model=ProgramAuthActionResponse, response_model_exclude_none=True)
def complete_register_program_auth(
    payload: ProgramAuthRegisterCompleteRequest,
    request: Request,
) -> ProgramAuthActionResponse:
    return _execute_action(
        action="program-auth.register.complete",
        invoke=lambda: _gateway(request).complete_register(
            email=payload.email,
            verification_ticket=payload.verification_ticket,
            username=payload.username,
            password=payload.password,
        ),
    )


@router.post("/password/send-reset-code", response_model=ProgramAuthActionResponse, response_model_exclude_none=True)
def send_password_reset_code(
    payload: ProgramAuthPasswordSendResetCodeRequest,
    request: Request,
) -> ProgramAuthActionResponse:
    return _execute_action(
        action="program-auth.password.send-reset-code",
        invoke=lambda: _gateway(request).send_reset_code(payload.email),
    )


@router.post("/password/reset", response_model=ProgramAuthActionResponse, response_model_exclude_none=True)
def reset_program_auth_password(
    payload: ProgramAuthPasswordResetRequest,
    request: Request,
) -> ProgramAuthActionResponse:
    return _execute_action(
        action="program-auth.password.reset",
        invoke=lambda: _gateway(request).reset_password(
            email=payload.email,
            code=payload.code,
            new_password=payload.new_password,
        ),
    )
