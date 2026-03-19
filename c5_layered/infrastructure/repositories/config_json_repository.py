from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from c5_layered.domain.models import ProductConfig, ProductRule


class JsonConfigRepository:
    def __init__(self, config_file: Path) -> None:
        self._config_file = config_file

    def list_configs(self) -> list[ProductConfig]:
        raw = self._load_raw()
        configs: list[ProductConfig] = []
        for item in raw.get("configs", []):
            configs.append(self._parse_config(item))
        return configs

    def get_by_name(self, name: str) -> ProductConfig | None:
        for config in self.list_configs():
            if config.name == name:
                return config
        return None

    def save_all(self, configs: list[ProductConfig]) -> None:
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"configs": [self._to_dict(cfg) for cfg in configs]}
        with self._config_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _load_raw(self) -> dict[str, Any]:
        if not self._config_file.exists():
            return {"configs": []}
        try:
            with self._config_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"configs": []}

    @staticmethod
    def _parse_config(data: dict[str, Any]) -> ProductConfig:
        products: list[ProductRule] = []
        for raw in data.get("products", []):
            products.append(
                ProductRule(
                    url=str(raw.get("url", "")),
                    item_id=str(raw.get("item_id", "")),
                    minwear=raw.get("minwear"),
                    max_wear=raw.get("max_wear"),
                    max_price=raw.get("max_price"),
                    item_name=raw.get("item_name"),
                    market_hash_name=raw.get("market_hash_name"),
                    created_at=raw.get("created_at"),
                    last_modified=raw.get("last_modified"),
                )
            )
        return ProductConfig(
            name=str(data.get("name", "")),
            created_at=data.get("created_at"),
            last_updated=data.get("last_updated"),
            products=products,
        )

    @staticmethod
    def _to_dict(config: ProductConfig) -> dict[str, Any]:
        return {
            "name": config.name,
            "created_at": config.created_at,
            "last_updated": config.last_updated,
            "products": [
                {
                    "url": product.url,
                    "item_id": product.item_id,
                    "minwear": product.minwear,
                    "max_wear": product.max_wear,
                    "max_price": product.max_price,
                    "item_name": product.item_name,
                    "market_hash_name": product.market_hash_name,
                    "created_at": product.created_at,
                    "last_modified": product.last_modified,
                }
                for product in config.products
            ],
        }

