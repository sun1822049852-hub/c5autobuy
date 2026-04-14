from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from inspect import Parameter, signature
from uuid import uuid4

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.domain.enums.query_modes import QueryMode
from app_backend.domain.models.query_config import QueryConfig, QueryModeSetting
from app_backend.infrastructure.query.runtime.api_key_status import (
    is_api_key_ip_invalid_error,
)
from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter
from app_backend.infrastructure.query.runtime.query_task_runtime import QueryTaskRuntime

RuntimeFactory = Callable[..., object]


class QueryRuntimeService:
    def __init__(
        self,
        *,
        query_config_repository,
        query_settings_repository=None,
        account_repository,
        runtime_factory: RuntimeFactory | None = None,
        purchase_runtime_service=None,
        open_api_binding_sync_service=None,
        stats_sink=None,
        runtime_update_hub=None,
    ) -> None:
        self._query_config_repository = query_config_repository
        self._query_settings_repository = query_settings_repository
        self._account_repository = account_repository
        self._runtime_factory = runtime_factory or self._build_default_runtime
        self._purchase_runtime_service = purchase_runtime_service
        self._open_api_binding_sync_service = open_api_binding_sync_service
        self._stats_sink = stats_sink
        self._runtime_update_hub = runtime_update_hub
        self._state_lock = threading.RLock()
        self._runtime = None
        self._retained_runtime = None
        self._runtime_accounts: dict[str, RuntimeAccountAdapter] = {}
        self._pending_resume_config_id: str | None = None
        self._pending_resume_config_name: str | None = None
        self._pending_resume_runtime_session_id: str | None = None
        self._paused_at: str | None = None
        self._auto_stop_requested = False
        self._runtime_update_thread_lock = threading.RLock()
        self._runtime_update_pending = False
        self._runtime_update_thread: threading.Thread | None = None
        self._register_purchase_runtime_callbacks()

    def start(self, *, config_id: str, resume: bool = False) -> tuple[bool, str]:
        config = None
        runtime_to_stop = None
        message = ""
        with self._state_lock:
            self._auto_stop_requested = False
            active_config_id = self._get_active_config_id_locked()
            allow_pending_resume = (
                resume
                and active_config_id == config_id
                and not self._has_running_runtime_locked()
                and self._has_pending_resume_state()
            )
            if active_config_id == config_id and not allow_pending_resume:
                return False, "已有查询任务在运行"
            if active_config_id is not None and not allow_pending_resume:
                config = self._query_config_repository.get_config(config_id)
                if config is None:
                    return False, "已有查询任务在运行"
                config = self._resolve_runtime_config(config)
                runtime_to_stop = self._runtime
                self._runtime = None
                self._clear_retained_runtime_locked()
                self._clear_pending_resume_state()
            else:
                config = self._query_config_repository.get_config(config_id)
                if config is None:
                    return False, "查询配置不存在"
                config = self._resolve_runtime_config(config)

        if runtime_to_stop is not None:
            runtime_to_stop.stop()

        with self._state_lock:
            current_active_config_id = self._get_active_config_id_locked()
            allow_pending_resume = (
                resume
                and current_active_config_id == config_id
                and not self._has_running_runtime_locked()
                and self._has_pending_resume_state()
            )
            if current_active_config_id is not None and not allow_pending_resume:
                return False, "已有查询任务在运行"

            purchase_started, purchase_message = self._ensure_purchase_runtime_started()
            if not purchase_started:
                return False, purchase_message
            retained_runtime = self._get_retained_runtime_locked(config_id)
            latest_accounts: list[object] | None = None
            if retained_runtime is not None:
                latest_accounts = list(self._account_repository.list_accounts())
                refresh_accounts = getattr(retained_runtime, "refresh_accounts", None)
                if callable(refresh_accounts):
                    refresh_accounts(latest_accounts)
                runtime_session_id = (
                    self._extract_runtime_session_id(retained_runtime)
                    or self._pending_resume_runtime_session_id
                    or self._build_runtime_session_id()
                )
            elif allow_pending_resume:
                runtime_session_id = self._pending_resume_runtime_session_id
            else:
                runtime_session_id = self._pending_resume_runtime_session_id or self._build_runtime_session_id()
            if not allow_pending_resume:
                self._bind_purchase_runtime_session(config=config, runtime_session_id=runtime_session_id)
            if not self._purchase_runtime_has_available_accounts():
                self._mark_waiting_for_purchase_recovery(config, runtime_session_id=runtime_session_id)
                message = "查询任务已启动，等待购买账号恢复"
            else:
                preserve_allocation_state = retained_runtime is not None
                if retained_runtime is not None:
                    runtime = retained_runtime
                else:
                    accounts = latest_accounts if latest_accounts is not None else list(self._account_repository.list_accounts())
                    hit_sink = self._resolve_hit_sink()
                    runtime = self._create_runtime(
                        config,
                        accounts,
                        hit_sink=hit_sink,
                        runtime_session_id=runtime_session_id,
                    )
                self._runtime = runtime
                self._retained_runtime = runtime
                self._start_runtime(runtime, preserve_allocation_state=preserve_allocation_state)
                self._clear_pending_resume_state()
                message = "查询任务已启动"

        self._publish_runtime_update()
        return True, message

    def stop(self) -> tuple[bool, str]:
        with self._state_lock:
            if not self._has_running_runtime_locked() and not self._has_pending_resume_state():
                self._runtime = None
                self._auto_stop_requested = False
                return False, "当前没有运行中的查询任务"

            runtime = self._runtime
            self._runtime = None
            self._clear_pending_resume_state()
            self._auto_stop_requested = False
        if runtime is not None:
            runtime.stop()
        self._close_runtime_accounts()
        self._stop_linked_purchase_runtime()
        self._publish_runtime_update()
        return True, "查询任务已停止"

    def refresh_runtime_accounts(self) -> None:
        latest_accounts = list(self._account_repository.list_accounts())
        with self._state_lock:
            runtimes: list[object] = []
            if self._runtime is not None:
                runtimes.append(self._runtime)
            if self._retained_runtime is not None and self._retained_runtime not in runtimes:
                runtimes.append(self._retained_runtime)

        for runtime in runtimes:
            refresh_accounts = getattr(runtime, "refresh_accounts", None)
            if callable(refresh_accounts):
                refresh_accounts(latest_accounts)
        if runtimes:
            self._publish_runtime_update()

    def get_status(self) -> dict[str, object]:
        with self._state_lock:
            if not self._has_running_runtime_locked():
                self._runtime = None
                if self._has_pending_resume_state():
                    return self._build_waiting_snapshot()
                return self._build_idle_snapshot()
            return self._normalize_snapshot(self._runtime.snapshot(), getattr(self._runtime, "config", None))

    def apply_query_item_runtime(self, *, config_id: str, query_item_id: str) -> dict[str, str]:
        config = self._query_config_repository.get_config(config_id)
        if config is None:
            raise KeyError(config_id)
        config = self._resolve_runtime_config(config)

        if all(str(item.query_item_id) != str(query_item_id) for item in config.items):
            raise KeyError(query_item_id)

        with self._state_lock:
            active_config_id = self._get_active_config_id_locked()
            runtime_is_running = self._has_running_runtime_locked()
            runtime = self._runtime if runtime_is_running else None
            pending_resume = self._has_pending_resume_state()
            if active_config_id != config_id:
                return self._build_apply_query_item_result(
                    status="skipped_inactive",
                    message="当前配置未在运行，已跳过热应用",
                    config_id=config_id,
                    query_item_id=query_item_id,
                )
            if not runtime_is_running:
                if pending_resume:
                    self._pending_resume_config_name = getattr(config, "name", None)
                    result = self._build_apply_query_item_result(
                        status="applied_waiting_resume",
                        message="当前配置等待恢复运行，已记录热应用",
                        config_id=config_id,
                        query_item_id=query_item_id,
                    )
                    self._publish_runtime_update()
                    return result
                return self._build_apply_query_item_result(
                    status="skipped_inactive",
                    message="当前配置未在运行，已跳过热应用",
                    config_id=config_id,
                    query_item_id=query_item_id,
                )

        apply_runtime = getattr(runtime, "apply_query_item_runtime", None)
        if not callable(apply_runtime):
            return self._build_apply_query_item_result(
                status="failed_after_save",
                message="配置已保存，但热应用失败：runtime apply hook unavailable",
                config_id=config_id,
                query_item_id=query_item_id,
            )
        try:
            apply_runtime(config=config, query_item_id=query_item_id)
        except Exception as exc:
            return self._build_apply_query_item_result(
                status="failed_after_save",
                message=f"配置已保存，但热应用失败：{exc}",
                config_id=config_id,
                query_item_id=query_item_id,
            )
        result = self._build_apply_query_item_result(
            status="applied",
            message="当前运行配置已热应用",
            config_id=config_id,
            query_item_id=query_item_id,
        )
        self._publish_runtime_update()
        return result

    def apply_manual_allocations(
        self,
        *,
        config_id: str,
        items: list[dict[str, object]],
    ) -> dict[str, object]:
        config = self._query_config_repository.get_config(config_id)
        if config is None:
            raise KeyError("查询配置不存在")
        config = self._resolve_runtime_config(config)

        known_item_ids = {
            str(item.query_item_id)
            for item in config.items
        }
        for raw_item in items:
            if not isinstance(raw_item, dict):
                continue
            query_item_id = str(raw_item.get("query_item_id") or "").strip()
            if query_item_id and query_item_id not in known_item_ids:
                raise KeyError("查询商品不存在")

        with self._state_lock:
            active_config_id = self._get_active_config_id_locked()
            runtime_is_running = self._has_running_runtime_locked()
            runtime = self._runtime if runtime_is_running else None
            if active_config_id != config_id or not runtime_is_running or runtime is None:
                raise ValueError("当前配置未在运行，无法提交运行时分配")

        apply_manual_allocations = getattr(runtime, "apply_manual_allocations", None)
        if not callable(apply_manual_allocations):
            raise ValueError("当前运行时不支持运行时分配调整")
        apply_manual_allocations(config=config, items=list(items))
        snapshot = self.get_status()
        self._publish_runtime_update()
        return snapshot

    def apply_runtime_config(self, *, config_id: str) -> dict[str, object]:
        config = self._query_config_repository.get_config(config_id)
        if config is None:
            raise KeyError("查询配置不存在")
        config = self._resolve_runtime_config(config)

        with self._state_lock:
            active_config_id = self._get_active_config_id_locked()
            runtime_is_running = self._has_running_runtime_locked()
            runtime = self._runtime if runtime_is_running else None
            pending_resume = self._has_pending_resume_state()
            if active_config_id != config_id:
                raise ValueError("当前配置未在运行，无法热应用整份配置")
            if not runtime_is_running:
                if pending_resume:
                    self._pending_resume_config_name = getattr(config, "name", None)
                    snapshot = self.get_status()
                    self._publish_runtime_update()
                    return snapshot
                raise ValueError("当前配置未在运行，无法热应用整份配置")

        apply_config = getattr(runtime, "apply_config", None)
        if not callable(apply_config):
            raise ValueError("当前运行时不支持整份配置热应用")
        apply_config(config)
        snapshot = self.get_status()
        self._publish_runtime_update()
        return snapshot

    def apply_query_settings(self) -> None:
        with self._state_lock:
            active_config_id = self._get_active_config_id_locked()
            if not active_config_id:
                return
            config = self._query_config_repository.get_config(active_config_id)
            if config is None:
                return
            runtime_config = self._resolve_runtime_config(config)
            runtime = self._runtime or self._retained_runtime
            if self._has_pending_resume_state():
                self._pending_resume_config_name = runtime_config.name
        if runtime is None:
            if self._has_pending_resume_state():
                self._publish_runtime_update()
            return
        apply_query_settings = getattr(runtime, "apply_query_settings", None)
        if not callable(apply_query_settings):
            return
        try:
            apply_query_settings(config=runtime_config)
        except Exception:
            return
        self._publish_runtime_update()

    def _has_running_runtime(self) -> bool:
        with self._state_lock:
            return self._has_running_runtime_locked()

    def _has_running_runtime_locked(self) -> bool:
        if self._runtime is None:
            return False
        snapshot = self._runtime.snapshot()
        return bool(snapshot.get("running"))

    def _get_retained_runtime_locked(self, config_id: str) -> object | None:
        runtime = self._retained_runtime
        if runtime is None:
            return None
        retained_config_id = self._extract_runtime_config_id(runtime)
        if retained_config_id != str(config_id):
            return None
        return runtime

    def _clear_retained_runtime_locked(self) -> None:
        self._retained_runtime = None

    def _has_pending_resume_state(self) -> bool:
        return bool(self._pending_resume_config_id)

    def _get_active_config_id_locked(self) -> str | None:
        if self._has_running_runtime_locked():
            runtime_config = getattr(self._runtime, "config", None)
            runtime_config_id = getattr(runtime_config, "config_id", None)
            if runtime_config_id:
                return str(runtime_config_id)
            snapshot = self._runtime.snapshot()
            normalized_config_id = str(snapshot.get("config_id") or "").strip()
            return normalized_config_id or None
        if self._has_pending_resume_state():
            return self._pending_resume_config_id
        return None

    def _clear_pending_resume_state(self) -> None:
        self._pending_resume_config_id = None
        self._pending_resume_config_name = None
        self._pending_resume_runtime_session_id = None
        self._paused_at = None

    @staticmethod
    def _build_apply_query_item_result(
        *,
        status: str,
        message: str,
        config_id: str,
        query_item_id: str,
    ) -> dict[str, str]:
        return {
            "status": str(status),
            "message": str(message),
            "config_id": str(config_id),
            "query_item_id": str(query_item_id),
        }

    def _build_idle_snapshot(self) -> dict[str, object]:
        return {
            "running": False,
            "config_id": None,
            "config_name": None,
            "message": "未运行",
            "account_count": 0,
            "started_at": None,
            "stopped_at": None,
            "total_query_count": 0,
            "total_found_count": 0,
            "modes": {},
            "group_rows": [],
            "recent_events": [],
            "item_rows": [],
        }

    def _build_waiting_snapshot(self) -> dict[str, object]:
        config_id = self._pending_resume_config_id
        config = self._query_config_repository.get_config(config_id) if config_id else None
        if config is not None:
            config = self._resolve_runtime_config(config)
        snapshot = {
            "running": False,
            "config_id": config_id,
            "config_name": self._pending_resume_config_name or getattr(config, "name", None),
            "message": "等待购买账号恢复",
            "account_count": 0,
            "started_at": None,
            "stopped_at": self._paused_at,
            "total_query_count": 0,
            "total_found_count": 0,
            "modes": {},
            "group_rows": [],
            "recent_events": [],
            "item_rows": self._build_default_item_rows(config),
        }
        if config is not None:
            for mode_setting in config.mode_settings:
                snapshot["modes"][mode_setting.mode_type] = self._build_default_mode_snapshot(mode_setting)
        return snapshot

    def _normalize_snapshot(self, snapshot: dict[str, object], config: QueryConfig | None) -> dict[str, object]:
        if config is not None:
            config = self._resolve_runtime_config(config)
        normalized = {
            "running": bool(snapshot.get("running")),
            "config_id": snapshot.get("config_id"),
            "config_name": snapshot.get("config_name"),
            "message": str(snapshot.get("message") or ("运行中" if snapshot.get("running") else "未运行")),
            "account_count": int(snapshot.get("account_count", 0)),
            "started_at": snapshot.get("started_at"),
            "stopped_at": snapshot.get("stopped_at"),
            "total_query_count": int(snapshot.get("total_query_count", 0)),
            "total_found_count": int(snapshot.get("total_found_count", 0)),
            "modes": {},
            "group_rows": self._normalize_group_rows(snapshot.get("group_rows")),
            "recent_events": self._normalize_recent_events(snapshot.get("recent_events")),
            "item_rows": self._normalize_item_rows(snapshot.get("item_rows")),
        }
        raw_modes = snapshot.get("modes")
        if isinstance(raw_modes, dict):
            for mode_type, mode_snapshot in raw_modes.items():
                if isinstance(mode_snapshot, dict):
                    normalized["modes"][str(mode_type)] = self._normalize_mode_snapshot(mode_snapshot)

        if config is not None:
            for mode_setting in config.mode_settings:
                if mode_setting.mode_type not in normalized["modes"]:
                    normalized["modes"][mode_setting.mode_type] = self._build_default_mode_snapshot(mode_setting)
        return normalized

    @staticmethod
    def _normalize_group_rows(raw_rows: object) -> list[dict[str, object]]:
        if not isinstance(raw_rows, list):
            return []

        normalized: list[dict[str, object]] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            normalized.append(
                {
                    "account_id": str(raw_row.get("account_id") or ""),
                    "account_display_name": str(raw_row.get("account_display_name") or raw_row.get("account_id") or ""),
                    "mode_type": str(raw_row.get("mode_type") or ""),
                    "active": bool(raw_row.get("active")),
                    "in_window": bool(raw_row.get("in_window")),
                    "cooldown_until": QueryRuntimeService._normalize_time_value(raw_row.get("cooldown_until")),
                    "last_query_at": QueryRuntimeService._normalize_time_value(raw_row.get("last_query_at")),
                    "last_success_at": QueryRuntimeService._normalize_time_value(raw_row.get("last_success_at")),
                    "query_count": int(raw_row.get("query_count", 0)),
                    "found_count": int(raw_row.get("found_count", 0)),
                    "disabled_reason": raw_row.get("disabled_reason"),
                    "last_error": raw_row.get("last_error"),
                    "rate_limit_increment": float(raw_row.get("rate_limit_increment", 0.0) or 0.0),
                }
            )
        return normalized

    @staticmethod
    def _normalize_mode_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
        enabled = bool(snapshot.get("enabled"))
        return {
            "mode_type": str(snapshot.get("mode_type") or ""),
            "enabled": enabled,
            "eligible_account_count": int(snapshot.get("eligible_account_count", 0)),
            "active_account_count": int(snapshot.get("active_account_count", 0)),
            "in_window": bool(snapshot.get("in_window", enabled)),
            "next_window_start": snapshot.get("next_window_start"),
            "next_window_end": snapshot.get("next_window_end"),
            "query_count": int(snapshot.get("query_count", 0)),
            "found_count": int(snapshot.get("found_count", 0)),
            "last_error": snapshot.get("last_error"),
        }

    @staticmethod
    def _build_default_mode_snapshot(mode_setting: QueryModeSetting) -> dict[str, object]:
        enabled = bool(mode_setting.enabled)
        return {
            "mode_type": mode_setting.mode_type,
            "enabled": enabled,
            "eligible_account_count": 0,
            "active_account_count": 0,
            "in_window": enabled and not bool(mode_setting.window_enabled) if enabled else False,
            "next_window_start": None,
            "next_window_end": None,
            "query_count": 0,
            "found_count": 0,
            "last_error": None,
        }

    @staticmethod
    def _build_default_item_rows(config: QueryConfig | None) -> list[dict[str, object]]:
        if config is None:
            return []

        rows: list[dict[str, object]] = []
        for item in config.items:
            allocation_map = {
                allocation.mode_type: int(allocation.target_dedicated_count)
                for allocation in item.mode_allocations
            }
            modes: dict[str, dict[str, object]] = {}
            for mode_setting in config.mode_settings:
                target = int(allocation_map.get(mode_setting.mode_type, 0))
                if item.manual_paused:
                    status = "manual_paused"
                    status_message = "手动暂停"
                else:
                    status = "unavailable"
                    status_message = f"无可用账号 0/{target}" if target > 0 else "无可用账号"
                modes[mode_setting.mode_type] = {
                    "mode_type": mode_setting.mode_type,
                    "target_dedicated_count": target,
                    "actual_dedicated_count": 0,
                    "status": status,
                    "status_message": status_message,
                    "shared_available_count": 0,
                }
            rows.append(
                {
                    "query_item_id": str(item.query_item_id),
                    "item_name": item.item_name or item.market_hash_name or item.query_item_id,
                    "max_price": item.max_price,
                    "min_wear": item.min_wear,
                    "max_wear": item.max_wear,
                    "detail_min_wear": item.detail_min_wear,
                    "detail_max_wear": item.detail_max_wear,
                    "manual_paused": bool(item.manual_paused),
            "query_count": 0,
            "modes": modes,
        }
            )
        return rows

    def _resolve_runtime_config(self, config: QueryConfig) -> QueryConfig:
        if self._query_settings_repository is None:
            return config
        get_settings = getattr(self._query_settings_repository, "get_settings", None)
        if not callable(get_settings):
            return config
        settings = get_settings()
        if settings is None:
            return config
        settings_modes = {
            str(mode.mode_type): mode
            for mode in getattr(settings, "modes", []) or []
        }
        if not settings_modes:
            return config
        now = datetime.now().isoformat(timespec="seconds")
        runtime_modes: list[QueryModeSetting] = []
        for mode_type in QueryMode.ALL:
            mode = settings_modes.get(mode_type)
            if mode is None:
                continue
            runtime_modes.append(
                QueryModeSetting(
                    mode_setting_id=f"global:{mode_type}",
                    config_id=str(config.config_id),
                    mode_type=mode_type,
                    enabled=bool(mode.enabled),
                    window_enabled=bool(mode.window_enabled),
                    start_hour=int(mode.start_hour),
                    start_minute=int(mode.start_minute),
                    end_hour=int(mode.end_hour),
                    end_minute=int(mode.end_minute),
                    base_cooldown_min=float(mode.base_cooldown_min),
                    base_cooldown_max=float(mode.base_cooldown_max),
                    item_min_cooldown_seconds=float(getattr(mode, "item_min_cooldown_seconds", 0.5)),
                    item_min_cooldown_strategy=str(
                        getattr(mode, "item_min_cooldown_strategy", "divide_by_assigned_count")
                    ),
                    random_delay_enabled=bool(mode.random_delay_enabled),
                    random_delay_min=float(mode.random_delay_min),
                    random_delay_max=float(mode.random_delay_max),
                    created_at=getattr(mode, "created_at", now),
                    updated_at=getattr(mode, "updated_at", now),
                )
            )
        if not runtime_modes:
            return config
        return replace(config, mode_settings=runtime_modes)

    @staticmethod
    def _normalize_recent_events(raw_events: object) -> list[dict[str, object]]:
        if not isinstance(raw_events, list):
            return []

        normalized: list[dict[str, object]] = []
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                continue
            normalized.append(
                {
                    "timestamp": str(raw_event.get("timestamp") or ""),
                    "level": str(raw_event.get("level") or ""),
                    "mode_type": str(raw_event.get("mode_type") or ""),
                    "account_id": str(raw_event.get("account_id") or ""),
                    "account_display_name": raw_event.get("account_display_name"),
                    "query_item_id": str(raw_event.get("query_item_id") or ""),
                    "query_item_name": raw_event.get("query_item_name"),
                    "message": str(raw_event.get("message") or ""),
                    "match_count": int(raw_event.get("match_count", 0)),
                    "product_list": QueryRuntimeService._normalize_product_list(raw_event.get("product_list")),
                    "total_price": (
                        float(raw_event["total_price"])
                        if raw_event.get("total_price") is not None
                        else None
                    ),
                    "total_wear_sum": (
                        float(raw_event["total_wear_sum"])
                        if raw_event.get("total_wear_sum") is not None
                        else None
                    ),
                    "latency_ms": (
                        float(raw_event["latency_ms"])
                        if raw_event.get("latency_ms") is not None
                        else None
                    ),
                    "error": raw_event.get("error"),
                    "status_code": (
                        int(raw_event["status_code"])
                        if raw_event.get("status_code") is not None
                        else None
                    ),
                    "request_method": raw_event.get("request_method"),
                    "request_path": raw_event.get("request_path"),
                    "request_body": raw_event.get("request_body"),
                    "response_text": raw_event.get("response_text"),
                }
            )
        return normalized

    @staticmethod
    def _normalize_item_rows(raw_rows: object) -> list[dict[str, object]]:
        if not isinstance(raw_rows, list):
            return []

        normalized: list[dict[str, object]] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            raw_modes = raw_row.get("modes")
            normalized_modes: dict[str, dict[str, object]] = {}
            if isinstance(raw_modes, dict):
                for mode_type, raw_mode in raw_modes.items():
                    if not isinstance(raw_mode, dict):
                        continue
                    normalized_modes[str(mode_type)] = {
                        "mode_type": str(raw_mode.get("mode_type") or mode_type or ""),
                        "target_dedicated_count": int(raw_mode.get("target_dedicated_count", 0)),
                        "actual_dedicated_count": int(raw_mode.get("actual_dedicated_count", 0)),
                        "status": str(raw_mode.get("status") or ""),
                        "status_message": str(raw_mode.get("status_message") or ""),
                        "shared_available_count": int(raw_mode.get("shared_available_count", 0)),
                    }
            normalized.append(
                {
                    "query_item_id": str(raw_row.get("query_item_id") or ""),
                    "item_name": raw_row.get("item_name"),
                    "max_price": (
                        float(raw_row["max_price"])
                        if raw_row.get("max_price") is not None
                        else None
                    ),
                    "min_wear": (
                        float(raw_row["min_wear"])
                        if raw_row.get("min_wear") is not None
                        else None
                    ),
                    "max_wear": (
                        float(raw_row["max_wear"])
                        if raw_row.get("max_wear") is not None
                        else None
                    ),
                    "detail_min_wear": (
                        float(raw_row["detail_min_wear"])
                        if raw_row.get("detail_min_wear") is not None
                        else None
                    ),
                    "detail_max_wear": (
                        float(raw_row["detail_max_wear"])
                        if raw_row.get("detail_max_wear") is not None
                        else None
                    ),
                    "manual_paused": bool(raw_row.get("manual_paused")),
                    "query_count": int(raw_row.get("query_count", 0)),
                    "modes": normalized_modes,
                }
            )
        return normalized

    @staticmethod
    def _normalize_product_list(raw_products: object) -> list[dict[str, object]]:
        if not isinstance(raw_products, list):
            return []

        normalized: list[dict[str, object]] = []
        for raw_product in raw_products:
            if not isinstance(raw_product, dict):
                continue
            normalized.append(
                {
                    "productId": str(raw_product.get("productId") or ""),
                    "price": float(raw_product.get("price", 0.0) or 0.0),
                    "actRebateAmount": float(raw_product.get("actRebateAmount", 0.0) or 0.0),
                }
            )
        return normalized

    @staticmethod
    def _normalize_time_value(value: object) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return value
        return QueryRuntimeService._normalize_numeric_timestamp(value)

    @staticmethod
    def _normalize_numeric_timestamp(value: object) -> str | None:
        try:
            return QueryRuntimeService._timestamp_to_iso(float(value))
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _timestamp_to_iso(value: float) -> str:
        from datetime import datetime

        return datetime.fromtimestamp(value).isoformat(timespec="seconds")

    @staticmethod
    def _build_default_runtime(
        config,
        accounts: list[object],
        *,
        runtime_session_id: str | None = None,
        runtime_account_provider=None,
        hit_sink=None,
        event_sink=None,
        stats_sink=None,
    ) -> QueryTaskRuntime:
        return QueryTaskRuntime(
            config,
            accounts,
            runtime_session_id=runtime_session_id,
            runtime_account_provider=runtime_account_provider,
            hit_sink=hit_sink,
            event_sink=event_sink,
            stats_sink=stats_sink,
        )

    def _create_runtime(self, config, accounts: list[object], *, hit_sink=None, runtime_session_id: str | None = None):
        kwargs = {}
        if runtime_session_id is not None and self._runtime_factory_accepts_parameter(
            "runtime_session_id",
            allow_var_keyword=False,
        ):
            kwargs["runtime_session_id"] = runtime_session_id
        if hit_sink is not None and self._runtime_factory_accepts_parameter("hit_sink"):
            kwargs["hit_sink"] = hit_sink
        event_sink = self._resolve_event_sink()
        if event_sink is not None and self._runtime_factory_accepts_parameter("event_sink"):
            kwargs["event_sink"] = event_sink
        stats_sink = self._resolve_stats_sink()
        if stats_sink is not None and self._runtime_factory_accepts_parameter("stats_sink"):
            kwargs["stats_sink"] = stats_sink
        runtime_account_provider = self._resolve_runtime_account_provider()
        if runtime_account_provider is not None and self._runtime_factory_accepts_parameter(
            "runtime_account_provider",
            allow_var_keyword=False,
        ):
            kwargs["runtime_account_provider"] = runtime_account_provider
        try:
            return self._runtime_factory(config, accounts, **kwargs)
        except TypeError as exc:
            message = str(exc)
            fallback_kwargs = dict(kwargs)
            if "unexpected keyword argument 'event_sink'" in message:
                fallback_kwargs.pop("event_sink", None)
            if "unexpected keyword argument 'stats_sink'" in message:
                fallback_kwargs.pop("stats_sink", None)
            if "unexpected keyword argument 'hit_sink'" in message:
                fallback_kwargs.pop("hit_sink", None)
            if "unexpected keyword argument 'runtime_account_provider'" in message:
                fallback_kwargs.pop("runtime_account_provider", None)
            if fallback_kwargs == kwargs:
                raise
            return self._runtime_factory(config, accounts, **fallback_kwargs)

    def _resolve_hit_sink(self):
        if self._purchase_runtime_service is None:
            return None
        enqueue_hit_sink = getattr(self._purchase_runtime_service, "enqueue_query_hit", None)
        if callable(enqueue_hit_sink):
            return enqueue_hit_sink
        async_hit_sink = getattr(self._purchase_runtime_service, "accept_query_hit_async", None)
        if callable(async_hit_sink):
            return async_hit_sink
        hit_sink = getattr(self._purchase_runtime_service, "accept_query_hit", None)
        return hit_sink if callable(hit_sink) else None

    def _runtime_factory_accepts_parameter(self, parameter_name: str, *, allow_var_keyword: bool = True) -> bool:
        try:
            parameters = signature(self._runtime_factory).parameters.values()
        except (TypeError, ValueError):
            return False

        for parameter in parameters:
            if allow_var_keyword and parameter.kind == Parameter.VAR_KEYWORD:
                return True
            if parameter.name == parameter_name:
                return True
        return False

    def _resolve_event_sink(self):
        return self._handle_runtime_event

    def _resolve_runtime_account_provider(self):
        return self._get_or_create_runtime_account

    def _resolve_stats_sink(self):
        return self._stats_sink

    def _ensure_purchase_runtime_started(self) -> tuple[bool, str]:
        if self._purchase_runtime_service is None:
            return True, "未接入购买运行时，跳过联动启动"

        start_purchase_runtime = getattr(self._purchase_runtime_service, "start", None)
        if not callable(start_purchase_runtime):
            return False, "购买运行时未接入启动接口"

        started, message = start_purchase_runtime()
        normalized_message = str(message or "")
        if started or normalized_message == "已有购买运行时在运行":
            return True, normalized_message or "购买运行时已启动"
        return False, normalized_message or "购买运行时启动失败"

    def _purchase_runtime_has_available_accounts(self) -> bool:
        if self._purchase_runtime_service is None:
            return True
        has_available_accounts = getattr(self._purchase_runtime_service, "has_available_accounts", None)
        if callable(has_available_accounts):
            return bool(has_available_accounts())
        get_status = getattr(self._purchase_runtime_service, "get_status", None)
        if callable(get_status):
            try:
                status = get_status()
            except Exception:
                return True
            return int(status.get("active_account_count", 0)) > 0
        return True

    def _stop_linked_purchase_runtime(self) -> None:
        if self._purchase_runtime_service is None:
            return

        stop_purchase_runtime = getattr(self._purchase_runtime_service, "stop", None)
        if not callable(stop_purchase_runtime):
            return

        stopped, message = stop_purchase_runtime()
        normalized_message = str(message or "")
        if stopped:
            return
        if normalized_message == "当前没有运行中的购买运行时":
            return

    def _register_purchase_runtime_callbacks(self) -> None:
        if self._purchase_runtime_service is None:
            return
        register_callbacks = getattr(self._purchase_runtime_service, "register_availability_callbacks", None)
        if not callable(register_callbacks):
            return
        register_callbacks(
            on_no_available_accounts=self._pause_for_purchase_unavailable,
            on_accounts_available=self._resume_after_purchase_recovered,
        )

    def _pause_for_purchase_unavailable(self) -> None:
        with self._state_lock:
            if not self._has_running_runtime_locked():
                return
            runtime = self._runtime
            config = getattr(runtime, "config", None) if runtime is not None else None
            runtime_session_id = self._extract_runtime_session_id(runtime)
            self._mark_waiting_for_purchase_recovery(config, runtime_session_id=runtime_session_id)
        if runtime is not None:
            runtime.stop()
        self._publish_runtime_update()

    def _resume_after_purchase_recovered(self) -> None:
        with self._state_lock:
            if self._has_running_runtime_locked():
                return
            config_id = self._pending_resume_config_id
        if not config_id:
            return
        self.start(config_id=config_id, resume=True)

    def _publish_runtime_update(self) -> None:
        if self._runtime_update_hub is None:
            return
        self._runtime_update_hub.publish(
            event="query_runtime.updated",
            payload=self.get_status(),
        )

    def _schedule_runtime_update_publish(self) -> None:
        if self._runtime_update_hub is None:
            return
        worker_to_start: threading.Thread | None = None
        with self._runtime_update_thread_lock:
            self._runtime_update_pending = True
            worker = self._runtime_update_thread
            if worker is None or not worker.is_alive():
                worker = threading.Thread(
                    target=self._drain_runtime_update_publishes,
                    name="query-runtime-update-publisher",
                    daemon=True,
                )
                self._runtime_update_thread = worker
                worker_to_start = worker
        if worker_to_start is not None:
            worker_to_start.start()

    def _drain_runtime_update_publishes(self) -> None:
        while True:
            with self._runtime_update_thread_lock:
                if not self._runtime_update_pending:
                    self._runtime_update_thread = None
                    return
                self._runtime_update_pending = False
            try:
                self._publish_runtime_update()
            except Exception:
                continue

    def _handle_runtime_event(self, event: dict[str, object]) -> None:
        if not isinstance(event, dict):
            return
        account_id = str(event.get("account_id") or "").strip()
        if not account_id:
            return
        error = str(event.get("error") or "").strip()
        if error == "Not login":
            self._mark_account_not_login(account_id=account_id, error=error)
        elif is_api_key_ip_invalid_error(
            error=error,
            response_text=str(event.get("response_text") or "") or None,
            status_code=event.get("status_code"),
        ):
            self._mark_account_api_key_ip_invalid(account_id=account_id, error=error)
        self._schedule_runtime_update_publish()

    def _mark_waiting_for_purchase_recovery(
        self,
        config: QueryConfig | None,
        *,
        runtime_session_id: str | None = None,
    ) -> None:
        self._runtime = None
        self._pending_resume_config_id = getattr(config, "config_id", None)
        self._pending_resume_config_name = getattr(config, "name", None)
        self._pending_resume_runtime_session_id = str(runtime_session_id or "") or None
        self._paused_at = datetime.now().isoformat(timespec="seconds")

    def _start_runtime(self, runtime, *, preserve_allocation_state: bool) -> None:
        start_runtime = getattr(runtime, "start", None)
        if not callable(start_runtime):
            return
        if self._callable_accepts_parameter(
            start_runtime,
            "preserve_allocation_state",
        ):
            start_runtime(preserve_allocation_state=preserve_allocation_state)
            return
        start_runtime()

    @staticmethod
    def _build_runtime_session_id() -> str:
        return uuid4().hex

    @staticmethod
    def _extract_runtime_session_id(runtime) -> str | None:
        if runtime is None:
            return None
        runtime_session_id = getattr(runtime, "runtime_session_id", None)
        if runtime_session_id:
            return str(runtime_session_id)
        snapshot = getattr(runtime, "snapshot", None)
        if not callable(snapshot):
            return None
        data = snapshot()
        if not isinstance(data, dict):
            return None
        value = str(data.get("runtime_session_id") or "").strip()
        return value or None

    @staticmethod
    def _extract_runtime_config_id(runtime) -> str | None:
        if runtime is None:
            return None
        runtime_config = getattr(runtime, "config", None)
        runtime_config_id = getattr(runtime_config, "config_id", None)
        if runtime_config_id:
            return str(runtime_config_id)
        snapshot = getattr(runtime, "snapshot", None)
        if not callable(snapshot):
            return None
        data = snapshot()
        if not isinstance(data, dict):
            return None
        value = str(data.get("config_id") or "").strip()
        return value or None

    @staticmethod
    def _callable_accepts_parameter(callable_obj, parameter_name: str) -> bool:
        try:
            parameters = signature(callable_obj).parameters.values()
        except (TypeError, ValueError):
            return False

        for parameter in parameters:
            if parameter.kind == Parameter.VAR_KEYWORD:
                return True
            if parameter.name == parameter_name:
                return True
        return False

    def _bind_purchase_runtime_session(self, *, config: QueryConfig, runtime_session_id: str | None) -> None:
        if self._purchase_runtime_service is None:
            return
        bind_query_runtime_session = getattr(self._purchase_runtime_service, "bind_query_runtime_session", None)
        if not callable(bind_query_runtime_session):
            return
        bind_query_runtime_session(
            query_config_id=str(getattr(config, "config_id", "") or "") or None,
            query_config_name=str(getattr(config, "name", "") or "") or None,
            runtime_session_id=runtime_session_id,
        )

    def _mark_account_not_login(self, *, account_id: str, error: str) -> None:
        account = None
        get_account = getattr(self._account_repository, "get_account", None)
        if callable(get_account):
            try:
                account = get_account(account_id)
            except Exception:
                account = None

        if (
            account is not None
            and str(getattr(account, "purchase_capability_state", "") or "") == PurchaseCapabilityState.EXPIRED
            and str(getattr(account, "last_error", "") or "") == error
        ):
            return

        update_account = getattr(self._account_repository, "update_account", None)
        if callable(update_account):
            try:
                update_account(
                    account_id,
                    purchase_capability_state=PurchaseCapabilityState.EXPIRED,
                    purchase_pool_state=PurchasePoolState.PAUSED_AUTH_INVALID,
                    last_error=error,
                    updated_at=datetime.now().isoformat(timespec="seconds"),
                )
            except Exception:
                pass

        if self._purchase_runtime_service is not None:
            mark_account_auth_invalid = getattr(self._purchase_runtime_service, "mark_account_auth_invalid", None)
            if callable(mark_account_auth_invalid):
                try:
                    mark_account_auth_invalid(account_id=account_id, error=error)
                except Exception:
                    pass
        self._schedule_stop_when_query_capacity_exhausted()

    def _mark_account_api_key_ip_invalid(self, *, account_id: str, error: str) -> None:
        account = None
        get_account = getattr(self._account_repository, "get_account", None)
        if callable(get_account):
            try:
                account = get_account(account_id)
            except Exception:
                account = None

        if (
            account is not None
            and str(getattr(account, "last_error", "") or "") == error
            and not bool(getattr(account, "new_api_enabled", True))
            and not bool(getattr(account, "fast_api_enabled", True))
            and str(getattr(account, "api_query_disabled_reason", "") or "") == "ip_invalid"
        ):
            return

        update_account = getattr(self._account_repository, "update_account", None)
        if not callable(update_account):
            return
        try:
            update_account(
                account_id,
                new_api_enabled=False,
                fast_api_enabled=False,
                api_query_disabled_reason="ip_invalid",
                last_error=error,
                updated_at=datetime.now().isoformat(timespec="seconds"),
            )
        except Exception:
            return
        try:
            self.refresh_runtime_accounts()
        except Exception:
            pass
        self._schedule_stop_when_query_capacity_exhausted()
        sync_service = self._open_api_binding_sync_service
        sync_account_now = getattr(sync_service, "sync_account_now", None) if sync_service is not None else None
        if callable(sync_account_now):
            try:
                sync_account_now(account_id, final=False)
            except Exception:
                return

    def _get_or_create_runtime_account(self, account: object) -> RuntimeAccountAdapter:
        account_id = str(getattr(account, "account_id", "") or "")
        if not account_id:
            return RuntimeAccountAdapter(account)
        runtime_account = self._runtime_accounts.get(account_id)
        if runtime_account is None:
            runtime_account = RuntimeAccountAdapter(account)
            self._runtime_accounts[account_id] = runtime_account
            return runtime_account
        runtime_account.bind_account(account)
        return runtime_account

    def _schedule_stop_when_query_capacity_exhausted(self) -> None:
        runtime_to_stop = None
        with self._state_lock:
            if self._auto_stop_requested or not self._has_running_runtime_locked():
                return
            config_id = self._get_active_config_id_locked()
            if not config_id:
                return
            config = self._query_config_repository.get_config(config_id)
            if config is None:
                return
            config = self._resolve_runtime_config(config)
            if self._has_available_query_capacity(config):
                return
            runtime_to_stop = self._runtime
            self._auto_stop_requested = True
        if runtime_to_stop is None:
            with self._state_lock:
                self._auto_stop_requested = False
            return
        threading.Thread(
            target=self._stop_runtime_if_still_current,
            args=(runtime_to_stop,),
            name="query-runtime-auto-stop",
            daemon=True,
        ).start()

    def _stop_runtime_if_still_current(self, runtime_to_stop) -> None:
        should_stop = False
        try:
            with self._state_lock:
                should_stop = (
                    runtime_to_stop is not None
                    and self._runtime is runtime_to_stop
                    and self._has_running_runtime_locked()
                )
            if should_stop:
                self.stop()
        finally:
            with self._state_lock:
                self._auto_stop_requested = False

    def _has_available_query_capacity(self, config: QueryConfig) -> bool:
        enabled_modes = {
            str(mode_setting.mode_type)
            for mode_setting in getattr(config, "mode_settings", []) or []
            if bool(getattr(mode_setting, "enabled", False))
        }
        if not enabled_modes:
            return True
        for account in self._account_repository.list_accounts():
            if self._account_supports_any_enabled_mode(account, enabled_modes=enabled_modes):
                return True
        return False

    def _account_supports_any_enabled_mode(self, account: object, *, enabled_modes: set[str]) -> bool:
        if QueryMode.NEW_API in enabled_modes and bool(getattr(account, "api_key", None)) and bool(
            getattr(account, "new_api_enabled", False)
        ):
            return True
        if QueryMode.FAST_API in enabled_modes and bool(getattr(account, "api_key", None)) and bool(
            getattr(account, "fast_api_enabled", False)
        ):
            return True
        if QueryMode.TOKEN not in enabled_modes:
            return False
        if not bool(getattr(account, "token_enabled", False)):
            return False
        if str(getattr(account, "last_error", "") or "").strip() == "Not login":
            return False
        return self._has_access_token(getattr(account, "cookie_raw", None))

    @staticmethod
    def _has_access_token(cookie_raw: str | None) -> bool:
        if not cookie_raw:
            return False
        for raw_part in str(cookie_raw).split(";"):
            key, _, value = raw_part.strip().partition("=")
            if key == "NC5_accessToken" and bool(value):
                return True
        return False

    def _close_runtime_accounts(self) -> None:
        runtime_accounts = list(self._runtime_accounts.values())
        self._runtime_accounts = {}
        for runtime_account in runtime_accounts:
            try:
                _run_coroutine_sync(runtime_account.close_global_session())
            except Exception:
                pass
            try:
                _run_coroutine_sync(runtime_account.close_api_session())
            except Exception:
                pass


def _run_coroutine_sync(coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result_holder: dict[str, object] = {}
    error_holder: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result_holder["value"] = asyncio.run(coroutine)
        except BaseException as exc:  # pragma: no cover - defensive thread bridge
            error_holder["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder.get("value")
