from __future__ import annotations

import threading
from collections import OrderedDict, deque

from .runtime_events import PurchaseHitBatch


class PurchaseScheduler:
    def __init__(self) -> None:
        self._queue: deque[PurchaseHitBatch] = deque()
        self._account_status: dict[str, dict[str, object]] = {}
        self._available_account_ids: list[str] = []
        self._idle_account_ids_by_bucket: dict[str, OrderedDict[str, None]] = {}
        self._idle_account_bucket_by_account_id: dict[str, str] = {}
        self._current_index = 0
        self._lock = threading.RLock()

    def register_account(
        self,
        account_id: str,
        *,
        available: bool,
        bucket_key: str = "direct",
        max_inflight: int = 1,
    ) -> None:
        with self._lock:
            self._remove_idle_account_locked(account_id)
            self._remove_available_account_locked(account_id)
            inflight_limit = max(int(max_inflight), 1)
            self._account_status[account_id] = {
                "available": bool(available),
                "busy": False,
                "inflight_count": 0,
                "max_inflight": inflight_limit,
                "bucket_key": str(bucket_key or "direct"),
                "disabled_reason": None if available else "no_available_inventory",
            }
            if available:
                self._add_available_account_locked(account_id)
                self._add_idle_account_locked(account_id)

    def submit(self, batch: PurchaseHitBatch) -> None:
        with self._lock:
            self._queue.append(batch)

    def pop_next_batch(self) -> PurchaseHitBatch | None:
        with self._lock:
            if not self._queue:
                return None
            return self._queue.popleft()

    def requeue_batch_front(self, batch: PurchaseHitBatch) -> None:
        with self._lock:
            self._queue.appendleft(batch)

    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear_queue(self) -> int:
        return len(self.clear_queue_batches())

    def clear_queue_batches(self) -> list[PurchaseHitBatch]:
        with self._lock:
            cleared = list(self._queue)
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
                status = self._account_status.get(account_id, {})
                inflight_count = int(status.get("inflight_count", 0) or 0)
                max_inflight = max(int(status.get("max_inflight", 1) or 1), 1)
                if inflight_count < max_inflight:
                    return account_id
            return None

    @staticmethod
    def _normalize_bucket_key(bucket_key: object) -> str:
        return str(bucket_key or "direct")

    @staticmethod
    def _max_inflight_from_status(status: dict[str, object]) -> int:
        return max(int(status.get("max_inflight", 1) or 1), 1)

    @classmethod
    def _can_accept_more_work(cls, status: dict[str, object]) -> bool:
        inflight_count = int(status.get("inflight_count", 0) or 0)
        return bool(status.get("available")) and inflight_count < cls._max_inflight_from_status(status)

    def _add_available_account_locked(self, account_id: str) -> None:
        if account_id not in self._available_account_ids:
            self._available_account_ids.append(account_id)

    def _remove_available_account_locked(self, account_id: str) -> None:
        if account_id not in self._available_account_ids:
            return
        remove_index = self._available_account_ids.index(account_id)
        self._available_account_ids.remove(account_id)
        if self._available_account_ids:
            if remove_index < self._current_index:
                self._current_index -= 1
            self._current_index %= len(self._available_account_ids)
        else:
            self._current_index = 0

    def _add_idle_account_locked(self, account_id: str) -> None:
        status = self._account_status.get(account_id)
        if status is None or not self._can_accept_more_work(status):
            self._remove_idle_account_locked(account_id)
            return
        bucket_key = self._normalize_bucket_key(status.get("bucket_key"))
        existing_bucket_key = self._idle_account_bucket_by_account_id.get(account_id)
        existing_bucket = self._idle_account_ids_by_bucket.get(bucket_key)
        if (
            existing_bucket_key == bucket_key
            and existing_bucket is not None
            and account_id in existing_bucket
        ):
            return
        self._remove_idle_account_locked(account_id)
        idle_bucket = self._idle_account_ids_by_bucket.setdefault(bucket_key, OrderedDict())
        idle_bucket[account_id] = None
        self._idle_account_bucket_by_account_id[account_id] = bucket_key

    def _remove_idle_account_locked(self, account_id: str) -> None:
        bucket_key = self._idle_account_bucket_by_account_id.pop(account_id, None)
        if bucket_key is None:
            return
        idle_bucket = self._idle_account_ids_by_bucket.get(bucket_key)
        if idle_bucket is None:
            return
        idle_bucket.pop(account_id, None)
        if not idle_bucket:
            self._idle_account_ids_by_bucket.pop(bucket_key, None)

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
            self._remove_idle_account_locked(account_id)
            self._remove_available_account_locked(account_id)

    def mark_available(self, account_id: str) -> None:
        with self._lock:
            status = self._account_status.setdefault(account_id, {})
            status["available"] = True
            status["bucket_key"] = self._normalize_bucket_key(status.get("bucket_key"))
            status["max_inflight"] = self._max_inflight_from_status(status)
            status["disabled_reason"] = None
            inflight_count = int(status.get("inflight_count", 0) or 0)
            max_inflight = self._max_inflight_from_status(status)
            status["busy"] = inflight_count >= max_inflight
            self._add_available_account_locked(account_id)
            self._add_idle_account_locked(account_id)

    def release_account(self, account_id: str) -> None:
        with self._lock:
            status = self._account_status.get(account_id)
            if status is None:
                return
            inflight_count = max(int(status.get("inflight_count", 0) or 0) - 1, 0)
            status["inflight_count"] = inflight_count
            max_inflight = self._max_inflight_from_status(status)
            status["busy"] = bool(status.get("available")) and inflight_count >= max_inflight
            self._add_idle_account_locked(account_id)

    def claim_idle_accounts_by_bucket(self, *, limit_per_bucket: int) -> list[str]:
        effective_limit = max(int(limit_per_bucket), 0)
        if effective_limit <= 0:
            return []

        with self._lock:
            claimed: list[str] = []
            requeue_by_bucket: dict[str, list[str]] = {}
            for bucket_key in tuple(self._idle_account_ids_by_bucket.keys()):
                idle_bucket = self._idle_account_ids_by_bucket.get(bucket_key)
                if not idle_bucket:
                    continue
                bucket_claimed = 0
                while bucket_claimed < effective_limit and idle_bucket:
                    account_id, _ = idle_bucket.popitem(last=False)
                    self._idle_account_bucket_by_account_id.pop(account_id, None)
                    status = self._account_status.get(account_id)
                    if status is None or not self._can_accept_more_work(status):
                        continue

                    inflight_count = int(status.get("inflight_count", 0) or 0) + 1
                    max_inflight = self._max_inflight_from_status(status)
                    status["inflight_count"] = inflight_count
                    status["busy"] = inflight_count >= max_inflight
                    claimed.append(account_id)
                    bucket_claimed += 1
                    if inflight_count < max_inflight:
                        requeue_by_bucket.setdefault(bucket_key, []).append(account_id)
                if not idle_bucket:
                    self._idle_account_ids_by_bucket.pop(bucket_key, None)

            for bucket_key, account_ids in requeue_by_bucket.items():
                idle_bucket = self._idle_account_ids_by_bucket.setdefault(bucket_key, OrderedDict())
                for account_id in account_ids:
                    if account_id in self._idle_account_bucket_by_account_id:
                        continue
                    idle_bucket[account_id] = None
                    self._idle_account_bucket_by_account_id[account_id] = bucket_key
            return claimed

    def available_account_ids(self) -> list[str]:
        with self._lock:
            return list(self._available_account_ids)

    def account_status(self, account_id: str) -> dict[str, object]:
        with self._lock:
            return dict(self._account_status[account_id])

    def update_account_max_inflight(self, account_id: str, *, max_inflight: int) -> None:
        with self._lock:
            status = self._account_status.get(account_id)
            if status is None:
                return
            inflight_limit = max(int(max_inflight), 1)
            status["max_inflight"] = inflight_limit
            inflight_count = int(status.get("inflight_count", 0) or 0)
            status["busy"] = bool(status.get("available")) and inflight_count >= inflight_limit
            self._add_idle_account_locked(account_id)

    def update_account_bucket(self, account_id: str, *, bucket_key: str) -> None:
        with self._lock:
            status = self._account_status.get(account_id)
            if status is None:
                return
            status["bucket_key"] = self._normalize_bucket_key(bucket_key)
            self._add_idle_account_locked(account_id)

    def total_inflight_count(self) -> int:
        with self._lock:
            return sum(max(int(status.get("inflight_count", 0) or 0), 0) for status in self._account_status.values())

    def drop_expired_batches(
        self,
        *,
        now: float | None = None,
        max_wait_seconds: float | None = None,
    ) -> list[PurchaseHitBatch]:
        with self._lock:
            return self._drop_expired_locked(now=now, max_wait_seconds=max_wait_seconds)

    def next_expiration_delay(
        self,
        *,
        now: float | None = None,
        max_wait_seconds: float | None = None,
    ) -> float | None:
        if max_wait_seconds is None or max_wait_seconds <= 0:
            return None

        current_time = float(now) if now is not None else None
        with self._lock:
            if not self._queue:
                return None
            batch = self._queue[0]
            enqueued_at = getattr(batch, "enqueued_at", None)
            if enqueued_at is None:
                return None
            if current_time is None:
                import time

                current_time = time.monotonic()
            delay = float(enqueued_at) + float(max_wait_seconds) - float(current_time)
            return max(delay, 0.0)

    def _drop_expired_locked(
        self,
        *,
        now: float | None,
        max_wait_seconds: float | None,
    ) -> list[PurchaseHitBatch]:
        if max_wait_seconds is None or max_wait_seconds <= 0:
            return []

        current_time = float(now) if now is not None else None
        removed: list[PurchaseHitBatch] = []
        while self._queue:
            batch = self._queue[0]
            enqueued_at = getattr(batch, "enqueued_at", None)
            if enqueued_at is None:
                break
            if current_time is None:
                import time

                current_time = time.monotonic()
            if current_time - float(enqueued_at) < float(max_wait_seconds):
                break
            removed.append(self._queue.popleft())
        return removed
