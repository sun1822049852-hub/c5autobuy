from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CapturedLoginIdentity:
    c5_user_id: str
    c5_nick_name: str
    cookie_raw: str

    def to_dict(self) -> dict[str, str]:
        return {
            "c5_user_id": self.c5_user_id,
            "c5_nick_name": self.c5_nick_name,
            "cookie_raw": self.cookie_raw,
        }


@dataclass(slots=True)
class StagedBundleRef:
    bundle_id: str
    state: str

    def to_dict(self) -> dict[str, str]:
        return {
            "bundle_id": self.bundle_id,
            "state": self.state,
        }


@dataclass(slots=True)
class LoginExecutionResult:
    captured_login: CapturedLoginIdentity
    session_payload: dict[str, Any] = field(default_factory=dict)
    staged_bundle_ref: StagedBundleRef | None = None

    @property
    def c5_user_id(self) -> str:
        return self.captured_login.c5_user_id

    @property
    def c5_nick_name(self) -> str:
        return self.captured_login.c5_nick_name

    @property
    def cookie_raw(self) -> str:
        return self.captured_login.cookie_raw

    def build_bundle_payload(self) -> dict[str, Any]:
        payload = dict(self.session_payload)
        payload.setdefault("c5_user_id", self.c5_user_id)
        payload.setdefault("c5_nick_name", self.c5_nick_name)
        payload.setdefault("cookie_raw", self.cookie_raw)
        return payload
