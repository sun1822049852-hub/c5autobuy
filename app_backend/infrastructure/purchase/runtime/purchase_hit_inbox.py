from __future__ import annotations

import time
from typing import Any

from .runtime_events import PurchaseHitBatch


class PurchaseHitInbox:
    def __init__(self, *, cache_duration: float = 5.0, now_provider=None) -> None:
        self._cache_duration = max(float(cache_duration), 0.0)
        self._now_provider = now_provider or time.time
        self._cache: dict[str, float] = {}

    def accept(self, hit: dict[str, Any]) -> PurchaseHitBatch | None:
        total_wear_sum = hit.get("total_wear_sum")
        if total_wear_sum is not None:
            cache_key = f"{float(total_wear_sum):.12f}"
            current_time = float(self._now_provider())
            self._clean_expired(current_time)
            cached_at = self._cache.get(cache_key)
            if cached_at is not None and current_time - cached_at < self._cache_duration:
                return None
            self._cache[cache_key] = current_time

        return PurchaseHitBatch(
            query_item_name=str(hit.get("query_item_name") or ""),
            external_item_id=str(hit.get("external_item_id") or "") or None,
            product_url=str(hit.get("product_url") or "") or None,
            product_list=list(hit.get("product_list") or []),
            total_price=float(hit.get("total_price") or 0.0),
            total_wear_sum=float(total_wear_sum) if total_wear_sum is not None else None,
            source_mode_type=str(hit.get("mode_type") or ""),
        )

    def _clean_expired(self, current_time: float) -> None:
        expired_keys = [
            cache_key
            for cache_key, cached_at in self._cache.items()
            if current_time - cached_at >= self._cache_duration
        ]
        for cache_key in expired_keys:
            del self._cache[cache_key]
