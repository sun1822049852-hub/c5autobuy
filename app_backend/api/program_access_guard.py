from __future__ import annotations

from fastapi import HTTPException, Request, status


PROGRAM_ACCESS_HTTP_STATUS = {
    "program_auth_required": status.HTTP_401_UNAUTHORIZED,
    "program_membership_expired": status.HTTP_403_FORBIDDEN,
    "program_membership_service_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "program_feature_not_enabled": status.HTTP_403_FORBIDDEN,
    "program_device_conflict": status.HTTP_409_CONFLICT,
    "program_permit_denied": status.HTTP_403_FORBIDDEN,
    "program_remote_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "program_snapshot_invalid": status.HTTP_401_UNAUTHORIZED,
    "program_grace_limited": status.HTTP_403_FORBIDDEN,
    "program_guard_bypassed_dev_only": status.HTTP_403_FORBIDDEN,
}


def guard_program_action(request: Request, action: str) -> None:
    decision = request.app.state.program_access_gateway.guard(action)
    if decision.allowed:
        return

    code = str(decision.code or "program_feature_not_enabled")
    message = str(decision.message or "当前程序访问权限不足")
    raise HTTPException(
        status_code=PROGRAM_ACCESS_HTTP_STATUS.get(code, status.HTTP_403_FORBIDDEN),
        detail={
            "code": code,
            "message": message,
            "action": action,
        },
    )
