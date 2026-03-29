from __future__ import annotations

import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from app_backend.infrastructure.browser_runtime.account_browser_profile_store import (
    AccountBrowserProfileStore,
)
from app_backend.infrastructure.browser_runtime.cdp_session_reader import (
    read_attached_session,
    read_open_api_page_state,
)
from app_backend.infrastructure.browser_runtime.edge_launch_support import (
    build_edge_launch_command,
    reserve_debug_port,
    terminate_process,
    wait_for_debugger_port,
)
from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime


class OpenApiBindingPageLauncher:
    OPEN_API_URL = "https://www.c5game.com/user/user/open-api"

    def __init__(
        self,
        *,
        runtime: ManagedBrowserRuntime,
        profile_store: AccountBrowserProfileStore | None = None,
        debug_log_path: Path | None = None,
    ) -> None:
        self._runtime = runtime
        self._profile_store = profile_store
        self._debug_log_path = Path(debug_log_path) if debug_log_path is not None else Path("data/runtime/open_api_binding_page_launcher.runtime.jsonl")
        self._launch_lock = threading.Lock()
        self._active_launches: dict[str, dict[str, object]] = {}

    def launch(
        self,
        *,
        account_id: str | None = None,
        profile_root: str | None = None,
        profile_directory: str | None = None,
        proxy_url: str | None = None,
        sync_service=None,
    ) -> dict[str, object]:
        normalized_profile_root = str(profile_root or "").strip()
        if not normalized_profile_root:
            raise RuntimeError("当前账号缺少可复用登录会话，无法打开 API 绑定页")
        normalized_account_id = str(account_id or "").strip()
        if normalized_account_id:
            with self._launch_lock:
                active_launch = self._active_launches.get(normalized_account_id)
                active_process = active_launch.get("process") if isinstance(active_launch, dict) else None
                if active_process is not None and active_process.poll() is None:
                    self._append_debug_log(
                        "launch_reused",
                        {
                            "account_id": normalized_account_id,
                            "debugger_address": active_launch.get("debugger_address"),
                        },
                    )
                    return {
                        "open_api_url": str(active_launch.get("open_api_url") or self.OPEN_API_URL),
                        "debugger_address": str(active_launch.get("debugger_address") or ""),
                    }
                self._active_launches.pop(normalized_account_id, None)

        cleanup_callbacks: list = []
        if self._profile_store is not None and str(account_id or "").strip():
            session_root = self._profile_store.clone_session(str(account_id))
        else:
            session_root = Path(normalized_profile_root)
        session_root = session_root.expanduser().resolve()
        session_root.mkdir(parents=True, exist_ok=True)

        edge_path = str(Path(self._runtime.resolve_browser_executable()).expanduser().resolve())
        port = reserve_debug_port()
        command = build_edge_launch_command(
            edge_path=edge_path,
            port=port,
            user_data_dir=str(session_root),
            proxy_url=proxy_url,
            cleanup_callbacks=cleanup_callbacks,
            profile_directory=str(profile_directory or "Default"),
        )
        command[-1] = self.OPEN_API_URL

        browser_process = subprocess.Popen(command)
        cleanup_callbacks.append(lambda process=browser_process: terminate_process(process))
        debugger_address = f"127.0.0.1:{port}"
        if normalized_account_id:
            with self._launch_lock:
                self._active_launches[normalized_account_id] = {
                    "process": browser_process,
                    "debugger_address": debugger_address,
                    "open_api_url": self.OPEN_API_URL,
                }

        self._append_debug_log(
            "launch_started",
            {
                "account_id": account_id,
                "session_root": str(session_root),
                "proxy_url": proxy_url,
                "edge_path": edge_path,
                "debugger_address": debugger_address,
                "command": command,
            },
        )

        try:
            wait_for_debugger_port(port, process=browser_process)
            self._schedule_watch(
                account_id=account_id,
                debugger_address=debugger_address,
                sync_service=sync_service,
            )
            self._schedule_cleanup(
                account_id=account_id,
                debugger_address=debugger_address,
                session_root=session_root,
                cleanup_callbacks=cleanup_callbacks,
                process=browser_process,
                remove_session_root=self._profile_store is not None and str(account_id or "").strip() != "",
            )
            return {
                "open_api_url": self.OPEN_API_URL,
                "debugger_address": debugger_address,
            }
        except Exception as exc:
            self._append_debug_log(
                "launch_failed",
                {
                    "account_id": account_id,
                    "error": repr(exc),
                    "debugger_address": debugger_address,
                },
            )
            terminate_process(browser_process)
            self._run_cleanup_callbacks(cleanup_callbacks)
            if normalized_account_id:
                with self._launch_lock:
                    active_launch = self._active_launches.get(normalized_account_id)
                    if isinstance(active_launch, dict) and active_launch.get("process") is browser_process:
                        self._active_launches.pop(normalized_account_id, None)
            raise

    def _schedule_watch(
        self,
        *,
        account_id: str | None,
        debugger_address: str,
        sync_service,
    ) -> None:
        normalized_account_id = str(account_id or "").strip()
        if not normalized_account_id or sync_service is None:
            return
        schedule_watch = getattr(sync_service, "schedule_account_watch", None)
        if not callable(schedule_watch):
            return
        schedule_watch(normalized_account_id, debugger_address=debugger_address)

    def _schedule_cleanup(
        self,
        *,
        account_id: str | None,
        debugger_address: str | None,
        session_root: Path,
        cleanup_callbacks: list,
        process,
        remove_session_root: bool,
    ) -> None:
        def _cleanup() -> None:
            persist_allowed: bool | None = None
            while process is not None and process.poll() is None:
                probe_result = _probe_session_persist_allowed(debugger_address)
                if probe_result is not None:
                    persist_allowed = probe_result
                time.sleep(1.0)
            self._run_cleanup_callbacks(cleanup_callbacks)
            normalized_account_id = str(account_id or "").strip()
            if normalized_account_id:
                with self._launch_lock:
                    active_launch = self._active_launches.get(normalized_account_id)
                    if isinstance(active_launch, dict) and active_launch.get("process") is process:
                        self._active_launches.pop(normalized_account_id, None)
            if remove_session_root and self._profile_store is not None and str(account_id or "").strip():
                if persist_allowed is False:
                    self._append_debug_log(
                        "persist_skipped_invalid_session",
                        {
                            "account_id": account_id,
                            "debugger_address": debugger_address,
                        },
                    )
                    return
                try:
                    self._profile_store.persist_session(str(account_id), session_root)
                except Exception:
                    pass

        thread = threading.Thread(
            target=_cleanup,
            name=f"open-api-bind-cleanup-{session_root.name}",
            daemon=True,
        )
        thread.start()

    @staticmethod
    def _run_cleanup_callbacks(cleanup_callbacks: list) -> None:
        for callback in cleanup_callbacks:
            try:
                callback()
            except Exception:
                pass

    def _append_debug_log(self, event: str, payload: dict[str, object]) -> None:
        try:
            self._debug_log_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "event": event,
                "payload": payload,
            }
            with self._debug_log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            return


def _probe_session_persist_allowed(debugger_address: str | None) -> bool | None:
    normalized_debugger_address = str(debugger_address or "").strip()
    if not normalized_debugger_address:
        return None

    try:
        payload = read_attached_session(normalized_debugger_address)
    except Exception:
        try:
            page_state = read_open_api_page_state(normalized_debugger_address)
        except Exception:
            return None
        href = str(page_state.get("href") or "").strip().lower()
        if _is_login_page_url(href):
            return False
        return None

    target_url = str(payload.get("target_url") or "").strip().lower()
    cookie_raw = str(payload.get("cookie_raw") or "").strip()
    if _is_login_page_url(target_url):
        return False
    if "NC5_accessToken=" not in cookie_raw:
        return False
    return True


def _is_login_page_url(url: str | None) -> bool:
    normalized = str(url or "").strip().lower()
    return (
        "c5game.com/login" in normalized
        or "c5game.com/user/login" in normalized
    )

