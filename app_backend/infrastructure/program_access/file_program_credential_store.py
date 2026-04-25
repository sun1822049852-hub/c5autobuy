from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from .device_id_store import DeviceIdStore
from .program_credential_bundle import ProgramCredentialBundle
from .secret_store import (
    SecretDecryptError,
    SecretNotFoundError,
    SecretStore,
    SecretStoreReadError,
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class FileProgramCredentialStore:
    def __init__(
        self,
        bundle_path: Path,
        *,
        secret_store: SecretStore,
        device_id_store: DeviceIdStore,
    ) -> None:
        self._bundle_path = Path(bundle_path)
        self._secret_store = secret_store
        self._device_id_store = device_id_store
        self._lock = threading.RLock()

    def load(self) -> ProgramCredentialBundle:
        with self._lock:
            device_id = self._device_id_store.load_or_create()
            payload, needs_repair = self._load_payload(device_id)
            if needs_repair:
                self._write_payload(payload)
            return ProgramCredentialBundle(**payload)

    def save(self, bundle: ProgramCredentialBundle) -> None:
        with self._lock:
            device_id = self._device_id_store.load_or_create()
            previous_ref = self._current_refresh_ref()
            payload = self._normalized_payload(
                {
                    "device_id": device_id,
                    "refresh_credential_ref": bundle.refresh_credential_ref,
                    "entitlement_snapshot": bundle.entitlement_snapshot,
                    "entitlement_signature": bundle.entitlement_signature,
                    "entitlement_kid": bundle.entitlement_kid,
                    "lease_id": bundle.lease_id,
                    "clock_offset": bundle.clock_offset,
                    "last_error_code": bundle.last_error_code,
                }
            )
            payload["updated_at"] = _now()
            self._write_payload(payload)
            self._cleanup_stale_ref(previous_ref=previous_ref, next_ref=payload["refresh_credential_ref"])

    def clear(self) -> None:
        with self._lock:
            device_id = self._device_id_store.load_or_create()
            previous_ref = self._current_refresh_ref()
            self._write_payload(self._empty_payload(device_id))
            self._cleanup_ref(previous_ref)

    def _load_payload(self, device_id: str) -> tuple[dict[str, Any], bool]:
        raw_payload = self._read_bundle_json()
        if raw_payload is None:
            return self._empty_payload(device_id), True

        payload = self._normalized_payload(raw_payload, device_id=device_id)
        needs_repair = raw_payload.get("device_id") != device_id
        if payload["device_id"] != device_id:
            payload["device_id"] = device_id
            needs_repair = True

        refresh_ref = payload["refresh_credential_ref"]
        if refresh_ref is not None:
            try:
                self._secret_store.get(refresh_ref)
            except (SecretNotFoundError, SecretStoreReadError, SecretDecryptError):
                return self._empty_payload(device_id), True

        if needs_repair:
            payload["updated_at"] = _now()
        return payload, needs_repair

    def _read_bundle_json(self) -> dict[str, Any] | None:
        if not self._bundle_path.exists():
            return None
        try:
            payload = json.loads(self._bundle_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _current_refresh_ref(self) -> str | None:
        payload = self._read_bundle_json()
        if not isinstance(payload, dict):
            return None
        refresh_ref = payload.get("refresh_credential_ref")
        return refresh_ref if isinstance(refresh_ref, str) and refresh_ref else None

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self._bundle_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._bundle_path.with_suffix(f"{self._bundle_path.suffix}.{uuid4().hex}.tmp")
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(str(tmp_path), str(self._bundle_path))

    def _cleanup_stale_ref(self, *, previous_ref: str | None, next_ref: str | None) -> None:
        if previous_ref is None or previous_ref == next_ref:
            return
        self._cleanup_ref(previous_ref)

    def _cleanup_ref(self, ref: str | None) -> None:
        if ref is None:
            return
        try:
            self._secret_store.delete(ref)
        except (SecretNotFoundError, SecretStoreReadError):
            return

    def _empty_payload(self, device_id: str) -> dict[str, Any]:
        return {
            "device_id": device_id,
            "refresh_credential_ref": None,
            "entitlement_snapshot": None,
            "entitlement_signature": None,
            "entitlement_kid": None,
            "lease_id": None,
            "clock_offset": 0.0,
            "last_error_code": "program_auth_required",
            "updated_at": _now(),
        }

    def _normalized_payload(
        self,
        payload: dict[str, Any],
        *,
        device_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_device_id = payload.get("device_id")
        if not isinstance(normalized_device_id, str) or not normalized_device_id:
            normalized_device_id = device_id

        refresh_ref = payload.get("refresh_credential_ref")
        if not isinstance(refresh_ref, str):
            refresh_ref = None

        snapshot = payload.get("entitlement_snapshot")
        if not isinstance(snapshot, dict):
            snapshot = None

        signature = payload.get("entitlement_signature")
        if not isinstance(signature, str) or not signature.strip():
            signature = None

        kid = payload.get("entitlement_kid")
        if not isinstance(kid, str) or not kid.strip():
            kid = None

        lease_id = payload.get("lease_id")
        if not isinstance(lease_id, str):
            lease_id = None

        clock_offset = payload.get("clock_offset", 0.0)
        try:
            normalized_clock_offset = float(clock_offset)
        except (TypeError, ValueError):
            normalized_clock_offset = 0.0

        last_error_code = payload.get("last_error_code")
        if not isinstance(last_error_code, str):
            last_error_code = None

        updated_at = payload.get("updated_at")
        if not isinstance(updated_at, str):
            updated_at = None

        return {
            "device_id": normalized_device_id,
            "refresh_credential_ref": refresh_ref,
            "entitlement_snapshot": snapshot,
            "entitlement_signature": signature,
            "entitlement_kid": kid,
            "lease_id": lease_id,
            "clock_offset": normalized_clock_offset,
            "last_error_code": last_error_code,
            "updated_at": updated_at,
        }
