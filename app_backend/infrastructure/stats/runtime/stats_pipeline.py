from __future__ import annotations

from queue import Empty, Full, Queue
import threading

from .stats_events import (
    PurchaseCreateOrderStatsEvent,
    PurchaseSubmitOrderStatsEvent,
    QueryExecutionStatsEvent,
    QueryHitStatsEvent,
)


class StatsPipeline:
    def __init__(
        self,
        *,
        repository,
        max_queue_size: int = 1000,
        flush_batch_size: int = 100,
        flush_interval_seconds: float = 0.25,
    ) -> None:
        self._repository = repository
        self._queue: Queue[object] = Queue(maxsize=max_queue_size)
        self._flush_batch_size = max(int(flush_batch_size), 1)
        self._flush_interval_seconds = max(float(flush_interval_seconds), 0.01)
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._dropped_event_count = 0

    @property
    def dropped_event_count(self) -> int:
        return self._dropped_event_count

    def start(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="stats-pipeline",
            daemon=True,
        )
        self._worker_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        worker_thread = self._worker_thread
        if worker_thread is not None and worker_thread.is_alive():
            worker_thread.join(timeout=0.2)
        self._worker_thread = None

    def enqueue(self, event: object) -> bool:
        try:
            self._queue.put_nowait(event)
            return True
        except Full:
            self._dropped_event_count += 1
            return False

    def flush_pending(self) -> int:
        drained = 0
        while drained < self._flush_batch_size:
            try:
                event = self._queue.get_nowait()
            except Empty:
                break
            self._dispatch(event)
            drained += 1
        return drained

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=self._flush_interval_seconds)
            except Empty:
                continue

            self._dispatch(event)
            processed = 1
            while processed < self._flush_batch_size:
                try:
                    next_event = self._queue.get_nowait()
                except Empty:
                    break
                self._dispatch(next_event)
                processed += 1

    def _dispatch(self, event: object) -> None:
        if isinstance(event, QueryExecutionStatsEvent):
            self._repository.apply_query_execution_event(event)
            return
        if isinstance(event, QueryHitStatsEvent):
            self._repository.apply_query_hit_event(event)
            return
        if isinstance(event, PurchaseCreateOrderStatsEvent):
            self._repository.apply_purchase_create_order_event(event)
            return
        if isinstance(event, PurchaseSubmitOrderStatsEvent):
            self._repository.apply_purchase_submit_order_event(event)
            return
        raise TypeError(f"Unsupported stats event: {type(event)!r}")
