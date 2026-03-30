from __future__ import annotations

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

        try:
            response = await call_next(request)
        except Exception as exc:
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

    def _append(self, payload: dict[str, object]) -> None:
        self._append_fn(self._log_path, payload)
