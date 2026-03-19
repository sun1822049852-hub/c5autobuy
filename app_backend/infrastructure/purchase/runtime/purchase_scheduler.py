from __future__ import annotations

from collections import deque

from .runtime_events import PurchaseHitBatch


class PurchaseScheduler:
    def __init__(self) -> None:
        self._queue: deque[PurchaseHitBatch] = deque()
        self._account_status: dict[str, dict[str, object]] = {}
        self._available_account_ids: list[str] = []
        self._current_index = 0

    def register_account(self, account_id: str, *, available: bool) -> None:
        self._account_status[account_id] = {
            "available": bool(available),
            "disabled_reason": None if available else "no_available_inventory",
        }
        if available and account_id not in self._available_account_ids:
            self._available_account_ids.append(account_id)

    def submit(self, batch: PurchaseHitBatch) -> None:
        self._queue.append(batch)

    def pop_next_batch(self) -> PurchaseHitBatch:
        return self._queue.popleft()

    def queue_size(self) -> int:
        return len(self._queue)

    def clear_queue(self) -> int:
        cleared = len(self._queue)
        self._queue.clear()
        return cleared

    def total_account_count(self) -> int:
        return len(self._account_status)

    def active_account_count(self) -> int:
        return len(self._available_account_ids)

    def select_next_account_id(self) -> str | None:
        if not self._available_account_ids:
            return None
        account_id = self._available_account_ids[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._available_account_ids)
        return account_id

    def mark_no_inventory(self, account_id: str) -> None:
        self.mark_unavailable(account_id, reason="no_available_inventory")

    def mark_inventory_recovered(self, account_id: str) -> None:
        self.mark_available(account_id)

    def mark_unavailable(self, account_id: str, *, reason: str | None) -> None:
        status = self._account_status.setdefault(account_id, {})
        status["available"] = False
        status["disabled_reason"] = reason
        if account_id in self._available_account_ids:
            remove_index = self._available_account_ids.index(account_id)
            self._available_account_ids.remove(account_id)
            if self._available_account_ids:
                if remove_index < self._current_index:
                    self._current_index -= 1
                self._current_index %= len(self._available_account_ids)
            else:
                self._current_index = 0

    def mark_available(self, account_id: str) -> None:
        status = self._account_status.setdefault(account_id, {})
        status["available"] = True
        status["disabled_reason"] = None
        if account_id not in self._available_account_ids:
            self._available_account_ids.append(account_id)

    def available_account_ids(self) -> list[str]:
        return list(self._available_account_ids)

    def account_status(self, account_id: str) -> dict[str, object]:
        return dict(self._account_status[account_id])
