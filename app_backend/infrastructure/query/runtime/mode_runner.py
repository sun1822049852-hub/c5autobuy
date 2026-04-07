from __future__ import annotations

import asyncio
import inspect
import random
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from typing import Any

# 北京时间时区 (UTC+8)
_TZ_CST = timezone(timedelta(hours=8))


def _cst_date_str(dt: datetime | None = None) -> str:
    """返回北京时间的日期字符串 YYYY-MM-DD，用于跨天检测。"""
    now = dt if dt is not None else datetime.now(tz=_TZ_CST)
    if now.tzinfo is None:
        # 本地 naive datetime 当作北京时间处理
        now = now.replace(tzinfo=_TZ_CST)
    return now.astimezone(_TZ_CST).strftime("%Y-%m-%d")


from app_backend.domain.models.query_config import QueryItem, QueryModeSetting

from .account_query_worker import AccountQueryWorker
from .query_mode_allocator import QueryModeAllocator
from .query_item_scheduler import QueryItemScheduler
from .runtime_events import QueryExecutionEvent
from app_backend.infrastructure.stats.runtime.stats_events import (
    QueryExecutionStatsEvent,
    QueryHitStatsEvent,
)
from .window_scheduler import WindowScheduler


class ModeRunner:
    _RECENT_EVENT_LIMIT = 1000

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
        stats_sink=None,
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
        self._stats_sink = stats_sink
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
        # 当天北京日期，用于跨天自动清零
        self._count_date: str = _cst_date_str(self._as_datetime(self._now_provider()))

    def start(self, *, preserve_allocation_state: bool = False) -> None:
        self._started = True
        self._has_run_cycle = False
        self._last_error = None
        self._recent_events = []
        self._worker_cooldown_until = {}

        # ── 跨天检测（北京时间）：仅跨天时清零计数，同天保留 ──
        today = _cst_date_str(self._as_datetime(self._now_provider()))
        if today != self._count_date:
            self._query_count = 0
            self._found_count = 0
            self._item_query_counts = {
                str(query_item.query_item_id): 0
                for query_item in self._query_items
            }
            self._count_date = today
        else:
            # 同天：补全新 item 的计数槽位，已有槽位保留
            for query_item in self._query_items:
                item_id = str(query_item.query_item_id)
                if item_id not in self._item_query_counts:
                    self._item_query_counts[item_id] = 0

        if not preserve_allocation_state:
            self._query_item_scheduler.reset()
            self._query_mode_allocator.reset()
        self._workers = [
            self._worker_factory(self._mode_setting.mode_type, account)
            for account in self._eligible_accounts()
        ]

    @property
    def mode_type(self) -> str:
        return str(self._mode_setting.mode_type)

    def stop(self) -> None:
        self._started = False
        self._has_run_cycle = False
        self._workers = []

    def refresh_accounts(self, accounts: list[object]) -> None:
        self._accounts = list(accounts)
        latest_by_account_id = {
            str(getattr(account, "account_id", "") or ""): account
            for account in self._accounts
        }
        for worker in self._workers:
            worker_account = getattr(worker, "account", None)
            account_id = str(getattr(worker_account, "account_id", "") or "")
            if not account_id:
                continue
            latest_account = latest_by_account_id.get(account_id, worker_account)
            refresh_account = getattr(worker, "refresh_account", None)
            if callable(refresh_account):
                refresh_account(
                    latest_account,
                    eligible=self._is_eligible_account(latest_account),
                )

    def sync_query_items(self, query_items: list[QueryItem]) -> None:
        self._query_items = list(query_items or [])
        self._item_query_counts = {
            str(query_item.query_item_id): int(self._item_query_counts.get(str(query_item.query_item_id), 0))
            for query_item in self._query_items
        }
        sync_query_items = getattr(self._query_item_scheduler, "sync_query_items", None)
        if callable(sync_query_items):
            sync_query_items(self._query_items)
        sync_allocator_items = getattr(self._query_mode_allocator, "sync_query_items", None)
        if callable(sync_allocator_items):
            sync_allocator_items(self._query_items)

    def apply_query_item_runtime(self, query_item: QueryItem) -> bool:
        item_id = str(query_item.query_item_id)
        next_items = list(self._query_items)
        for index, current_item in enumerate(next_items):
            if str(current_item.query_item_id) != item_id:
                continue
            next_items[index] = query_item
            self.sync_query_items(next_items)
            return True

        next_items.append(query_item)
        self.sync_query_items(next_items)
        return True

    def apply_mode_setting(self, mode_setting: QueryModeSetting) -> None:
        self._mode_setting = mode_setting
        self._window_scheduler = WindowScheduler(
            window_enabled=bool(mode_setting.window_enabled),
            start_hour=mode_setting.start_hour,
            start_minute=mode_setting.start_minute,
            end_hour=mode_setting.end_hour,
            end_minute=mode_setting.end_minute,
        )
        apply_mode_setting = getattr(self._query_item_scheduler, "apply_mode_setting", None)
        if callable(apply_mode_setting):
            apply_mode_setting(mode_setting)

    def apply_manual_allocation_targets(self, *, target_actual_counts: dict[str, int]) -> None:
        allocation_workers = self._allocation_workers()
        self._query_mode_allocator.apply_target_actual_counts(
            target_actual_counts=target_actual_counts,
            active_workers=allocation_workers,
        )

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
        allocation_snapshot = self._query_mode_allocator.snapshot(active_workers=self._allocation_workers())
        item_rows = allocation_snapshot.get("item_rows", [])
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
            "shared_available_count": int(allocation_snapshot.get("shared_available_count", 0)),
            "shared_candidate_count": int(allocation_snapshot.get("shared_candidate_count", 0)),
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

    def _allocation_workers(self) -> list[object]:
        active_workers = self._active_workers()
        if active_workers:
            return active_workers
        return [
            SimpleNamespace(account=account)
            for account in self._eligible_accounts()
        ]

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

    async def _forward_stats(self, event: QueryExecutionEvent) -> None:
        if self._stats_sink is None:
            return

        try:
            execution_result = self._stats_sink(self._build_query_execution_stats_event(event))
            if inspect.isawaitable(execution_result):
                await execution_result
            if int(getattr(event, "match_count", 0)) > 0:
                hit_result = self._stats_sink(self._build_query_hit_stats_event(event))
                if inspect.isawaitable(hit_result):
                    await hit_result
        except Exception:
            return

    async def _handle_event(self, event: QueryExecutionEvent) -> None:
        self._query_count += 1
        self._found_count += int(getattr(event, "match_count", 0))
        self._last_error = getattr(event, "error", None)
        item_id = str(getattr(event, "query_item_id", "") or "")
        if item_id:
            self._item_query_counts[item_id] = self._item_query_counts.get(item_id, 0) + 1
        self._record_event(event)
        await self._forward_event(event)
        await self._forward_stats(event)
        await self._forward_hit(event)

    @staticmethod
    def _build_rule_fingerprint(event: QueryExecutionEvent) -> str:
        detail_min_wear = getattr(event, "detail_min_wear", None)
        detail_max_wear = getattr(event, "detail_max_wear", None)
        max_price = getattr(event, "max_price", None)
        return "|".join(
            [
                "" if detail_min_wear is None else str(detail_min_wear),
                "" if detail_max_wear is None else str(detail_max_wear),
                "" if max_price is None else str(max_price),
            ]
        )

    def _build_query_execution_stats_event(self, event: QueryExecutionEvent) -> QueryExecutionStatsEvent:
        return QueryExecutionStatsEvent(
            timestamp=str(event.timestamp),
            query_config_id=getattr(event, "query_config_id", None),
            query_item_id=str(getattr(event, "query_item_id", "") or ""),
            external_item_id=str(getattr(event, "external_item_id", "") or ""),
            rule_fingerprint=self._build_rule_fingerprint(event),
            detail_min_wear=getattr(event, "detail_min_wear", None),
            detail_max_wear=getattr(event, "detail_max_wear", None),
            max_price=getattr(event, "max_price", None),
            mode_type=str(getattr(event, "mode_type", "") or ""),
            account_id=str(getattr(event, "account_id", "") or ""),
            account_display_name=getattr(event, "account_display_name", None),
            item_name=getattr(event, "query_item_name", None),
            product_url=getattr(event, "product_url", None),
            latency_ms=float(getattr(event, "latency_ms", 0) or 0),
            success=not bool(getattr(event, "error", None)),
            error=getattr(event, "error", None),
        )

    def _build_query_hit_stats_event(self, event: QueryExecutionEvent) -> QueryHitStatsEvent:
        return QueryHitStatsEvent(
            timestamp=str(event.timestamp),
            runtime_session_id=getattr(event, "runtime_session_id", None),
            query_config_id=getattr(event, "query_config_id", None),
            query_item_id=str(getattr(event, "query_item_id", "") or ""),
            external_item_id=str(getattr(event, "external_item_id", "") or ""),
            rule_fingerprint=self._build_rule_fingerprint(event),
            detail_min_wear=getattr(event, "detail_min_wear", None),
            detail_max_wear=getattr(event, "detail_max_wear", None),
            max_price=getattr(event, "max_price", None),
            mode_type=str(getattr(event, "mode_type", "") or ""),
            account_id=str(getattr(event, "account_id", "") or ""),
            account_display_name=getattr(event, "account_display_name", None),
            item_name=getattr(event, "query_item_name", None),
            product_url=getattr(event, "product_url", None),
            matched_count=int(getattr(event, "match_count", 0) or 0),
            product_ids=self._collect_product_ids(event),
        )

    @staticmethod
    def _collect_product_ids(event: QueryExecutionEvent) -> list[str]:
        product_list = getattr(event, "product_list", None)
        if not isinstance(product_list, list):
            return []

        product_ids: list[str] = []
        seen: set[str] = set()
        for product in product_list:
            if not isinstance(product, dict):
                continue
            product_id = str(product.get("productId") or "").strip()
            if not product_id or product_id in seen:
                continue
            seen.add(product_id)
            product_ids.append(product_id)
        return product_ids

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
            "detail_min_wear": getattr(event, "detail_min_wear", None),
            "detail_max_wear": getattr(event, "detail_max_wear", None),
            "max_price": getattr(event, "max_price", None),
            "latency_ms": event.latency_ms,
            "error": event.error,
            "status_code": getattr(event, "status_code", None),
            "request_method": getattr(event, "request_method", None),
            "request_path": getattr(event, "request_path", None),
            "response_text": getattr(event, "response_text", None),
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
