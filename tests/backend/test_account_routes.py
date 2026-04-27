from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app_backend.domain.enums.account_states import PurchaseCapabilityState
from app_backend.infrastructure.program_access.entitlement_verifier import (
    EntitlementVerifier,
    derive_key_id,
    stable_stringify,
)
from app_backend.infrastructure.program_access.program_credential_bundle import ProgramCredentialBundle
from app_backend.infrastructure.program_access.remote_control_plane_client import (
    RemoteAuthBundle,
    RemoteAuthResult,
)
from app_backend.infrastructure.program_access.remote_entitlement_gateway import RemoteEntitlementGateway


def _account_payload(*, remark_name, browser_proxy_mode="direct", browser_proxy_url=None, api_proxy_mode="direct", api_proxy_url=None, api_key=None):
    return {
        "remark_name": remark_name,
        "browser_proxy_mode": browser_proxy_mode,
        "browser_proxy_url": browser_proxy_url,
        "api_proxy_mode": api_proxy_mode,
        "api_proxy_url": api_proxy_url,
        "api_key": api_key,
    }


class _DenyProgramAccessGateway:
    def __init__(self, *, code: str, message: str) -> None:
        self._code = code
        self._message = message

    def guard(self, action: str):
        _ = action
        return type(
            "Decision",
            (),
            {
                "allowed": False,
                "code": self._code,
                "message": self._message,
            },
        )()


class _RouteRemoteClientStub:
    def __init__(self, *, refresh_result: RemoteAuthResult) -> None:
        self._refresh_result = refresh_result
        self.refresh_calls: list[dict[str, str]] = []

    def refresh(self, *, refresh_token: str, device_id: str) -> RemoteAuthResult:
        self.refresh_calls.append(
            {
                "refresh_token": refresh_token,
                "device_id": device_id,
            }
        )
        return self._refresh_result


@dataclass
class _RouteMemoryCredentialStore:
    bundle: ProgramCredentialBundle

    def load(self) -> ProgramCredentialBundle:
        return self.bundle

    def save(self, bundle: ProgramCredentialBundle) -> None:
        self.bundle = bundle

    def clear(self) -> None:
        self.bundle = ProgramCredentialBundle(device_id=self.bundle.device_id)


class _RouteMemorySecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._counter = 0

    def put(self, secret: str) -> str:
        self._counter += 1
        ref = f"secret:{self._counter}"
        self._values[ref] = secret
        return ref

    def get(self, ref: str) -> str:
        return self._values[ref]


@dataclass(frozen=True)
class _RouteStaticDeviceIdStore:
    value: str

    def load_or_create(self) -> str:
        return self.value


def _build_program_access_snapshot(
    *,
    feature_enabled: bool,
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
        "runtime_state": "stopped",
        "iat": _to_iso_z(now - timedelta(minutes=1)),
        "exp": _to_iso_z(now + timedelta(minutes=20)),
    }


def _build_remote_auth_result(
    *,
    private_key: Ed25519PrivateKey,
    kid: str,
    refresh_token: str,
    snapshot: dict[str, object],
) -> RemoteAuthResult:
    return RemoteAuthResult(
        message="刷新成功",
        auth_bundle=RemoteAuthBundle(
            refresh_token=refresh_token,
            snapshot=snapshot,
            signature=_sign_snapshot(private_key, snapshot),
            kid=kid,
        ),
        user={"id": "user-1"},
    )


def _build_live_browser_query_gateway(
    tmp_path: Path,
    *,
    cached_snapshot: dict[str, object],
    refreshed_snapshot: dict[str, object],
) -> tuple[RemoteEntitlementGateway, _RouteRemoteClientStub]:
    private_key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "control-plane-public.pem"
    key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    verifier = EntitlementVerifier(key_cache_path=key_path)
    kid = derive_key_id(private_key.public_key())
    secret_store = _RouteMemorySecretStore()
    credential_store = _RouteMemoryCredentialStore(
        ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref=secret_store.put("refresh-token-1"),
            entitlement_snapshot=cached_snapshot,
            entitlement_signature=_sign_snapshot(private_key, cached_snapshot),
            entitlement_kid=kid,
            last_error_code=None,
        )
    )
    remote_client = _RouteRemoteClientStub(
        refresh_result=_build_remote_auth_result(
            private_key=private_key,
            kid=kid,
            refresh_token="refresh-token-2",
            snapshot=refreshed_snapshot,
        )
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=_RouteStaticDeviceIdStore("device-alpha"),
        stage="packaged_release",
    )
    return gateway, remote_client


def _sign_snapshot(private_key: Ed25519PrivateKey, snapshot: dict[str, object]) -> str:
    return base64.b64encode(private_key.sign(stable_stringify(snapshot).encode("utf-8"))).decode("ascii")


def _to_iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


async def test_post_accounts_creates_account(client):
    response = await client.post(
        "/accounts",
        json=_account_payload(remark_name="测试备注", api_key="key-123"),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["remark_name"] == "测试备注"
    assert payload["api_key"] == "key-123"
    assert payload["purchase_capability_state"] == "unbound"
    assert payload["purchase_pool_state"] == "not_connected"
    assert payload["default_name"]
    assert payload["new_api_enabled"] is True
    assert payload["fast_api_enabled"] is True
    assert payload["token_enabled"] is True
    assert payload["api_query_disabled_reason"] is None
    assert payload["browser_query_disabled_reason"] is None


async def test_post_accounts_treats_blank_custom_proxy_as_direct(client):
    response = await client.post(
        "/accounts",
        json=_account_payload(
            remark_name="测试备注",
            browser_proxy_mode="custom",
            browser_proxy_url="   ",
            api_proxy_mode="custom",
            api_proxy_url="   ",
            api_key=None,
        ),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["browser_proxy_mode"] == "direct"
    assert payload["browser_proxy_url"] is None
    assert payload["api_proxy_mode"] == "direct"
    assert payload["api_proxy_url"] is None
    assert payload["api_key"] is None


async def test_get_accounts_returns_created_accounts(client):
    await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key=None),
    )

    response = await client.get("/accounts")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["display_name"] == "账号A"


async def test_patch_account_updates_allowed_fields(client):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name=None, api_key=None),
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}",
        json=_account_payload(
            remark_name="新备注",
            browser_proxy_mode="custom",
            browser_proxy_url="http://127.0.0.1:8080",
            api_proxy_mode="custom",
            api_proxy_url="http://127.0.0.1:8080",
            api_key="new-key",
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remark_name"] == "新备注"
    assert payload["browser_proxy_url"] == "http://127.0.0.1:8080"
    assert payload["api_proxy_url"] == "http://127.0.0.1:8080"
    assert payload["api_key"] == "new-key"


async def test_patch_account_normalizes_scheme_less_proxy_and_auth(client):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name=None, api_key=None),
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}",
        json=_account_payload(
            remark_name=None,
            browser_proxy_mode="custom",
            browser_proxy_url="user:pass@127.0.0.1:8080",
            api_proxy_mode="custom",
            api_proxy_url="user:pass@127.0.0.1:8080",
            api_key=None,
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["browser_proxy_mode"] == "custom"
    assert payload["browser_proxy_url"] == "http://user:pass@127.0.0.1:8080"
    assert payload["api_proxy_mode"] == "custom"
    assert payload["api_proxy_url"] == "http://user:pass@127.0.0.1:8080"


async def test_patch_account_refreshes_query_runtime_accounts(client, app):
    class FakeQueryRuntimeService:
        def __init__(self) -> None:
            self.calls = 0

        def refresh_runtime_accounts(self) -> None:
            self.calls += 1

    app.state.query_runtime_service = FakeQueryRuntimeService()
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key="key-123"),
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}",
        json=_account_payload(
            remark_name="账号A-变更",
            browser_proxy_mode="custom",
            browser_proxy_url="http://127.0.0.1:18080",
            api_proxy_mode="custom",
            api_proxy_url="http://127.0.0.1:18081",
            api_key="key-456",
        ),
    )

    assert response.status_code == 200
    assert app.state.query_runtime_service.calls == 1


async def test_patch_account_query_modes_updates_api_and_browser_flags(client):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key=None),
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "api_query_enabled": False,
            "api_query_disabled_reason": "manual_disabled",
            "browser_query_enabled": False,
            "browser_query_disabled_reason": "manual_disabled",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["new_api_enabled"] is False
    assert payload["fast_api_enabled"] is False
    assert payload["token_enabled"] is False
    assert payload["api_query_disabled_reason"] == "manual_disabled"
    assert payload["browser_query_disabled_reason"] == "manual_disabled"


async def test_patch_account_query_modes_supports_partial_browser_toggle(client):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key="key-123"),
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "browser_query_enabled": False,
            "browser_query_disabled_reason": "manual_disabled",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["new_api_enabled"] is True
    assert payload["fast_api_enabled"] is True
    assert payload["token_enabled"] is False
    assert payload["api_query_disabled_reason"] is None
    assert payload["browser_query_disabled_reason"] == "manual_disabled"


async def test_patch_account_query_modes_requires_entitlement_to_enable_browser_query(client, app):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key="key-123"),
    )
    account_id = created.json()["account_id"]
    app.state.account_repository.update_account(
        account_id,
        token_enabled=False,
        browser_query_disabled_reason="manual_disabled",
    )
    app.state.program_access_gateway = _DenyProgramAccessGateway(
        code="program_feature_not_enabled",
        message="当前此功能未开放",
    )

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "browser_query_enabled": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "program_feature_not_enabled",
        "message": "当前此功能未开放",
        "action": "account.browser_query.enable",
    }
    stored = app.state.account_repository.get_account(account_id)
    assert stored is not None
    assert stored.token_enabled is False
    assert stored.browser_query_disabled_reason == "manual_disabled"


async def test_patch_account_query_modes_uses_live_remote_refresh_to_allow_browser_query_enable(
    client,
    app,
    tmp_path: Path,
):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key="key-123"),
    )
    account_id = created.json()["account_id"]
    app.state.account_repository.update_account(
        account_id,
        token_enabled=False,
        browser_query_disabled_reason="manual_disabled",
    )
    gateway, remote_client = _build_live_browser_query_gateway(
        tmp_path,
        cached_snapshot=_build_program_access_snapshot(feature_enabled=True),
        refreshed_snapshot=_build_program_access_snapshot(
            feature_enabled=True,
            extra_permissions=["account.browser_query.enable"],
        ),
    )
    app.state.program_access_gateway = gateway

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "browser_query_enabled": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_enabled"] is True
    assert payload["browser_query_disabled_reason"] is None
    assert remote_client.refresh_calls == [
        {
            "refresh_token": "refresh-token-1",
            "device_id": "device-alpha",
        }
    ]


async def test_patch_account_query_modes_does_not_trust_stale_browser_query_permission_snapshot(
    client,
    app,
    tmp_path: Path,
):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key="key-123"),
    )
    account_id = created.json()["account_id"]
    app.state.account_repository.update_account(
        account_id,
        token_enabled=False,
        browser_query_disabled_reason="manual_disabled",
    )
    gateway, remote_client = _build_live_browser_query_gateway(
        tmp_path,
        cached_snapshot=_build_program_access_snapshot(
            feature_enabled=True,
            extra_permissions=["account.browser_query.enable"],
        ),
        refreshed_snapshot=_build_program_access_snapshot(feature_enabled=True),
    )
    app.state.program_access_gateway = gateway

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "browser_query_enabled": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "program_feature_not_enabled",
        "message": "当前此功能未开放",
        "action": "account.browser_query.enable",
    }
    stored = app.state.account_repository.get_account(account_id)
    assert stored is not None
    assert stored.token_enabled is False
    assert stored.browser_query_disabled_reason == "manual_disabled"
    assert remote_client.refresh_calls == [
        {
            "refresh_token": "refresh-token-1",
            "device_id": "device-alpha",
        }
    ]


async def test_patch_account_query_modes_still_allows_disabling_browser_query_without_entitlement(client, app):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key="key-123"),
    )
    account_id = created.json()["account_id"]
    app.state.program_access_gateway = _DenyProgramAccessGateway(
        code="program_feature_not_enabled",
        message="当前此功能未开放",
    )

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "browser_query_enabled": False,
            "browser_query_disabled_reason": "manual_disabled",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_enabled"] is False
    assert payload["browser_query_disabled_reason"] == "manual_disabled"


async def test_patch_account_query_modes_refreshes_query_runtime_accounts(client, app):
    class FakeQueryRuntimeService:
        def __init__(self) -> None:
            self.calls = 0

        def refresh_runtime_accounts(self) -> None:
            self.calls += 1

    app.state.query_runtime_service = FakeQueryRuntimeService()
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key="key-123"),
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "api_query_enabled": False,
            "api_query_disabled_reason": "manual_disabled",
        },
    )

    assert response.status_code == 200
    assert app.state.query_runtime_service.calls == 1


async def test_clear_purchase_capability_keeps_api_key(client, app):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key="key-123"),
    )
    account_id = created.json()["account_id"]
    repository = app.state.account_repository
    repository.update_account(
        account_id,
        c5_user_id="10001",
        c5_nick_name="nick",
        cookie_raw="cookie=value",
        purchase_capability_state=PurchaseCapabilityState.BOUND,
    )

    response = await client.post(f"/accounts/{account_id}/purchase-capability/clear")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key"] == "key-123"
    assert payload["c5_user_id"] is None
    assert payload["cookie_raw"] is None
    assert payload["purchase_capability_state"] == "unbound"


async def test_delete_account_removes_record(client):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key=None),
    )
    account_id = created.json()["account_id"]

    delete_response = await client.delete(f"/accounts/{account_id}")
    list_response = await client.get("/accounts")

    assert delete_response.status_code == 204
    assert list_response.json() == []


async def test_delete_account_removes_active_session_bundle(app, client):
    created = await client.post(
        "/accounts",
        json=_account_payload(remark_name="账号A", api_key=None),
    )
    account_id = created.json()["account_id"]
    bundle_repository = app.state.account_session_bundle_repository
    staged = bundle_repository.stage_bundle(
        account_id=account_id,
        captured_c5_user_id="10001",
        payload={"cookie_raw": "cookie=value"},
    )
    verified = bundle_repository.mark_bundle_verified(staged.bundle_id)
    bundle_repository.activate_bundle(verified.bundle_id, account_id=account_id)

    delete_response = await client.delete(f"/accounts/{account_id}")

    assert delete_response.status_code == 204
    assert bundle_repository.get_active_bundle(account_id) is None
