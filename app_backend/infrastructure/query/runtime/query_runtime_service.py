from __future__ import annotations

from collections.abc import Callable
from inspect import Parameter, signature

from app_backend.domain.models.query_config import QueryConfig, QueryModeSetting
from app_backend.infrastructure.query.runtime.query_task_runtime import QueryTaskRuntime

RuntimeFactory = Callable[..., object]


class QueryRuntimeService:
    def __init__(
        self,
        *,
        query_config_repository,
        account_repository,
        runtime_factory: RuntimeFactory | None = None,
        purchase_runtime_service=None,
    ) -> None:
        self._query_config_repository = query_config_repository
        self._account_repository = account_repository
        self._runtime_factory = runtime_factory or self._build_default_runtime
        self._purchase_runtime_service = purchase_runtime_service
        self._runtime = None

    def start(self, *, config_id: str) -> tuple[bool, str]:
        if self._has_running_runtime():
            return False, "已有查询任务在运行"

        config = self._query_config_repository.get_config(config_id)
        if config is None:
            return False, "查询配置不存在"

        purchase_started, purchase_message = self._ensure_purchase_runtime_started()
        if not purchase_started:
            return False, purchase_message

        accounts = list(self._account_repository.list_accounts())
        hit_sink = self._resolve_hit_sink()
        if hit_sink is not None and self._runtime_factory_accepts_hit_sink():
            runtime = self._runtime_factory(config, accounts, hit_sink=hit_sink)
        else:
            runtime = self._runtime_factory(config, accounts)
        runtime.start()
        self._runtime = runtime
        return True, "查询任务已启动"

    def stop(self) -> tuple[bool, str]:
        if not self._has_running_runtime():
            self._runtime = None
            return False, "当前没有运行中的查询任务"

        self._runtime.stop()
        self._runtime = None
        self._stop_linked_purchase_runtime()
        return True, "查询任务已停止"

    def get_status(self) -> dict[str, object]:
        if not self._has_running_runtime():
            self._runtime = None
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
            }
        return self._normalize_snapshot(self._runtime.snapshot(), getattr(self._runtime, "config", None))

    def _has_running_runtime(self) -> bool:
        if self._runtime is None:
            return False
        snapshot = self._runtime.snapshot()
        return bool(snapshot.get("running"))

    def _normalize_snapshot(self, snapshot: dict[str, object], config: QueryConfig | None) -> dict[str, object]:
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
    def _build_default_runtime(config, accounts: list[object], *, hit_sink=None) -> QueryTaskRuntime:
        return QueryTaskRuntime(config, accounts, hit_sink=hit_sink)

    def _resolve_hit_sink(self):
        if self._purchase_runtime_service is None:
            return None
        async_hit_sink = getattr(self._purchase_runtime_service, "accept_query_hit_async", None)
        if callable(async_hit_sink):
            return async_hit_sink
        hit_sink = getattr(self._purchase_runtime_service, "accept_query_hit", None)
        return hit_sink if callable(hit_sink) else None

    def _runtime_factory_accepts_hit_sink(self) -> bool:
        try:
            parameters = signature(self._runtime_factory).parameters.values()
        except (TypeError, ValueError):
            return False

        for parameter in parameters:
            if parameter.kind == Parameter.VAR_KEYWORD:
                return True
            if parameter.name == "hit_sink":
                return True
        return False

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
