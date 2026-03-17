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
    def __init__(self, query_items: list[QueryItem], *, min_cooldown_seconds: float = 0.1) -> None:
        self._query_items = list(query_items)
        self._min_cooldown_seconds = max(float(min_cooldown_seconds), 0.0)
        self._lock = asyncio.Lock()
        self.reset()

    async def reserve_next(self, *, now: float | datetime | int | None = None) -> QueryItemReservation | None:
        async with self._lock:
            if not self._query_items:
                return None

            current_time = self._to_seconds(now)
            query_item = self._query_items[self._pointer]
            self._pointer = (self._pointer + 1) % len(self._query_items)

            item_id = str(query_item.query_item_id)
            execute_at = max(current_time, self._available_at.get(item_id, 0.0))
            self._available_at[item_id] = execute_at + self._min_cooldown_seconds
            return QueryItemReservation(query_item=query_item, execute_at=execute_at)

    def reset(self) -> None:
        self._pointer = 0
        self._available_at = {
            str(query_item.query_item_id): 0.0
            for query_item in self._query_items
        }

    @staticmethod
    def _to_seconds(value: float | datetime | int | None) -> float:
        if value is None:
            return datetime.now().timestamp()
        if isinstance(value, datetime):
            return value.timestamp()
        return float(value)
