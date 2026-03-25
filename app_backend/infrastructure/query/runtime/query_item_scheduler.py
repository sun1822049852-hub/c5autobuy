from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from app_backend.domain.models.query_config import QueryItem


@dataclass(slots=True)
class QueryItemReservation:
    query_item: QueryItem
    execute_at: float


class QueryItemScheduler:
    def __init__(
        self,
        query_items: list[QueryItem],
        *,
        min_cooldown_seconds: float = 0.1,
        item_min_cooldown_seconds: float = 0.5,
        item_min_cooldown_strategy: str = "divide_by_assigned_count",
    ) -> None:
        self._query_items = list(query_items)
        self._min_cooldown_seconds = max(float(min_cooldown_seconds), 0.0)
        self._item_min_cooldown_seconds = 0.5
        self._item_min_cooldown_strategy = "divide_by_assigned_count"
        self._lock = asyncio.Lock()
        self.apply_item_cooldown_settings(
            item_min_cooldown_seconds=item_min_cooldown_seconds,
            item_min_cooldown_strategy=item_min_cooldown_strategy,
        )
        self.reset()

    async def reserve_next(self, *, now: float | datetime | int | None = None) -> QueryItemReservation | None:
        async with self._lock:
            if not self._query_items:
                return None

            current_time = self._to_seconds(now)
            query_item = self._query_items[self._pointer]
            self._pointer = (self._pointer + 1) % len(self._query_items)
            return self._reserve_item_locked(query_item, current_time=current_time)

    async def reserve_item(
        self,
        query_item: QueryItem,
        *,
        now: float | datetime | int | None = None,
        actual_assigned_count: int | None = None,
    ) -> QueryItemReservation:
        async with self._lock:
            current_time = self._to_seconds(now)
            return self._reserve_item_locked(
                query_item,
                current_time=current_time,
                actual_assigned_count=actual_assigned_count,
            )

    def reset(self) -> None:
        self._pointer = 0
        self._available_at = {
            str(query_item.query_item_id): 0.0
            for query_item in self._query_items
        }

    def apply_mode_setting(self, mode_setting) -> None:
        self.apply_item_cooldown_settings(
            item_min_cooldown_seconds=getattr(mode_setting, "item_min_cooldown_seconds", 0.5),
            item_min_cooldown_strategy=getattr(mode_setting, "item_min_cooldown_strategy", "divide_by_assigned_count"),
        )

    def apply_item_cooldown_settings(
        self,
        *,
        item_min_cooldown_seconds: float,
        item_min_cooldown_strategy: str,
    ) -> None:
        self._item_min_cooldown_seconds = max(float(item_min_cooldown_seconds), 0.0)
        strategy = str(item_min_cooldown_strategy or "divide_by_assigned_count")
        if strategy not in {"fixed", "divide_by_assigned_count"}:
            strategy = "divide_by_assigned_count"
        self._item_min_cooldown_strategy = strategy

    def _reserve_item_locked(
        self,
        query_item: QueryItem,
        *,
        current_time: float,
        actual_assigned_count: int | None = None,
    ) -> QueryItemReservation:
        item_id = str(query_item.query_item_id)
        execute_at = max(current_time, self._available_at.get(item_id, 0.0))
        self._available_at[item_id] = execute_at + self._compute_cooldown_seconds(actual_assigned_count)
        return QueryItemReservation(query_item=query_item, execute_at=execute_at)

    def _compute_cooldown_seconds(self, actual_assigned_count: int | None) -> float:
        if actual_assigned_count is None:
            return self._min_cooldown_seconds
        if self._item_min_cooldown_strategy == "fixed":
            return self._item_min_cooldown_seconds
        count = max(int(actual_assigned_count), 1)
        return self._item_min_cooldown_seconds / count

    @staticmethod
    def _to_seconds(value: float | datetime | int | None) -> float:
        if value is None:
            return datetime.now().timestamp()
        if isinstance(value, datetime):
            return value.timestamp()
        return float(value)
