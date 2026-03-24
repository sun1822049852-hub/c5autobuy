from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Any

from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter
from xsign import XSignWrapper

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional dependency in unit tests
    aiohttp = None

from app_backend.infrastructure.c5.response_status import classify_c5_response_error


@lru_cache(maxsize=1)
def get_default_xsign_wrapper() -> XSignWrapper:
    repo_root = Path(__file__).resolve().parents[4]
    return XSignWrapper(wasm_path=str(repo_root / "test.wasm"), persistent=True, timeout=10)


class ProductDetailFetcher:
    API_BASE_URL = "https://www.c5game.com/api/v1"
    REQUEST_TIMEOUT_SECONDS = 8

    def __init__(
        self,
        *,
        selector,
        xsign_wrapper: Any | None = None,
        runtime_account_factory=None,
    ) -> None:
        self._selector = selector
        self._xsign_wrapper = xsign_wrapper
        self._runtime_account_factory = runtime_account_factory or RuntimeAccountAdapter

    async def fetch(self, *, external_item_id: str, product_url: str) -> dict[str, object]:
        last_error = "商品信息补全失败"
        for account in self._selector.build_attempt_order():
            runtime_account = self._build_runtime_account(account)
            try:
                preview_payload = await self._fetch_preview_payload(
                    runtime_account=runtime_account,
                    external_item_id=external_item_id,
                    product_url=product_url,
                )
                market_payload = await self._fetch_market_payload(
                    runtime_account=runtime_account,
                    external_item_id=external_item_id,
                    product_url=product_url,
                )
                return self._merge_payloads(
                    external_item_id=external_item_id,
                    product_url=product_url,
                    preview_payload=preview_payload,
                    market_payload=market_payload,
                )
            except ValueError as exc:
                last_error = str(exc)
                continue
        raise ValueError(last_error)

    def _build_runtime_account(self, account: object):
        if isinstance(account, RuntimeAccountAdapter):
            return account
        return self._runtime_account_factory(account)

    async def _fetch_preview_payload(
        self,
        *,
        runtime_account,
        external_item_id: str,
        product_url: str,
    ) -> dict[str, Any]:
        api_path = f"support/trade/product/batch/v1/preview/{external_item_id}"
        headers = self._build_post_headers(
            runtime_account=runtime_account,
            product_url=product_url,
            api_path=api_path,
        )
        session = await runtime_account.get_global_session()
        if session is None:
            raise ValueError("无法创建浏览器会话")

        try:
            async with session.post(
                url=f"{self.API_BASE_URL}/{api_path}",
                json={"itemId": str(external_item_id)},
                headers=headers,
                timeout=self._build_request_timeout(),
            ) as response:
                status = response.status
                text = await response.text()
        except asyncio.TimeoutError:
            raise ValueError("请求超时") from None
        except Exception as exc:
            raise ValueError(f"请求失败: {exc}") from exc

        return self._parse_success_payload(status=status, text=text)

    async def _fetch_market_payload(
        self,
        *,
        runtime_account,
        external_item_id: str,
        product_url: str,
    ) -> dict[str, Any]:
        api_path = f"search/v2/sell/{external_item_id}/list"
        headers = self._build_get_headers(
            runtime_account=runtime_account,
            product_url=product_url,
            api_path=api_path,
        )
        session = await runtime_account.get_global_session()
        if session is None:
            raise ValueError("无法创建浏览器会话")

        try:
            async with session.get(
                url=f"{self.API_BASE_URL}/{api_path}",
                params={"itemId": str(external_item_id), "page": 1, "limit": 10},
                headers=headers,
                timeout=self._build_request_timeout(),
            ) as response:
                status = response.status
                text = await response.text()
        except asyncio.TimeoutError:
            raise ValueError("请求超时") from None
        except Exception as exc:
            raise ValueError(f"请求失败: {exc}") from exc

        return self._parse_success_payload(status=status, text=text)

    def _build_post_headers(
        self,
        *,
        runtime_account,
        product_url: str,
        api_path: str,
    ) -> OrderedDict[str, str]:
        access_token = runtime_account.get_x_access_token()
        device_id = runtime_account.get_x_device_id()
        timestamp = self._build_timestamp()
        if not all([access_token, device_id, product_url]):
            raise ValueError("构建请求头失败")

        x_sign = self._generate_x_sign(
            api_path=api_path,
            method="POST",
            access_token=str(access_token),
            timestamp=timestamp,
        )

        headers = self._build_common_headers(
            runtime_account=runtime_account,
            product_url=product_url,
            timestamp=timestamp,
            x_sign=x_sign,
        )
        headers["Content-Type"] = "application/json"
        return headers

    def _build_get_headers(
        self,
        *,
        runtime_account,
        product_url: str,
        api_path: str,
    ) -> OrderedDict[str, str]:
        access_token = runtime_account.get_x_access_token()
        device_id = runtime_account.get_x_device_id()
        timestamp = self._build_timestamp()
        if not all([access_token, device_id, product_url]):
            raise ValueError("构建请求头失败")

        x_sign = self._generate_x_sign(
            api_path=api_path,
            method="GET",
            access_token=str(access_token),
            timestamp=timestamp,
        )

        return self._build_common_headers(
            runtime_account=runtime_account,
            product_url=product_url,
            timestamp=timestamp,
            x_sign=x_sign,
        )

    def _build_common_headers(
        self,
        *,
        runtime_account,
        product_url: str,
        timestamp: str,
        x_sign: str,
    ) -> OrderedDict[str, str]:
        access_token = runtime_account.get_x_access_token()
        device_id = runtime_account.get_x_device_id()

        headers: OrderedDict[str, str] = OrderedDict()
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = runtime_account.get_user_agent()
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = product_url
        headers["Connection"] = "keep-alive"
        headers["Cookie"] = runtime_account.get_cookie_header_exact()
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

    def _generate_x_sign(
        self,
        *,
        api_path: str,
        method: str,
        access_token: str,
        timestamp: str,
    ) -> str:
        try:
            return self._get_xsign_wrapper().generate(
                path=api_path,
                method=method,
                timestamp=timestamp,
                token=access_token,
            )
        except Exception as exc:
            raise ValueError(f"x-sign生成失败: {exc}") from exc

    @staticmethod
    def _parse_success_payload(*, status: int, text: str) -> dict[str, Any]:
        http_error = classify_c5_response_error(status=status, text=text)
        if http_error is not None:
            raise ValueError(http_error)

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            raise ValueError("响应不是有效的JSON格式") from None

        if not payload.get("success", False):
            raise ValueError(f"请求失败: {payload.get('errorMsg') or '未知错误'}")
        return payload.get("data", {})

    @staticmethod
    def _merge_payloads(
        *,
        external_item_id: str,
        product_url: str,
        preview_payload: dict[str, Any],
        market_payload: dict[str, Any],
    ) -> dict[str, object]:
        wear_range = preview_payload.get("wearRange") or []
        min_wear = None
        max_wear = None
        if isinstance(wear_range, list) and wear_range:
            min_wear = wear_range[0].get("start")
            max_wear = wear_range[-1].get("end")

        market_hash_name = None
        item_list = market_payload.get("list") or []
        if isinstance(item_list, list) and item_list:
            market_hash_name = item_list[0].get("marketHashName")

        return {
            "external_item_id": str(preview_payload.get("itemId") or external_item_id),
            "product_url": product_url,
            "item_name": preview_payload.get("itemName"),
            "market_hash_name": market_hash_name,
            "min_wear": min_wear,
            "max_wear": max_wear,
            "last_market_price": preview_payload.get("minPrice"),
        }

    @staticmethod
    def _build_timestamp() -> str:
        return str(int(time.time() * 1000))

    @staticmethod
    def _build_request_timeout():
        if aiohttp is None:  # pragma: no cover - exercised only without aiohttp
            return 8
        return aiohttp.ClientTimeout(total=8)

    def _get_xsign_wrapper(self) -> Any:
        return self._xsign_wrapper or get_default_xsign_wrapper()
