from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class ProductUrlParseResult:
    product_url: str
    external_item_id: str


class ProductUrlParser:
    _ITEM_ID_PATTERN = re.compile(r"(\d{8,})")

    def parse(self, product_url: str) -> ProductUrlParseResult:
        normalized_url = (product_url or "").strip()
        match = self._ITEM_ID_PATTERN.search(normalized_url)
        if not match:
            raise ValueError("无法从商品 URL 中解析 item_id")
        return ProductUrlParseResult(
            product_url=normalized_url,
            external_item_id=match.group(1),
        )
