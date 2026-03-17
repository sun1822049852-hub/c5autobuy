from __future__ import annotations


class FetchQueryItemDetailUseCase:
    def __init__(self, collector) -> None:
        self._collector = collector

    async def execute(self, *, external_item_id: str, product_url: str):
        return await self._collector.fetch_detail(
            external_item_id=external_item_id,
            product_url=product_url,
        )
