from __future__ import annotations

import time

from app_backend.domain.models.query_config import QueryItem

from .fast_api_query_executor import FastApiQueryExecutor
from .new_api_query_executor import NewApiQueryExecutor
from .runtime_account_adapter import RuntimeAccountAdapter
from .runtime_events import QueryExecutionResult
from .token_query_executor import TokenQueryExecutor


class QueryExecutorRouter:
    def __init__(
        self,
        *,
        new_api_executor: NewApiQueryExecutor | None = None,
        fast_api_executor: FastApiQueryExecutor | None = None,
        token_executor: TokenQueryExecutor | None = None,
    ) -> None:
        self._new_api_executor = new_api_executor or NewApiQueryExecutor()
        self._fast_api_executor = fast_api_executor or FastApiQueryExecutor()
        self._token_executor = token_executor or TokenQueryExecutor()

    def build_scanner(self, mode_type: str, *, account: object, query_item: QueryItem) -> object:
        raise ValueError(f"{mode_type} is handled by runtime query executors")

    async def execute_query(
        self,
        *,
        mode_type: str,
        account: object,
        query_item: QueryItem,
    ) -> QueryExecutionResult:
        started_at = time.perf_counter()
        runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)

        try:
            if mode_type == "new_api":
                return await self._new_api_executor.execute_query(
                    account=runtime_account,
                    query_item=query_item,
                )
            if mode_type == "fast_api":
                return await self._fast_api_executor.execute_query(
                    account=runtime_account,
                    query_item=query_item,
                )
            if mode_type == "token":
                return await self._token_executor.execute_query(
                    account=runtime_account,
                    query_item=query_item,
                )
        except Exception as exc:
            return QueryExecutionResult(
                success=False,
                match_count=0,
                product_list=[],
                total_price=0.0,
                total_wear_sum=0.0,
                error=str(exc),
                latency_ms=(time.perf_counter() - started_at) * 1000,
            )

        return QueryExecutionResult(
            success=False,
            match_count=0,
            product_list=[],
            total_price=0.0,
            total_wear_sum=0.0,
            error=f"Unsupported mode_type: {mode_type}",
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )
