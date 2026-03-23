from __future__ import annotations

import threading
from collections import deque

from .runtime_events import PurchaseHitBatch


class PurchaseScheduler:
    def __init__(self) -> None:
        self._pending_queue: deque[PurchaseHitBatch] = deque()
        self._dispatch_queue: deque[tuple[str, PurchaseHitBatch]] = deque()
        self._account_status: dict[str, dict[str, object]] = {}
        self._available_account_ids: list[str] = []
        self._ready_account_ids: deque[str] = deque()
        self._busy_account_ids: set[str] = set()
        self._lock = threading.RLock()

    def register_account(self, account_id: str, *, available: bool) -> None:
        with self._lock:
            self._account_status[account_id] = {
                "available": bool(available),
                "disabled_reason": None if available else "no_available_inventory",
            }
            if available and account_id not in self._available_account_ids:
                self._available_account_ids.append(account_id)
            if available:
                self._promote_account_locked(account_id)

    def submit(self, batch: PurchaseHitBatch) -> str:
        with self._lock:
            if self._dispatch_to_ready_locked(batch):
                return "dispatched"
            self._pending_queue.append(batch)
            return "queued"

    def claim_next_dispatch(self) -> tuple[str, PurchaseHitBatch] | None:
        with self._lock:
            self._fill_dispatch_from_pending_locked()
            if not self._dispatch_queue:
                return None
            return self._dispatch_queue.popleft()

    def queue_size(self) -> int:
        with self._lock:
            return len(self._pending_queue) + len(self._dispatch_queue)

    def pending_queue_size(self) -> int:
        with self._lock:
            return len(self._pending_queue)

    def clear_queue(self) -> int:
        with self._lock:
            cleared = len(self._pending_queue) + len(self._dispatch_queue)
            self._pending_queue.clear()
            while self._dispatch_queue:
                account_id, _batch = self._dispatch_queue.popleft()
                self._busy_account_ids.discard(account_id)
                self._promote_account_locked(account_id)
            return cleared

    def total_account_count(self) -> int:
        with self._lock:
            return len(self._account_status)

    def active_account_count(self) -> int:
        with self._lock:
            return len(self._available_account_ids)

    def select_next_account_id(self) -> str | None:
        with self._lock:
            if self._ready_account_ids:
                return self._ready_account_ids[0]
            if not self._available_account_ids:
                return None
            return self._available_account_ids[0]

    def claim_next_account_id(self) -> str | None:
        with self._lock:
            dispatch = self.claim_next_dispatch()
            if dispatch is None:
                return None
            account_id, batch = dispatch
            self._dispatch_queue.appendleft((account_id, batch))
            return account_id

    def finish_account(self, account_id: str) -> bool:
        with self._lock:
            self._busy_account_ids.discard(account_id)
            status = self._account_status.get(account_id) or {}
            if not status.get("available", False):
                return False
            return self._promote_account_locked(account_id)

    def release_account(self, account_id: str) -> None:
        self.finish_account(account_id)

    def mark_no_inventory(self, account_id: str) -> None:
        self.mark_unavailable(account_id, reason="no_available_inventory")

    def mark_inventory_recovered(self, account_id: str) -> None:
        self.mark_available(account_id)

    def mark_unavailable(self, account_id: str, *, reason: str | None) -> None:
        with self._lock:
            status = self._account_status.setdefault(account_id, {})
            status["available"] = False
            status["disabled_reason"] = reason
            self._remove_ready_account_locked(account_id)
            self._requeue_dispatches_for_account_locked(account_id)
            self._busy_account_ids.discard(account_id)
            if account_id in self._available_account_ids:
                self._available_account_ids.remove(account_id)

    def mark_available(self, account_id: str) -> None:
        with self._lock:
            status = self._account_status.setdefault(account_id, {})
            status["available"] = True
            status["disabled_reason"] = None
            if account_id not in self._available_account_ids:
                self._available_account_ids.append(account_id)
            if account_id not in self._busy_account_ids and not self._account_has_dispatch_locked(account_id):
                self._promote_account_locked(account_id)

    def available_account_ids(self) -> list[str]:
        with self._lock:
            return list(self._available_account_ids)

    def ready_account_ids(self) -> list[str]:
        with self._lock:
            return list(self._ready_account_ids)

    def account_status(self, account_id: str) -> dict[str, object]:
        with self._lock:
            status = dict(self._account_status[account_id])
            status["busy"] = account_id in self._busy_account_ids
            return status

    def _dispatch_to_ready_locked(self, batch: PurchaseHitBatch) -> bool:
        if not self._ready_account_ids:
            return False
        account_id = self._ready_account_ids.popleft()
        self._busy_account_ids.add(account_id)
        self._dispatch_queue.append((account_id, batch))
        return True

    def _fill_dispatch_from_pending_locked(self) -> None:
        while self._pending_queue and self._ready_account_ids:
            batch = self._pending_queue.popleft()
            self._dispatch_to_ready_locked(batch)

    def _promote_account_locked(self, account_id: str) -> bool:
        status = self._account_status.get(account_id) or {}
        if not status.get("available", False):
            return False
        if account_id in self._busy_account_ids or self._account_has_dispatch_locked(account_id):
            return False
        self._remove_ready_account_locked(account_id)
        if self._pending_queue:
            batch = self._pending_queue.popleft()
            self._busy_account_ids.add(account_id)
            self._dispatch_queue.append((account_id, batch))
            return True
        self._ready_account_ids.append(account_id)
        return False

    def _remove_ready_account_locked(self, account_id: str) -> None:
        if account_id not in self._ready_account_ids:
            return
        self._ready_account_ids = deque(
            candidate
            for candidate in self._ready_account_ids
            if candidate != account_id
        )

    def _requeue_dispatches_for_account_locked(self, account_id: str) -> None:
        if not self._dispatch_queue:
            return
        remaining_dispatches: deque[tuple[str, PurchaseHitBatch]] = deque()
        requeued_batches: list[PurchaseHitBatch] = []
        while self._dispatch_queue:
            candidate_account_id, batch = self._dispatch_queue.popleft()
            if candidate_account_id == account_id:
                requeued_batches.append(batch)
                continue
            remaining_dispatches.append((candidate_account_id, batch))
        self._dispatch_queue = remaining_dispatches
        for batch in reversed(requeued_batches):
            self._pending_queue.appendleft(batch)

    def _account_has_dispatch_locked(self, account_id: str) -> bool:
        return any(candidate_account_id == account_id for candidate_account_id, _batch in self._dispatch_queue)
