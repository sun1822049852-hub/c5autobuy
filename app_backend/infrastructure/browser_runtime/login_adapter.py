from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import threading
from threading import Thread as BlockingThread
import time
from typing import Any, Awaitable, Callable
from uuid import uuid4

from app_backend.infrastructure.browser_runtime.cdp_session_reader import read_attached_session
from app_backend.infrastructure.browser_runtime.login_execution_result import (
    CapturedLoginIdentity,
    LoginExecutionResult,
    StagedBundleRef,
)
from app_backend.infrastructure.browser_runtime.account_browser_profile_store import (
    AccountBrowserProfileStore,
)
from app_backend.infrastructure.browser_runtime.edge_launch_support import (
    DEFAULT_EDGE_PROFILE_DIRECTORY,
    SUCCESS_URL_PATTERN,
    build_proxy_plugin,
    remove_temp_path,
    reserve_debug_port,
    wait_for_debugger_port,
)
from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

ProgressCallback = Callable[[str], Awaitable[None] | None]
LoginRunner = Callable[..., Awaitable["LoginCapture | LoginExecutionResult | dict[str, Any]"]]


async def _noop_emit(_: str) -> None:
    return None


async def _safe_emit(callback: ProgressCallback, state: str) -> None:
    result = callback(state)
    if asyncio.iscoroutine(result):
        await result


@dataclass(slots=True)
class LoginCapture:
    c5_user_id: str
    c5_nick_name: str
    cookie_raw: str


class BrowserLoginAdapter:
    def __init__(
        self,
        *,
        login_runner: LoginRunner,
    ) -> None:
        self._login_runner = login_runner

    async def run_login(
        self,
        *,
        proxy_url: str | None,
        account_id: str | None = None,
        emit_state: ProgressCallback | None = None,
    ) -> LoginExecutionResult:
        callback = emit_state or _noop_emit
        payload = await self._login_runner(
            proxy_url=proxy_url,
            account_id=account_id,
            emit_state=callback,
        )
        return self._normalize_payload(payload)

    @staticmethod
    def _normalize_payload(
        payload: LoginCapture | LoginExecutionResult | dict[str, Any],
    ) -> LoginExecutionResult:
        if isinstance(payload, LoginExecutionResult):
            return payload
        if isinstance(payload, LoginCapture):
            captured_login = CapturedLoginIdentity(
                c5_user_id=payload.c5_user_id,
                c5_nick_name=payload.c5_nick_name,
                cookie_raw=payload.cookie_raw,
            )
            return LoginExecutionResult(
                captured_login=captured_login,
                session_payload=captured_login.to_dict(),
            )

        staged_bundle_ref = None
        raw_bundle_ref = payload.get("staged_bundle_ref")
        if isinstance(raw_bundle_ref, dict) and raw_bundle_ref.get("bundle_id"):
            staged_bundle_ref = StagedBundleRef(
                bundle_id=str(raw_bundle_ref.get("bundle_id") or ""),
                state=str(raw_bundle_ref.get("state") or ""),
            )

        captured_login = CapturedLoginIdentity(
            c5_user_id=str(payload.get("c5_user_id") or ""),
            c5_nick_name=str(payload.get("c5_nick_name") or ""),
            cookie_raw=str(payload.get("cookie_raw") or ""),
        )
        session_payload = dict(payload)
        session_payload.setdefault("c5_user_id", captured_login.c5_user_id)
        session_payload.setdefault("c5_nick_name", captured_login.c5_nick_name)
        session_payload.setdefault("cookie_raw", captured_login.cookie_raw)
        return LoginExecutionResult(
            captured_login=captured_login,
            session_payload=session_payload,
            staged_bundle_ref=staged_bundle_ref,
        )


class ManagedEdgeCdpLoginRunner:
    OPEN_API_URL = "https://www.c5game.com/user/user/open-api"

    def __init__(
        self,
        *,
        runtime: ManagedBrowserRuntime,
        profile_store: AccountBrowserProfileStore | None = None,
        login_timeout_seconds: float = 600.0,
        poll_interval_seconds: float = 1.5,
        close_delay_seconds: float = 600.0,
    ) -> None:
        self._runtime = runtime
        self._profile_store = profile_store
        self._login_timeout_seconds = float(login_timeout_seconds)
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._close_delay_seconds = float(close_delay_seconds)

    async def run(
        self,
        *,
        proxy_url: str | None,
        account_id: str | None = None,
        emit_state: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        callback = emit_state or _noop_emit
        remove_session_root = True
        account_profile_root: Path | None = None
        if self._profile_store is not None and str(account_id or "").strip():
            account_profile_root = self._profile_store.ensure_account_profile(str(account_id))
            session_root = self._profile_store.clone_session(
                str(account_id),
                session_name=f"login-{account_id}-{uuid4().hex}",
            )
        else:
            session_root = self._runtime.session_root / f"session-{uuid4().hex}"
        cleanup_callbacks: list[Callable[[], None]] = []
        browser_process: subprocess.Popen[Any] | None = None
        debugger_address = ""
        captured = False
        try:
            browser_process, debugger_address = await self._run_blocking(
                self._launch_browser,
                session_root=session_root,
                proxy_url=proxy_url,
                cleanup_callbacks=cleanup_callbacks,
            )
            await _safe_emit(callback, "waiting_for_scan")
            payload = await self._wait_for_login_capture(
                debugger_address=debugger_address,
                browser_process=browser_process,
            )
            payload["debugger_address"] = debugger_address
            if account_profile_root is not None and account_id is not None:
                self._profile_store.persist_session(str(account_id), session_root)
                payload.update(AccountBrowserProfileStore.build_profile_payload(account_profile_root))
            await _safe_emit(callback, "captured_login_info")
            captured = True
            self._schedule_delayed_cleanup(
                process=browser_process,
                session_root=session_root,
                cleanup_callbacks=cleanup_callbacks,
                remove_session_root=True,
            )
            return payload
        finally:
            if not captured:
                await self._run_blocking(self._terminate_process, browser_process)
                await self._run_blocking(self._run_cleanup_callbacks, cleanup_callbacks)
                if remove_session_root:
                    await self._run_blocking(shutil.rmtree, session_root, True)

    def _launch_browser(
        self,
        *,
        session_root: Path,
        proxy_url: str | None,
        cleanup_callbacks: list[Callable[[], None]],
    ) -> tuple[subprocess.Popen[Any], str]:
        edge_path = str(Path(self._runtime.resolve_browser_executable()).expanduser().resolve())
        session_root = Path(session_root).expanduser().resolve()
        session_root.mkdir(parents=True, exist_ok=True)
        port = reserve_debug_port()
        command = self._build_launch_command(
            edge_path=edge_path,
            port=port,
            session_root=session_root,
            proxy_url=proxy_url,
            cleanup_callbacks=cleanup_callbacks,
        )
        browser_process = subprocess.Popen(command)
        try:
            wait_for_debugger_port(port, process=browser_process)
        except Exception as exc:
            self._terminate_process(browser_process)
            raise RuntimeError("无法启动登录浏览器") from exc
        return browser_process, f"127.0.0.1:{port}"

    def _build_launch_command(
        self,
        *,
        edge_path: str,
        port: int,
        session_root: Path,
        proxy_url: str | None,
        cleanup_callbacks: list[Callable[[], None]],
    ) -> list[str]:
        command = [
            edge_path,
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={session_root}",
            f"--profile-directory={DEFAULT_EDGE_PROFILE_DIRECTORY}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--new-window",
        ]

        normalized_proxy = str(proxy_url or "").strip()
        if normalized_proxy and normalized_proxy.lower() != "direct":
            plugin_path = build_proxy_plugin(normalized_proxy)
            if plugin_path is not None:
                cleanup_callbacks.append(lambda path=plugin_path: remove_temp_path(path))
                command.extend(
                    [
                        f"--disable-extensions-except={plugin_path}",
                        f"--load-extension={plugin_path}",
                    ]
                )
            else:
                pure_proxy = re.sub(r"https?://[^@]*@", "", normalized_proxy)
                pure_proxy = re.sub(r"^https?://", "", pure_proxy)
                command.append(f"--proxy-server={pure_proxy}")
        else:
            command.append("--disable-extensions")

        command.append(SUCCESS_URL_PATTERN)
        return command

    async def _wait_for_login_capture(
        self,
        *,
        debugger_address: str,
        browser_process: subprocess.Popen[Any],
    ) -> dict[str, Any]:
        deadline = time.time() + self._login_timeout_seconds
        last_error: Exception | None = None
        while time.time() < deadline:
            if browser_process.poll() is not None:
                raise RuntimeError("用户取消了登录")
            try:
                payload = await self._run_blocking(read_attached_session, debugger_address)
            except Exception as exc:
                last_error = exc
                payload = None
            if isinstance(payload, dict):
                cookie_raw = str(payload.get("cookie_raw") or "")
                c5_user_id = str(payload.get("c5_user_id") or "")
                c5_nick_name = str(payload.get("c5_nick_name") or "")
                target_url = str(payload.get("target_url") or "")
                if (
                    "NC5_accessToken=" in cookie_raw
                    and c5_user_id
                    and c5_nick_name
                    and "c5game.com/user/user" in target_url
                ):
                    return payload
            await asyncio.sleep(self._poll_interval_seconds)
        if last_error is not None:
            raise RuntimeError(f"登录失败或超时: {last_error}") from last_error
        raise RuntimeError("登录失败或超时")

    @staticmethod
    async def _run_blocking(func: Callable[..., Any], /, *args, **kwargs) -> Any:
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def runner() -> None:
            try:
                result = func(*args, **kwargs)
            except BaseException as exc:  # pragma: no cover - defensive bridge
                loop.call_soon_threadsafe(future.set_exception, exc)
            else:
                loop.call_soon_threadsafe(future.set_result, result)

        BlockingThread(target=runner, name="login-blocking-call", daemon=True).start()
        return await future

    @staticmethod
    def _terminate_process(process: subprocess.Popen[Any] | None) -> None:
        if process is None:
            return
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    @staticmethod
    def _run_cleanup_callbacks(cleanup_callbacks: list[Callable[[], None]]) -> None:
        for cleanup in cleanup_callbacks:
            try:
                cleanup()
            except Exception:
                pass

    def _wait_for_process_exit(
        process: subprocess.Popen[Any] | None,
        *,
        timeout_seconds: float,
    ) -> None:
        if process is None or process.poll() is not None:
            return
        try:
            process.wait(timeout=max(timeout_seconds, 0.0))
        except subprocess.TimeoutExpired:
            return
        except Exception:
            return

    def _schedule_delayed_cleanup(
        self,
        *,
        process: subprocess.Popen[Any] | None,
        session_root: Path,
        cleanup_callbacks: list[Callable[[], None]],
        remove_session_root: bool = True,
    ) -> None:
        delay_seconds = max(self._close_delay_seconds, 0.0)

        def _cleanup() -> None:
            self._wait_for_process_exit(process, timeout_seconds=delay_seconds)
            self._terminate_process(process)
            self._run_cleanup_callbacks(cleanup_callbacks)
            if remove_session_root:
                shutil.rmtree(session_root, ignore_errors=True)

        thread = threading.Thread(
            target=_cleanup,
            name=f"managed-edge-cleanup-{session_root.name}",
            daemon=True,
        )
        thread.start()

