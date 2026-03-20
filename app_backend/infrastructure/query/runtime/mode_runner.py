from __future__ import annotations

import asyncio
import inspect
import random
from datetime import datetime
from typing import Any

from app_backend.domain.models.query_config import QueryItem, QueryModeSetting

from .account_query_worker import AccountQueryWorker
from .query_mode_allocator import QueryModeAllocator
from .query_item_scheduler import QueryItemScheduler
from .runtime_events import QueryExecutionEvent
from .window_scheduler import WindowScheduler


class ModeRunner:
    _RECENT_EVENT_LIMIT = 20

    def __init__(
        self,
        mode_setting: QueryModeSetting,
        accounts: list[object],
        *,
        query_items: list[QueryItem] | None = None,
        query_item_scheduler: QueryItemScheduler | None = None,
        query_config_id: str | None = None,
        runtime_session_id: str | None = None,
        worker_factory=None,
        runtime_account_provider=None,
        now_provider=None,
        random_provider=None,
        hit_sink=None,
        event_sink=None,
    ) -> None:
        self._mode_setting = mode_setting
        self._accounts = list(accounts)
        self._query_items = list(query_items or [])
        self._worker_factory = worker_factory or self._build_default_worker
        self._now_provider = now_provider or datetime.now
        self._random_provider = random_provider or random.uniform
        self._query_config_id = str(query_config_id or "") or None
        self._runtime_session_id = str(runtime_session_id or "") or None
        self._runtime_account_provider = runtime_account_provider
        self._hit_sink = hit_sink
        self._event_sink = event_sink
        self._query_item_scheduler = query_item_scheduler or QueryItemScheduler(self._query_items)
        self._query_mode_allocator = QueryModeAllocator(
            mode_setting.mode_type,
            self._query_items,
            query_item_scheduler=self._query_item_scheduler,
        )
        self._window_scheduler = WindowScheduler(
            window_enabled=bool(mode_setting.window_enabled),
            start_hour=mode_setting.start_hour,
            start_minute=mode_setting.start_minute,
            end_hour=mode_setting.end_hour,
            end_minute=mode_setting.end_minute,
        )
        self._workers: list[Any] = []
        self._started = False
        self._has_run_cycle = False
        self._query_count = 0
        self._found_count = 0
        self._last_error: str | None = None
        self._recent_events: list[dict[str, object]] = []
        self._worker_cooldown_until: dict[str, float | None] = {}
        self._item_query_counts: dict[str, int] = {}

    def start(self) -> None:
        self._started = True
        self._has_run_cycle = False
        self._query_count = 0
        self._found_count = 0
        self._last_error = None
        self._recent_events = []
        self._worker_cooldown_until = {}
        self._item_query_counts = {
            str(query_item.query_item_id): 0
            for query_item in self._query_items
        }
        self._query_item_scheduler.reset()
        self._query_mode_allocator.reset()
        self._workers = [
            self._worker_factory(self._mode_setting.mode_type, account)
            for account in self._eligible_accounts()
        ]

    def stop(self) -> None:
        self._started = False
        self._has_run_cycle = False
        self._workers = []

    async def cleanup(self) -> None:
        for worker in self._workers:
            cleanup = getattr(worker, "cleanup", None)
            if callable(cleanup):
                await cleanup()

    async def run_loop(self, stop_event) -> None:
        if not self._workers:
            while self._started and not stop_event.is_set():
                await self._wait_for_stop(stop_event, 0.1)
            return

        worker_tasks = [
            asyncio.create_task(self._run_worker_loop(worker, stop_event))
            for worker in self._workers
        ]
        try:
            await asyncio.gather(*worker_tasks, return_exceptions=True)
        finally:
            for task in worker_tasks:
                if not task.done():
                    task.cancel()
            if worker_tasks:
                await asyncio.gather(*worker_tasks, return_exceptions=True)

    async def run_once(self) -> list[object]:
        if not self._started or not self._mode_setting.enabled or not self._query_items:
            return []

        if not self._window_scheduler.compute(now=self._as_datetime(self._now_provider())).in_window:
            return []

        events: list[object] = []
        self._has_run_cycle = True
        active_workers = self._active_workers()
        for worker in active_workers:
            reservation = await self._reserve_next_item(worker, active_workers=active_workers)
            if reservation is None:
                break
            await self._wait_until(None, reservation.execute_at)
            event = await worker.run_once(reservation.query_item)
            if event is not None:
                await self._handle_event(event)
                events.append(event)
        return events

    def snapshot(self) -> dict[str, object]:
        enabled = bool(self._mode_setting.enabled)
        window_state = self._window_scheduler.compute(now=self._as_datetime(self._now_provider()))
        worker_snapshots = [worker.snapshot() for worker in self._workers]
        last_error = self._last_error
        if last_error is None:
            for worker_snapshot in worker_snapshots:
                error = worker_snapshot.get("last_error")
                if error:
                    last_error = error
        next_window_start = None
        next_window_end = None
        if enabled and self._mode_setting.window_enabled:
            next_window_start = window_state.next_window_start.isoformat(timespec="seconds")
            next_window_end = window_state.next_window_end.isoformat(timespec="seconds")
        item_rows = self._query_mode_allocator.snapshot(active_workers=self._active_workers()).get("item_rows", [])
        for row in item_rows:
            if not isinstance(row, dict):
                continue
            item_id = str(row.get("query_item_id") or "")
            row["query_count"] = int(self._item_query_counts.get(item_id, 0))

        return {
            "mode_type": self._mode_setting.mode_type,
            "enabled": enabled,
            "eligible_account_count": self._count_eligible_accounts(),
            "active_account_count": sum(1 for snapshot in worker_snapshots if snapshot.get("active")) if self._has_run_cycle else 0,
            "in_window": enabled and window_state.in_window if enabled else False,
            "next_window_start": next_window_start,
            "next_window_end": next_window_end,
            "query_count": self._query_count,
            "found_count": self._found_count,
            "last_error": last_error,
            "group_rows": self._build_group_rows(worker_snapshots, in_window=bool(enabled and window_state.in_window)),
            "item_rows": item_rows,
            "recent_events": list(self._recent_events),
        }

    def _count_eligible_accounts(self) -> int:
        if not self._mode_setting.enabled:
            return 0
        return len(self._eligible_accounts())

    def _eligible_accounts(self) -> list[object]:
        if not self._mode_setting.enabled:
            return []
        return [account for account in self._accounts if self._is_eligible_account(account)]

    def _active_workers(self) -> list[object]:
        active_workers: list[object] = []
        for worker in self._workers:
            snapshot = worker.snapshot()
            if snapshot.get("active"):
                active_workers.append(worker)
        return active_workers

    def _build_default_worker(self, mode_type: str, account: object) -> AccountQueryWorker:
        runtime_account = None
        if callable(self._runtime_account_provider):
            runtime_account = self._runtime_account_provider(account)
        return AccountQueryWorker(
            mode_type=mode_type,
            account=account,
            runtime_account=runtime_account,
        )

    async def _reserve_next_item(self, worker: object, *, active_workers: list[object]):
        if not hasattr(self._query_item_scheduler, "reserve_item"):
            return await self._query_item_scheduler.reserve_next(now=self._now_provider())
        return await self._query_mode_allocator.reserve_next(
            worker,
            active_workers=active_workers,
            now=self._now_provider(),
        )

    async def _run_worker_loop(self, worker: object, stop_event) -> None:
        while self._started and not stop_event.is_set():
            if not self._mode_setting.enabled or not self._query_items:
                if await self._wait_for_stop(stop_event, 0.1):
                    return
                continue

            worker_snapshot = worker.snapshot()
            if not worker_snapshot.get("active"):
                if worker_snapshot.get("disabled_reason"):
                    return
                if await self._wait_for_stop(stop_event, 0.1):
                    return
                continue

            now = self._as_datetime(self._now_provider())
            window_state = self._window_scheduler.compute(now=now)
            if not window_state.in_window:
                wait_seconds = max((window_state.next_window_start - now).total_seconds(), 0.0)
                if await self._wait_for_stop(stop_event, wait_seconds):
                    return
                continue

            self._has_run_cycle = True
            reservation = await self._reserve_next_item(
                worker,
                active_workers=self._active_workers(),
            )
            if reservation is None:
                if await self._wait_for_stop(stop_event, 0.1):
                    return
                continue

            if await self._wait_until(stop_event, reservation.execute_at):
                return

            event = await worker.run_once(reservation.query_item)
            if event is not None:
                await self._handle_event(event)

            worker_snapshot = worker.snapshot()
            cooldown_seconds = self._compute_cycle_delay(
                rate_limit_increment=worker_snapshot.get("rate_limit_increment", 0.0),
            )
            self._set_worker_cooldown_until(worker, cooldown_seconds)
            if await self._wait_for_stop(stop_event, cooldown_seconds):
                return
            self._clear_worker_cooldown_until(worker)

    def _compute_cycle_delay(self, *, rate_limit_increment: object = 0.0) -> float:
        base_delay = self._pick_delay(
            self._mode_setting.base_cooldown_min,
            self._mode_setting.base_cooldown_max,
        )
        random_delay = 0.0
        if self._mode_setting.random_delay_enabled:
            random_delay = self._pick_delay(
                self._mode_setting.random_delay_min,
                self._mode_setting.random_delay_max,
            )
        try:
            rate_limit_delay = max(float(rate_limit_increment or 0.0), 0.0)
        except (TypeError, ValueError):
            rate_limit_delay = 0.0
        return max(base_delay + random_delay + rate_limit_delay, 0.0)

    def _pick_delay(self, minimum: float, maximum: float) -> float:
        minimum_value = max(float(minimum), 0.0)
        maximum_value = max(float(maximum), minimum_value)
        if maximum_value == minimum_value:
            return minimum_value
        return float(self._random_provider(minimum_value, maximum_value))

    def _is_eligible_account(self, account: object) -> bool:
        mode_type = self._mode_setting.mode_type
        if mode_type == "new_api":
            return bool(getattr(account, "new_api_enabled", False)) and bool(getattr(account, "api_key", None))
        if mode_type == "fast_api":
            return bool(getattr(account, "fast_api_enabled", False)) and bool(getattr(account, "api_key", None))
        if mode_type == "token":
            if str(getattr(account, "last_error", "") or "").strip() == "Not login":
                return False
            return bool(getattr(account, "token_enabled", False)) and self._has_access_token(
                getattr(account, "cookie_raw", None)
            )
        return False

    @staticmethod
    def _has_access_token(cookie_raw: str | None) -> bool:
        if not cookie_raw:
            return False

        for raw_part in cookie_raw.split(";"):
            key, _, value = raw_part.strip().partition("=")
            if key == "NC5_accessToken" and bool(value):
                return True
        return False

    @staticmethod
    def _as_datetime(value: datetime | float | int) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromtimestamp(float(value))

    @staticmethod
    async def _wait_for_stop(stop_event, timeout: float) -> bool:
        timeout_value = max(float(timeout), 0.0)
        if timeout_value == 0:
            await asyncio.sleep(0)
            return bool(stop_event is not None and stop_event.is_set())
        if stop_event is None:
            await asyncio.sleep(timeout_value)
            return False
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=timeout_value)
            return True
        except asyncio.TimeoutError:
            return False

    async def _wait_until(self, stop_event, execute_at: float) -> bool:
        delay = max(float(execute_at) - self._to_timestamp(self._now_provider()), 0.0)
        if delay <= 0:
            return bool(stop_event is not None and stop_event.is_set())
        return await self._wait_for_stop(stop_event, delay)

    def _record_event(self, event: QueryExecutionEvent) -> None:
        if int(getattr(event, "match_count", 0)) <= 0 and not getattr(event, "error", None):
            return
        self._recent_events.insert(0, self._serialize_event(event))
        del self._recent_events[self._RECENT_EVENT_LIMIT :]

    async def _forward_hit(self, event: QueryExecutionEvent) -> None:
        if self._hit_sink is None or int(getattr(event, "match_count", 0)) <= 0:
            return

        result = self._hit_sink(self._serialize_event(event))
        if inspect.isawaitable(result):
            await result

    async def _forward_event(self, event: QueryExecutionEvent) -> None:
        if self._event_sink is None:
            return

        result = self._event_sink(self._serialize_event(event))
        if inspect.isawaitable(result):
            await result

    async def _handle_event(self, event: QueryExecutionEvent) -> None:
        self._query_count += 1
        self._found_count += int(getattr(event, "match_count", 0))
        self._last_error = getattr(event, "error", None)
        item_id = str(getattr(event, "query_item_id", "") or "")
        if item_id:
            self._item_query_counts[item_id] = self._item_query_counts.get(item_id, 0) + 1
        self._record_event(event)
        await self._forward_event(event)
        await self._forward_hit(event)

    def _build_group_rows(self, worker_snapshots: list[dict[str, object]], *, in_window: bool) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for worker, worker_snapshot in zip(self._workers, worker_snapshots, strict=False):
            account = getattr(worker, "account", None)
            account_id = str(worker_snapshot.get("account_id") or getattr(account, "account_id", "") or "")
            display_name = str(getattr(account, "display_name", None) or account_id)
            cooldown_until = worker_snapshot.get("backoff_until") or self._worker_cooldown_until.get(account_id)
            rows.append(
                {
                    "account_id": account_id,
                    "account_display_name": display_name,
                    "mode_type": self._mode_setting.mode_type,
                    "active": bool(worker_snapshot.get("active")),
                    "in_window": in_window,
                    "cooldown_until": self._format_optional_timestamp(cooldown_until),
                    "last_query_at": self._format_optional_timestamp(worker_snapshot.get("last_query_at")),
                    "last_success_at": self._format_optional_timestamp(worker_snapshot.get("last_success_at")),
                    "query_count": int(worker_snapshot.get("query_count", 0)),
                    "found_count": int(worker_snapshot.get("found_count", 0)),
                    "disabled_reason": worker_snapshot.get("disabled_reason"),
                    "last_error": worker_snapshot.get("last_error"),
                    "rate_limit_increment": float(worker_snapshot.get("rate_limit_increment", 0.0) or 0.0),
                }
            )
        return rows

    def _set_worker_cooldown_until(self, worker: object, cooldown_seconds: float) -> None:
        account = getattr(worker, "account", None)
        account_id = str(getattr(account, "account_id", "") or "")
        if not account_id:
            return
        self._worker_cooldown_until[account_id] = self._to_timestamp(self._now_provider()) + max(float(cooldown_seconds), 0.0)

    def _clear_worker_cooldown_until(self, worker: object) -> None:
        account = getattr(worker, "account", None)
        account_id = str(getattr(account, "account_id", "") or "")
        if not account_id:
            return
        self._worker_cooldown_until[account_id] = None

    def _serialize_event(self, event: QueryExecutionEvent) -> dict[str, object]:
        query_config_id = str(getattr(event, "query_config_id", "") or self._query_config_id or "") or None
        runtime_session_id = str(getattr(event, "runtime_session_id", "") or self._runtime_session_id or "") or None
        return {
            "timestamp": event.timestamp,
            "level": event.level,
            "mode_type": event.mode_type,
            "query_config_id": query_config_id,
            "runtime_session_id": runtime_session_id,
            "account_id": event.account_id,
            "account_display_name": event.account_display_name,
            "query_item_id": event.query_item_id,
            "external_item_id": event.external_item_id,
            "product_url": event.product_url,
            "query_item_name": event.query_item_name,
            "message": event.message,
            "match_count": int(event.match_count),
            "product_list": list(event.product_list),
            "total_price": event.total_price,
            "total_wear_sum": event.total_wear_sum,
            "latency_ms": event.latency_ms,
            "error": event.error,
        }

    @staticmethod
    def _to_timestamp(value: datetime | float | int) -> float:
        if isinstance(value, datetime):
            return value.timestamp()
        return float(value)

    @staticmethod
    def _format_optional_timestamp(value: object) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")
        return datetime.fromtimestamp(float(value)).isoformat(timespec="seconds")
