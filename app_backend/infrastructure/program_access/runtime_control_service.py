from __future__ import annotations

import threading
import time

from .remote_control_plane_client import (
    RemoteControlPlaneError,
    RemoteControlPlaneTransportError,
)


class RuntimeControlService:
    def __init__(
        self,
        *,
        remote_client,
        credential_store,
        secret_store,
        device_id_store=None,
        on_force_stop=None,
        grace_seconds: float = 5.0,
        reconnect_delay_seconds: float = 0.5,
        read_timeout_seconds: float = 2.5,
        time_fn=None,
    ) -> None:
        self._remote_client = remote_client
        self._credential_store = credential_store
        self._secret_store = secret_store
        self._device_id_store = device_id_store
        self._on_force_stop = on_force_stop
        self._grace_seconds = max(float(grace_seconds), 0.01)
        self._reconnect_delay_seconds = max(float(reconnect_delay_seconds), 0.0)
        self._read_timeout_seconds = max(float(read_timeout_seconds), 0.01)
        self._time = time_fn or time.monotonic
        self._thread_lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._force_stop_emitted = False

    def set_on_force_stop(self, callback) -> None:
        self._on_force_stop = callback

    def start(self) -> None:
        with self._thread_lock:
            thread = self._thread
            if thread is not None and thread.is_alive():
                return
            self._force_stop_emitted = False
            self._stop_event = threading.Event()
            worker = threading.Thread(
                target=self._run,
                name="program-runtime-control-service",
                daemon=True,
            )
            self._thread = worker
            worker.start()

    def stop(self, *, timeout: float = 1.0) -> None:
        with self._thread_lock:
            thread = self._thread
            stop_event = self._stop_event
        stop_event.set()
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(float(timeout), 0.0))
        with self._thread_lock:
            if self._thread is thread:
                self._thread = None

    def _run(self) -> None:
        disconnect_started_at: float | None = None
        while not self._stop_event.is_set():
            credentials = self._load_credentials()
            if credentials is None:
                self._emit_force_stop("program_runtime_control_unreachable")
                return
            refresh_token, device_id = credentials
            try:
                for frame in self._remote_client.stream_runtime_control_events(
                    refresh_token=refresh_token,
                    device_id=device_id,
                    read_timeout_seconds=self._read_timeout_seconds,
                ):
                    if self._stop_event.is_set():
                        return
                    disconnect_started_at = None
                    event_name = getattr(frame, "event", None)
                    if isinstance(frame, dict):
                        event_name = frame.get("event")
                    if event_name == "runtime.revoke":
                        self._emit_force_stop("program_runtime_revoked")
                        return
                if self._stop_event.is_set():
                    return
                if disconnect_started_at is None:
                    disconnect_started_at = self._time()
            except (RemoteControlPlaneTransportError, RemoteControlPlaneError):
                if self._stop_event.is_set():
                    return
                if disconnect_started_at is None:
                    disconnect_started_at = self._time()
            except Exception:
                if self._stop_event.is_set():
                    return
                if disconnect_started_at is None:
                    disconnect_started_at = self._time()

            if disconnect_started_at is not None and (self._time() - disconnect_started_at) >= self._grace_seconds:
                self._emit_force_stop("program_runtime_control_unreachable")
                return
            self._stop_event.wait(self._reconnect_delay_seconds)

    def _load_credentials(self) -> tuple[str, str] | None:
        bundle = self._credential_store.load()
        refresh_ref = getattr(bundle, "refresh_credential_ref", None)
        if not isinstance(refresh_ref, str) or not refresh_ref:
            return None
        try:
            refresh_token = self._secret_store.get(refresh_ref)
        except Exception:
            return None
        device_id = getattr(bundle, "device_id", None)
        if (not isinstance(device_id, str) or not device_id) and self._device_id_store is not None:
            load_or_create = getattr(self._device_id_store, "load_or_create", None)
            if callable(load_or_create):
                device_id = load_or_create()
        if not isinstance(device_id, str) or not device_id:
            return None
        return refresh_token, device_id

    def _emit_force_stop(self, reason: str) -> None:
        if self._stop_event.is_set() or self._force_stop_emitted:
            return
        self._force_stop_emitted = True
        callback = self._on_force_stop
        if not callable(callback):
            return
        try:
            callback(str(reason))
        except Exception:
            return
