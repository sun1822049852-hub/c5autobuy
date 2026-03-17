from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import uvicorn

from app_backend.main import create_app


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LocalBackendServer:
    def __init__(self, *, db_path: Path, host: str = "127.0.0.1", port: int | None = None) -> None:
        self._db_path = db_path
        self._host = host
        self._port = port or _find_free_port()
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def start(self, timeout: float = 10.0) -> None:
        if self._thread is not None:
            return

        app = create_app(db_path=self._db_path)
        config = uvicorn.Config(
            app,
            host=self._host,
            port=self._port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        deadline = time.monotonic() + timeout
        while not server.started:
            if not thread.is_alive():
                raise RuntimeError("本地后端启动失败")
            if time.monotonic() > deadline:
                server.should_exit = True
                thread.join(timeout=1.0)
                raise TimeoutError("等待本地后端启动超时")
            time.sleep(0.05)

        self._server = server
        self._thread = thread

    def stop(self, timeout: float = 5.0) -> None:
        if self._server is None or self._thread is None:
            return

        self._server.should_exit = True
        self._thread.join(timeout=timeout)
        self._server = None
        self._thread = None

