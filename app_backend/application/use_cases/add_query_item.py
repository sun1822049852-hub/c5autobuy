from __future__ import annotations

from app_backend.application.services.query_item_threshold_service import validate_max_wear


class AddQueryItemUseCase:
    def __init__(self, repository, parser, collector) -> None:
        self._repository = repository
        self._parser = parser
        self._collector = collector

    async def execute(
        self,
        *,
        config_id: str,
        product_url: str,
        max_wear: float | None,
        max_price: float | None,
    ):
        parsed = self._parser.parse(product_url)
        detail = await self._collector.fetch_detail(
            external_item_id=parsed.external_item_id,
            product_url=parsed.product_url,
        )
        validate_max_wear(
            max_wear=max_wear,
            min_wear=detail.min_wear,
            detail_max_wear=detail.max_wear,
        )
        return self._repository.add_item(
            config_id=config_id,
            product_url=parsed.product_url,
            external_item_id=detail.external_item_id,
            item_name=detail.item_name,
            market_hash_name=detail.market_hash_name,
            min_wear=detail.min_wear,
            detail_max_wear=detail.max_wear,
            max_wear=max_wear,
            max_price=max_price,
            last_market_price=detail.last_market_price,
        )
