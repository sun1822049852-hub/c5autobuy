from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app_backend.infrastructure.program_access.entitlement_verifier import (
    EntitlementVerifier,
    derive_key_id,
    stable_stringify,
)
from app_backend.infrastructure.program_access.program_credential_bundle import ProgramCredentialBundle
from app_backend.infrastructure.program_access.remote_control_plane_client import (
    RemoteAuthBundle,
    RemoteAuthResult,
    RemoteControlPlaneError,
    RemoteMessageResult,
    RemotePermitResult,
    RemoteRuntimePermit,
)
from app_backend.infrastructure.program_access.remote_entitlement_gateway import RemoteEntitlementGateway
from app_backend.infrastructure.program_access.secret_store import SecretDecryptError


def test_remote_gateway_login_persists_verified_snapshot_and_rotated_refresh_token(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    old_ref = secret_store.put("refresh-token-old")
    bundle = ProgramCredentialBundle(
        device_id="device-alpha",
        refresh_credential_ref=old_ref,
        entitlement_snapshot=_build_snapshot(feature_enabled=True),
        last_error_code=None,
    )
    credential_store = _MemoryCredentialStore(bundle)
    remote_client = _RemoteClientStub(
        login_result=_build_auth_result(
            private_key=private_key,
            kid=kid,
            refresh_token="refresh-token-new",
            snapshot=_build_snapshot(feature_enabled=True, runtime_state="running"),
            message="登录成功",
        ),
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.login(username="alice", password="Secret123!")
    stored_bundle = credential_store.load()

    assert result.accepted is True
    assert result.message == "登录成功"
    assert result.summary.username == "alice"
    assert result.summary.auth_state == "active"
    assert result.summary.last_error_code is None
    assert stored_bundle.refresh_credential_ref != old_ref
    assert stored_bundle.refresh_credential_ref is not None
    assert secret_store.get(stored_bundle.refresh_credential_ref) == "refresh-token-new"
    assert old_ref in secret_store.deleted_refs
    assert isinstance(stored_bundle.entitlement_snapshot, dict)
    assert stored_bundle.entitlement_snapshot["runtime_state"] == "running"
    assert stored_bundle.entitlement_signature is not None
    assert stored_bundle.entitlement_kid == kid


def test_remote_gateway_login_fetches_public_key_when_local_key_cache_is_missing(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    missing_key_cache_path = tmp_path / "missing" / "control-plane-public.pem"
    verifier = EntitlementVerifier(key_cache_path=missing_key_cache_path)
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    credential_store = _MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha"))
    remote_client = _RemoteClientStub(
        login_result=_build_auth_result(
            private_key=private_key,
            kid=kid,
            refresh_token="refresh-token-new",
            snapshot=_build_snapshot(feature_enabled=True, runtime_state="running"),
            message="登录成功",
        ),
        public_key_pem=_build_public_key_pem(private_key),
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.login(username="alice", password="Secret123!")
    stored_bundle = credential_store.load()

    assert result.accepted is True
    assert remote_client.public_key_fetch_calls == 1
    assert missing_key_cache_path.exists() is True
    assert "BEGIN PUBLIC KEY" in missing_key_cache_path.read_text(encoding="utf-8")
    assert stored_bundle.entitlement_signature is not None
    assert stored_bundle.entitlement_kid == kid
    assert isinstance(stored_bundle.entitlement_snapshot, dict)
    assert stored_bundle.entitlement_snapshot["runtime_state"] == "running"


def test_remote_gateway_logout_clears_local_auth_and_returns_explicit_success_message(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    refresh_ref = secret_store.put("refresh-token-1")
    cached_snapshot = _build_snapshot(feature_enabled=True, runtime_state="running")
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=refresh_ref,
            entitlement_snapshot=cached_snapshot,
            entitlement_signature=_sign_snapshot(private_key, cached_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    remote_client = _RemoteClientStub()
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.logout()

    assert result.accepted is True
    assert result.message == "已退出登录"
    assert result.summary.auth_state is None
    assert result.summary.last_error_code == "program_auth_required"
    assert remote_client.logout_calls == ["refresh-token-1"]
    assert credential_store.load() == ProgramCredentialBundle(device_id="device-alpha")


def test_remote_gateway_logout_rejects_remote_failure_instead_of_claiming_success(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    refresh_ref = secret_store.put("refresh-token-1")
    cached_snapshot = _build_snapshot(feature_enabled=True, runtime_state="running")
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=refresh_ref,
            entitlement_snapshot=cached_snapshot,
            entitlement_signature=_sign_snapshot(private_key, cached_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    remote_client = _RemoteClientStub(
        logout_error=RemoteControlPlaneError(
            status_code=429,
            reason="rate_limited",
            message="操作过于频繁",
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.logout()

    assert result.accepted is False
    assert result.code == "rate_limited"
    assert result.message == "操作过于频繁"
    assert result.summary.auth_state == "active"
    assert result.summary.last_error_code is None
    assert remote_client.logout_calls == ["refresh-token-1"]


def test_remote_gateway_send_register_code_returns_remote_message_and_summary(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    remote_client = _RemoteClientStub(
        send_register_code_result=RemoteMessageResult(
            message="注册验证码已发送",
            expires_in_seconds=300,
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=_MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha")),
        secret_store=_MemorySecretStore(),
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.send_register_code("alice@example.com")

    assert result.accepted is True
    assert result.message == "注册验证码已发送"
    assert result.summary.registration_flow_version == 3
    assert result.summary.last_error_code == "program_auth_required"
    assert remote_client.send_register_code_calls == [
        {
            "email": "alice@example.com",
            "install_id": "device-alpha",
        }
    ]


def test_remote_gateway_send_register_code_preserves_retry_after_seconds_from_control_plane(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    gateway = RemoteEntitlementGateway(
        remote_client=_RemoteClientStub(
            send_register_code_error=RemoteControlPlaneError(
                status_code=429,
                reason="REGISTER_SEND_RETRY_LATER",
                message="register send is cooling down",
                payload={
                    "error_code": "REGISTER_SEND_RETRY_LATER",
                    "message": "register send is cooling down",
                    "retry_after_seconds": 52,
                },
            )
        ),
        verifier=verifier,
        credential_store=_MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha")),
        secret_store=_MemorySecretStore(),
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.send_register_code("alice@example.com")

    assert result.accepted is False
    assert result.code == "REGISTER_SEND_RETRY_LATER"
    assert result.message == "register send is cooling down"
    assert result.payload == {"retry_after_seconds": 52}


def test_remote_gateway_summary_does_not_probe_registration_readiness_synchronously(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    remote_client = _RemoteClientStub(
        registration_readiness_result=_ReadinessStub(ready=True, registration_flow_version=3),
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=_MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha")),
        secret_store=_MemorySecretStore(),
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
        probe_registration_readiness=True,
    )

    summary = gateway.get_summary()

    assert summary.registration_flow_version == 2
    assert remote_client.registration_readiness_calls == 0


def test_remote_gateway_verify_register_code_returns_remote_message_and_summary(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    gateway = RemoteEntitlementGateway(
        remote_client=_RemoteClientStub(
            verify_register_code_result=_ResultStub(
                message="验证码已验证",
                verification_ticket="ticket_1",
            )
        ),
        verifier=verifier,
        credential_store=_MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha")),
        secret_store=_MemorySecretStore(),
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.verify_register_code(
        email="alice@example.com",
        code="123456",
        register_session_id="register_session_1",
    )

    assert result.accepted is True
    assert result.message == "验证码已验证"
    assert result.summary.registration_flow_version == 3


def test_remote_gateway_complete_register_preserves_remote_success_message_when_snapshot_is_authorized(
    tmp_path: Path,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    credential_store = _MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha"))
    remote_client = _RemoteClientStub(
        complete_register_result=_build_auth_result(
            private_key=private_key,
            kid=kid,
            refresh_token="refresh-token-1",
            snapshot=_build_snapshot(feature_enabled=True, runtime_state="running"),
            message="注册成功",
        ),
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.complete_register(
        email="alice@example.com",
        verification_ticket="ticket_1",
        username="alice",
        password="Secret123!",
    )
    stored_bundle = credential_store.load()

    assert result.accepted is True
    assert result.message == "注册成功"
    assert result.summary.auth_state == "active"
    assert result.summary.last_error_code is None
    assert result.summary.message == "当前程序会员权限有效"
    assert stored_bundle.refresh_credential_ref is not None
    assert secret_store.get(stored_bundle.refresh_credential_ref) == "refresh-token-1"
    assert stored_bundle.entitlement_signature is not None
    assert stored_bundle.entitlement_kid == kid
    assert isinstance(stored_bundle.entitlement_snapshot, dict)
    assert stored_bundle.entitlement_snapshot["runtime_state"] == "running"
    assert stored_bundle.last_error_code is None


def test_remote_gateway_complete_register_falls_back_to_not_member_message_when_snapshot_has_no_program_access(
    tmp_path: Path,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    credential_store = _MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha"))
    remote_client = _RemoteClientStub(
        complete_register_result=_build_auth_result(
            private_key=private_key,
            kid=kid,
            refresh_token="refresh-token-1",
            snapshot=_build_snapshot(feature_enabled=False, runtime_state="stopped"),
            message="注册成功",
        ),
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.complete_register(
        email="alice@example.com",
        verification_ticket="ticket_1",
        username="alice",
        password="Secret123!",
    )

    assert result.accepted is True
    assert result.message == "账号已创建，但当前未开通会员"
    assert result.summary.auth_state == "revoked"
    assert result.summary.last_error_code == "program_feature_not_enabled"
    assert result.summary.message == "当前套餐暂未开放该功能"


def test_remote_gateway_complete_register_rejects_program_snapshot_invalid_when_signature_and_kid_mismatch(
    tmp_path: Path,
) -> None:
    signing_key = Ed25519PrivateKey.generate()
    decoy_key = Ed25519PrivateKey.generate()
    jwks_path = _write_jwks(
        tmp_path,
        {
            "signing-key": signing_key.public_key(),
            "decoy-key": decoy_key.public_key(),
        },
    )
    verifier = EntitlementVerifier(key_cache_path=jwks_path)
    secret_store = _MemorySecretStore()
    credential_store = _MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha"))
    remote_client = _RemoteClientStub(
        # Signature issued by `signing_key` but kid points to `decoy-key`.
        complete_register_result=_build_auth_result(
            private_key=signing_key,
            kid="decoy-key",
            refresh_token="refresh-token-1",
            snapshot=_build_snapshot(feature_enabled=True, runtime_state="running"),
            message="注册成功",
        ),
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.complete_register(
        email="alice@example.com",
        verification_ticket="ticket_1",
        username="alice",
        password="Secret123!",
    )
    stored_bundle = credential_store.load()
    summary = gateway.get_summary()

    assert result.accepted is False
    assert result.code == "program_snapshot_invalid"
    assert summary.last_error_code == "program_snapshot_invalid"
    # clear_auth=True should clear persisted auth material on invalid snapshot.
    assert stored_bundle.refresh_credential_ref is None
    assert stored_bundle.entitlement_snapshot is None
    assert stored_bundle.entitlement_signature is None
    assert stored_bundle.entitlement_kid is None


def test_remote_gateway_send_reset_code_maps_remote_user_not_found_for_route_layer(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    gateway = RemoteEntitlementGateway(
        remote_client=_RemoteClientStub(
            send_reset_code_error=RemoteControlPlaneError(
                status_code=404,
                reason="user_not_found",
                message="用户不存在",
            )
        ),
        verifier=verifier,
        credential_store=_MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha")),
        secret_store=_MemorySecretStore(),
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.send_reset_code("alice@example.com")

    assert result.accepted is False
    assert result.code == "user_not_found"
    assert result.message == "用户不存在"


def test_remote_gateway_reset_password_maps_invalid_credentials_for_route_layer(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    gateway = RemoteEntitlementGateway(
        remote_client=_RemoteClientStub(
            reset_password_error=RemoteControlPlaneError(
                status_code=401,
                reason="invalid_credentials",
                message="验证码错误",
            )
        ),
        verifier=verifier,
        credential_store=_MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha")),
        secret_store=_MemorySecretStore(),
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.reset_password(
        email="alice@example.com",
        code="123456",
        new_password="NewSecret456!",
    )

    assert result.accepted is False
    assert result.code == "invalid_credentials"
    assert result.message == "验证码错误"


@pytest.mark.parametrize(
    ("action", "reason", "message"),
    [
        ("send_register_code", "email_invalid", "邮箱格式错误"),
        ("verify_register_code", "email_code_invalid", "验证码错误"),
        ("complete_register", "register_payload_invalid", "注册参数无效"),
        ("reset_password_code", "email_code_invalid", "验证码错误"),
        ("reset_password_payload", "reset_payload_invalid", "重置参数无效"),
    ],
)
def test_remote_gateway_route_only_actions_passthrough_control_plane_validation_reasons(
    tmp_path: Path,
    action: str,
    reason: str,
    message: str,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    if action == "send_register_code":
        remote_client = _RemoteClientStub(
            send_register_code_error=RemoteControlPlaneError(
                status_code=400,
                reason=reason,
                message=message,
            )
        )
    elif action == "verify_register_code":
        remote_client = _RemoteClientStub(
            verify_register_code_error=RemoteControlPlaneError(
                status_code=400,
                reason=reason,
                message=message,
            )
        )
    elif action == "complete_register":
        remote_client = _RemoteClientStub(
            complete_register_error=RemoteControlPlaneError(
                status_code=400,
                reason=reason,
                message=message,
            )
        )
    else:
        remote_client = _RemoteClientStub(
            reset_password_error=RemoteControlPlaneError(
                status_code=400,
                reason=reason,
                message=message,
            )
        )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=_MemoryCredentialStore(ProgramCredentialBundle(device_id="device-alpha")),
        secret_store=_MemorySecretStore(),
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    if action == "send_register_code":
        result = gateway.send_register_code("alice@example.com")
    elif action == "verify_register_code":
        result = gateway.verify_register_code(
            email="alice@example.com",
            code="123456",
            register_session_id="register_session_1",
        )
    elif action == "complete_register":
        result = gateway.complete_register(
            email="alice@example.com",
            verification_ticket="ticket_1",
            username="alice",
            password="Secret123!",
        )
    else:
        result = gateway.reset_password(
            email="alice@example.com",
            code="123456",
            new_password="NewSecret456!",
        )

    assert result.accepted is False
    assert result.code == reason
    assert result.message == message


def test_remote_gateway_guard_runtime_start_requests_runtime_permit_and_updates_snapshot(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    refresh_ref = secret_store.put("refresh-token-1")
    cached_snapshot = _build_snapshot(feature_enabled=True, runtime_state="stopped")
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=refresh_ref,
            entitlement_snapshot=cached_snapshot,
            entitlement_signature=_sign_snapshot(private_key, cached_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    remote_client = _RemoteClientStub(
        permit_result=_build_permit_result(
            private_key=private_key,
            kid=kid,
            snapshot=_build_snapshot(feature_enabled=True, runtime_state="running"),
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    decision = gateway.guard("runtime.start")
    stored_bundle = credential_store.load()

    assert decision.allowed is True
    assert remote_client.permit_calls == [
        {
            "refresh_token": "refresh-token-1",
            "device_id": "device-alpha",
            "action": "runtime.start",
        }
    ]
    assert isinstance(stored_bundle.entitlement_snapshot, dict)
    assert stored_bundle.entitlement_snapshot["runtime_state"] == "running"
    assert stored_bundle.entitlement_signature is not None
    assert stored_bundle.entitlement_kid == kid


def test_remote_gateway_guard_denies_non_runtime_action_when_program_access_disabled(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    cached_snapshot = _build_snapshot(feature_enabled=False)
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=secret_store.put("refresh-token-1"),
            entitlement_snapshot=cached_snapshot,
            entitlement_signature=_sign_snapshot(private_key, cached_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=_RemoteClientStub(),
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    decision = gateway.guard("query.start")

    assert decision.allowed is False
    assert decision.code == "program_feature_not_enabled"


def test_remote_gateway_guard_denies_browser_query_enable_when_live_refresh_revokes_specific_permission(
    tmp_path: Path,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    cached_snapshot = _build_snapshot(
        feature_enabled=True,
        extra_permissions=["account.browser_query.enable"],
    )
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=secret_store.put("refresh-token-1"),
            entitlement_snapshot=cached_snapshot,
            entitlement_signature=_sign_snapshot(private_key, cached_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    remote_client = _RemoteClientStub(
        refresh_result=_build_auth_result(
            private_key=private_key,
            kid=kid,
            refresh_token="refresh-token-2",
            snapshot=_build_snapshot(feature_enabled=True),
            message="刷新成功",
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    decision = gateway.guard("account.browser_query.enable")

    assert decision.allowed is False
    assert decision.code == "program_feature_not_enabled"
    assert decision.message == "当前此功能未开放"
    assert remote_client.refresh_calls == [
        {
            "refresh_token": "refresh-token-1",
            "device_id": "device-alpha",
        }
    ]


def test_remote_gateway_guard_allows_browser_query_enable_after_live_refresh_grants_permission(
    tmp_path: Path,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    cached_snapshot = _build_snapshot(feature_enabled=True)
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=secret_store.put("refresh-token-1"),
            entitlement_snapshot=cached_snapshot,
            entitlement_signature=_sign_snapshot(private_key, cached_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    remote_client = _RemoteClientStub(
        refresh_result=_build_auth_result(
            private_key=private_key,
            kid=kid,
            refresh_token="refresh-token-2",
            snapshot=_build_snapshot(
                feature_enabled=True,
                extra_permissions=["account.browser_query.enable"],
            ),
            message="刷新成功",
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    decision = gateway.guard("account.browser_query.enable")
    stored_bundle = credential_store.load()

    assert decision.allowed is True
    assert remote_client.refresh_calls == [
        {
            "refresh_token": "refresh-token-1",
            "device_id": "device-alpha",
        }
    ]
    assert isinstance(stored_bundle.entitlement_snapshot, dict)
    assert "account.browser_query.enable" in stored_bundle.entitlement_snapshot["permissions"]


def test_remote_gateway_refresh_maps_remote_unauthorized_to_guarded_summary(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    secret_store = _MemorySecretStore()
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=secret_store.put("refresh-token-1"),
            entitlement_snapshot=_build_snapshot(feature_enabled=True),
            last_error_code=None,
        )
    )
    remote_client = _RemoteClientStub(
        refresh_error=RemoteControlPlaneError(
            status_code=401,
            reason="invalid_refresh_token",
            message="refresh token invalid",
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.refresh(reason="scheduler")

    assert result.accepted is False
    assert result.code == "program_auth_required"
    assert result.summary.last_error_code == "program_auth_required"
    assert result.summary.runtime_state == "stopped"


def test_remote_gateway_refresh_distinguishes_local_refresh_material_read_failure(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    kid = derive_key_id(private_key.public_key())
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    cached_snapshot = _build_snapshot(feature_enabled=True, runtime_state="running")
    secret_store = _ExplodingSecretStore(error=SecretDecryptError("decrypt failed"))
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref="secret:broken",
            entitlement_snapshot=cached_snapshot,
            entitlement_signature=_sign_snapshot(private_key, cached_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=_RemoteClientStub(),
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.refresh(reason="scheduler")
    stored_bundle = credential_store.load()

    assert result.accepted is False
    assert result.code == "refresh_credential_invalid"
    assert result.message == "本地授权材料读取失败，请重新登录程序会员"
    assert result.summary.last_error_code == "refresh_credential_invalid"
    assert result.summary.auth_state == "active"
    assert result.summary.username == "alice"
    assert stored_bundle.refresh_credential_ref == "secret:broken"


def test_remote_gateway_refresh_success_rotates_refresh_token_and_cleans_old_ref(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    old_ref = secret_store.put("refresh-token-old")
    cached_snapshot = _build_snapshot(feature_enabled=True, runtime_state="stopped")
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=old_ref,
            entitlement_snapshot=cached_snapshot,
            entitlement_signature=_sign_snapshot(private_key, cached_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    refreshed_snapshot = _build_snapshot(feature_enabled=True, runtime_state="running")
    remote_client = _RemoteClientStub(
        refresh_result=_build_auth_result(
            private_key=private_key,
            kid=kid,
            refresh_token="refresh-token-new",
            snapshot=refreshed_snapshot,
            message="刷新成功",
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.refresh(reason="scheduler")
    stored_bundle = credential_store.load()

    assert result.accepted is True
    assert stored_bundle.refresh_credential_ref is not None
    assert stored_bundle.refresh_credential_ref != old_ref
    assert secret_store.get(stored_bundle.refresh_credential_ref) == "refresh-token-new"
    assert old_ref in secret_store.deleted_refs
    assert stored_bundle.entitlement_signature is not None
    assert stored_bundle.entitlement_kid == kid
    assert isinstance(stored_bundle.entitlement_snapshot, dict)
    assert stored_bundle.entitlement_snapshot["runtime_state"] == "running"


def test_remote_gateway_guard_rejects_tampered_cached_snapshot(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    original_snapshot = _build_snapshot(feature_enabled=True)
    tampered_snapshot = dict(original_snapshot)
    tampered_snapshot["feature_flags"] = {"program_access_enabled": True}
    tampered_snapshot["runtime_state"] = "running"
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=secret_store.put("refresh-token-1"),
            entitlement_snapshot=tampered_snapshot,
            entitlement_signature=_sign_snapshot(private_key, original_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=_RemoteClientStub(),
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    decision = gateway.guard("query.start")
    summary = gateway.get_summary()

    assert decision.allowed is False
    assert decision.code == "program_snapshot_invalid"
    assert summary.last_error_code == "program_snapshot_invalid"
    assert summary.auth_state is None


def test_remote_gateway_refresh_error_does_not_keep_tampered_runtime_state(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = EntitlementVerifier(key_cache_path=_write_public_key(tmp_path, private_key))
    kid = derive_key_id(private_key.public_key())
    secret_store = _MemorySecretStore()
    original_snapshot = _build_snapshot(feature_enabled=True, runtime_state="stopped")
    tampered_snapshot = dict(original_snapshot)
    tampered_snapshot["runtime_state"] = "running"
    credential_store = _MemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=secret_store.put("refresh-token-1"),
            entitlement_snapshot=tampered_snapshot,
            entitlement_signature=_sign_snapshot(private_key, original_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    remote_client = _RemoteClientStub(
        refresh_error=RemoteControlPlaneError(
            status_code=401,
            reason="invalid_refresh_token",
            message="refresh token invalid",
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_StaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )

    result = gateway.refresh(reason="scheduler")

    assert result.accepted is False
    assert result.summary.runtime_state == "stopped"
    assert result.summary.last_error_code == "program_auth_required"


class _RemoteClientStub:
    def __init__(
        self,
        *,
        login_result: RemoteAuthResult | None = None,
        public_key_pem: str | None = None,
        send_register_code_result: RemoteMessageResult | None = None,
        verify_register_code_result: object | None = None,
        complete_register_result: RemoteAuthResult | None = None,
        registration_readiness_result: object | None = None,
        send_reset_code_result: RemoteMessageResult | None = None,
        reset_password_result: RemoteMessageResult | None = None,
        refresh_result: RemoteAuthResult | None = None,
        permit_result: RemotePermitResult | None = None,
        logout_error: Exception | None = None,
        send_register_code_error: Exception | None = None,
        verify_register_code_error: Exception | None = None,
        complete_register_error: Exception | None = None,
        send_reset_code_error: Exception | None = None,
        reset_password_error: Exception | None = None,
        refresh_error: Exception | None = None,
    ) -> None:
        self._login_result = login_result
        self._public_key_pem = public_key_pem
        self._send_register_code_result = send_register_code_result
        self._verify_register_code_result = verify_register_code_result
        self._complete_register_result = complete_register_result
        self._registration_readiness_result = registration_readiness_result
        self._send_reset_code_result = send_reset_code_result
        self._reset_password_result = reset_password_result
        self._refresh_result = refresh_result
        self._permit_result = permit_result
        self._logout_error = logout_error
        self._send_register_code_error = send_register_code_error
        self._verify_register_code_error = verify_register_code_error
        self._complete_register_error = complete_register_error
        self._send_reset_code_error = send_reset_code_error
        self._reset_password_error = reset_password_error
        self._refresh_error = refresh_error
        self.logout_calls: list[str] = []
        self.refresh_calls: list[dict[str, str]] = []
        self.permit_calls: list[dict[str, object]] = []
        self.send_register_code_calls: list[dict[str, object]] = []
        self.verify_register_code_calls: list[dict[str, object]] = []
        self.complete_register_calls: list[dict[str, object]] = []
        self.registration_readiness_calls = 0
        self.send_reset_code_calls: list[str] = []
        self.reset_password_calls: list[dict[str, str]] = []
        self.public_key_fetch_calls = 0

    def login(self, *, username: str, password: str, device_id: str) -> RemoteAuthResult:
        _ = username
        _ = password
        _ = device_id
        if self._login_result is None:
            raise AssertionError("login result not configured")
        return self._login_result

    def fetch_public_key_pem(self) -> str:
        self.public_key_fetch_calls += 1
        if self._public_key_pem is None:
            raise AssertionError("public key pem not configured")
        return self._public_key_pem

    def logout(self, *, refresh_token: str) -> RemoteMessageResult:
        self.logout_calls.append(refresh_token)
        if self._logout_error is not None:
            raise self._logout_error
        return RemoteMessageResult(message="已退出登录")

    def send_register_code(self, email: str, install_id: str = "") -> RemoteMessageResult:
        self.send_register_code_calls.append(
            {
                "email": email,
                "install_id": install_id,
            }
        )
        if self._send_register_code_error is not None:
            raise self._send_register_code_error
        if self._send_register_code_result is None:
            raise AssertionError("send register code result not configured")
        return self._send_register_code_result

    def verify_register_code(
        self,
        *,
        email: str,
        code: str,
        register_session_id: str,
        install_id: str = "",
    ) -> object:
        self.verify_register_code_calls.append(
            {
                "email": email,
                "code": code,
                "register_session_id": register_session_id,
                "install_id": install_id,
            }
        )
        if self._verify_register_code_error is not None:
            raise self._verify_register_code_error
        if self._verify_register_code_result is None:
            raise AssertionError("verify register code result not configured")
        return self._verify_register_code_result

    def get_registration_readiness(self) -> object:
        self.registration_readiness_calls += 1
        if self._registration_readiness_result is None:
            raise AssertionError("registration readiness result not configured")
        return self._registration_readiness_result

    def refresh(self, *, refresh_token: str, device_id: str) -> RemoteAuthResult:
        self.refresh_calls.append(
            {
                "refresh_token": refresh_token,
                "device_id": device_id,
            }
        )
        if self._refresh_error is not None:
            raise self._refresh_error
        if self._refresh_result is None:
            raise AssertionError("refresh result not configured")
        return self._refresh_result

    def send_reset_code(self, email: str) -> RemoteMessageResult:
        self.send_reset_code_calls.append(email)
        if self._send_reset_code_error is not None:
            raise self._send_reset_code_error
        if self._send_reset_code_result is None:
            raise AssertionError("send reset code result not configured")
        return self._send_reset_code_result

    def reset_password(
        self,
        *,
        email: str,
        code: str,
        new_password: str,
    ) -> RemoteMessageResult:
        self.reset_password_calls.append(
            {
                "email": email,
                "code": code,
                "new_password": new_password,
            }
        )
        if self._reset_password_error is not None:
            raise self._reset_password_error
        if self._reset_password_result is None:
            raise AssertionError("reset password result not configured")
        return self._reset_password_result

    def complete_register(
        self,
        *,
        email: str,
        verification_ticket: str,
        username: str,
        password: str,
        install_id: str = "",
    ) -> RemoteAuthResult:
        self.complete_register_calls.append(
            {
                "email": email,
                "verification_ticket": verification_ticket,
                "username": username,
                "password": password,
                "install_id": install_id,
            }
        )
        if self._complete_register_error is not None:
            raise self._complete_register_error
        if self._complete_register_result is None:
            raise AssertionError("complete register result not configured")
        return self._complete_register_result

    def request_runtime_permit(
        self,
        *,
        refresh_token: str,
        device_id: str,
        action: str,
    ) -> RemotePermitResult:
        self.permit_calls.append(
            {
                "refresh_token": refresh_token,
                "device_id": device_id,
                "action": action,
            }
        )
        if self._permit_result is None:
            raise AssertionError("permit result not configured")
        return self._permit_result


@dataclass
class _MemoryCredentialStore:
    bundle: ProgramCredentialBundle

    def load(self) -> ProgramCredentialBundle:
        return self.bundle

    def save(self, bundle: ProgramCredentialBundle) -> None:
        self.bundle = bundle

    def clear(self) -> None:
        self.bundle = ProgramCredentialBundle(device_id=self.bundle.device_id)


class _MemorySecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self.deleted_refs: list[str] = []
        self._counter = 0

    def put(self, secret: str) -> str:
        self._counter += 1
        ref = f"secret:{self._counter}"
        self._values[ref] = secret
        return ref

    def get(self, ref: str) -> str:
        return self._values[ref]

    def delete(self, ref: str) -> None:
        self.deleted_refs.append(ref)
        self._values.pop(ref, None)


@dataclass
class _ExplodingSecretStore:
    error: Exception

    def put(self, secret: str) -> str:
        _ = secret
        return "secret:broken"

    def get(self, ref: str) -> str:
        _ = ref
        raise self.error

    def delete(self, ref: str) -> None:
        _ = ref


@dataclass(frozen=True)
class _StaticDeviceIdStore:
    value: str

    def load_or_create(self) -> str:
        return self.value


def _build_auth_result(
    *,
    private_key: Ed25519PrivateKey,
    kid: str,
    refresh_token: str,
    snapshot: dict[str, object],
    message: str,
) -> RemoteAuthResult:
    signature = _sign_snapshot(private_key, snapshot)
    return RemoteAuthResult(
        message=message,
        auth_bundle=RemoteAuthBundle(
            refresh_token=refresh_token,
            snapshot=snapshot,
            signature=signature,
            kid=kid,
        ),
        user={"id": "user-1"},
    )


def _build_permit_result(
    *,
    private_key: Ed25519PrivateKey,
    kid: str,
    snapshot: dict[str, object],
) -> RemotePermitResult:
    signature = _sign_snapshot(private_key, snapshot)
    return RemotePermitResult(
        message="运行许可已签发",
        permit=RemoteRuntimePermit(
            snapshot=snapshot,
            signature=signature,
            kid=kid,
        ),
    )


def _build_snapshot(
    *,
    feature_enabled: bool,
    runtime_state: str = "stopped",
    extra_permissions: list[str] | None = None,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    permissions = ["runtime.start"] if feature_enabled else []
    if feature_enabled:
        permissions.append("program_access_enabled")
    if extra_permissions:
        permissions.extend(extra_permissions)
    return {
        "username": "alice",
        "sub": "user-1",
        "membership_plan": "member" if feature_enabled else "inactive",
        "device_id": "device-alpha",
        "permissions": sorted(set(permissions)),
        "feature_flags": {
            "program_access_enabled": feature_enabled,
        },
        "runtime_state": runtime_state,
        "iat": _to_iso_z(now - timedelta(minutes=1)),
        "exp": _to_iso_z(now + timedelta(minutes=20)),
    }


def _to_iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _write_public_key(tmp_path: Path, private_key: Ed25519PrivateKey) -> Path:
    key_path = tmp_path / "control-plane-public.pem"
    key_path.write_text(_build_public_key_pem(private_key), encoding="utf-8")
    return key_path


def _write_jwks(
    tmp_path: Path,
    keys: dict[str, Ed25519PublicKey],
) -> Path:
    jwks_path = tmp_path / "control-plane-public.jwks.json"
    jwks_path.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "kty": "OKP",
                        "crv": "Ed25519",
                        "kid": kid,
                        "x": _to_base64url(public_key.public_bytes_raw()),
                    }
                    for kid, public_key in keys.items()
                ]
            }
        ),
        encoding="utf-8",
    )
    return jwks_path


def _to_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _build_public_key_pem(private_key: Ed25519PrivateKey) -> str:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _sign_snapshot(private_key: Ed25519PrivateKey, snapshot: dict[str, object]) -> str:
    return base64.b64encode(private_key.sign(stable_stringify(snapshot).encode("utf-8"))).decode("ascii")


@dataclass(frozen=True)
class _ResultStub:
    message: str
    verification_ticket: str


@dataclass(frozen=True)
class _ReadinessStub:
    ready: bool
    registration_flow_version: int
