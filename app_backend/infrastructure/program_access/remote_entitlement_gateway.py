from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from app_backend.application.program_access import (
    PROGRAM_ACCESS_UNLOCKED_MESSAGE,
    PROGRAM_REGISTERED_BUT_NOT_MEMBER_MESSAGE,
    PROGRAM_AUTH_REQUIRED_CODE,
    PROGRAM_AUTH_REQUIRED_MESSAGE,
    PROGRAM_FEATURE_NOT_ENABLED_CODE,
    PROGRAM_FEATURE_NOT_ENABLED_MESSAGE,
    PROGRAM_PERMIT_DENIED_CODE,
    PROGRAM_PERMIT_DENIED_MESSAGE,
    PROGRAM_REFRESH_FAILED_CODE,
    PROGRAM_REFRESH_FAILED_MESSAGE,
    PROGRAM_REMOTE_UNAVAILABLE_CODE,
    PROGRAM_REMOTE_UNAVAILABLE_MESSAGE,
    PROGRAM_SNAPSHOT_INVALID_CODE,
    PROGRAM_SNAPSHOT_INVALID_MESSAGE,
    ProgramAccessActionResult,
    ProgramAccessDecision,
    ProgramAccessSummary,
)

from .device_id_store import DeviceIdStore
from .entitlement_verifier import EntitlementVerifier
from .program_credential_bundle import ProgramCredentialBundle
from .remote_control_plane_client import (
    RemoteAuthResult,
    RemoteControlPlaneClient,
    RemoteControlPlaneError,
    RemoteControlPlaneTransportError,
)
from .secret_store import SecretDecryptError, SecretNotFoundError, SecretStore, SecretStoreReadError


class ProgramCredentialStore(Protocol):
    def load(self) -> ProgramCredentialBundle: ...

    def save(self, bundle: ProgramCredentialBundle) -> None: ...

    def clear(self) -> None: ...


@dataclass(frozen=True)
class _VerifiedEnvelope:
    snapshot: dict[str, object] | None
    signature: str | None
    kid: str | None
    invalid: bool


class RemoteEntitlementGateway:
    def __init__(
        self,
        *,
        remote_client: RemoteControlPlaneClient,
        verifier: EntitlementVerifier,
        credential_store: ProgramCredentialStore,
        secret_store: SecretStore,
        device_id_store: DeviceIdStore,
        stage: str = "packaged_release",
        probe_registration_readiness: bool = False,
    ) -> None:
        self._remote_client = remote_client
        self._verifier = verifier
        self._credential_store = credential_store
        self._secret_store = secret_store
        self._device_id_store = device_id_store
        self._stage = stage
        self._probe_registration_readiness = probe_registration_readiness
        self._registration_flow_version_cache = 2

    def close(self) -> None:
        close = getattr(self._remote_client, "close", None)
        if callable(close):
            close()

    def get_summary(self) -> ProgramAccessSummary:
        return self._build_summary(self._credential_store.load())

    def get_auth_status(self) -> ProgramAccessSummary:
        return self.get_summary()

    def login(self, *, username: str, password: str) -> ProgramAccessActionResult:
        device_id = self._device_id_store.load_or_create()
        try:
            result = self._remote_client.login(
                username=username,
                password=password,
                device_id=device_id,
            )
        except Exception as exc:
            return self._reject_for_remote_error(exc)
        return self._apply_remote_auth_result(result)

    def refresh(self, *, reason: str) -> ProgramAccessActionResult:
        _ = reason
        bundle = self._credential_store.load()
        envelope = self._load_verified_envelope(bundle)
        refresh_token = self._read_refresh_token(bundle)
        if not refresh_token:
            if envelope.invalid:
                return self._reject_with_code(PROGRAM_SNAPSHOT_INVALID_CODE, clear_auth=True)
            return self._reject_with_code(PROGRAM_AUTH_REQUIRED_CODE, clear_auth=True)
        try:
            result = self._remote_client.refresh(
                refresh_token=refresh_token,
                device_id=self._device_id_store.load_or_create(),
            )
        except Exception as exc:
            return self._reject_for_remote_error(exc)
        return self._apply_remote_auth_result(result)

    def logout(self) -> ProgramAccessActionResult:
        bundle = self._credential_store.load()
        refresh_token = self._read_refresh_token(bundle)
        previous_ref = bundle.refresh_credential_ref
        if not refresh_token:
            self._credential_store.clear()
            self._cleanup_previous_refresh_ref(previous_ref=previous_ref, next_ref=None)
            return ProgramAccessActionResult.accept(
                summary=self.get_summary(),
                message="已退出登录",
            )
        try:
            result = self._remote_client.logout(refresh_token=refresh_token)
        except Exception as exc:
            return self._reject_route_action_error(
                exc,
                clear_auth=_should_clear_auth_on_logout_error(exc),
            )
        self._credential_store.clear()
        self._cleanup_previous_refresh_ref(previous_ref=previous_ref, next_ref=None)
        return ProgramAccessActionResult.accept(
            summary=self.get_summary(),
            message=result.message,
        )

    def send_register_code(self, email: str) -> ProgramAccessActionResult:
        try:
            result = self._remote_client.send_register_code(
                email,
                install_id=self._device_id_store.load_or_create(),
            )
        except Exception as exc:
            return self._reject_route_action_error(exc)
        self._registration_flow_version_cache = 3
        return ProgramAccessActionResult.accept(
            summary=self.get_summary(),
            message=result.message,
            payload=_compact_payload({
                "register_session_id": result.register_session_id,
                "masked_email": result.masked_email,
                "code_length": result.code_length,
                "code_expires_in_seconds": result.code_expires_in_seconds or result.expires_in_seconds,
                "resend_after_seconds": result.resend_after_seconds,
            }),
        )

    def verify_register_code(
        self,
        *,
        email: str,
        code: str,
        register_session_id: str,
    ) -> ProgramAccessActionResult:
        try:
            result = self._remote_client.verify_register_code(
                email=email,
                code=code,
                register_session_id=register_session_id,
                install_id=self._device_id_store.load_or_create(),
            )
        except Exception as exc:
            return self._reject_route_action_error(exc)
        self._registration_flow_version_cache = 3
        return ProgramAccessActionResult.accept(
            summary=self.get_summary(),
            message=result.message,
            payload=_compact_payload({
                "verification_ticket": result.verification_ticket,
                "ticket_expires_in_seconds": getattr(result, "ticket_expires_in_seconds", None),
            }),
        )

    def register(
        self,
        *,
        email: str,
        code: str,
        username: str,
        password: str,
    ) -> ProgramAccessActionResult:
        try:
            self._remote_client.register(
                email=email,
                code=code,
                username=username,
                password=password,
            )
        except Exception as exc:
            return self._reject_route_action_error(exc)
        return ProgramAccessActionResult.accept(
            summary=self.get_summary(),
            message=PROGRAM_REGISTERED_BUT_NOT_MEMBER_MESSAGE,
        )

    def complete_register(
        self,
        *,
        email: str,
        verification_ticket: str,
        username: str,
        password: str,
    ) -> ProgramAccessActionResult:
        try:
            result = self._remote_client.complete_register(
                email=email,
                verification_ticket=verification_ticket,
                username=username,
                password=password,
                install_id=self._device_id_store.load_or_create(),
            )
        except Exception as exc:
            return self._reject_route_action_error(exc)
        self._registration_flow_version_cache = 3
        applied = self._apply_remote_auth_result(result)
        if not applied.accepted:
            return applied
        return ProgramAccessActionResult.accept(
            summary=applied.summary,
            message=PROGRAM_REGISTERED_BUT_NOT_MEMBER_MESSAGE,
        )

    def send_reset_code(self, email: str) -> ProgramAccessActionResult:
        try:
            result = self._remote_client.send_reset_code(email)
        except Exception as exc:
            return self._reject_route_action_error(exc)
        return ProgramAccessActionResult.accept(
            summary=self.get_summary(),
            message=result.message,
        )

    def reset_password(
        self,
        *,
        email: str,
        code: str,
        new_password: str,
    ) -> ProgramAccessActionResult:
        try:
            result = self._remote_client.reset_password(
                email=email,
                code=code,
                new_password=new_password,
            )
        except Exception as exc:
            return self._reject_route_action_error(exc)
        return ProgramAccessActionResult.accept(
            summary=self.get_summary(),
            message=result.message,
        )

    def guard(self, action: str) -> ProgramAccessDecision:
        bundle = self._credential_store.load()
        envelope = self._load_verified_envelope(bundle)
        snapshot = envelope.snapshot
        if envelope.invalid:
            action_result = self._reject_with_code(PROGRAM_SNAPSHOT_INVALID_CODE, clear_auth=True)
            return ProgramAccessDecision.deny(
                code=action_result.code or PROGRAM_SNAPSHOT_INVALID_CODE,
                message=action_result.message or PROGRAM_SNAPSHOT_INVALID_MESSAGE,
            )

        if snapshot is None:
            action_result = self._reject_with_code(PROGRAM_AUTH_REQUIRED_CODE, clear_auth=True)
            return ProgramAccessDecision.deny(
                code=action_result.code or PROGRAM_AUTH_REQUIRED_CODE,
                message=action_result.message or PROGRAM_AUTH_REQUIRED_MESSAGE,
            )

        if not _feature_enabled(snapshot):
            self._set_last_error(PROGRAM_FEATURE_NOT_ENABLED_CODE)
            return ProgramAccessDecision.deny(
                code=PROGRAM_FEATURE_NOT_ENABLED_CODE,
                message=PROGRAM_FEATURE_NOT_ENABLED_MESSAGE,
            )

        if action != "runtime.start":
            self._clear_last_error()
            return ProgramAccessDecision.allow()

        refresh_token = self._read_refresh_token(bundle)
        if not refresh_token:
            action_result = self._reject_with_code(PROGRAM_AUTH_REQUIRED_CODE, clear_auth=True)
            return ProgramAccessDecision.deny(
                code=action_result.code or PROGRAM_AUTH_REQUIRED_CODE,
                message=action_result.message or PROGRAM_AUTH_REQUIRED_MESSAGE,
            )

        try:
            permit_result = self._remote_client.request_runtime_permit(
                refresh_token=refresh_token,
                device_id=self._device_id_store.load_or_create(),
                action="runtime.start",
            )
        except Exception as exc:
            action_result = self._reject_for_remote_error(
                exc,
                permit_mode=True,
            )
            return ProgramAccessDecision.deny(
                code=action_result.code or PROGRAM_PERMIT_DENIED_CODE,
                message=action_result.message or PROGRAM_PERMIT_DENIED_MESSAGE,
            )

        verified_snapshot = self._verify_snapshot(
            snapshot=permit_result.permit.snapshot,
            signature=permit_result.permit.signature,
            kid=permit_result.permit.kid,
        )
        if verified_snapshot is None:
            action_result = self._reject_with_code(PROGRAM_SNAPSHOT_INVALID_CODE, clear_auth=True)
            return ProgramAccessDecision.deny(
                code=action_result.code or PROGRAM_SNAPSHOT_INVALID_CODE,
                message=action_result.message or PROGRAM_SNAPSHOT_INVALID_MESSAGE,
            )

        self._persist_snapshot(
            bundle=bundle,
            snapshot=verified_snapshot,
            entitlement_signature=permit_result.permit.signature,
            entitlement_kid=permit_result.permit.kid,
            last_error_code=None,
        )
        return ProgramAccessDecision.allow()

    def _apply_remote_auth_result(self, result: RemoteAuthResult) -> ProgramAccessActionResult:
        verified_snapshot = self._verify_snapshot(
            snapshot=result.auth_bundle.snapshot,
            signature=result.auth_bundle.signature,
            kid=result.auth_bundle.kid,
        )
        if verified_snapshot is None:
            return self._reject_with_code(PROGRAM_SNAPSHOT_INVALID_CODE, clear_auth=True)

        existing_bundle = self._credential_store.load()
        refresh_ref = self._secret_store.put(result.auth_bundle.refresh_token)
        self._persist_snapshot(
            bundle=existing_bundle,
            snapshot=verified_snapshot,
            refresh_credential_ref=refresh_ref,
            entitlement_signature=result.auth_bundle.signature,
            entitlement_kid=result.auth_bundle.kid,
            last_error_code=None,
        )
        self._cleanup_previous_refresh_ref(
            previous_ref=existing_bundle.refresh_credential_ref,
            next_ref=refresh_ref,
        )
        return ProgramAccessActionResult.accept(
            summary=self.get_summary(),
            message=result.message,
        )

    def _verify_snapshot(
        self,
        *,
        snapshot: dict[str, object],
        signature: str,
        kid: str,
    ) -> dict[str, object] | None:
        verification = self._verifier.verify(
            {
                "snapshot": snapshot,
                "signature": signature,
                "kid": kid,
            }
        )
        if verification.reason == "kid_unknown" and self._refresh_public_key_cache():
            verification = self._verifier.verify(
                {
                    "snapshot": snapshot,
                    "signature": signature,
                    "kid": kid,
                }
            )
        if not verification.ok or verification.snapshot is None:
            return None
        return verification.snapshot

    def _refresh_public_key_cache(self) -> bool:
        fetch_public_key = getattr(self._remote_client, "fetch_public_key_pem", None)
        if not callable(fetch_public_key):
            return False
        try:
            public_key_pem = fetch_public_key()
            self._verifier.replace_key_cache(public_key_pem)
        except Exception:
            return False
        return True

    def _reject_for_remote_error(
        self,
        error: Exception,
        *,
        permit_mode: bool = False,
    ) -> ProgramAccessActionResult:
        mapped_code = _map_remote_error_code(error, permit_mode=permit_mode)
        clear_auth = mapped_code == PROGRAM_AUTH_REQUIRED_CODE
        return self._reject_with_code(mapped_code, clear_auth=clear_auth)

    def _reject_route_action_error(
        self,
        error: Exception,
        *,
        clear_auth: bool = False,
    ) -> ProgramAccessActionResult:
        previous_ref: str | None = None
        if clear_auth:
            previous_ref = self._credential_store.load().refresh_credential_ref
            self._credential_store.clear()
            self._cleanup_previous_refresh_ref(previous_ref=previous_ref, next_ref=None)
        if isinstance(error, RemoteControlPlaneError):
            code = str(error.reason or PROGRAM_REMOTE_UNAVAILABLE_CODE).strip() or PROGRAM_REMOTE_UNAVAILABLE_CODE
            message = str(error.message or PROGRAM_REMOTE_UNAVAILABLE_MESSAGE).strip() or PROGRAM_REMOTE_UNAVAILABLE_MESSAGE
            payload = _compact_payload({
                "retry_after_seconds": _read_optional_int(error.payload, "retry_after_seconds"),
            })
        else:
            code = PROGRAM_REMOTE_UNAVAILABLE_CODE
            message = PROGRAM_REMOTE_UNAVAILABLE_MESSAGE
            payload = None
        return ProgramAccessActionResult.reject(
            summary=self.get_summary(),
            code=code,
            message=message,
            payload=payload,
        )

    def _reject_with_code(
        self,
        code: str,
        *,
        clear_auth: bool,
    ) -> ProgramAccessActionResult:
        if clear_auth:
            self._credential_store.clear()
            bundle = self._credential_store.load()
        else:
            bundle = self._credential_store.load()
        envelope = self._load_verified_envelope(bundle)
        self._persist_snapshot(
            bundle=bundle,
            snapshot=envelope.snapshot,
            entitlement_signature=envelope.signature,
            entitlement_kid=envelope.kid,
            last_error_code=code,
        )
        summary = self.get_summary()
        return ProgramAccessActionResult.reject(
            summary=summary,
            code=code,
            message=_code_message(code),
        )

    def _set_last_error(self, code: str) -> None:
        bundle = self._credential_store.load()
        envelope = self._load_verified_envelope(bundle)
        self._persist_snapshot(
            bundle=bundle,
            snapshot=envelope.snapshot,
            entitlement_signature=envelope.signature,
            entitlement_kid=envelope.kid,
            last_error_code=code,
        )

    def _clear_last_error(self) -> None:
        bundle = self._credential_store.load()
        if bundle.last_error_code is None:
            return
        envelope = self._load_verified_envelope(bundle)
        self._persist_snapshot(
            bundle=bundle,
            snapshot=envelope.snapshot,
            entitlement_signature=envelope.signature,
            entitlement_kid=envelope.kid,
            last_error_code=None,
        )

    def _persist_snapshot(
        self,
        *,
        bundle: ProgramCredentialBundle,
        snapshot: dict[str, object] | None,
        refresh_credential_ref: str | None = None,
        entitlement_signature: str | None = None,
        entitlement_kid: str | None = None,
        last_error_code: str | None,
    ) -> None:
        self._credential_store.save(
            ProgramCredentialBundle(
                device_id=self._device_id_store.load_or_create(),
                refresh_credential_ref=(
                    bundle.refresh_credential_ref if refresh_credential_ref is None else refresh_credential_ref
                ),
                entitlement_snapshot=snapshot,
                entitlement_signature=entitlement_signature,
                entitlement_kid=entitlement_kid,
                lease_id=bundle.lease_id,
                clock_offset=bundle.clock_offset,
                last_error_code=last_error_code,
                updated_at=bundle.updated_at,
            )
        )

    def _cleanup_previous_refresh_ref(self, *, previous_ref: str | None, next_ref: str | None) -> None:
        if not previous_ref or previous_ref == next_ref:
            return
        try:
            self._secret_store.delete(previous_ref)
        except Exception:
            return

    def _read_refresh_token(self, bundle: ProgramCredentialBundle) -> str | None:
        ref = bundle.refresh_credential_ref
        if not isinstance(ref, str) or not ref:
            return None
        try:
            return self._secret_store.get(ref)
        except (SecretNotFoundError, SecretStoreReadError, SecretDecryptError):
            return None

    def _build_summary(self, bundle: ProgramCredentialBundle) -> ProgramAccessSummary:
        envelope = self._load_verified_envelope(bundle)
        snapshot = envelope.snapshot
        feature_enabled = _feature_enabled(snapshot)
        if bundle.last_error_code:
            last_error_code = bundle.last_error_code
        elif envelope.invalid:
            last_error_code = PROGRAM_SNAPSHOT_INVALID_CODE
        elif snapshot is None:
            last_error_code = PROGRAM_AUTH_REQUIRED_CODE
        elif not feature_enabled:
            last_error_code = PROGRAM_FEATURE_NOT_ENABLED_CODE
        else:
            last_error_code = None

        auth_state: str | None
        if snapshot is None:
            auth_state = None
        elif feature_enabled:
            auth_state = "active"
        else:
            auth_state = "revoked"

        return ProgramAccessSummary(
            mode="remote_entitlement",
            stage=self._stage,
            guard_enabled=True,
            message=_code_message(last_error_code),
            registration_flow_version=self._resolve_registration_flow_version(),
            username=_read_optional_string(snapshot, "username"),
            auth_state=auth_state,
            runtime_state=_read_optional_string(snapshot, "runtime_state") or "stopped",
            grace_expires_at=_read_optional_string(snapshot, "grace_expires_at"),
            last_error_code=last_error_code,
        )

    def _resolve_registration_flow_version(self) -> int:
        if self._registration_flow_version_cache == 3:
            return 3
        if not self._probe_registration_readiness:
            return self._registration_flow_version_cache
        get_readiness = getattr(self._remote_client, "get_registration_readiness", None)
        if not callable(get_readiness):
            return self._registration_flow_version_cache
        try:
            readiness = get_readiness()
        except Exception:
            return self._registration_flow_version_cache
        if bool(getattr(readiness, "ready", False)) and int(getattr(readiness, "registration_flow_version", 2)) == 3:
            self._registration_flow_version_cache = 3
        else:
            self._registration_flow_version_cache = 2
        return self._registration_flow_version_cache

    def _load_verified_envelope(self, bundle: ProgramCredentialBundle) -> _VerifiedEnvelope:
        snapshot = _as_snapshot(bundle.entitlement_snapshot)
        signature = _non_empty_string(bundle.entitlement_signature)
        kid = _non_empty_string(bundle.entitlement_kid)
        if snapshot is None:
            return _VerifiedEnvelope(snapshot=None, signature=None, kid=None, invalid=False)
        if signature is None or kid is None:
            return _VerifiedEnvelope(snapshot=None, signature=None, kid=None, invalid=True)
        verified_snapshot = self._verify_snapshot(
            snapshot=snapshot,
            signature=signature,
            kid=kid,
        )
        if verified_snapshot is None:
            return _VerifiedEnvelope(snapshot=None, signature=None, kid=None, invalid=True)
        return _VerifiedEnvelope(
            snapshot=verified_snapshot,
            signature=signature,
            kid=kid,
            invalid=False,
        )


def _as_snapshot(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, Mapping):
        return None
    return {str(key): payload[key] for key in payload}


def _non_empty_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _feature_enabled(snapshot: dict[str, object] | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    feature_flags = snapshot.get("feature_flags")
    if isinstance(feature_flags, Mapping):
        enabled_flag = feature_flags.get("program_access_enabled")
        if isinstance(enabled_flag, bool):
            return enabled_flag
    permissions = snapshot.get("permissions")
    if isinstance(permissions, list):
        return "program_access_enabled" in permissions
    return False


def _read_optional_string(snapshot: dict[str, object] | None, key: str) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    value = snapshot.get(key)
    return value if isinstance(value, str) and value else None


def _read_optional_int(snapshot: dict[str, object] | None, key: str) -> int | None:
    if not isinstance(snapshot, dict):
        return None
    value = snapshot.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _map_remote_error_code(error: Exception, *, permit_mode: bool) -> str:
    if isinstance(error, RemoteControlPlaneTransportError):
        return PROGRAM_REMOTE_UNAVAILABLE_CODE
    if not isinstance(error, RemoteControlPlaneError):
        return PROGRAM_REMOTE_UNAVAILABLE_CODE

    reason = str(error.reason)
    if error.status_code == 401 or reason in {
        "unauthorized",
        "invalid_refresh_token",
        "refresh_token_invalid",
        "refresh_token_missing",
        "device_session_revoked",
    }:
        return PROGRAM_AUTH_REQUIRED_CODE
    if reason in {"membership_not_enabled", "feature_not_enabled"}:
        return PROGRAM_FEATURE_NOT_ENABLED_CODE
    if permit_mode and (error.status_code == 403 or reason in {"runtime_permission_denied", "permission_denied"}):
        return PROGRAM_PERMIT_DENIED_CODE
    return PROGRAM_REMOTE_UNAVAILABLE_CODE


def _should_clear_auth_on_logout_error(error: Exception) -> bool:
    if not isinstance(error, RemoteControlPlaneError):
        return False
    reason = str(error.reason)
    return error.status_code == 401 or reason in {
        "unauthorized",
        "invalid_refresh_token",
        "refresh_token_invalid",
        "refresh_token_missing",
        "device_session_revoked",
        "refresh_credential_invalid",
    }


def _code_message(code: str | None) -> str:
    if code == PROGRAM_AUTH_REQUIRED_CODE:
        return PROGRAM_AUTH_REQUIRED_MESSAGE
    if code == PROGRAM_FEATURE_NOT_ENABLED_CODE:
        return PROGRAM_FEATURE_NOT_ENABLED_MESSAGE
    if code == PROGRAM_PERMIT_DENIED_CODE:
        return PROGRAM_PERMIT_DENIED_MESSAGE
    if code == PROGRAM_REMOTE_UNAVAILABLE_CODE:
        return PROGRAM_REMOTE_UNAVAILABLE_MESSAGE
    if code == PROGRAM_SNAPSHOT_INVALID_CODE:
        return PROGRAM_SNAPSHOT_INVALID_MESSAGE
    if code == PROGRAM_REFRESH_FAILED_CODE:
        return PROGRAM_REFRESH_FAILED_MESSAGE
    return PROGRAM_ACCESS_UNLOCKED_MESSAGE


def _compact_payload(payload: dict[str, object | None]) -> dict[str, object] | None:
    normalized = {key: value for key, value in payload.items() if value is not None}
    return normalized or None
