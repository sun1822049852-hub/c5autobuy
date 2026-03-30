from __future__ import annotations

import time
import threading
from typing import Any

from .runtime_events import PurchaseHitBatch


class PurchaseHitInbox:
    def __init__(self, *, cache_duration: float = 5.0, now_provider=None) -> None:
        self._cache_duration = max(float(cache_duration), 0.0)
        self._now_provider = now_provider or time.time
        self._cache: dict[str, float] = {}
        self._lock = threading.RLock()

    def accept(self, hit: dict[str, Any]) -> PurchaseHitBatch | None:
        with self._lock:
            current_time = float(self._now_provider())
            total_wear_sum = hit.get("total_wear_sum")
            if total_wear_sum is not None:
                cache_key = self._build_cache_key(total_wear_sum)
                self._clean_expired(current_time)
                cached_at = self._cache.get(cache_key)
                if cached_at is not None and current_time - cached_at < self._cache_duration:
                    return None
                self._cache[cache_key] = current_time

            return PurchaseHitBatch(
                query_item_name=str(hit.get("query_item_name") or ""),
                query_config_id=str(hit.get("query_config_id") or "") or None,
                query_item_id=str(hit.get("query_item_id") or "") or None,
                runtime_session_id=str(hit.get("runtime_session_id") or "") or None,
                external_item_id=str(hit.get("external_item_id") or "") or None,
                product_url=str(hit.get("product_url") or "") or None,
                product_list=list(hit.get("product_list") or []),
                total_price=float(hit.get("total_price") or 0.0),
                total_wear_sum=float(total_wear_sum) if total_wear_sum is not None else None,
                source_mode_type=str(hit.get("mode_type") or ""),
                detail_min_wear=float(hit["detail_min_wear"]) if hit.get("detail_min_wear") is not None else None,
                detail_max_wear=float(hit["detail_max_wear"]) if hit.get("detail_max_wear") is not None else None,
                max_price=float(hit["max_price"]) if hit.get("max_price") is not None else None,
                enqueued_at=current_time,
            )

    def forget_batch(self, batch: PurchaseHitBatch | None) -> None:
        if batch is None:
            return
        cache_key = self._build_cache_key(getattr(batch, "total_wear_sum", None))
        if cache_key is None:
            return
        with self._lock:
            self._cache.pop(cache_key, None)

    def forget_batches(self, batches: list[PurchaseHitBatch]) -> None:
        with self._lock:
            for batch in batches:
                cache_key = self._build_cache_key(getattr(batch, "total_wear_sum", None))
                if cache_key is not None:
                    self._cache.pop(cache_key, None)

    def reset(self) -> None:
        with self._lock:
            self._cache.clear()

    def _clean_expired(self, current_time: float) -> None:
        expired_keys = [
            cache_key
            for cache_key, cached_at in self._cache.items()
            if current_time - cached_at >= self._cache_duration
        ]
        for cache_key in expired_keys:
            del self._cache[cache_key]

    @staticmethod
    def _build_cache_key(total_wear_sum: Any) -> str | None:
        if total_wear_sum is None:
            return None
        return f"{float(total_wear_sum):.12f}"
