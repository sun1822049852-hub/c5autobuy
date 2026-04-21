from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


@dataclass(frozen=True, slots=True)
class VerificationResult:
    ok: bool
    reason: str | None = None
    snapshot: dict[str, object] | None = None
    kid: str | None = None


@dataclass(frozen=True, slots=True)
class _VerifierKeySet:
    keys_by_kid: dict[str, Ed25519PublicKey]


class EntitlementVerifier:
    def __init__(self, *, key_cache_path: str | Path) -> None:
        self._key_cache_path = Path(key_cache_path)
        self._key_set = _load_key_set(self._key_cache_path)

    def replace_key_cache(self, raw_text: str) -> None:
        normalized_text = str(raw_text).strip()
        self._key_set = _parse_key_set(normalized_text)
        self._key_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._key_cache_path.write_text(f"{normalized_text}\n", encoding="utf-8")

    def verify(
        self,
        envelope: Mapping[str, object],
        *,
        now: datetime | None = None,
    ) -> VerificationResult:
        snapshot = envelope.get("snapshot")
        if not isinstance(snapshot, Mapping):
            return VerificationResult(ok=False, reason="snapshot_invalid")
        normalized_snapshot = {str(key): snapshot[key] for key in snapshot}
        signature = envelope.get("signature")
        if not isinstance(signature, str) or not signature.strip():
            return VerificationResult(ok=False, reason="signature_missing")
        kid = envelope.get("kid")
        if kid is None:
            return VerificationResult(ok=False, reason="kid_missing")
        if not isinstance(kid, str) or not kid.strip():
            return VerificationResult(ok=False, reason="kid_invalid")
        if kid not in self._key_set.keys_by_kid:
            return VerificationResult(ok=False, reason="kid_unknown", kid=kid)

        current_time = _normalize_datetime(now or datetime.now(timezone.utc))
        issued_at = _parse_timestamp(normalized_snapshot.get("iat"))
        expires_at = _parse_timestamp(normalized_snapshot.get("exp"))
        if issued_at is None or expires_at is None:
            return VerificationResult(ok=False, reason="timestamp_invalid", kid=kid)
        if issued_at > current_time:
            return VerificationResult(ok=False, reason="not_yet_valid", kid=kid)
        if expires_at < current_time:
            return VerificationResult(ok=False, reason="expired", kid=kid)

        try:
            signature_bytes = base64.b64decode(signature, validate=True)
        except ValueError:
            return VerificationResult(ok=False, reason="signature_invalid", kid=kid)

        payload = stable_stringify(normalized_snapshot).encode("utf-8")
        public_key = self._key_set.keys_by_kid[kid]
        try:
            public_key.verify(signature_bytes, payload)
        except InvalidSignature:
            return VerificationResult(ok=False, reason="signature_invalid", kid=kid)
        return VerificationResult(
            ok=True,
            snapshot=normalized_snapshot,
            kid=kid,
        )


def stable_stringify(value: object) -> str:
    if isinstance(value, list):
        return "[" + ",".join(stable_stringify(item) for item in value) + "]"
    if isinstance(value, Mapping):
        items = [
            f"{json.dumps(str(key), ensure_ascii=False, separators=(',', ':'))}:{stable_stringify(value[key])}"
            for key in sorted(value)
        ]
        return "{" + ",".join(items) + "}"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_key_set(path: Path) -> _VerifierKeySet:
    if not path.exists():
        return _VerifierKeySet(keys_by_kid={})

    raw_text = path.read_text(encoding="utf-8").strip()
    return _parse_key_set(raw_text)


def _parse_key_set(raw_text: str) -> _VerifierKeySet:
    if not raw_text:
        return _VerifierKeySet(keys_by_kid={})

    if "BEGIN PUBLIC KEY" in raw_text:
        public_key = serialization.load_pem_public_key(raw_text.encode("utf-8"))
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError("PEM key must be Ed25519")
        derived_kid = derive_key_id(public_key)
        return _VerifierKeySet(keys_by_kid={derived_kid: public_key})

    payload = json.loads(raw_text)
    keys = payload.get("keys")
    if not isinstance(keys, list):
        raise ValueError("JWKS cache must contain a keys array")

    keys_by_kid: dict[str, Ed25519PublicKey] = {}
    for entry in keys:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("kty") != "OKP" or entry.get("crv") != "Ed25519":
            continue
        x = entry.get("x")
        if not isinstance(x, str) or not x.strip():
            continue
        public_key = Ed25519PublicKey.from_public_bytes(_decode_base64url(x))
        candidate_kid = entry.get("kid")
        if isinstance(candidate_kid, str) and candidate_kid.strip():
            keys_by_kid[candidate_kid] = public_key

    if not keys_by_kid:
        raise ValueError("JWKS cache does not contain any Ed25519 keys")
    return _VerifierKeySet(keys_by_kid=keys_by_kid)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _normalize_datetime(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def derive_key_id(public_key: Ed25519PublicKey) -> str:
    public_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = base64.urlsafe_b64encode(hashlib.sha256(public_der).digest()).decode("ascii").rstrip("=")
    return f"ed25519:{fingerprint[:32]}"
