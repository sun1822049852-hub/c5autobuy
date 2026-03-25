from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Any

from app_backend.domain.models.query_config import QueryItem
from xsign import XSignWrapper

from .runtime_account_adapter import RuntimeAccountAdapter
from .runtime_events import QueryExecutionResult

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional dependency in unit tests
    aiohttp = None


@lru_cache(maxsize=1)
def _get_default_xsign_wrapper() -> XSignWrapper:
    repo_root = Path(__file__).resolve().parents[4]
    wasm_path = repo_root / "test.wasm"
    return XSignWrapper(wasm_path=str(wasm_path), persistent=True, timeout=10)


class TokenQueryExecutor:
    API_PATH = "support/trade/product/batch/v1/sell/query"

    def __init__(self, *, xsign_wrapper: Any | None = None) -> None:
        self._xsign_wrapper = xsign_wrapper

    @classmethod
    def build_request_url(cls) -> str:
        return f"https://www.c5game.com/api/v1/{cls.API_PATH}"

    @staticmethod
    def build_request_body(query_item: QueryItem) -> dict[str, object]:
        return {
            "itemId": str(query_item.external_item_id),
            "maxPrice": str(query_item.max_price),
            "delivery": 0,
            "minWear": float(query_item.configured_min_wear),
            "maxWear": float(query_item.configured_max_wear),
            "limit": "200",
            "giftBuy": "",
        }

    def build_request_headers(
        self,
        *,
        account: RuntimeAccountAdapter,
        query_item: QueryItem,
        timestamp: str,
        x_sign: str,
    ) -> OrderedDict[str, str] | None:
        access_token = account.get_x_access_token()
        device_id = account.get_x_device_id()
        if not all([access_token, device_id, x_sign, query_item.product_url]):
            return None

        headers: OrderedDict[str, str] = OrderedDict()
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = query_item.product_url
        headers["Cookie"] = account.get_cookie_header_exact()
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "no-cors"
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["TE"] = "trailers"
        headers["x-app-channel"] = "WEB"
        headers["x-device-id"] = str(device_id)
        headers["x-start-req-time"] = timestamp
        headers["x-source"] = "1"
        headers["x-sign"] = x_sign
        headers["x-access-token"] = str(access_token)
        headers["Priority"] = "u=4"
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        return headers

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
            active_session = await runtime_account.get_global_session()
            if active_session is None:
                active_session = await runtime_account.get_global_session(force_new=True)
                if active_session is None:
                    return self._build_failure_result("无法创建浏览器会话", started_at=started_at)

        if getattr(active_session, "closed", False):
            active_session = await runtime_account.get_global_session(force_new=True)
            if active_session is None:
                return self._build_failure_result("无法创建浏览器会话", started_at=started_at)

        access_token = runtime_account.get_x_access_token()
        timestamp = str(int(time.time() * 1000))
        try:
            x_sign = self._get_xsign_wrapper().generate(
                path=self.API_PATH,
                method="POST",
                timestamp=timestamp,
                token=access_token,
            )
        except Exception as exc:
            return self._build_failure_result(f"x-sign生成失败: {exc}", started_at=started_at)

        headers = self.build_request_headers(
            account=runtime_account,
            query_item=query_item,
            timestamp=timestamp,
            x_sign=x_sign,
        )
        if headers is None:
            return self._build_failure_result("构建请求头失败", started_at=started_at)

        try:
            query_item.require_configured_wear_range()
        except ValueError as exc:
            return self._build_failure_result(str(exc), started_at=started_at)

        try:
            async with active_session.post(
                url=self.build_request_url(),
                json=self.build_request_body(query_item),
                headers=headers,
                timeout=self._build_request_timeout(),
            ) as response:
                status = response.status
                text = await response.text()
        except asyncio.TimeoutError:
            return self._build_failure_result(
                "请求超时",
                started_at=started_at,
                request_method="POST",
                request_path=f"/{self.API_PATH}",
            )
        except Exception as exc:
            return self._build_failure_result(
                f"请求错误: {exc}",
                started_at=started_at,
                request_method="POST",
                request_path=f"/{self.API_PATH}",
            )

        if status == 403:
            return self._build_failure_result(
                "HTTP 403 Forbidden",
                started_at=started_at,
                status_code=status,
                request_method="POST",
                request_path=f"/{self.API_PATH}",
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
            request_path=f"/{self.API_PATH}",
            response_text=None if success else text,
        )

    @staticmethod
    def _build_request_timeout():
        if aiohttp is None:  # pragma: no cover - exercised only without aiohttp
            return 8
        return aiohttp.ClientTimeout(total=8)

    def _get_xsign_wrapper(self) -> Any:
        return self._xsign_wrapper or _get_default_xsign_wrapper()

    @staticmethod
    def _build_failure_result(
        error: str,
        *,
        started_at: float,
        status_code: int | None = None,
        request_method: str | None = None,
        request_path: str | None = None,
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
            response_text=response_text,
        )

    def _parse_response(
        self,
        response_data: str | dict[str, Any],
    ) -> tuple[bool, int, list[dict[str, Any]], float, float, str | None]:
        if isinstance(response_data, str) and "Not login" in response_data:
            return False, 0, [], 0.0, 0.0, "Not login"

        try:
            data = json.loads(response_data) if isinstance(response_data, str) else response_data
            if not data.get("success", False):
                error_msg = str(data.get("errorMsg") or "未知错误")
                if error_msg.strip() == "Not login":
                    return False, 0, [], 0.0, 0.0, "Not login"
                return False, 0, [], 0.0, 0.0, f"请求失败: {error_msg}"

            match_count = int(data.get("data", {}).get("matchCount", 0) or 0)
            sell_list = data.get("data", {}).get("sellList", [])
            product_list: list[dict[str, Any]] = []
            total_price_sum = 0.0
            total_wear_sum = 0.0

            for item in sell_list:
                item_id = item.get("id")
                price = item.get("price")
                wear = None
                asset_info = item.get("assetInfo", {})
                if isinstance(asset_info, dict):
                    wear_str = asset_info.get("wear")
                    if wear_str:
                        try:
                            wear = float(wear_str)
                            total_wear_sum += wear
                        except (TypeError, ValueError):
                            wear = None

                if item_id and price is not None:
                    try:
                        formatted_price = round(float(price), 2)
                    except (TypeError, ValueError):
                        continue
                    product_list.append(
                        {
                            "productId": str(item_id),
                            "price": formatted_price,
                            "actRebateAmount": 0,
                        }
                    )
                    total_price_sum += formatted_price

            return True, match_count, product_list, total_price_sum, total_wear_sum, None
        except json.JSONDecodeError:
            return False, 0, [], 0.0, 0.0, "响应不是有效的JSON格式"
        except Exception as exc:
            return False, 0, [], 0.0, 0.0, f"解析响应失败: {exc}"
