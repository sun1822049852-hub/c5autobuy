from __future__ import annotations

from pydantic import BaseModel


class ProgramAuthStatusResponse(BaseModel):
    mode: str
    stage: str
    guard_enabled: bool
    message: str
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
