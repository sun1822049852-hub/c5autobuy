from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from app_backend.domain.models.query_config import QueryItem

from .legacy_scanner_adapter import LegacyScannerAdapter
from .runtime_account_adapter import RuntimeAccountAdapter
from .runtime_events import QueryExecutionEvent, QueryExecutionResult


class AccountQueryWorker:
    def __init__(
        self,
        *,
        mode_type: str,
        account: object,
        scanner_adapter: LegacyScannerAdapter | Any | None = None,
        now_provider=None,
    ) -> None:
        self._mode_type = mode_type
        self._account = account
        self._runtime_account = RuntimeAccountAdapter(account)
        self._scanner_adapter = scanner_adapter or LegacyScannerAdapter()
        self._now_provider = now_provider or time.time
        self._query_count = 0
        self._found_count = 0
        self._disabled_reason: str | None = None
        self._backoff_until: float | datetime | None = None
        self._rate_limit_increment = 0.0
        self._last_query_at: float | datetime | None = None
        self._last_success_at: float | datetime | None = None
        self._last_error: str | None = None

    @property
    def account(self) -> object:
        return self._account

    async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent | None:
        if not self._is_active():
            return None

        now_value = self._now_provider()
        self._last_query_at = now_value
        self._query_count += 1

        result = await self._scanner_adapter.execute_query(
            mode_type=self._mode_type,
            account=self._runtime_account,
            query_item=query_item,
        )
        self._apply_result(now_value, result)
        return QueryExecutionEvent(
            timestamp=self._format_timestamp(now_value),
            level="info" if result.success else "error",
            mode_type=self._mode_type,
            account_id=str(getattr(self._account, "account_id")),
            account_display_name=str(getattr(self._account, "display_name", None) or getattr(self._account, "default_name", "") or ""),
            query_item_id=query_item.query_item_id,
            external_item_id=query_item.external_item_id,
            product_url=query_item.product_url,
            message="query completed" if result.success else (result.error or "query failed"),
            match_count=int(result.match_count),
            query_item_name=query_item.item_name or query_item.market_hash_name or query_item.query_item_id,
            product_list=list(result.product_list),
            total_price=float(result.total_price) if result.success and result.match_count > 0 else None,
            total_wear_sum=float(result.total_wear_sum) if result.success and result.match_count > 0 else None,
            latency_ms=result.latency_ms,
            error=result.error,
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "account_id": str(getattr(self._account, "account_id")),
            "active": self._is_active(),
            "eligible": True,
            "query_count": self._query_count,
            "found_count": self._found_count,
            "disabled_reason": self._disabled_reason,
            "backoff_until": self._format_time_value(self._backoff_until),
            "rate_limit_increment": round(self._rate_limit_increment, 2),
            "last_query_at": self._format_time_value(self._last_query_at),
            "last_success_at": self._format_time_value(self._last_success_at),
            "last_error": self._last_error,
        }

    async def cleanup(self) -> None:
        await self._runtime_account.close_global_session()
        await self._runtime_account.close_api_session()

    def _apply_result(self, now_value: float | datetime, result: QueryExecutionResult) -> None:
        self._last_error = result.error
        if result.success:
            self._found_count += int(result.match_count)
            self._last_success_at = now_value
            return

        error = (result.error or "").strip()
        if error == "HTTP 429 Too Many Requests":
            self._rate_limit_increment = round(self._rate_limit_increment + 0.05, 2)
            self._backoff_until = self._add_seconds(now_value, 600)
            return

        if error == "Not login" or "HTTP 403" in error:
            self._disabled_reason = error or "query disabled"

    def _is_active(self) -> bool:
        if self._disabled_reason:
            return False
        if self._backoff_until is None:
            return True
        return self._to_seconds(self._now_provider()) >= self._to_seconds(self._backoff_until)

    @staticmethod
    def _add_seconds(now_value: float | datetime, seconds: float) -> float | datetime:
        if isinstance(now_value, datetime):
            return now_value + timedelta(seconds=seconds)
        return float(now_value) + seconds

    @staticmethod
    def _to_seconds(value: float | datetime) -> float:
        if isinstance(value, datetime):
            return value.timestamp()
        return float(value)

    @staticmethod
    def _format_timestamp(now_value: float | datetime) -> str:
        if isinstance(now_value, datetime):
            return now_value.isoformat(timespec="seconds")
        return datetime.fromtimestamp(float(now_value)).isoformat(timespec="seconds")

    @staticmethod
    def _format_time_value(value: float | datetime | None) -> float | str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")
        return float(value)
