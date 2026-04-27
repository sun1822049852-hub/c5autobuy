from __future__ import annotations

import copy
import threading
import time

from app_backend.infrastructure.program_access.program_credential_bundle import ProgramCredentialBundle
from app_backend.infrastructure.program_access.remote_control_plane_client import RemoteControlPlaneTransportError
from app_backend.infrastructure.program_access.runtime_control_service import RuntimeControlService


def _wait_until(predicate, *, timeout: float = 1.0, interval: float = 0.01) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


class _FakeCredentialStore:
    def __init__(self, bundle: ProgramCredentialBundle) -> None:
        self.bundle = bundle

    def load(self) -> ProgramCredentialBundle:
        return self.bundle


class _FakeSecretStore:
    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = dict(secrets)

    def get(self, ref: str) -> str:
        return self._secrets[ref]


class _FakeDeviceIdStore:
    def __init__(self, device_id: str) -> None:
        self._device_id = device_id

    def load_or_create(self) -> str:
        return self._device_id


class _ScriptedRemoteClient:
    def __init__(self, attempts: list[list[object]]) -> None:
        self._attempts = [list(attempt) for attempt in attempts]
        self.calls: list[dict[str, object]] = []

    def stream_runtime_control_events(
        self,
        *,
        refresh_token: str,
        device_id: str,
        read_timeout_seconds: float = 0.0,
    ):
        self.calls.append(
            {
                "refresh_token": refresh_token,
                "device_id": device_id,
                "read_timeout_seconds": read_timeout_seconds,
            }
        )
        attempt = self._attempts.pop(0) if self._attempts else []
        for step in attempt:
            if isinstance(step, tuple) and step and step[0] == "sleep":
                time.sleep(float(step[1]))
                continue
            if isinstance(step, BaseException):
                raise step
            yield step


def _build_service(
    remote_client: _ScriptedRemoteClient,
    *,
    bundle: ProgramCredentialBundle | None = None,
    grace_seconds: float = 0.05,
    reconnect_delay_seconds: float = 0.01,
) -> tuple[RuntimeControlService, list[str], _FakeCredentialStore]:
    snapshot = {
        "membership_plan": "member",
        "permissions": ["program_access_enabled", "runtime.start"],
        "feature_flags": {
            "program_access_enabled": True,
        },
    }
    credential_store = _FakeCredentialStore(
        bundle
        or ProgramCredentialBundle(
            device_id="device-alpha",
            refresh_credential_ref="refresh-ref-1",
            entitlement_snapshot=copy.deepcopy(snapshot),
            entitlement_signature="signature",
            entitlement_kid="kid",
            last_error_code="program_ok",
        )
    )
    secret_store = _FakeSecretStore({"refresh-ref-1": "refresh-token-1"})
    device_id_store = _FakeDeviceIdStore("device-alpha")
    callbacks: list[str] = []
    service = RuntimeControlService(
        remote_client=remote_client,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=device_id_store,
        on_force_stop=callbacks.append,
        grace_seconds=grace_seconds,
        reconnect_delay_seconds=reconnect_delay_seconds,
        read_timeout_seconds=0.01,
    )
    return service, callbacks, credential_store


def test_runtime_control_service_triggers_force_stop_once_on_revoke() -> None:
    remote_client = _ScriptedRemoteClient(
        [
            [
                {"event": "hello", "data": {"stream_version": "runtime-control/v1"}},
                {"event": "runtime.revoke", "data": {"reason": "user_disabled"}},
            ]
        ]
    )
    service, callbacks, _credential_store = _build_service(remote_client)

    service.start()
    try:
        assert _wait_until(lambda: callbacks == ["program_runtime_revoked"])
        assert callbacks == ["program_runtime_revoked"]
    finally:
        service.stop()


def test_runtime_control_service_keeps_running_during_short_jitter_inside_grace() -> None:
    remote_client = _ScriptedRemoteClient(
        [
            [
                {"event": "hello", "data": {"stream_version": "runtime-control/v1"}},
                RemoteControlPlaneTransportError("temporary disconnect"),
            ],
            [
                {"event": "hello", "data": {"stream_version": "runtime-control/v1"}},
                RemoteControlPlaneTransportError("temporary disconnect again"),
            ],
            [
                {"event": "hello", "data": {"stream_version": "runtime-control/v1"}},
                RemoteControlPlaneTransportError("temporary disconnect third"),
            ],
        ]
    )
    service, callbacks, _credential_store = _build_service(remote_client, grace_seconds=0.2)

    service.start()
    try:
        time.sleep(0.05)
        assert callbacks == []
    finally:
        service.stop()

    assert callbacks == []


def test_runtime_control_service_stops_after_keepalive_silence_exceeds_grace() -> None:
    remote_client = _ScriptedRemoteClient(
        [
            [
                {"event": "hello", "data": {"stream_version": "runtime-control/v1"}},
                ("sleep", 0.02),
                RemoteControlPlaneTransportError("read timeout"),
            ],
            [
                ("sleep", 0.02),
                RemoteControlPlaneTransportError("read timeout again"),
            ],
            [
                ("sleep", 0.02),
                RemoteControlPlaneTransportError("read timeout third"),
            ],
        ]
    )
    service, callbacks, _credential_store = _build_service(remote_client, grace_seconds=0.05)

    service.start()
    try:
        assert _wait_until(lambda: callbacks == ["program_runtime_control_unreachable"])
        assert callbacks == ["program_runtime_control_unreachable"]
    finally:
        service.stop()


def test_runtime_control_service_transport_loss_does_not_rewrite_program_access_summary() -> None:
    snapshot = {
        "membership_plan": "member",
        "permissions": ["program_access_enabled", "runtime.start"],
        "feature_flags": {
            "program_access_enabled": True,
        },
    }
    bundle = ProgramCredentialBundle(
        device_id="device-alpha",
        refresh_credential_ref="refresh-ref-1",
        entitlement_snapshot=copy.deepcopy(snapshot),
        entitlement_signature="signature",
        entitlement_kid="kid",
        last_error_code="program_ok",
    )
    remote_client = _ScriptedRemoteClient(
        [
            [
                {"event": "hello", "data": {"stream_version": "runtime-control/v1"}},
                ("sleep", 0.02),
                RemoteControlPlaneTransportError("read timeout"),
            ],
            [
                ("sleep", 0.02),
                RemoteControlPlaneTransportError("read timeout again"),
            ],
            [
                ("sleep", 0.02),
                RemoteControlPlaneTransportError("read timeout third"),
            ],
        ]
    )
    service, callbacks, credential_store = _build_service(
        remote_client,
        bundle=bundle,
        grace_seconds=0.05,
    )

    service.start()
    try:
        assert _wait_until(lambda: callbacks == ["program_runtime_control_unreachable"])
    finally:
        service.stop()

    assert credential_store.load().last_error_code == "program_ok"
    assert credential_store.load().entitlement_snapshot == snapshot


def test_runtime_control_service_does_not_emit_duplicate_stop_on_normal_local_stop() -> None:
    remote_client = _ScriptedRemoteClient(
        [
            [
                {"event": "hello", "data": {"stream_version": "runtime-control/v1"}},
                ("sleep", 0.2),
            ]
        ]
    )
    service, callbacks, _credential_store = _build_service(remote_client, grace_seconds=0.3)

    service.start()
    time.sleep(0.02)
    service.stop()

    assert callbacks == []
