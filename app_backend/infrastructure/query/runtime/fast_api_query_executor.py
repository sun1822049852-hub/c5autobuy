from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from app_backend.domain.models.query_config import QueryItem

from .runtime_account_adapter import RuntimeAccountAdapter
from .runtime_events import QueryExecutionResult

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional dependency in unit tests
    aiohttp = None


class FastApiQueryExecutor:
    BASE_URL = "https://openapi.c5game.com/merchant/market/v2/products/list"

    @classmethod
    def build_request_url(cls) -> str:
        return cls.BASE_URL

    @staticmethod
    def build_request_params(account: RuntimeAccountAdapter) -> dict[str, str]:
        return {"app-key": str(account.get_api_key() or "")}

    @staticmethod
    def build_request_body(query_item: QueryItem, *, page_size: int = 50) -> dict[str, object]:
        return {
            "pageSize": min(page_size, 50),
            "pageNum": 1,
            "appId": 730,
            "marketHashName": query_item.market_hash_name,
            "delivery": 1,
            "assetType": 1,
        }

    @staticmethod
    def build_request_headers() -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    async def execute_query(
        self,
        *,
        account: RuntimeAccountAdapter,
        query_item: QueryItem,
        session: Any | None = None,
    ) -> QueryExecutionResult:
        started_at = time.perf_counter()
        runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
        active_session = session

        if active_session is None:
            active_session = await runtime_account.get_api_session()
            if active_session is None:
                active_session = await runtime_account.get_api_session(force_new=True)
                if active_session is None:
                    return self._build_failure_result("无法创建OpenAPI会话", started_at=started_at)

        if getattr(active_session, "closed", False):
            active_session = await runtime_account.get_api_session(force_new=True)
            if active_session is None:
                return self._build_failure_result("OpenAPI会话已关闭且无法重新创建", started_at=started_at)

        try:
            async with active_session.post(
                url=self.build_request_url(),
                params=self.build_request_params(runtime_account),
                json=self.build_request_body(query_item),
                headers=self.build_request_headers(),
                timeout=self._build_request_timeout(),
            ) as response:
                status = response.status
                text = await response.text()
        except asyncio.TimeoutError:
            return self._build_failure_result("请求超时 (8秒)", started_at=started_at)
        except Exception as exc:
            if aiohttp is not None and isinstance(exc, aiohttp.ClientError):
                return self._build_failure_result(f"网络错误: {exc}", started_at=started_at)
            return self._build_failure_result(f"请求失败: {exc}", started_at=started_at)

        if status == 429:
            return self._build_failure_result("HTTP 429 Too Many Requests", started_at=started_at)
        if status == 403:
            return self._build_failure_result("HTTP 403 请求失败 (可能IP未加入白名单)", started_at=started_at)
        if status != 200:
            return self._build_failure_result(f"HTTP {status} 请求失败", started_at=started_at)

        success, match_count, product_list, total_price, total_wear_sum, error = self._parse_response(
            text,
            query_item=query_item,
        )
        return QueryExecutionResult(
            success=success,
            match_count=match_count,
            product_list=product_list,
            total_price=total_price,
            total_wear_sum=total_wear_sum,
            error=error,
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )

    @staticmethod
    def _build_request_timeout():
        if aiohttp is None:  # pragma: no cover - exercised only without aiohttp
            return 8
        return aiohttp.ClientTimeout(total=8)

    @staticmethod
    def _build_failure_result(error: str, *, started_at: float) -> QueryExecutionResult:
        return QueryExecutionResult(
            success=False,
            match_count=0,
            product_list=[],
            total_price=0.0,
            total_wear_sum=0.0,
            error=error,
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )

    def _parse_response(
        self,
        response_text: str | dict[str, Any],
        *,
        query_item: QueryItem,
    ) -> tuple[bool, int, list[dict[str, Any]], float, float, str | None]:
        try:
            data = json.loads(response_text) if isinstance(response_text, str) else response_text
            if not data.get("success", False):
                error_msg = data.get("errorMsg", "未知错误")
                error_code = data.get("errorCode")
                if error_code:
                    error_msg = f"{error_msg} (代码: {error_code})"
                return False, 0, [], 0.0, 0.0, f"API请求失败: {error_msg}"

            item_list = data.get("data", {}).get("list", [])
            processed_results = [
                item
                for item in (self._quick_process_item(raw_item, query_item=query_item) for raw_item in item_list)
                if item
            ]
            if not processed_results:
                return True, 0, [], 0.0, 0.0, None

            product_list: list[dict[str, Any]] = []
            total_price_sum = 0.0
            total_wear_sum = 0.0
            for product_info, price, wear in processed_results:
                product_list.append(product_info)
                total_price_sum += price
                if wear is not None:
                    total_wear_sum += wear
            return True, len(product_list), product_list, total_price_sum, total_wear_sum, None
        except json.JSONDecodeError:
            return False, 0, [], 0.0, 0.0, "响应不是有效的JSON格式"
        except Exception as exc:
            return False, 0, [], 0.0, 0.0, f"解析响应失败: {exc}"

    @staticmethod
    def _quick_process_item(
        item: dict[str, Any],
        *,
        query_item: QueryItem,
    ) -> tuple[dict[str, Any], float, float | None] | None:
        product_id = item.get("productId")
        price_str = item.get("price")
        if not product_id or price_str is None:
            return None

        try:
            price = float(price_str)
            if float(query_item.max_price) > 0 and price > float(query_item.max_price):
                return None
        except (TypeError, ValueError):
            return None

        min_wear = float(query_item.configured_min_wear)
        max_wear = float(query_item.configured_max_wear)
        need_wear_check = min_wear > 0 or max_wear < 1

        wear = None
        asset_info = item.get("assetInfo")
        if isinstance(asset_info, dict):
            wear_value = asset_info.get("floatWear")
            if wear_value is not None:
                try:
                    wear = float(wear_value)
                    if need_wear_check and (wear < min_wear or wear > max_wear):
                        return None
                except (TypeError, ValueError):
                    if need_wear_check:
                        return None
                    wear = None
        elif need_wear_check:
            return None

        rounded_price = round(price, 2)
        product_info = {
            "productId": str(product_id),
            "price": rounded_price,
            "actRebateAmount": 0,
        }
        return product_info, rounded_price, wear
