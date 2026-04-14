from __future__ import annotations

from datetime import datetime

class FetchQueryItemDetailUseCase:
    def __init__(self, collector, repository) -> None:
        self._collector = collector
        self._repository = repository

    async def execute(self, *, external_item_id: str, product_url: str):
        detail = await self._collector.fetch_detail(
            external_item_id=external_item_id,
            product_url=product_url,
        )
        try:
            self._repository.upsert_product(
                external_item_id=detail.external_item_id,
                product_url=detail.product_url,
                item_name=detail.item_name,
                market_hash_name=detail.market_hash_name,
                min_wear=detail.min_wear,
                max_wear=detail.max_wear,
                last_market_price=detail.last_market_price,
                last_detail_sync_at=datetime.now().isoformat(timespec="seconds"),
            )
        except Exception as exc:  # pragma: no cover - exercised via route test
            raise RuntimeError("商品缓存写入失败") from exc
        return detail
