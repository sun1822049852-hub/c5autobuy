from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from typing import Any

from app_backend.domain.models.query_config import QueryItem

from .runtime_account_adapter import RuntimeAccountAdapter
from .runtime_events import QueryExecutionResult


@dataclass(slots=True)
class _LegacyProductItem:
    url: str
    item_id: str
    minwear: float | None
    max_wear: float | None
    max_price: float | None
    item_name: str | None
    market_hash_name: str | None
    created_at: str
    last_modified: str

    @property
    def product_url(self) -> str:
        return self.url


class LegacyScannerAdapter:
    _SCANNER_MAP = {
        "new_api": "C5MarketAPIScanner",
        "fast_api": "C5MarketAPIFastScanner",
        "token": "ProductQueryScanner",
    }

    def __init__(self, *, legacy_module: Any | None = None) -> None:
        self._legacy_module = legacy_module

    def build_scanner(self, mode_type: str, *, account: object, query_item: QueryItem) -> object:
        runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
        scanner_cls = getattr(self._get_legacy_module(), self._SCANNER_MAP[mode_type])
        return scanner_cls(
            runtime_account,
            self._build_legacy_product_item(query_item),
        )

    async def execute_query(
        self,
        *,
        mode_type: str,
        account: object,
        query_item: QueryItem,
    ) -> QueryExecutionResult:
        started_at = time.perf_counter()
        try:
            runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
            scanner = self.build_scanner(mode_type, account=runtime_account, query_item=query_item)
            if mode_type == "token":
                session = await runtime_account.get_global_session()
                if session is None:
                    return QueryExecutionResult(
                        success=False,
                        match_count=0,
                        product_list=[],
                        total_price=0.0,
                        total_wear_sum=0.0,
                        error="无法创建浏览器会话",
                        latency_ms=(time.perf_counter() - started_at) * 1000,
                    )
                result = await scanner.execute_query(session)
            else:
                result = await scanner.execute_query()
        except Exception as exc:
            latency_ms = (time.perf_counter() - started_at) * 1000
            return QueryExecutionResult(
                success=False,
                match_count=0,
                product_list=[],
                total_price=0.0,
                total_wear_sum=0.0,
                error=str(exc),
                latency_ms=latency_ms,
            )

        latency_ms = (time.perf_counter() - started_at) * 1000
        success, match_count, product_list, total_price, total_wear_sum, error = self._normalize_result(result)
        return QueryExecutionResult(
            success=success,
            match_count=match_count,
            product_list=product_list,
            total_price=total_price,
            total_wear_sum=total_wear_sum,
            error=error,
            latency_ms=latency_ms,
        )

    def _get_legacy_module(self) -> Any:
        if self._legacy_module is None:
            self._legacy_module = importlib.import_module("autobuy")
        return self._legacy_module

    @staticmethod
    def _build_legacy_product_item(query_item: QueryItem) -> _LegacyProductItem:
        return _LegacyProductItem(
            url=query_item.product_url,
            item_id=str(query_item.external_item_id),
            minwear=query_item.min_wear,
            max_wear=query_item.max_wear,
            max_price=query_item.max_price,
            item_name=query_item.item_name,
            market_hash_name=query_item.market_hash_name,
            created_at=query_item.created_at,
            last_modified=query_item.updated_at,
        )

    @staticmethod
    def _normalize_result(result: Any) -> tuple[bool, int, list[dict[str, Any]], float, float, str | None]:
        if isinstance(result, QueryExecutionResult):
            return (
                bool(result.success),
                int(result.match_count),
                list(result.product_list),
                float(result.total_price),
                float(result.total_wear_sum),
                result.error,
            )
        if isinstance(result, tuple) and len(result) == 6:
            success, match_count, product_list, total_price, total_wear_sum, error = result
            return (
                bool(success),
                int(match_count or 0),
                list(product_list or []),
                float(total_price or 0.0),
                float(total_wear_sum or 0.0),
                error,
            )
        raise ValueError("Unsupported legacy scanner result")
