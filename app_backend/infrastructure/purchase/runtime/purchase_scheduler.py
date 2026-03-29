from __future__ import annotations

import threading
from collections import deque

from .runtime_events import PurchaseHitBatch


class PurchaseScheduler:
    def __init__(self) -> None:
        self._queue: deque[PurchaseHitBatch] = deque()
        self._account_status: dict[str, dict[str, object]] = {}
        self._available_account_ids: list[str] = []
        self._current_index = 0
        self._lock = threading.RLock()

    def register_account(self, account_id: str, *, available: bool, bucket_key: str = "direct") -> None:
        with self._lock:
            self._account_status[account_id] = {
                "available": bool(available),
                "busy": False,
                "bucket_key": str(bucket_key or "direct"),
                "disabled_reason": None if available else "no_available_inventory",
            }
            if available and account_id not in self._available_account_ids:
                self._available_account_ids.append(account_id)

    def submit(self, batch: PurchaseHitBatch) -> None:
        with self._lock:
            self._queue.append(batch)

    def pop_next_batch(self) -> PurchaseHitBatch:
        with self._lock:
            return self._queue.popleft()

    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear_queue(self) -> int:
        with self._lock:
            cleared = len(self._queue)
            self._queue.clear()
            return cleared

    def total_account_count(self) -> int:
        with self._lock:
            return len(self._account_status)

    def active_account_count(self) -> int:
        with self._lock:
            return len(self._available_account_ids)

    def select_next_account_id(self) -> str | None:
        with self._lock:
            if not self._available_account_ids:
                return None
            checked = 0
            while checked < len(self._available_account_ids):
                account_id = self._available_account_ids[self._current_index]
                self._current_index = (self._current_index + 1) % len(self._available_account_ids)
                checked += 1
                if not bool(self._account_status.get(account_id, {}).get("busy")):
                    return account_id
            return None

    def mark_no_inventory(self, account_id: str) -> None:
        self.mark_unavailable(account_id, reason="no_available_inventory")

    def mark_inventory_recovered(self, account_id: str) -> None:
        self.mark_available(account_id)

    def mark_unavailable(self, account_id: str, *, reason: str | None) -> None:
        with self._lock:
            status = self._account_status.setdefault(account_id, {})
            status["available"] = False
            status["busy"] = False
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
        with self._lock:
            status = self._account_status.setdefault(account_id, {})
            status["available"] = True
            status["disabled_reason"] = None
            status["busy"] = False
            if account_id not in self._available_account_ids:
                self._available_account_ids.append(account_id)

    def release_account(self, account_id: str) -> None:
        with self._lock:
            status = self._account_status.get(account_id)
            if status is None:
                return
            status["busy"] = False

    def claim_idle_accounts_by_bucket(self, *, limit_per_bucket: int) -> list[str]:
        effective_limit = max(int(limit_per_bucket), 0)
        if effective_limit <= 0:
            return []

        with self._lock:
            idle_by_bucket: dict[str, list[str]] = {}
            for account_id in self._available_account_ids:
                status = self._account_status.get(account_id, {})
                if not bool(status.get("available")) or bool(status.get("busy")):
                    continue
                bucket_key = str(status.get("bucket_key") or "direct")
                idle_by_bucket.setdefault(bucket_key, []).append(account_id)

            claimed: list[str] = []
            for account_ids in idle_by_bucket.values():
                for account_id in account_ids[:effective_limit]:
                    self._account_status[account_id]["busy"] = True
                    claimed.append(account_id)
            return claimed

    def available_account_ids(self) -> list[str]:
        with self._lock:
            return list(self._available_account_ids)

    def account_status(self, account_id: str) -> dict[str, object]:
        with self._lock:
            return dict(self._account_status[account_id])
