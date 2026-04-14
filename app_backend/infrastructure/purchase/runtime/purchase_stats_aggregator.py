from __future__ import annotations

from queue import Empty, Queue
from threading import Event, RLock, Thread
from typing import Any


class PurchaseStatsAggregator:
    _STOP = object()
    _RECENT_HIT_SOURCE_LIMIT = 10
    _IGNORED_FAILURE_STATUSES = {
        "ignored_no_available_accounts",
        "duplicate_filtered",
        "queued",
        "inventory_recovered",
        "recovery_waiting",
        "backlog_cleared_no_purchase_accounts",
    }

    def __init__(self) -> None:
        self._lock = RLock()
        self._queue: Queue[object] = Queue()
        self._stop_signal = Event()
        self._worker_thread: Thread | None = None
        self._runtime_session_id: str | None = None
        self._query_config_id: str | None = None
        self._query_config_name: str | None = None
        self._matched_product_keys: set[tuple[str, str, str]] = set()
        self._matched_product_count = 0
        self._purchase_success_count = 0
        self._purchase_failed_count = 0
        self._account_stats: dict[str, dict[str, int]] = {}
        self._item_stats: dict[str, dict[str, int]] = {}

    def start(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_signal = Event()
        self._queue = Queue()
        self._worker_thread = Thread(
            target=self._run,
            name="purchase-stats-aggregator",
            daemon=True,
        )
        self._worker_thread.start()

    def stop(self) -> None:
        self._stop_signal.set()
        self._queue.put(self._STOP)
        worker_thread = self._worker_thread
        if worker_thread is not None and worker_thread.is_alive():
            worker_thread.join(timeout=0.5)
        self._worker_thread = None

    def reset(
        self,
        *,
        runtime_session_id: str | None,
        query_config_id: str | None = None,
        query_config_name: str | None = None,
    ) -> None:
        self.start()
        with self._lock:
            self._runtime_session_id = self._normalize_optional_str(runtime_session_id)
            self._query_config_id = self._normalize_optional_str(query_config_id)
            self._query_config_name = self._normalize_optional_str(query_config_name)
            self._matched_product_keys = set()
            self._matched_product_count = 0
            self._purchase_success_count = 0
            self._purchase_failed_count = 0
            self._account_stats = {}
            self._item_stats = {}

    def enqueue_hit(self, hit: dict[str, Any]) -> None:
        self.start()
        self._queue.put(
            (
                "hit",
                {
                    "runtime_session_id": hit.get("runtime_session_id"),
                    "query_item_id": hit.get("query_item_id"),
                    "timestamp": hit.get("timestamp"),
                    "mode_type": hit.get("mode_type"),
                    "account_id": hit.get("account_id"),
                    "account_display_name": hit.get("account_display_name"),
                    "product_list": hit.get("product_list"),
                },
            )
        )

    def enqueue_outcome(
        self,
        *,
        account_id: str | None,
        batch,
        status: str,
        purchased_count: int,
    ) -> None:
        self.start()
        self._queue.put(
            (
                "outcome",
                {
                    "account_id": self._normalize_optional_str(account_id),
                    "runtime_session_id": self._normalize_optional_str(getattr(batch, "runtime_session_id", None)),
                    "query_item_id": self._normalize_optional_str(getattr(batch, "query_item_id", None)),
                    "piece_count": len(list(getattr(batch, "product_list", []) or [])),
                    "status": str(status or ""),
                    "purchased_count": max(int(purchased_count), 0),
                },
            )
        )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "runtime_session_id": self._runtime_session_id,
                "query_config_id": self._query_config_id,
                "query_config_name": self._query_config_name,
                "matched_product_count": self._matched_product_count,
                "purchase_success_count": self._purchase_success_count,
                "purchase_failed_count": self._purchase_failed_count,
                "accounts": [
                    {
                        "account_id": account_id,
                        "submitted_product_count": stats["submitted_product_count"],
                        "purchase_success_count": stats["purchase_success_count"],
                        "purchase_failed_count": stats["purchase_failed_count"],
                    }
                    for account_id, stats in sorted(self._account_stats.items())
                ],
                "item_rows": [
                    {
                        "query_item_id": query_item_id,
                        "matched_product_count": stats["matched_product_count"],
                        "purchase_success_count": stats["purchase_success_count"],
                        "purchase_failed_count": stats["purchase_failed_count"],
                        "source_mode_stats": self._serialize_source_mode_stats(stats),
                        "recent_hit_sources": list(stats["recent_hit_sources"]),
                    }
                    for query_item_id, stats in sorted(self._item_stats.items())
                ],
            }

    def _run(self) -> None:
        while not self._stop_signal.is_set():
            try:
                event = self._queue.get(timeout=0.1)
            except Empty:
                continue
            if event is self._STOP:
                return
            if not isinstance(event, tuple) or len(event) != 2:
                continue
            kind, payload = event
            if kind == "hit" and isinstance(payload, dict):
                self._consume_hit(payload)
            elif kind == "outcome" and isinstance(payload, dict):
                self._consume_outcome(payload)

    def _consume_hit(self, payload: dict[str, object]) -> None:
        runtime_session_id = self._normalize_optional_str(payload.get("runtime_session_id"))
        if not self._session_matches(runtime_session_id):
            return
        session_key = runtime_session_id or self._runtime_session_id or "__default__"
        query_item_id = self._normalize_optional_str(payload.get("query_item_id")) or ""
        product_list = self._normalize_product_list(payload.get("product_list"))
        hit_timestamp = self._normalize_optional_str(payload.get("timestamp"))
        mode_type = self._normalize_optional_str(payload.get("mode_type")) or ""
        account_id = self._normalize_optional_str(payload.get("account_id"))
        account_display_name = self._normalize_optional_str(payload.get("account_display_name"))

        with self._lock:
            item_stats = self._ensure_item_stats(query_item_id)
            matched_in_hit = 0
            for product in product_list:
                product_id = self._normalize_optional_str(product.get("productId"))
                if not product_id:
                    continue
                key = (session_key, query_item_id, product_id)
                if key in self._matched_product_keys:
                    continue
                self._matched_product_keys.add(key)
                self._matched_product_count += 1
                item_stats["matched_product_count"] += 1
                matched_in_hit += 1
            if matched_in_hit > 0:
                self._record_hit_source(
                    item_stats,
                    mode_type=mode_type,
                    account_id=account_id,
                    account_display_name=account_display_name,
                    last_hit_at=hit_timestamp,
                    hit_count=matched_in_hit,
                )

    def _consume_outcome(self, payload: dict[str, object]) -> None:
        runtime_session_id = self._normalize_optional_str(payload.get("runtime_session_id"))
        if not self._session_matches(runtime_session_id):
            return
        piece_count = max(int(payload.get("piece_count") or 0), 0)
        if piece_count <= 0:
            return

        status = str(payload.get("status") or "")
        if status in self._IGNORED_FAILURE_STATUSES:
            return

        success_count = 0
        failed_count = 0
        if status == "success":
            success_count = min(max(int(payload.get("purchased_count") or 0), 0), piece_count)
            failed_count = max(piece_count - success_count, 0)
        else:
            failed_count = piece_count

        account_id = self._normalize_optional_str(payload.get("account_id")) or ""
        query_item_id = self._normalize_optional_str(payload.get("query_item_id")) or ""

        with self._lock:
            if account_id:
                account_stats = self._ensure_account_stats(account_id)
                account_stats["submitted_product_count"] += piece_count
                account_stats["purchase_success_count"] += success_count
                account_stats["purchase_failed_count"] += failed_count
            item_stats = self._ensure_item_stats(query_item_id)
            item_stats["purchase_success_count"] += success_count
            item_stats["purchase_failed_count"] += failed_count
            self._purchase_success_count += success_count
            self._purchase_failed_count += failed_count

    def _session_matches(self, runtime_session_id: str | None) -> bool:
        with self._lock:
            current_session_id = self._runtime_session_id
        if current_session_id is None:
            return runtime_session_id is None or bool(runtime_session_id)
        if runtime_session_id is None:
            return False
        return runtime_session_id == current_session_id

    def _ensure_account_stats(self, account_id: str) -> dict[str, int]:
        return self._account_stats.setdefault(
            account_id,
            {
                "submitted_product_count": 0,
                "purchase_success_count": 0,
                "purchase_failed_count": 0,
            },
        )

    def _ensure_item_stats(self, query_item_id: str) -> dict[str, object]:
        return self._item_stats.setdefault(
            query_item_id,
            {
                "matched_product_count": 0,
                "purchase_success_count": 0,
                "purchase_failed_count": 0,
                "source_mode_stats": {},
                "recent_hit_sources": [],
            },
        )

    def _record_hit_source(
        self,
        item_stats: dict[str, object],
        *,
        mode_type: str,
        account_id: str | None,
        account_display_name: str | None,
        last_hit_at: str | None,
        hit_count: int,
    ) -> None:
        source_rows = item_stats.setdefault("source_mode_stats", {})
        if not isinstance(source_rows, dict):
            source_rows = {}
            item_stats["source_mode_stats"] = source_rows

        source_key = (mode_type, account_id or "")
        row = source_rows.setdefault(
            source_key,
            {
                "mode_type": mode_type,
                "hit_count": 0,
                "last_hit_at": None,
                "account_id": account_id,
                "account_display_name": account_display_name,
            },
        )
        row["hit_count"] = int(row.get("hit_count", 0)) + int(hit_count)
        row["account_id"] = account_id
        row["account_display_name"] = account_display_name
        row["last_hit_at"] = self._pick_latest_timestamp(row.get("last_hit_at"), last_hit_at)

        recent_rows = item_stats.setdefault("recent_hit_sources", [])
        if not isinstance(recent_rows, list):
            recent_rows = []
            item_stats["recent_hit_sources"] = recent_rows
        recent_rows.insert(
            0,
            {
                "mode_type": mode_type,
                "hit_count": int(hit_count),
                "last_hit_at": last_hit_at,
                "account_id": account_id,
                "account_display_name": account_display_name,
            },
        )
        del recent_rows[self._RECENT_HIT_SOURCE_LIMIT :]

    @staticmethod
    def _serialize_source_mode_stats(item_stats: dict[str, object]) -> list[dict[str, object]]:
        raw_rows = item_stats.get("source_mode_stats")
        if not isinstance(raw_rows, dict):
            return []

        serialized = [
            {
                "mode_type": str(row.get("mode_type") or ""),
                "hit_count": int(row.get("hit_count", 0)),
                "last_hit_at": row.get("last_hit_at"),
                "account_id": row.get("account_id"),
                "account_display_name": row.get("account_display_name"),
            }
            for row in raw_rows.values()
            if isinstance(row, dict)
        ]
        serialized.sort(
            key=lambda row: (
                -int(row.get("hit_count", 0)),
                str(row.get("last_hit_at") or ""),
                str(row.get("account_id") or ""),
                str(row.get("mode_type") or ""),
            ),
        )
        return serialized

    @staticmethod
    def _pick_latest_timestamp(current: object, incoming: object) -> str | None:
        current_text = str(current or "").strip() or None
        incoming_text = str(incoming or "").strip() or None
        if current_text is None:
            return incoming_text
        if incoming_text is None:
            return current_text
        return incoming_text if incoming_text >= current_text else current_text

    @staticmethod
    def _normalize_optional_str(value: object) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _normalize_product_list(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [
            dict(product)
            for product in value
            if isinstance(product, dict)
        ]
