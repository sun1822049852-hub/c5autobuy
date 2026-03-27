from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class AccountSessionBundleState(str, Enum):
    STAGED = "staged"
    VERIFIED = "verified"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


@dataclass(slots=True)
class AccountSessionBundle:
    bundle_id: str
    account_id: str | None
    captured_c5_user_id: str | None
    state: AccountSessionBundleState
    schema_version: int
    payload_path: Path
    payload: dict[str, Any]
    created_at: str
    updated_at: str
