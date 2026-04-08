from __future__ import annotations

import re
from dataclasses import dataclass

from app_backend.infrastructure.query.product_url_utils import normalize_c5_product_url


@dataclass(slots=True)
class ProductUrlParseResult:
    product_url: str
    external_item_id: str


class ProductUrlParser:
    _ITEM_ID_PATTERN = re.compile(r"(\d{8,})")

    def parse(self, product_url: str) -> ProductUrlParseResult:
        normalized_url = normalize_c5_product_url(product_url)
        match = self._ITEM_ID_PATTERN.search(normalized_url)
        if not match:
            raise ValueError("无法从商品 URL 中解析 item_id")
        return ProductUrlParseResult(
            product_url=normalized_url,
            external_item_id=match.group(1),
        )
