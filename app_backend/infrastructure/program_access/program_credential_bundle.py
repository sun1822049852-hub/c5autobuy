from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgramCredentialBundle:
    device_id: str
    refresh_credential_ref: str | None = None
    entitlement_snapshot: dict[str, object] | None = None
    entitlement_signature: str | None = None
    entitlement_kid: str | None = None
    lease_id: str | None = None
    clock_offset: float = 0.0
    last_error_code: str | None = None
    updated_at: str | None = None
