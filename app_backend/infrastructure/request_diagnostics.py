from __future__ import annotations

import asyncio
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
        if response.status_code >= 500 or duration_ms >= self._slow_ms:
            self._append(
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

    def _append(self, payload: dict[str, object]) -> None:
        self._append_fn(self._log_path, payload)
