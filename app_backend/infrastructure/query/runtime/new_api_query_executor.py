from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from urllib.parse import urlsplit

from app_backend.domain.models.query_config import QueryItem

from .runtime_account_adapter import RuntimeAccountAdapter
from .runtime_events import QueryExecutionResult

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional dependency in unit tests
    aiohttp = None


class NewApiQueryExecutor:
    BASE_URL = "https://openapi.c5game.com/merchant/market/v2/products/search"

    @classmethod
    def build_request_url(cls) -> str:
        return cls.BASE_URL

    @staticmethod
    def build_request_params(account: RuntimeAccountAdapter) -> dict[str, str]:
        return {"app-key": str(account.get_api_key() or "")}

    @staticmethod
    def build_request_body(query_item: QueryItem, *, page_size: int = 50) -> dict[str, object]:
        return {
            "pageSize": page_size,
            "appId": 730,
            "marketHashName": query_item.market_hash_name,
            "priceMax": float(query_item.max_price),
            "wearMin": float(query_item.configured_min_wear),
            "wearMax": float(query_item.configured_max_wear),
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
            query_item.require_configured_wear_range()
        except ValueError as exc:
            return self._build_failure_result(str(exc), started_at=started_at)

        request_body = self.build_request_body(query_item)

        try:
            async with active_session.post(
                url=self.build_request_url(),
                params=self.build_request_params(runtime_account),
                json=request_body,
                headers=self.build_request_headers(),
                timeout=self._build_request_timeout(),
            ) as response:
                status = response.status
                text = await response.text()
        except asyncio.TimeoutError:
            return self._build_failure_result(
                "请求超时",
                started_at=started_at,
                request_method="POST",
                request_path="/merchant/market/v2/products/search",
                request_body=request_body,
            )
        except Exception as exc:
            if aiohttp is not None and isinstance(exc, aiohttp.ClientError):
                return self._build_failure_result(
                    self._format_client_error(
                        exc,
                        proxy_url=getattr(runtime_account, "_api_proxy_url_or_none", None),
                    ),
                    started_at=started_at,
                    request_method="POST",
                    request_path="/merchant/market/v2/products/search",
                    request_body=request_body,
                )
            return self._build_failure_result(
                f"请求失败: {exc}",
                started_at=started_at,
                request_method="POST",
                request_path="/merchant/market/v2/products/search",
                request_body=request_body,
            )

        if status == 429:
            return self._build_failure_result(
                "HTTP 429 Too Many Requests",
                started_at=started_at,
                status_code=status,
                request_method="POST",
                request_path="/merchant/market/v2/products/search",
                request_body=request_body,
                response_text=text,
            )
        if status != 200:
            return self._build_failure_result(
                f"HTTP {status} 请求失败",
                started_at=started_at,
                status_code=status,
                request_method="POST",
                request_path="/merchant/market/v2/products/search",
                request_body=request_body,
                response_text=text,
            )

        success, match_count, product_list, total_price, total_wear_sum, error = self._parse_response(text)
        return QueryExecutionResult(
            success=success,
            match_count=match_count,
            product_list=product_list,
            total_price=total_price,
            total_wear_sum=total_wear_sum,
            error=error,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            status_code=None if success else status,
            request_method="POST",
            request_path="/merchant/market/v2/products/search",
            request_body=request_body,
            response_text=None if success else text,
        )

    @staticmethod
    def _build_request_timeout():
        if aiohttp is None:  # pragma: no cover - exercised only without aiohttp
            return 8
        return aiohttp.ClientTimeout(total=8)

    @staticmethod
    def _build_failure_result(
        error: str,
        *,
        started_at: float,
        status_code: int | None = None,
        request_method: str | None = None,
        request_path: str | None = None,
        request_body: dict[str, object] | None = None,
        response_text: str | None = None,
    ) -> QueryExecutionResult:
        return QueryExecutionResult(
            success=False,
            match_count=0,
            product_list=[],
            total_price=0.0,
            total_wear_sum=0.0,
            error=error,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            status_code=status_code,
            request_method=request_method,
            request_path=request_path,
            request_body=request_body,
            response_text=response_text,
        )

    @classmethod
    def _format_client_error(cls, exc: Exception, *, proxy_url: str | None) -> str:
        proxy_summary = cls._summarize_proxy_url(proxy_url)
        if not proxy_summary:
            return f"网络错误: {exc}"

        raw_error = str(exc)
        error_text = raw_error.lower()
        error_class_name = exc.__class__.__name__.lower()
        if "407" in error_text or "proxy authentication" in error_text:
            return f"代理认证失败: {proxy_summary}; 原始错误: {exc}"
        if "proxy" in error_class_name or cls._error_mentions_proxy_target(raw_error, proxy_url):
            return f"代理连接失败: {proxy_summary}; 原始错误: {exc}"
        return f"代理网络错误: {proxy_summary}; 原始错误: {exc}"

    @staticmethod
    def _summarize_proxy_url(proxy_url: str | None) -> str | None:
        normalized = str(proxy_url or "").strip()
        if not normalized:
            return None
        parsed = urlsplit(normalized)
        host = parsed.hostname or ""
        if not host:
            return None
        scheme = parsed.scheme or "http"
        auth_used = "yes" if (parsed.username or parsed.password) else "no"
        location = f"{host}:{parsed.port}" if parsed.port is not None else host
        return f"{scheme}://{location} (auth={auth_used})"

    @staticmethod
    def _error_mentions_proxy_target(error_message: str, proxy_url: str | None) -> bool:
        normalized = str(proxy_url or "").strip()
        if not normalized:
            return False
        parsed = urlsplit(normalized)
        host = parsed.hostname or ""
        if not host:
            return False
        port = parsed.port
        message = str(error_message or "")
        if host not in message:
            return False
        if port is None:
            return True
        return f"{host}:{port}" in message

    def _parse_response(
        self,
        response_text: str | dict[str, Any],
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
            processed_results = [item for item in (self._quick_process_item(raw_item) for raw_item in item_list) if item]
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
    def _quick_process_item(item: dict[str, Any]) -> tuple[dict[str, Any], float, float | None] | None:
        product_id = item.get("productId")
        price_str = item.get("price")
        if not product_id or price_str is None:
            return None

        try:
            price = round(float(price_str), 2)
        except (TypeError, ValueError):
            return None

        wear = None
        asset_info = item.get("assetInfo")
        if isinstance(asset_info, dict):
            wear_value = asset_info.get("floatWear")
            if wear_value is not None:
                try:
                    wear = float(wear_value)
                except (TypeError, ValueError):
                    wear = None

        product_info = {
            "productId": str(product_id),
            "price": price,
            "actRebateAmount": 0,
        }
        return product_info, price, wear
