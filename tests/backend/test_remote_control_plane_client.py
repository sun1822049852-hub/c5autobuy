from __future__ import annotations

import base64
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app_backend.infrastructure.program_access.entitlement_verifier import (
    EntitlementVerifier,
    derive_key_id,
)
from app_backend.infrastructure.program_access.remote_control_plane_client import (
    RemoteAuthBundle,
    RemoteControlPlaneClient,
    RemoteControlPlaneError,
)

FIXED_NOW = datetime(2026, 4, 20, 8, 0, 0, tzinfo=timezone.utc)


def test_send_register_code_maps_success_message() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"ok": True, "expires_in_seconds": 300})

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://control-plane.test",
    ) as http_client:
        client = RemoteControlPlaneClient(
            base_url="https://control-plane.test",
            client=http_client,
        )

        result = client.send_register_code("alice@example.com")

    assert captured["path"] == "/api/auth/email/send-code"
    assert captured["body"] == {"email": "alice@example.com"}
    assert result.message == "注册验证码已发送"
    assert result.expires_in_seconds == 300


def test_fetch_public_key_pem_maps_success_response() -> None:
    captured: dict[str, object] = {}
    public_key_pem = "-----BEGIN PUBLIC KEY-----\\nTEST\\n-----END PUBLIC KEY-----\\n"

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "ok": True,
                "public_key_pem": public_key_pem,
                "kid": "ed25519-2026-04",
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://control-plane.test",
    ) as http_client:
        client = RemoteControlPlaneClient(
            base_url="https://control-plane.test",
            client=http_client,
        )

        result = client.fetch_public_key_pem()

    assert captured["path"] == "/api/auth/public-key"
    assert result == public_key_pem


def test_login_returns_typed_auth_bundle() -> None:
    snapshot = _build_snapshot()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "refresh_token": "refresh-token-1",
                "access_bundle": {
                    "snapshot": snapshot,
                    "signature": "c2lnbmF0dXJl",
                    "kid": "ed25519-2026-04",
                },
                "user": {
                    "id": "user-1",
                    "username": "alice",
                    "membership_plan": "member",
                },
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://control-plane.test",
    ) as http_client:
        client = RemoteControlPlaneClient(
            base_url="https://control-plane.test",
            client=http_client,
        )

        result = client.login(
            username="alice",
            password="Secret123!",
            device_id="device-alpha",
        )

    assert result.message == "登录成功"
    assert isinstance(result.auth_bundle, RemoteAuthBundle)
    assert result.auth_bundle.refresh_token == "refresh-token-1"
    assert result.auth_bundle.snapshot["username"] == "alice"
    assert result.auth_bundle.signature == "c2lnbmF0dXJl"
    assert result.auth_bundle.kid == "ed25519-2026-04"


def test_runtime_permit_maps_http_error_reason() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "ok": False,
                "reason": "runtime_permission_denied",
                "message": "runtime permission denied",
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://control-plane.test",
    ) as http_client:
        client = RemoteControlPlaneClient(
            base_url="https://control-plane.test",
            client=http_client,
        )

        with pytest.raises(RemoteControlPlaneError) as exc_info:
            client.request_runtime_permit(
                refresh_token="refresh-token-1",
                device_id="device-alpha",
            )

    assert exc_info.value.status_code == 403
    assert exc_info.value.reason == "runtime_permission_denied"
    assert exc_info.value.message == "runtime permission denied"


def test_client_raises_domain_error_for_malformed_success_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "expires_in_seconds": "300"})

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://control-plane.test",
    ) as http_client:
        client = RemoteControlPlaneClient(
            base_url="https://control-plane.test",
            client=http_client,
        )

        with pytest.raises(RemoteControlPlaneError) as exc_info:
            client.send_register_code("alice@example.com")

    assert exc_info.value.reason == "invalid_response"
    assert exc_info.value.status_code == 200


def test_client_raises_domain_error_for_non_object_json_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://control-plane.test",
    ) as http_client:
        client = RemoteControlPlaneClient(
            base_url="https://control-plane.test",
            client=http_client,
        )

        with pytest.raises(RemoteControlPlaneError) as exc_info:
            client.send_register_code("alice@example.com")

    assert exc_info.value.reason == "invalid_response"
    assert exc_info.value.status_code == 200


def test_client_raises_domain_error_for_malformed_error_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"ok": False, "reason": 123})

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://control-plane.test",
    ) as http_client:
        client = RemoteControlPlaneClient(
            base_url="https://control-plane.test",
            client=http_client,
        )

        with pytest.raises(RemoteControlPlaneError) as exc_info:
            client.request_runtime_permit(
                refresh_token="refresh-token-1",
                device_id="device-alpha",
            )

    assert exc_info.value.reason == "invalid_response"
    assert exc_info.value.status_code == 403


def test_entitlement_verifier_accepts_signed_snapshot_from_pem_file_with_matching_kid(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    pem_path = _write_public_key(tmp_path, private_key)
    verifier = EntitlementVerifier(key_cache_path=pem_path)
    snapshot = _build_snapshot()
    envelope = _sign_envelope(
        private_key,
        snapshot,
        kid=derive_key_id(private_key.public_key()),
    )

    result = verifier.verify(envelope, now=FIXED_NOW)

    assert result.ok is True
    assert result.snapshot == snapshot


def test_entitlement_verifier_rejects_missing_or_unknown_kid_for_pem_cache(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    pem_path = _write_public_key(tmp_path, private_key)
    verifier = EntitlementVerifier(key_cache_path=pem_path)
    envelope = _sign_envelope(
        private_key,
        _build_snapshot(),
        kid=derive_key_id(private_key.public_key()),
    )

    missing_kid_result = verifier.verify(
        {key: value for key, value in envelope.items() if key != "kid"},
        now=FIXED_NOW,
    )
    unknown_kid_result = verifier.verify(
        {**envelope, "kid": "ed25519:unknown-key"},
        now=FIXED_NOW,
    )

    assert missing_kid_result.ok is False
    assert missing_kid_result.reason == "kid_missing"
    assert unknown_kid_result.ok is False
    assert unknown_kid_result.reason == "kid_unknown"


def test_entitlement_verifier_rejects_bad_signature(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    pem_path = _write_public_key(tmp_path, private_key)
    verifier = EntitlementVerifier(key_cache_path=pem_path)
    envelope = _sign_envelope(
        private_key,
        _build_snapshot(),
        kid=derive_key_id(private_key.public_key()),
    )
    snapshot_with_bad_signature = {
        **envelope,
        "signature": base64.b64encode(
            Ed25519PrivateKey.generate().sign(
                _stable_stringify(envelope["snapshot"]).encode("utf-8")
            )
        ).decode("ascii"),
    }

    assert verifier.verify(snapshot_with_bad_signature, now=FIXED_NOW).ok is False


def test_entitlement_verifier_uses_explicit_jwks_kid_mapping(tmp_path: Path) -> None:
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
    envelope = _sign_envelope(signing_key, _build_snapshot(), kid="signing-key")

    known_result = verifier.verify(envelope, now=FIXED_NOW)
    unknown_result = verifier.verify({**envelope, "kid": "unknown-key"}, now=FIXED_NOW)

    assert known_result.ok is True
    assert unknown_result.ok is False
    assert unknown_result.reason == "kid_unknown"


def test_entitlement_verifier_rejects_expired_snapshot(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    pem_path = _write_public_key(tmp_path, private_key)
    verifier = EntitlementVerifier(key_cache_path=pem_path)
    snapshot = _build_snapshot(
        iat=FIXED_NOW - timedelta(minutes=10),
        exp=FIXED_NOW - timedelta(seconds=1),
    )
    envelope = _sign_envelope(
        private_key,
        snapshot,
        kid=derive_key_id(private_key.public_key()),
    )

    result = verifier.verify(envelope, now=FIXED_NOW)

    assert result.ok is False
    assert result.reason == "expired"


def test_entitlement_verifier_accepts_real_node_signer_bundle(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    private_key_path = tmp_path / "entitlement-private.pem"
    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pem_path = _write_public_key(tmp_path, private_key)
    verifier = EntitlementVerifier(key_cache_path=pem_path)
    envelope = _issue_node_bundle(private_key_path)

    result = verifier.verify(envelope, now=FIXED_NOW)

    assert result.ok is True
    assert result.snapshot is not None
    assert result.snapshot["device_id"] == "device-alpha"
    assert result.kid == envelope["kid"]


def _write_public_key(tmp_path: Path, private_key: Ed25519PrivateKey) -> Path:
    pem_path = tmp_path / "control-plane-public.pem"
    pem_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return pem_path


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


def _sign_envelope(
    private_key: Ed25519PrivateKey,
    snapshot: dict[str, object],
    *,
    kid: str,
) -> dict[str, object]:
    return {
        "snapshot": snapshot,
        "signature": base64.b64encode(
            private_key.sign(_stable_stringify(snapshot).encode("utf-8"))
        ).decode("ascii"),
        "kid": kid,
    }


def _issue_node_bundle(private_key_path: Path) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[2]
    node_script = """
const {createEntitlementSigner} = require(process.argv[1]);
const privateKeyFile = process.argv[2];
const fixedNow = process.argv[3];
const signer = createEntitlementSigner({
  privateKeyFile,
  now: () => new Date(fixedNow)
});
const bundle = signer.issueBundle({
  user: {
    id: "user-1",
    username: "alice",
    membership_plan: "member"
  },
  deviceId: "device-alpha",
  permissions: ["runtime.start", "program_access_enabled"],
  featureFlags: {
    nested: {beta: false, alpha: true},
    program_access_enabled: true
  }
});
process.stdout.write(JSON.stringify(bundle));
""".strip()
    completed = subprocess.run(
        [
            "node",
            "-e",
            node_script,
            str(repo_root / "program_admin_console/src/entitlementSigner.js"),
            str(private_key_path),
            FIXED_NOW.isoformat().replace("+00:00", "Z"),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return json.loads(completed.stdout)


def _build_snapshot(
    *,
    iat: datetime | None = None,
    exp: datetime | None = None,
) -> dict[str, object]:
    return {
        "username": "alice",
        "sub": "user-1",
        "membership_plan": "member",
        "device_id": "device-alpha",
        "permissions": ["runtime.start", "program_access_enabled"],
        "feature_flags": {
            "nested": {"beta": False, "alpha": True},
            "program_access_enabled": True,
        },
        "iat": _to_iso_z(iat or (FIXED_NOW - timedelta(minutes=1))),
        "exp": _to_iso_z(exp or (FIXED_NOW + timedelta(minutes=10))),
    }


def _to_iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


def _stable_stringify(value: object) -> str:
    if isinstance(value, list):
        return "[" + ",".join(_stable_stringify(item) for item in value) + "]"
    if isinstance(value, dict):
        parts = [
            f"{json.dumps(key, ensure_ascii=False, separators=(',', ':'))}:{_stable_stringify(value[key])}"
            for key in sorted(value)
        ]
        return "{" + ",".join(parts) + "}"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _to_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
