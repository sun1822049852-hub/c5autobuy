from __future__ import annotations

from datetime import datetime

from app_backend.application.services.query_item_settings_service import normalize_mode_allocations, validate_max_price
from app_backend.application.services.query_item_threshold_service import (
    ensure_final_detail_wear_range,
    validate_detail_max_wear,
    validate_detail_min_wear,
)


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
        detail_min_wear: float | None,
        detail_max_wear: float | None,
        max_price: float | None,
        manual_paused: bool = False,
        mode_allocations: dict[str, int] | None = None,
    ):
        parsed = self._parser.parse(product_url)
        product = self._repository.get_product(parsed.external_item_id)
        if product is None or not self._is_complete_product(product):
            detail = await self._collector.fetch_detail(
                external_item_id=parsed.external_item_id,
                product_url=parsed.product_url,
            )
            product = self._repository.upsert_product(
                external_item_id=detail.external_item_id,
                product_url=detail.product_url,
                item_name=detail.item_name,
                market_hash_name=detail.market_hash_name,
                min_wear=detail.min_wear,
                max_wear=detail.max_wear,
                last_market_price=detail.last_market_price,
                last_detail_sync_at=datetime.now().isoformat(timespec="seconds"),
            )

        next_detail_min_wear = product.min_wear if detail_min_wear is None else detail_min_wear
        next_detail_max_wear = product.max_wear if detail_max_wear is None else detail_max_wear
        ensure_final_detail_wear_range(
            detail_min_wear=next_detail_min_wear,
            detail_max_wear=next_detail_max_wear,
        )
        validate_detail_min_wear(
            detail_min_wear=next_detail_min_wear,
            min_wear=product.min_wear,
            max_wear=product.max_wear,
        )
        validate_detail_max_wear(
            detail_max_wear=next_detail_max_wear,
            detail_min_wear=next_detail_min_wear,
            min_wear=product.min_wear,
            max_wear=product.max_wear,
        )
        validate_max_price(max_price)
        return self._repository.add_item(
            config_id=config_id,
            product_url=parsed.product_url,
            external_item_id=product.external_item_id,
            item_name=product.item_name,
            market_hash_name=product.market_hash_name,
            min_wear=product.min_wear,
            max_wear=product.max_wear,
            detail_min_wear=next_detail_min_wear,
            detail_max_wear=next_detail_max_wear,
            max_price=max_price,
            last_market_price=product.last_market_price,
            last_detail_sync_at=product.last_detail_sync_at,
            manual_paused=bool(manual_paused),
            mode_allocations=normalize_mode_allocations(mode_allocations),
        )

    @staticmethod
    def _is_complete_product(product) -> bool:
        return (
            bool(getattr(product, "external_item_id", None))
            and bool(getattr(product, "product_url", None))
            and getattr(product, "min_wear", None) is not None
            and getattr(product, "max_wear", None) is not None
        )
