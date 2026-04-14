from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class QueryExecutionResult:
    success: bool
    match_count: int
    product_list: list[dict[str, Any]] = field(default_factory=list)
    total_price: float = 0.0
    total_wear_sum: float = 0.0
    error: str | None = None
    latency_ms: float | None = None
    status_code: int | None = None
    request_method: str | None = None
    request_path: str | None = None
    request_body: dict[str, Any] | None = None
    response_text: str | None = None


@dataclass(slots=True)
class QueryExecutionEvent:
    timestamp: str
    level: str
    mode_type: str
    account_id: str
    query_item_id: str
    message: str
    match_count: int
    query_config_id: str | None = None
    runtime_session_id: str | None = None
    external_item_id: str | None = None
    product_url: str | None = None
    account_display_name: str | None = None
    query_item_name: str | None = None
    product_list: list[dict[str, Any]] = field(default_factory=list)
    total_price: float | None = None
    total_wear_sum: float | None = None
    detail_min_wear: float | None = None
    detail_max_wear: float | None = None
    max_price: float | None = None
    latency_ms: float | None = None
    error: str | None = None
    status_code: int | None = None
    request_method: str | None = None
    request_path: str | None = None
    request_body: dict[str, Any] | None = None
    response_text: str | None = None
