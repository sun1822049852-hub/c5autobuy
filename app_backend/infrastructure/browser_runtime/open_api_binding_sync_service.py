from __future__ import annotations

import json
from pathlib import Path
import threading
import time
import urllib.request
from datetime import datetime
from typing import Callable

from app_backend.infrastructure.browser_runtime.cdp_session_reader import (
    capture_open_api_partner_info,
    navigate_and_capture_open_api_partner_info,
    poll_open_api_page_partner_info,
)
from app_backend.infrastructure.network import PublicIpResolver


PublicIpFetcher = Callable[[str | None], str | None]


class OpenApiBindingSyncService:
    PUBLIC_IP_URL = "https://api.ipify.org?format=json"
    INITIAL_CAPTURE_TIMEOUT_SECONDS = 2.0

    def __init__(
        self,
        *,
        account_repository,
        account_update_hub=None,
        account_cleanup_callback=None,
        public_ip_fetcher: PublicIpFetcher | None = None,
        poll_interval_seconds: float = 5.0,
        max_wait_seconds: float = 600.0,
        debug_log_path: Path | None = None,
    ) -> None:
        self._account_repository = account_repository
        self._account_update_hub = account_update_hub
        self._account_cleanup_callback = account_cleanup_callback
        self._public_ip_fetcher = public_ip_fetcher or self._fetch_public_ip
        self._public_ip_resolver = PublicIpResolver()
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._max_wait_seconds = float(max_wait_seconds)
        self._watch_lock = threading.Lock()
        self._active_watches: set[str] = set()
        self._debug_log_path = Path(debug_log_path) if debug_log_path is not None else Path("data/open_api_binding_debug.jsonl")

    def schedule_account_watch(
        self,
        account_id: str,
        debugger_address: str | None = None,
        source_account_id: str | None = None,
        source_api_key: str | None = None,
    ) -> None:
        normalized_account_id = str(account_id or "").strip()
        if not normalized_account_id:
            return
        with self._watch_lock:
            if normalized_account_id in self._active_watches:
                return
            self._active_watches.add(normalized_account_id)

        thread = threading.Thread(
            target=self._watch_account,
            args=(
                normalized_account_id,
                str(debugger_address or "").strip() or None,
                str(source_account_id or "").strip() or None,
                str(source_api_key or "").strip() or None,
            ),
            name=f"open-api-binding-watch-{normalized_account_id}",
            daemon=True,
        )
        thread.start()

    def sync_account_now(
        self,
        account_id: str,
        *,
        final: bool = False,
        partner_payload_override: dict[str, object] | None = None,
    ) -> dict[str, object]:
        account = self._account_repository.get_account(account_id)
        if account is None:
            self._append_debug_log("sync_skip_missing_account", {"account_id": account_id})
            return {"matched": False, "updated": False}
        cookie_raw = getattr(account, "cookie_raw", None)
        if not _has_access_token(cookie_raw):
            self._append_debug_log("sync_skip_missing_token", {"account_id": account_id})
            return {"matched": False, "updated": False}

        # Do not issue a backend HTTP request to partner/v1/info here.
        # The site-specific payload is intentionally sourced from the live browser page only,
        # because the standalone backend request has proven unstable and can diverge from the
        # browser-authenticated state the user actually passed in the open-api page.
        partner_payload = partner_payload_override or _build_stored_partner_payload(account)
        api_key, allow_list = _extract_partner_info(partner_payload)
        early_changes: dict[str, object] = {}
        if api_key or allow_list:
            early_changes = _build_account_changes(
                account=account,
                api_key=api_key,
                allow_list=allow_list,
                public_ip=None,
            )
        if early_changes:
            account = self._account_repository.update_account(account_id, **early_changes)
            self._publish_account_update(account_id, "write_account_fast", early_changes)
            self._append_debug_log(
                "write_account_fast",
                {
                    "account_id": account_id,
                    "change_keys": sorted(early_changes.keys()),
                    "api_key_written": bool(early_changes.get("api_key")),
                    "allow_list_written": bool(early_changes.get("api_ip_allow_list")),
                },
            )

        public_ip = self._resolve_account_ip(account)
        matched = _ip_in_allow_list(public_ip, allow_list)
        self._append_debug_log(
            "sync_result",
            {
                "account_id": account_id,
                "final": final,
                "used_override": partner_payload_override is not None,
                "partner_info_source": "browser_page" if partner_payload_override is not None else "stored_account_snapshot",
                "api_key_found": bool(api_key),
                "allow_list_found": bool(allow_list),
                "public_ip": public_ip,
                "matched": matched,
                "payload_summary": _summarize_partner_payload(partner_payload),
            },
        )
        changes = _build_account_changes(
            account=account,
            api_key=api_key,
            allow_list=allow_list,
            public_ip=public_ip,
        )
        changes = {
            key: value for key, value in changes.items()
            if early_changes.get(key) != value
        }
        if not changes:
            self._append_debug_log("sync_no_changes", {"account_id": account_id, "matched": matched})
            return {"matched": matched, "updated": False}
        self._account_repository.update_account(account_id, **changes)
        self._publish_account_update(account_id, "write_account", changes)
        self._append_debug_log(
            "write_account",
            {
                "account_id": account_id,
                "matched": matched,
                "change_keys": sorted(changes.keys()),
                "api_key_written": bool(changes.get("api_key")),
                "allow_list_written": bool(changes.get("api_ip_allow_list")),
                "api_public_ip_written": bool(changes.get("api_public_ip")),
            },
        )
        return {"matched": matched, "updated": True}

    def _watch_account(
        self,
        account_id: str,
        debugger_address: str | None,
        source_account_id: str | None = None,
        source_api_key: str | None = None,
    ) -> None:
        deadline = time.time() + self._max_wait_seconds
        source_cleanup_done = False
        try:
            self._append_debug_log(
                "watch_started",
                {
                    "account_id": account_id,
                    "debugger_address": debugger_address,
                    "source_account_id": source_account_id,
                    "source_api_key_present": bool(source_api_key),
                },
            )
            navigated_open_api = False
            last_browser_payload_signature: str | None = None
            while time.time() < deadline:
                browser_payload_seen = False
                if debugger_address:
                    partner_payload = None
                    remaining_seconds = max(deadline - time.time(), 0.1)
                    try:
                        if not navigated_open_api:
                            partner_payload = navigate_and_capture_open_api_partner_info(
                                debugger_address,
                                "https://www.c5game.com/user/user/open-api",
                                timeout_seconds=min(self.INITIAL_CAPTURE_TIMEOUT_SECONDS, remaining_seconds),
                            )
                            navigated_open_api = True
                            self._append_debug_log(
                                "natural_capture",
                                {
                                    "account_id": account_id,
                                    "captured": partner_payload is not None,
                                    "payload_summary": _summarize_partner_payload(partner_payload),
                                },
                            )
                        else:
                            partner_payload = poll_open_api_page_partner_info(
                                debugger_address,
                                timeout_seconds=min(2.0, remaining_seconds),
                                interval_seconds=min(1.0, self._poll_interval_seconds),
                            )
                    except Exception:
                        event_name = "natural_capture_error" if not navigated_open_api else "page_state_poll_error"
                        self._append_debug_log(event_name, {"account_id": account_id})
                        try:
                            partner_payload = capture_open_api_partner_info(
                                debugger_address,
                                timeout_seconds=min(2.0, remaining_seconds),
                            )
                        except Exception:
                            partner_payload = None
                    if partner_payload is not None:
                        browser_payload_seen = True
                        payload_signature = json.dumps(partner_payload, sort_keys=True, ensure_ascii=False)
                        if payload_signature != last_browser_payload_signature:
                            last_browser_payload_signature = payload_signature
                            outcome = self.sync_account_now(
                                account_id,
                                final=False,
                                partner_payload_override=partner_payload,
                            )
                            api_key, allow_list = _extract_partner_info(partner_payload)
                            self._append_debug_log(
                                "page_state_poll",
                                {
                                    "account_id": account_id,
                                    "captured": True,
                                    "matched": bool(outcome.get("matched")),
                                    "api_key_found": bool(api_key),
                                    "allow_list_found": bool(allow_list),
                                    "payload_summary": _summarize_partner_payload(partner_payload),
                                },
                            )
                            if (
                                not source_cleanup_done
                                and source_account_id
                                and source_account_id != account_id
                                and api_key
                                and source_api_key
                                and api_key == source_api_key
                            ):
                                self._cleanup_source_account(source_account_id)
                                source_cleanup_done = True
                            if outcome.get("matched"):
                                self._append_debug_log(
                                    "watch_finished",
                                    {"account_id": account_id, "reason": "matched_from_browser"},
                                )
                                return
                if browser_payload_seen:
                    time.sleep(self._poll_interval_seconds)
                    continue
                outcome = self.sync_account_now(account_id, final=False)
                if outcome.get("matched"):
                    self._append_debug_log("watch_finished", {"account_id": account_id, "reason": "matched_from_stored_snapshot"})
                    return
                time.sleep(self._poll_interval_seconds)
            self.sync_account_now(account_id, final=True)
            self._append_debug_log("watch_finished", {"account_id": account_id, "reason": "timeout_final_sync"})
        finally:
            with self._watch_lock:
                self._active_watches.discard(account_id)

    def _cleanup_source_account(self, source_account_id: str) -> None:
        callback = self._account_cleanup_callback
        if callable(callback):
            try:
                callback(source_account_id)
                self._append_debug_log("cleanup_source_account", {"source_account_id": source_account_id, "mode": "callback"})
                return
            except Exception:
                self._append_debug_log("cleanup_source_account_error", {"source_account_id": source_account_id, "mode": "callback"})
                return

        delete_account = getattr(self._account_repository, "delete_account", None)
        if not callable(delete_account):
            return
        try:
            delete_account(source_account_id)
            self._append_debug_log("cleanup_source_account", {"source_account_id": source_account_id, "mode": "repository"})
        except Exception:
            self._append_debug_log("cleanup_source_account_error", {"source_account_id": source_account_id, "mode": "repository"})

    def _resolve_account_ip(self, account) -> str | None:
        api_proxy_mode = str(getattr(account, "api_proxy_mode", "") or "direct")
        api_proxy_url = str(getattr(account, "api_proxy_url", "") or "").strip() or None
        if api_proxy_mode != "direct" and api_proxy_url is not None:
            self._append_debug_log("public_ip_proxy_passthrough", {"proxy_url": api_proxy_url, "public_ip": api_proxy_url})
            return api_proxy_url
        return self._public_ip_fetcher(None)

    def _fetch_public_ip(self, proxy_url: str | None) -> str | None:
        ip = self._public_ip_resolver.resolve(proxy_url)
        if not ip:
            self._append_debug_log("public_ip_fetch_error", {"proxy_url": proxy_url})
            return None
        self._append_debug_log("public_ip_fetch", {"proxy_url": proxy_url, "public_ip": ip or None})
        return ip or None

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

    def _publish_account_update(self, account_id: str, event: str, changes: dict[str, object]) -> None:
        hub = self._account_update_hub
        if hub is None:
            return
        publish = getattr(hub, "publish", None)
        if not callable(publish):
            return
        try:
            publish(account_id=account_id, event=event, payload=changes)
        except Exception:
            return


def _build_opener(proxy_url: str | None):
    proxy = str(proxy_url or "").strip()
    if not proxy:
        return urllib.request.build_opener()
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({
            "http": proxy,
            "https": proxy,
        })
    )


def _has_access_token(cookie_raw: str | None) -> bool:
    for raw_part in str(cookie_raw or "").split(";"):
        key, _, value = raw_part.strip().partition("=")
        if key == "NC5_accessToken" and value:
            return True
    return False


def _extract_partner_info(payload: dict[str, object] | None) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict) or not payload.get("success"):
        return None, None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, None
    api_info = data.get("apiInfo")
    if not isinstance(api_info, dict):
        return None, None
    api_key = str(api_info.get("key") or "").strip() or None
    allow_list = _normalize_allow_list(str(api_info.get("ipAllowList") or "").strip() or None)
    return api_key, allow_list


def _build_stored_partner_payload(account) -> dict[str, object] | None:
    api_key = str(getattr(account, "api_key", "") or "").strip() or None
    allow_list = _normalize_allow_list(getattr(account, "api_ip_allow_list", None))
    if not api_key and not allow_list:
        return None
    return {
        "success": True,
        "data": {
            "apiInfo": {
                "key": api_key,
                "ipAllowList": allow_list,
            }
        },
    }


def _normalize_allow_list(raw_allow_list: str | None) -> str | None:
    values = [
        item.strip()
        for chunk in str(raw_allow_list or "").replace("\r", "\n").split("\n")
        for item in chunk.split(",")
        if item.strip()
    ]
    if not values:
        return None
    return ", ".join(values)


def _ip_in_allow_list(public_ip: str | None, allow_list: str | None) -> bool:
    ip = str(public_ip or "").strip()
    if not ip:
        return False
    values = {item.strip() for item in str(allow_list or "").split(",") if item.strip()}
    return ip in values


def _build_account_changes(
    *,
    account,
    api_key: str | None,
    allow_list: str | None,
    public_ip: str | None,
) -> dict[str, object]:
    changes: dict[str, object] = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if api_key:
        changes["api_key"] = api_key
    if allow_list is not None:
        changes["api_ip_allow_list"] = allow_list
    if public_ip is not None:
        changes["api_public_ip"] = public_ip
        browser_proxy_mode = str(getattr(account, "browser_proxy_mode", "") or "direct")
        browser_proxy_url = str(getattr(account, "browser_proxy_url", "") or "").strip() or None
        api_proxy_mode = str(getattr(account, "api_proxy_mode", "") or "direct")
        api_proxy_url = str(getattr(account, "api_proxy_url", "") or "").strip() or None
        if browser_proxy_mode == "direct" and browser_proxy_url is None:
            changes["browser_public_ip"] = public_ip
        elif browser_proxy_mode != "direct" and browser_proxy_url is not None:
            changes["browser_public_ip"] = browser_proxy_url
        elif browser_proxy_url is not None and browser_proxy_url == api_proxy_url and api_proxy_mode != "direct":
            changes["browser_public_ip"] = public_ip
    return changes


def _summarize_partner_payload(payload: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"has_payload": False}
    data = payload.get("data")
    api_info = data.get("apiInfo") if isinstance(data, dict) else None
    return {
        "has_payload": True,
        "success": bool(payload.get("success")),
        "has_data": isinstance(data, dict),
        "has_api_info": isinstance(api_info, dict),
        "api_key_present": bool(isinstance(api_info, dict) and api_info.get("key")),
        "ip_allow_list_present": bool(isinstance(api_info, dict) and api_info.get("ipAllowList")),
        "keys": sorted(payload.keys()),
    }

