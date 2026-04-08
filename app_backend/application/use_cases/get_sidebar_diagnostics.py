from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from app_backend.application.use_cases.get_purchase_runtime_status import GetPurchaseRuntimeStatusUseCase


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class GetSidebarDiagnosticsUseCase:
    _QUERY_ACCOUNT_LIMIT = 8
    _PURCHASE_ACCOUNT_LIMIT = 8
    _QUERY_EVENT_LIMIT = 20
    _PURCHASE_EVENT_LIMIT = 20
    _LOGIN_TASK_LIMIT = 12
    _LOGIN_TASK_SCAN_LIMIT = 64
    _LOGIN_EVENT_LIMIT = 3
    _MODE_ORDER = {
        "new_api": 0,
        "fast_api": 1,
        "token": 2,
    }
    _TERMINAL_TASK_STATES = {"succeeded", "success", "failed", "cancelled"}

    def __init__(self, query_runtime_service, purchase_runtime_service, task_manager) -> None:
        self._query_runtime_service = query_runtime_service
        self._purchase_runtime_service = purchase_runtime_service
        self._task_manager = task_manager

    def execute(self) -> dict[str, object]:
        query_snapshot = self._read_query_snapshot()
        purchase_snapshot = self._read_purchase_snapshot(query_snapshot)
        login_snapshot = self._build_login_tasks_snapshot()
        updated_at = self._latest_timestamp(
            query_snapshot.get("updated_at"),
            purchase_snapshot.get("updated_at"),
            login_snapshot.get("updated_at"),
        ) or _now()

        summary = {
            "backend_online": True,
            "query_running": bool(query_snapshot.get("running")),
            "purchase_running": bool(purchase_snapshot.get("running")),
            "active_query_config_name": query_snapshot.get("config_name") or None,
            "last_error": self._first_non_empty(
                query_snapshot.get("last_error"),
                purchase_snapshot.get("last_error"),
                self._latest_login_error(login_snapshot),
            ),
            "updated_at": updated_at,
        }
        return {
            "summary": summary,
            "query": query_snapshot,
            "purchase": purchase_snapshot,
            "login_tasks": login_snapshot,
            "updated_at": updated_at,
        }

    def _read_query_snapshot(self) -> dict[str, object]:
        raw_status = {}
        get_status = getattr(self._query_runtime_service, "get_status", None)
        if callable(get_status):
            snapshot = get_status()
            if isinstance(snapshot, dict):
                raw_status = snapshot
        return self._build_query_snapshot(raw_status)

    def _read_purchase_snapshot(self, query_snapshot: dict[str, object]) -> dict[str, object]:
        raw_status = {}
        if self._purchase_runtime_service is not None:
            snapshot = GetPurchaseRuntimeStatusUseCase(
                self._purchase_runtime_service,
                self._query_runtime_service,
            ).execute()
            if isinstance(snapshot, dict):
                raw_status = snapshot
        return self._build_purchase_snapshot(raw_status, query_snapshot=query_snapshot)

    def _build_query_snapshot(self, raw_status: dict[str, object]) -> dict[str, object]:
        raw_modes = raw_status.get("modes")
        raw_group_rows = raw_status.get("group_rows")
        raw_events = raw_status.get("recent_events")

        mode_rows = []
        if isinstance(raw_modes, dict):
            for mode_type, raw_mode in sorted(
                raw_modes.items(),
                key=lambda item: self._MODE_ORDER.get(str(item[0]), 99),
            ):
                if not isinstance(raw_mode, dict):
                    continue
                mode_rows.append(
                    {
                        "mode_type": str(raw_mode.get("mode_type") or mode_type or ""),
                        "enabled": bool(raw_mode.get("enabled")),
                        "eligible_account_count": int(raw_mode.get("eligible_account_count", 0)),
                        "active_account_count": int(raw_mode.get("active_account_count", 0)),
                        "query_count": int(raw_mode.get("query_count", 0)),
                        "found_count": int(raw_mode.get("found_count", 0)),
                        "last_error": self._coerce_optional_str(raw_mode.get("last_error")),
                    }
                )

        account_rows = []
        if isinstance(raw_group_rows, list):
            for raw_row in raw_group_rows:
                if not isinstance(raw_row, dict):
                    continue
                last_seen_at = (
                    self._coerce_optional_str(raw_row.get("last_success_at"))
                    or self._coerce_optional_str(raw_row.get("last_query_at"))
                    or self._coerce_optional_str(raw_row.get("cooldown_until"))
                )
                row = {
                    "account_id": str(raw_row.get("account_id") or ""),
                    "display_name": self._coerce_optional_str(raw_row.get("account_display_name")),
                    "mode_type": str(raw_row.get("mode_type") or ""),
                    "active": bool(raw_row.get("active")),
                    "query_count": int(raw_row.get("query_count", 0)),
                    "found_count": int(raw_row.get("found_count", 0)),
                    "last_error": self._coerce_optional_str(raw_row.get("last_error")),
                    "disabled_reason": self._coerce_optional_str(raw_row.get("disabled_reason")),
                    "last_seen_at": last_seen_at,
                }
                if row["last_error"] or row["disabled_reason"]:
                    account_rows.append(row)

        account_rows.sort(
            key=lambda row: (
                bool(row["last_error"]),
                bool(row["disabled_reason"]),
                str(row.get("last_seen_at") or ""),
                row["account_id"],
            ),
            reverse=True,
        )
        account_rows = account_rows[: self._QUERY_ACCOUNT_LIMIT]

        recent_events = []
        if isinstance(raw_events, list):
            for raw_event in raw_events[: self._QUERY_EVENT_LIMIT]:
                if not isinstance(raw_event, dict):
                    continue
                recent_events.append(
                    {
                        "timestamp": str(raw_event.get("timestamp") or ""),
                        "level": str(raw_event.get("level") or "info"),
                        "mode_type": str(raw_event.get("mode_type") or ""),
                        "account_id": str(raw_event.get("account_id") or ""),
                        "account_display_name": self._coerce_optional_str(raw_event.get("account_display_name")),
                        "query_item_id": str(raw_event.get("query_item_id") or ""),
                        "query_item_name": self._coerce_optional_str(raw_event.get("query_item_name")),
                        "message": str(raw_event.get("message") or ""),
                        "match_count": int(raw_event.get("match_count", 0)),
                        "total_price": self._coerce_optional_float(raw_event.get("total_price")),
                        "total_wear_sum": self._coerce_optional_float(raw_event.get("total_wear_sum")),
                        "latency_ms": self._coerce_optional_float(raw_event.get("latency_ms")),
                        "error": self._coerce_optional_str(raw_event.get("error")),
                        "status_code": self._coerce_optional_int(raw_event.get("status_code")),
                        "request_method": self._coerce_optional_str(raw_event.get("request_method")),
                        "request_path": self._coerce_optional_str(raw_event.get("request_path")),
                        "response_text": self._coerce_optional_str(raw_event.get("response_text")),
                    }
                )

        updated_at = self._latest_timestamp(
            raw_status.get("started_at"),
            raw_status.get("stopped_at"),
            *[row.get("last_seen_at") for row in account_rows],
            *[event.get("timestamp") for event in recent_events],
        ) or _now()

        return {
            "running": bool(raw_status.get("running")),
            "config_id": self._coerce_optional_str(raw_status.get("config_id")),
            "config_name": self._coerce_optional_str(raw_status.get("config_name")),
            "message": str(raw_status.get("message") or ("运行中" if raw_status.get("running") else "未运行")),
            "total_query_count": int(raw_status.get("total_query_count", 0)),
            "total_found_count": int(raw_status.get("total_found_count", 0)),
            "last_error": self._first_non_empty(
                *[row.get("last_error") for row in mode_rows],
                *[row.get("last_error") for row in account_rows],
                *[event.get("error") for event in recent_events],
                *[row.get("disabled_reason") for row in account_rows],
            ),
            "updated_at": updated_at,
            "mode_rows": mode_rows,
            "account_rows": account_rows,
            "recent_events": recent_events,
        }

    def _build_purchase_snapshot(
        self,
        raw_status: dict[str, object],
        *,
        query_snapshot: dict[str, object],
    ) -> dict[str, object]:
        raw_accounts = raw_status.get("accounts")
        raw_events = raw_status.get("recent_events")

        account_rows = []
        if isinstance(raw_accounts, list):
            for raw_account in raw_accounts:
                if not isinstance(raw_account, dict):
                    continue
                row = {
                    "account_id": str(raw_account.get("account_id") or ""),
                    "display_name": self._coerce_optional_str(raw_account.get("display_name")),
                    "purchase_capability_state": self._coerce_optional_str(raw_account.get("purchase_capability_state")),
                    "purchase_pool_state": self._coerce_optional_str(raw_account.get("purchase_pool_state")),
                    "purchase_disabled": bool(raw_account.get("purchase_disabled", False)),
                    "selected_inventory_name": self._coerce_optional_str(raw_account.get("selected_inventory_name")),
                    "selected_inventory_remaining_capacity": self._coerce_optional_int(
                        raw_account.get("selected_inventory_remaining_capacity")
                    ),
                    "last_error": self._coerce_optional_str(raw_account.get("last_error")),
                }
                if row["last_error"] or row["purchase_disabled"] or str(row["purchase_pool_state"] or "").startswith("paused"):
                    account_rows.append(row)

        account_rows.sort(
            key=lambda row: (
                bool(row["last_error"]),
                bool(row["purchase_disabled"]),
                str(row.get("purchase_pool_state") or ""),
                row["account_id"],
            ),
            reverse=True,
        )
        account_rows = account_rows[: self._PURCHASE_ACCOUNT_LIMIT]

        recent_events = []
        if isinstance(raw_events, list):
            for raw_event in raw_events[: self._PURCHASE_EVENT_LIMIT]:
                if not isinstance(raw_event, dict):
                    continue
                recent_events.append(
                    {
                        "occurred_at": str(raw_event.get("occurred_at") or ""),
                        "status": str(raw_event.get("status") or ""),
                        "message": str(raw_event.get("message") or ""),
                        "query_item_name": str(raw_event.get("query_item_name") or ""),
                        "source_mode_type": str(raw_event.get("source_mode_type") or ""),
                        "total_price": self._coerce_optional_float(raw_event.get("total_price")),
                        "total_wear_sum": self._coerce_optional_float(raw_event.get("total_wear_sum")),
                        "status_code": self._coerce_optional_int(raw_event.get("status_code")),
                        "request_method": self._coerce_optional_str(raw_event.get("request_method")),
                        "request_path": self._coerce_optional_str(raw_event.get("request_path")),
                        "response_text": self._coerce_optional_str(raw_event.get("response_text")),
                    }
                )

        updated_at = self._latest_timestamp(
            raw_status.get("started_at"),
            raw_status.get("stopped_at"),
            *[event.get("occurred_at") for event in recent_events],
        ) or query_snapshot.get("updated_at") or _now()

        return {
            "running": bool(raw_status.get("running")),
            "message": str(raw_status.get("message") or ("运行中" if raw_status.get("running") else "未运行")),
            "active_account_count": int(raw_status.get("active_account_count", 0)),
            "total_purchased_count": int(raw_status.get("total_purchased_count", 0)),
            "last_error": self._first_non_empty(
                *[row.get("last_error") for row in account_rows],
                *[
                    event.get("message")
                    for event in recent_events
                    if self._is_purchase_last_error_event(event)
                ],
            ),
            "updated_at": updated_at,
            "account_rows": account_rows,
            "recent_events": recent_events,
        }

    def _build_login_tasks_snapshot(self) -> dict[str, object]:
        raw_tasks = []
        list_recent_tasks = getattr(self._task_manager, "list_recent_tasks", None)
        if callable(list_recent_tasks):
            raw_tasks = list_recent_tasks(
                task_type="login",
                limit=self._LOGIN_TASK_SCAN_LIMIT,
            )

        recent_tasks = []
        for task in raw_tasks[: self._LOGIN_TASK_LIMIT]:
            event_rows = [
                {
                    "state": event.state,
                    "timestamp": event.timestamp,
                    "message": event.message,
                    "payload": deepcopy(event.payload) if isinstance(event.payload, dict) else None,
                }
                for event in list(getattr(task, "events", []) or [])[-self._LOGIN_EVENT_LIMIT :]
            ]
            result = getattr(task, "result", None) if isinstance(getattr(task, "result", None), dict) else {}
            pending_conflict = (
                getattr(task, "pending_conflict", None)
                if isinstance(getattr(task, "pending_conflict", None), dict)
                else None
            )
            recent_tasks.append(
                {
                    "task_id": task.task_id,
                    "account_id": self._coerce_optional_str(
                        result.get("account_id") if isinstance(result, dict) else None
                    ),
                    "account_display_name": self._coerce_optional_str(
                        result.get("account_display_name") if isinstance(result, dict) else None
                    ),
                    "state": task.state,
                    "started_at": task.created_at,
                    "updated_at": task.updated_at,
                    "last_message": self._extract_last_task_message(task),
                    "result": result or None,
                    "error": self._coerce_optional_str(getattr(task, "error", None)),
                    "pending_conflict": pending_conflict,
                    "events": event_rows,
                }
            )

        updated_at = self._latest_timestamp(*[task.get("updated_at") for task in recent_tasks]) or _now()
        return {
            "running_count": sum(
                1
                for task in raw_tasks
                if task.state not in self._TERMINAL_TASK_STATES and task.state != "conflict"
            ),
            "conflict_count": sum(1 for task in raw_tasks if task.state == "conflict"),
            "failed_count": sum(1 for task in raw_tasks if task.state == "failed"),
            "updated_at": updated_at,
            "recent_tasks": recent_tasks,
        }

    @staticmethod
    def _extract_last_task_message(task) -> str | None:
        events = list(getattr(task, "events", []) or [])
        for event in reversed(events):
            if event.message:
                return event.message
        return getattr(task, "error", None)

    @staticmethod
    def _latest_login_error(login_snapshot: dict[str, object]) -> str | None:
        recent_tasks = login_snapshot.get("recent_tasks")
        if not isinstance(recent_tasks, list):
            return None
        for task in recent_tasks:
            if not isinstance(task, dict):
                continue
            if task.get("state") == "failed" and task.get("last_message"):
                return str(task["last_message"])
        return None

    @staticmethod
    def _first_non_empty(*values: object) -> str | None:
        for value in values:
            text = GetSidebarDiagnosticsUseCase._coerce_optional_str(value)
            if text:
                return text
        return None

    @staticmethod
    def _coerce_optional_str(value: object) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _coerce_optional_float(value: object) -> float | None:
        if value is None or value == "":
            return None
        return float(value)

    @staticmethod
    def _coerce_optional_int(value: object) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    @staticmethod
    def _is_purchase_last_error_event(event: dict[str, object]) -> bool:
        normalized_status = str(event.get("status") or "").strip().lower()
        return normalized_status not in {
            "success",
            "queued",
            "duplicate_filtered",
            "item_unavailable",
        }

    @staticmethod
    def _latest_timestamp(*values: object) -> str | None:
        normalized = [
            str(value).strip()
            for value in values
            if str(value or "").strip()
        ]
        if not normalized:
            return None
        return max(normalized)
