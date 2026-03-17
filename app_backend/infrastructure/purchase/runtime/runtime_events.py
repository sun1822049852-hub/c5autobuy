from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PurchaseHitBatch:
    query_item_name: str
    external_item_id: str | None = None
    product_url: str | None = None
    product_list: list[dict[str, Any]] = field(default_factory=list)
    total_price: float = 0.0
    total_wear_sum: float | None = None
    source_mode_type: str = ""


@dataclass(slots=True)
class PurchaseExecutionResult:
    status: str
    purchased_count: int = 0
    error: str | None = None

    @classmethod
    def success(cls, *, purchased_count: int) -> "PurchaseExecutionResult":
        return cls(status="success", purchased_count=int(purchased_count))

    @classmethod
    def auth_invalid(cls, error: str) -> "PurchaseExecutionResult":
        return cls(status="auth_invalid", purchased_count=0, error=error)


@dataclass(slots=True)
class InventoryRefreshResult:
    status: str
    inventories: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def success(cls, *, inventories: list[dict[str, Any]]) -> "InventoryRefreshResult":
        return cls(
            status="success",
            inventories=[dict(inventory) for inventory in inventories],
            error=None,
        )

    @classmethod
    def auth_invalid(cls, error: str) -> "InventoryRefreshResult":
        return cls(status="auth_invalid", inventories=[], error=error)


@dataclass(slots=True)
class PurchaseWorkerOutcome:
    status: str
    purchased_count: int
    selected_steam_id: str | None
    pool_state: str
    capability_state: str
    requires_remote_refresh: bool
    error: str | None = None
