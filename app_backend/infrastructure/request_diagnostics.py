from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware


def append_request_diagnostic(
    log_path: Path,
    payload: dict[str, object],
) -> Path:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{json.dumps(payload, ensure_ascii=False)}\n")
    return log_path


class RequestTraceRecorder:
    def __init__(self) -> None:
        self._name: str | None = None
        self._details: dict[str, object] = {}
        self._phase_order: list[str] = []
        self._phases: dict[str, dict[str, float | int]] = {}

    def set_name(self, name: str | None) -> None:
        normalized = str(name or "").strip()
        if normalized:
            self._name = normalized

    def set_detail(self, key: str, value: object) -> None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return
        self._details[normalized_key] = value

    def increment_detail(self, key: str, amount: int = 1) -> None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return
        current = self._details.get(normalized_key, 0)
        if not isinstance(current, int):
            current = 0
        self._details[normalized_key] = current + int(amount)

    def record_duration(self, name: str, duration_ms: float) -> None:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            return
        phase = self._phases.get(normalized_name)
        if phase is None:
            phase = {
                "count": 0,
                "total_ms": 0.0,
                "max_ms": 0.0,
            }
            self._phases[normalized_name] = phase
            self._phase_order.append(normalized_name)
        phase["count"] = int(phase["count"]) + 1
        phase["total_ms"] = float(phase["total_ms"]) + max(float(duration_ms), 0.0)
        phase["max_ms"] = max(float(phase["max_ms"]), max(float(duration_ms), 0.0))

    @contextmanager
    def measure(self, name: str):
        started_at = time.perf_counter()
        try:
            yield
        finally:
            self.record_duration(name, (time.perf_counter() - started_at) * 1000)

    def snapshot(self) -> dict[str, object] | None:
        if not self._name and not self._details and not self._phases:
            return None
        payload: dict[str, object] = {}
        if self._name:
            payload["name"] = self._name
        if self._details:
            payload["details"] = dict(self._details)
        if self._phases:
            payload["phases"] = [
                {
                    "name": phase_name,
                    "count": int(phase["count"]),
                    "total_ms": round(float(phase["total_ms"]), 3),
                    "max_ms": round(float(phase["max_ms"]), 3),
                }
                for phase_name in self._phase_order
                for phase in [self._phases[phase_name]]
            ]
        return payload


def get_request_trace_recorder(request, *, name: str | None = None) -> RequestTraceRecorder | None:
    state = getattr(request, "state", None)
    recorder = getattr(state, "request_trace_recorder", None)
    if isinstance(recorder, RequestTraceRecorder) and name:
        recorder.set_name(name)
    return recorder if isinstance(recorder, RequestTraceRecorder) else None


class RequestDiagnosticsMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        log_path: Path,
        slow_ms: float = 2_000,
        append_fn=append_request_diagnostic,
    ) -> None:
        super().__init__(app)
        self._log_path = Path(log_path)
        self._slow_ms = max(float(slow_ms), 0.0)
        self._append_fn = append_fn

    async def dispatch(self, request, call_next):
        started_at = datetime.now().isoformat(timespec="milliseconds")
        started_perf = time.perf_counter()
        if getattr(request, "state", None) is not None:
            request.state.request_trace_recorder = RequestTraceRecorder()
        request_completed = asyncio.Event()
        inflight_watchdog = self._create_inflight_watchdog(
            request=request,
            started_at=started_at,
            started_perf=started_perf,
            request_completed=request_completed,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            await self._finish_inflight_watchdog(request_completed, inflight_watchdog)
            duration_ms = round((time.perf_counter() - started_perf) * 1000, 2)
            self._append(
                request,
                {
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "event": "request_exception",
                    "started_at": started_at,
                    "duration_ms": duration_ms,
                    "method": request.method,
                    "path": request.url.path,
                    "query_string": request.url.query or "",
                    "status_code": None,
                    "client_host": request.client.host if request.client else None,
                    "thread_id": threading.get_ident(),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            raise

        await self._finish_inflight_watchdog(request_completed, inflight_watchdog)
        duration_ms = round((time.perf_counter() - started_perf) * 1000, 2)
        trace_payload = self._trace_payload(request)
        if response.status_code >= 500 or duration_ms >= self._slow_ms:
            self._append(
                request,
                {
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "event": "error_response" if response.status_code >= 500 else "slow_request",
                    "started_at": started_at,
                    "duration_ms": duration_ms,
                    "method": request.method,
                    "path": request.url.path,
                    "query_string": request.url.query or "",
                    "status_code": int(response.status_code),
                    "client_host": request.client.host if request.client else None,
                    "thread_id": threading.get_ident(),
                    "error_type": None,
                    "error_message": None,
                }
            )
        elif trace_payload is not None and trace_payload.get("name"):
            self._append(
                request,
                {
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "event": "request_trace",
                    "started_at": started_at,
                    "duration_ms": duration_ms,
                    "method": request.method,
                    "path": request.url.path,
                    "query_string": request.url.query or "",
                    "status_code": int(response.status_code),
                    "client_host": request.client.host if request.client else None,
                    "thread_id": threading.get_ident(),
                    "error_type": None,
                    "error_message": None,
                },
                trace_payload=trace_payload,
            )
        return response

    def _create_inflight_watchdog(self, *, request, started_at: str, started_perf: float, request_completed: asyncio.Event):
        if self._slow_ms <= 0:
            return None
        return asyncio.create_task(
            self._watch_inflight_request(
                request=request,
                started_at=started_at,
                started_perf=started_perf,
                request_completed=request_completed,
            )
        )

    async def _watch_inflight_request(
        self,
        *,
        request,
        started_at: str,
        started_perf: float,
        request_completed: asyncio.Event,
    ) -> None:
        try:
            await asyncio.wait_for(request_completed.wait(), timeout=self._slow_ms / 1000)
        except asyncio.TimeoutError:
            duration_ms = round((time.perf_counter() - started_perf) * 1000, 2)
            self._append(
                request,
                {
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "event": "request_inflight_timeout",
                    "started_at": started_at,
                    "duration_ms": duration_ms,
                    "method": request.method,
                    "path": request.url.path,
                    "query_string": request.url.query or "",
                    "status_code": None,
                    "client_host": request.client.host if request.client else None,
                    "thread_id": threading.get_ident(),
                    "error_type": None,
                    "error_message": None,
                }
            )

    @staticmethod
    async def _finish_inflight_watchdog(request_completed: asyncio.Event, inflight_watchdog: asyncio.Task | None) -> None:
        request_completed.set()
        if inflight_watchdog is None:
            return
        inflight_watchdog.cancel()
        try:
            await inflight_watchdog
        except asyncio.CancelledError:
            pass

    def _trace_payload(self, request) -> dict[str, object] | None:
        trace_recorder = get_request_trace_recorder(request)
        return trace_recorder.snapshot() if trace_recorder is not None else None

    def _append(self, request, payload: dict[str, object], *, trace_payload: dict[str, object] | None = None) -> None:
        if trace_payload is None:
            trace_payload = self._trace_payload(request)
        if trace_payload is not None:
            payload = dict(payload)
            payload["trace"] = trace_payload
        self._append_fn(self._log_path, payload)
