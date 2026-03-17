from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


Fetcher = Callable[..., Awaitable[dict]]


@dataclass(slots=True)
class ProductDetail:
    external_item_id: str
    product_url: str
    item_name: str | None
    market_hash_name: str | None
    min_wear: float | None
    max_wear: float | None
    last_market_price: float | None


async def _missing_fetcher(**_: object) -> dict:
    raise NotImplementedError("ProductDetailCollector 需要注入 fetcher")


class ProductDetailCollector:
    def __init__(self, *, fetcher: Fetcher | None = None) -> None:
        self._fetcher = fetcher or _missing_fetcher

    async def fetch_detail(self, *, external_item_id: str, product_url: str) -> ProductDetail:
        payload = await self._fetcher(
            external_item_id=external_item_id,
            product_url=product_url,
        )
        return ProductDetail(
            external_item_id=str(payload.get("external_item_id") or external_item_id),
            product_url=str(payload.get("product_url") or product_url),
            item_name=payload.get("item_name"),
            market_hash_name=payload.get("market_hash_name"),
            min_wear=payload.get("min_wear"),
            max_wear=payload.get("max_wear"),
            last_market_price=payload.get("last_market_price"),
        )
