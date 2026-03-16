from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class ProductRule:
    url: str
    item_id: str
    minwear: Optional[float] = None
    max_wear: Optional[float] = None
    max_price: Optional[float] = None
    item_name: Optional[str] = None
    market_hash_name: Optional[str] = None
    created_at: Optional[str] = None
    last_modified: Optional[str] = None


@dataclass(slots=True)
class ProductConfig:
    name: str
    created_at: Optional[str] = None
    last_updated: Optional[str] = None
    products: list[ProductRule] = field(default_factory=list)


@dataclass(slots=True)
class AccountProfile:
    user_id: str
    name: str
    proxy: Optional[str] = None
    login: bool = False
    api_key: Optional[str] = None
    created_at: Optional[str] = None
    last_updated: Optional[str] = None
    file_path: Optional[str] = None

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


@dataclass(slots=True)
class ItemSnapshot:
    item_id: str
    item_name: Optional[str] = None
    minwear: Optional[float] = None
    maxwear: Optional[float] = None
    min_price: Optional[float] = None
    grade: Optional[str] = None
    last_modified: Optional[str] = None

