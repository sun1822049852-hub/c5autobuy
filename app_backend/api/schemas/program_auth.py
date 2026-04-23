from __future__ import annotations

from pydantic import BaseModel


class ProgramAuthStatusResponse(BaseModel):
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


class ProgramAuthLoginRequest(BaseModel):
    username: str
    password: str


class ProgramAuthRegisterSendCodeRequest(BaseModel):
    email: str


class ProgramAuthRegisterRequest(BaseModel):
    email: str
    code: str
    username: str
    password: str


class ProgramAuthRegisterVerifyCodeRequest(BaseModel):
    email: str
    code: str
    register_session_id: str


class ProgramAuthRegisterCompleteRequest(BaseModel):
    email: str
    verification_ticket: str
    username: str
    password: str


class ProgramAuthPasswordSendResetCodeRequest(BaseModel):
    email: str


class ProgramAuthPasswordResetRequest(BaseModel):
    email: str
    code: str
    new_password: str


class ProgramAuthActionResponse(BaseModel):
    ok: bool
    message: str
    summary: ProgramAuthStatusResponse
    register_session_id: str | None = None
    masked_email: str | None = None
    code_length: int | None = None
    code_expires_in_seconds: int | None = None
    resend_after_seconds: int | None = None
    verification_ticket: str | None = None
    ticket_expires_in_seconds: int | None = None
