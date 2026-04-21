from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from typing import Protocol

from app_backend.application.program_access import (
    PROGRAM_REFRESH_FAILED_CODE,
    PROGRAM_REFRESH_FAILED_MESSAGE,
    ProgramAccessActionResult,
    ProgramAccessSummary,
)


class RefreshableGateway(Protocol):
    def refresh(self, *, reason: str) -> ProgramAccessActionResult: ...

    def get_summary(self) -> ProgramAccessSummary: ...


@dataclass
class RefreshScheduler:
    gateway: RefreshableGateway
    interval_seconds: float = 300.0

    def __post_init__(self) -> None:
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._lock = Lock()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.trigger_now("startup")
        self._thread = Thread(
            target=self._run_loop,
            name="program-access-refresh-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def trigger_now(self, reason: str) -> ProgramAccessActionResult:
        with self._lock:
            try:
                return self.gateway.refresh(reason=reason)
            except Exception:
                summary = _safe_summary(self.gateway)
                return ProgramAccessActionResult.reject(
                    summary=summary,
                    code=PROGRAM_REFRESH_FAILED_CODE,
                    message=PROGRAM_REFRESH_FAILED_MESSAGE,
                )

    def _run_loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            self.trigger_now("interval")


def _safe_summary(gateway: RefreshableGateway) -> ProgramAccessSummary:
    try:
        base = gateway.get_summary()
        return ProgramAccessSummary(
            mode=base.mode,
            stage=base.stage,
            guard_enabled=base.guard_enabled,
            message=PROGRAM_REFRESH_FAILED_MESSAGE,
            auth_state=base.auth_state,
            runtime_state=base.runtime_state,
            grace_expires_at=base.grace_expires_at,
            last_error_code=PROGRAM_REFRESH_FAILED_CODE,
        )
    except Exception:
        return ProgramAccessSummary(
            mode="remote_entitlement",
            stage="packaged_release",
            guard_enabled=True,
            message=PROGRAM_REFRESH_FAILED_MESSAGE,
            auth_state=None,
            runtime_state="stopped",
            grace_expires_at=None,
            last_error_code=PROGRAM_REFRESH_FAILED_CODE,
        )
