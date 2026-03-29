from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class QueryExecutionStatsEvent:
    timestamp: str
    query_config_id: str | None
    query_item_id: str
    external_item_id: str
    rule_fingerprint: str
    detail_min_wear: float | None
    detail_max_wear: float | None
    max_price: float | None
    mode_type: str
    account_id: str
    account_display_name: str | None
    item_name: str | None
    product_url: str | None
    latency_ms: float
    success: bool
    error: str | None


@dataclass(slots=True)
class QueryHitStatsEvent:
    timestamp: str
    runtime_session_id: str | None
    query_config_id: str | None
    query_item_id: str
    external_item_id: str
    rule_fingerprint: str
    detail_min_wear: float | None
    detail_max_wear: float | None
    max_price: float | None
    mode_type: str
    account_id: str
    account_display_name: str | None
    item_name: str | None
    product_url: str | None
    matched_count: int
    product_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PurchaseCreateOrderStatsEvent:
    timestamp: str
    runtime_session_id: str | None
    query_config_id: str | None
    query_item_id: str | None
    external_item_id: str
    rule_fingerprint: str
    detail_min_wear: float | None
    detail_max_wear: float | None
    max_price: float | None
    item_name: str | None
    product_url: str | None
    account_id: str
    account_display_name: str | None
    create_order_latency_ms: float
    submitted_count: int
    status: str
    error: str | None


@dataclass(slots=True)
class PurchaseSubmitOrderStatsEvent:
    timestamp: str
    runtime_session_id: str | None
    query_config_id: str | None
    query_item_id: str | None
    external_item_id: str
    rule_fingerprint: str
    detail_min_wear: float | None
    detail_max_wear: float | None
    max_price: float | None
    item_name: str | None
    product_url: str | None
    account_id: str
    account_display_name: str | None
    submit_order_latency_ms: float
    submitted_count: int
    success_count: int
    failed_count: int
    status: str
    error: str | None
