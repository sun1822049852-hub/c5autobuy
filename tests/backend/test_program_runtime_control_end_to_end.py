from __future__ import annotations

import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app_backend.infrastructure.program_access.program_credential_bundle import ProgramCredentialBundle
from app_backend.infrastructure.program_access.remote_control_plane_client import (
    RemoteControlPlaneClient,
    RemoteControlPlaneError,
)
from app_backend.infrastructure.program_access.runtime_control_service import RuntimeControlService


def _wait_until(predicate, *, timeout: float = 2.0, interval: float = 0.02) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


class _FakeCredentialStore:
    def __init__(self, bundle: ProgramCredentialBundle) -> None:
        self._bundle = bundle

    def load(self) -> ProgramCredentialBundle:
        return self._bundle


class _FakeSecretStore:
    def __init__(self, refresh_token: str) -> None:
        self._refresh_token = refresh_token

    def get(self, ref: str) -> str:
        assert ref == "refresh-ref-1"
        return self._refresh_token


class _FakeDeviceIdStore:
    def __init__(self, device_id: str) -> None:
        self._device_id = device_id

    def load_or_create(self) -> str:
        return self._device_id


@contextmanager
def _running_control_plane_server():
    repo_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="program-control-plane-e2e-") as temp_dir:
        db_path = Path(temp_dir) / "control-plane.sqlite"
        port_path = Path(temp_dir) / "port.txt"
        node_script = """
const fs = require("node:fs");
const {createServer} = require(process.argv[1]);
const dbPath = process.argv[2];
const portPath = process.argv[3];
const server = createServer({
  dbPath,
  now() {
    return new Date();
  },
  runtimeControlKeepaliveMs: 50,
  codeGenerator() {
    return "123456";
  },
  mailConfigFactory() {
    return {
      configured: true,
      authCodeTtlMinutes: 5,
      refreshSessionDays: 30,
      adminSessionHours: 12,
    };
  },
  mailServiceFactory() {
    return {
      async sendVerificationCode() {
        return {messageId: "msg_1"};
      },
    };
  },
});
server.listen(0, "127.0.0.1", () => {
  const address = server.address();
  fs.writeFileSync(portPath, String(address.port), "utf8");
});
function shutdown() {
  server.close(() => process.exit(0));
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
""".strip()
        process = subprocess.Popen(
            [
                "node",
                "-e",
                node_script,
                str(repo_root / "program_admin_console/src/server.js"),
                str(db_path),
                str(port_path),
            ],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.time() + 10.0
            while time.time() < deadline:
                if port_path.exists():
                    break
                if process.poll() is not None:
                    break
                time.sleep(0.05)
            if not port_path.exists():
                stdout, stderr = process.communicate(timeout=1.0)
                raise AssertionError(
                    "control plane test server failed to start\n"
                    f"stdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                )
            port = int(port_path.read_text(encoding="utf-8").strip())
            yield f"http://127.0.0.1:{port}"
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5.0)


def _bootstrap_admin(base_url: str) -> dict[str, str]:
    with httpx.Client(base_url=base_url, timeout=5.0, trust_env=False) as client:
        bootstrap = client.post(
            "/api/admin/bootstrap",
            json={"username": "ops", "password": "Root123!"},
        )
        assert bootstrap.status_code == 200, bootstrap.text
        login = client.post(
            "/api/admin/login",
            json={"username": "ops", "password": "Root123!"},
        )
        assert login.status_code == 200, login.text
        token = login.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


def _register_user(
    base_url: str,
    *,
    email: str,
    username: str,
    password: str,
    device_id: str,
) -> dict[str, object]:
    with httpx.Client(base_url=base_url, timeout=5.0, trust_env=False) as http_client:
        client = RemoteControlPlaneClient(
            base_url=base_url,
            client=http_client,
            timeout=5.0,
            verify=False,
        )
        send_result = client.send_register_code(email, install_id=device_id)
        assert send_result.register_session_id
        verify_result = client.verify_register_code(
            email=email,
            code="123456",
            register_session_id=send_result.register_session_id,
            install_id=device_id,
        )
        complete_result = client.complete_register(
            email=email,
            verification_ticket=verify_result.verification_ticket,
            username=username,
            password=password,
            install_id=device_id,
        )
    return {
        "refresh_token": complete_result.auth_bundle.refresh_token,
        "user": complete_result.user,
    }


def _login_user(
    base_url: str,
    *,
    username: str,
    password: str,
    device_id: str,
) -> str:
    with httpx.Client(base_url=base_url, timeout=5.0, trust_env=False) as http_client:
        client = RemoteControlPlaneClient(
            base_url=base_url,
            client=http_client,
            timeout=5.0,
            verify=False,
        )
        result = client.login(
            username=username,
            password=password,
            device_id=device_id,
        )
    return result.auth_bundle.refresh_token


def _find_user(base_url: str, admin_headers: dict[str, str], *, username: str) -> dict[str, object]:
    with httpx.Client(base_url=base_url, timeout=5.0, trust_env=False) as client:
        response = client.get("/api/admin/users", headers=admin_headers)
        assert response.status_code == 200, response.text
        items = response.json()["items"]
    for item in items:
        if item["username"] == username:
            return item
    raise AssertionError(f"user not found in admin list: {username}")


def _patch_user_membership(
    base_url: str,
    admin_headers: dict[str, str],
    *,
    user_id: int,
    expires_at: str,
) -> None:
    with httpx.Client(base_url=base_url, timeout=5.0, trust_env=False) as client:
        response = client.patch(
            f"/api/admin/users/{user_id}",
            headers=admin_headers,
            json={
                "membership_plan": "member",
                "membership_expires_at": expires_at,
                "permission_overrides": [],
            },
        )
        assert response.status_code == 200, response.text


def _build_runtime_control_service(
    *,
    base_url: str,
    refresh_token: str,
    device_id: str,
    callbacks: list[str],
) -> tuple[RemoteControlPlaneClient, RuntimeControlService]:
    http_client = httpx.Client(base_url=base_url, timeout=2.0, trust_env=False)
    remote_client = RemoteControlPlaneClient(
        base_url=base_url,
        client=http_client,
        timeout=2.0,
        verify=False,
    )
    service = RuntimeControlService(
        remote_client=remote_client,
        credential_store=_FakeCredentialStore(
            ProgramCredentialBundle(
                device_id=device_id,
                refresh_credential_ref="refresh-ref-1",
                entitlement_snapshot={
                    "membership_plan": "member",
                    "permissions": ["program_access_enabled", "runtime.start"],
                    "feature_flags": {"program_access_enabled": True},
                },
                entitlement_signature="signature",
                entitlement_kid="kid",
                last_error_code="program_ok",
            )
        ),
        secret_store=_FakeSecretStore(refresh_token),
        device_id_store=_FakeDeviceIdStore(device_id),
        on_force_stop=callbacks.append,
        grace_seconds=0.1,
        reconnect_delay_seconds=0.02,
        read_timeout_seconds=0.2,
    )
    return remote_client, service


def test_runtime_permit_denies_immediately_after_membership_expiry() -> None:
    with _running_control_plane_server() as base_url:
        admin_headers = _bootstrap_admin(base_url)
        registration = _register_user(
            base_url,
            email="expiry@example.com",
            username="expiry_user",
            password="Secret123!",
            device_id="device-expiry",
        )
        user = _find_user(base_url, admin_headers, username="expiry_user")
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=3)
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        _patch_user_membership(base_url, admin_headers, user_id=int(user["id"]), expires_at=expires_at)
        refresh_token = _login_user(
            base_url,
            username="expiry_user",
            password="Secret123!",
            device_id="device-expiry",
        )

        with httpx.Client(base_url=base_url, timeout=2.0, trust_env=False) as http_client:
            client = RemoteControlPlaneClient(
                base_url=base_url,
                client=http_client,
                timeout=2.0,
                verify=False,
            )
            permit = client.request_runtime_permit(
                refresh_token=refresh_token,
                device_id="device-expiry",
            )
            assert permit.permit.snapshot["action"] == "runtime.start"

            time.sleep(3.2)

            with pytest.raises(RemoteControlPlaneError) as exc_info:
                client.request_runtime_permit(
                    refresh_token=refresh_token,
                    device_id="device-expiry",
                )

        assert exc_info.value.status_code == 403
        assert exc_info.value.reason == "runtime_permission_denied"
        expired_user = _find_user(base_url, admin_headers, username="expiry_user")
        assert expired_user["entitlements"]["membership_active"] is False
        assert expired_user["entitlements"]["membership_plan"] == "inactive"


def test_runtime_control_service_receives_runtime_revoke_from_real_control_plane() -> None:
    with _running_control_plane_server() as base_url:
        admin_headers = _bootstrap_admin(base_url)
        registration = _register_user(
            base_url,
            email="runtime-revoke@example.com",
            username="runtime_revoke_user",
            password="Secret123!",
            device_id="device-runtime-revoke",
        )
        user = _find_user(base_url, admin_headers, username="runtime_revoke_user")
        _patch_user_membership(
            base_url,
            admin_headers,
            user_id=int(user["id"]),
            expires_at="2099-01-01T00:00:00.000Z",
        )
        refresh_token = _login_user(
            base_url,
            username="runtime_revoke_user",
            password="Secret123!",
            device_id="device-runtime-revoke",
        )

        callbacks: list[str] = []
        remote_client, service = _build_runtime_control_service(
            base_url=base_url,
            refresh_token=refresh_token,
            device_id="device-runtime-revoke",
            callbacks=callbacks,
        )
        service.start()
        try:
            with httpx.Client(base_url=base_url, timeout=5.0, trust_env=False) as client:
                response = client.patch(
                    f"/api/admin/users/{int(user['id'])}",
                    headers=admin_headers,
                    json={
                        "membership_plan": "inactive",
                        "permission_overrides": [],
                    },
                )
                assert response.status_code == 200, response.text

            assert _wait_until(lambda: callbacks == ["program_runtime_revoked"])
        finally:
            service.stop()
            remote_client.close()


def test_runtime_control_service_receives_device_revoke_from_real_control_plane() -> None:
    with _running_control_plane_server() as base_url:
        admin_headers = _bootstrap_admin(base_url)
        registration = _register_user(
            base_url,
            email="device-revoke@example.com",
            username="device_revoke_user",
            password="Secret123!",
            device_id="device-revoke-target",
        )
        user = _find_user(base_url, admin_headers, username="device_revoke_user")
        _patch_user_membership(
            base_url,
            admin_headers,
            user_id=int(user["id"]),
            expires_at="2099-01-01T00:00:00.000Z",
        )
        refresh_token = _login_user(
            base_url,
            username="device_revoke_user",
            password="Secret123!",
            device_id="device-revoke-target",
        )

        callbacks: list[str] = []
        remote_client, service = _build_runtime_control_service(
            base_url=base_url,
            refresh_token=refresh_token,
            device_id="device-revoke-target",
            callbacks=callbacks,
        )
        service.start()
        try:
            with httpx.Client(base_url=base_url, timeout=5.0, trust_env=False) as client:
                devices = client.get(
                    f"/api/admin/users/{int(user['id'])}/devices",
                    headers=admin_headers,
                )
                assert devices.status_code == 200, devices.text
                items = devices.json()["items"]
                target_device = next(
                    item for item in items if item["device_id"] == "device-revoke-target"
                )
                revoke = client.post(
                    f"/api/admin/users/{int(user['id'])}/devices/{int(target_device['id'])}/revoke",
                    headers=admin_headers,
                    json={},
                )
                assert revoke.status_code == 200, revoke.text

            assert _wait_until(lambda: callbacks == ["program_runtime_revoked"])
        finally:
            service.stop()
            remote_client.close()
