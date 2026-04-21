from __future__ import annotations

from dataclasses import dataclass

from app_backend.application.program_access import ProgramAccessActionResult, ProgramAccessSummary
from app_backend.infrastructure.program_access.refresh_scheduler import RefreshScheduler


def test_refresh_scheduler_trigger_now_calls_gateway_refresh_with_reason() -> None:
    gateway = _RecordingGateway()
    scheduler = RefreshScheduler(gateway=gateway, interval_seconds=60.0)

    result = scheduler.trigger_now("manual-test")

    assert gateway.reasons == ["manual-test"]
    assert result.accepted is True
    assert result.summary.mode == "remote_entitlement"


def test_refresh_scheduler_start_triggers_startup_refresh_once() -> None:
    gateway = _RecordingGateway()
    scheduler = RefreshScheduler(gateway=gateway, interval_seconds=9999.0)

    scheduler.start()
    scheduler.stop()

    assert gateway.reasons[0] == "startup"


def test_refresh_scheduler_trigger_now_converts_gateway_exception_to_guarded_result() -> None:
    gateway = _RecordingGateway(raise_error=True)
    scheduler = RefreshScheduler(gateway=gateway, interval_seconds=60.0)

    result = scheduler.trigger_now("manual-error")

    assert result.accepted is False
    assert result.code == "program_refresh_failed"
    assert result.summary.last_error_code == "program_refresh_failed"


@dataclass
class _RecordingGateway:
    raise_error: bool = False

    def __post_init__(self) -> None:
        self.reasons: list[str] = []

    def refresh(self, *, reason: str) -> ProgramAccessActionResult:
        self.reasons.append(reason)
        if self.raise_error:
            raise RuntimeError("refresh exploded")
        return ProgramAccessActionResult.accept(
            summary=ProgramAccessSummary(
                mode="remote_entitlement",
                stage="packaged_release",
                guard_enabled=True,
                message="ok",
                auth_state="active",
                runtime_state="stopped",
                grace_expires_at=None,
                last_error_code=None,
            )
        )
