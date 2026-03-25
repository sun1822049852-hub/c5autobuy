from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PurchaseHitBatch:
    query_item_name: str
    query_config_id: str | None = None
    query_item_id: str | None = None
    runtime_session_id: str | None = None
    external_item_id: str | None = None
    product_url: str | None = None
    product_list: list[dict[str, Any]] = field(default_factory=list)
    total_price: float = 0.0
    total_wear_sum: float | None = None
    source_mode_type: str = ""
    detail_min_wear: float | None = None
    detail_max_wear: float | None = None
    max_price: float | None = None


@dataclass(slots=True)
class PurchaseExecutionResult:
    status: str
    purchased_count: int = 0
    submitted_count: int = 0
    error: str | None = None
    create_order_latency_ms: float | None = None
    submit_order_latency_ms: float | None = None
    status_code: int | None = None
    request_method: str | None = None
    request_path: str | None = None
    response_text: str | None = None

    @classmethod
    def success(
        cls,
        *,
        purchased_count: int,
        submitted_count: int = 0,
        create_order_latency_ms: float | None = None,
        submit_order_latency_ms: float | None = None,
        status_code: int | None = None,
        request_method: str | None = None,
        request_path: str | None = None,
        response_text: str | None = None,
    ) -> "PurchaseExecutionResult":
        return cls(
            status="success",
            purchased_count=int(purchased_count),
            submitted_count=max(int(submitted_count), 0),
            error=None,
            create_order_latency_ms=create_order_latency_ms,
            submit_order_latency_ms=submit_order_latency_ms,
            status_code=status_code,
            request_method=request_method,
            request_path=request_path,
            response_text=response_text,
        )

    @classmethod
    def auth_invalid(
        cls,
        error: str,
        *,
        submitted_count: int = 0,
        create_order_latency_ms: float | None = None,
        submit_order_latency_ms: float | None = None,
        status_code: int | None = None,
        request_method: str | None = None,
        request_path: str | None = None,
        response_text: str | None = None,
    ) -> "PurchaseExecutionResult":
        return cls(
            status="auth_invalid",
            purchased_count=0,
            submitted_count=max(int(submitted_count), 0),
            error=error,
            create_order_latency_ms=create_order_latency_ms,
            submit_order_latency_ms=submit_order_latency_ms,
            status_code=status_code,
            request_method=request_method,
            request_path=request_path,
            response_text=response_text,
        )


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
    submitted_count: int
    selected_steam_id: str | None
    pool_state: str
    capability_state: str
    requires_remote_refresh: bool
    create_order_latency_ms: float | None = None
    submit_order_latency_ms: float | None = None
    error: str | None = None
    status_code: int | None = None
    request_method: str | None = None
    request_path: str | None = None
    response_text: str | None = None
