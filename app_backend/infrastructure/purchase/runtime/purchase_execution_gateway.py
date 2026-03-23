from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Any

import aiohttp

from app_backend.infrastructure.c5.response_status import (
    classify_c5_response_error,
    is_auth_invalid_c5_error,
)
from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter
from xsign import XSignWrapper

from .runtime_events import PurchaseExecutionResult


class PurchaseExecutionGateway:
    ORDER_API_PATH = "support/trade/order/buy/v2/create"
    PAY_API_PATH = "pay/order/v1/pay"
    API_BASE_URL = "https://www.c5game.com/api/v1"
    ORDER_TIMEOUT_SECONDS = 10
    PAY_TIMEOUT_SECONDS = 8

    def __init__(self, *, xsign_wrapper: Any | None = None) -> None:
        self._xsign_wrapper = xsign_wrapper

    async def execute(self, *, account, batch, selected_steam_id: str) -> PurchaseExecutionResult:
        runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
        if not runtime_account.get_x_access_token() or not runtime_account.get_x_device_id():
            return PurchaseExecutionResult.auth_invalid("Not login")

        item_id = str(getattr(batch, "external_item_id", None) or "")
        product_url = str(getattr(batch, "product_url", None) or "")
        if not item_id or not product_url:
            return PurchaseExecutionResult(
                status="invalid_batch",
                purchased_count=0,
                error="Missing external_item_id or product_url",
            )

        product_list = getattr(batch, "product_list", []) or []
        if not product_list:
            return PurchaseExecutionResult(
                status="invalid_batch",
                purchased_count=0,
                error="Missing product_list",
            )

        order_success, order_id, order_error = await self.create_order(
            runtime_account=runtime_account,
            item_id=item_id,
            total_price=float(getattr(batch, "total_price", 0.0) or 0.0),
            selected_steam_id=selected_steam_id,
            product_list=product_list,
            product_url=product_url,
        )
        if not order_success:
            return self._build_error_result("order_failed", order_error)

        payment_success, success_count, payment_error = await self.process_payment(
            runtime_account=runtime_account,
            order_id=str(order_id),
            pay_amount=float(getattr(batch, "total_price", 0.0) or 0.0),
            selected_steam_id=selected_steam_id,
            product_url=product_url,
        )
        if not payment_success:
            return self._build_error_result("payment_failed", payment_error)

        purchased_count = int(success_count or 0)
        if purchased_count <= 0:
            return PurchaseExecutionResult(status="payment_success_no_items", purchased_count=0)
        return PurchaseExecutionResult.success(purchased_count=purchased_count)

    async def create_order(
        self,
        *,
        runtime_account: RuntimeAccountAdapter,
        item_id: str,
        total_price: float,
        selected_steam_id: str,
        product_list: list[dict[str, Any]],
        product_url: str,
    ) -> tuple[bool, str | None, str | None]:
        request_body = self.build_order_request_body(
            item_id=item_id,
            total_price=total_price,
            selected_steam_id=selected_steam_id,
            product_list=product_list,
        )
        current_timestamp = self._build_timestamp()
        try:
            headers = self._build_headers(
                runtime_account=runtime_account,
                api_path=self.ORDER_API_PATH,
                timestamp=current_timestamp,
                referer_url=product_url,
            )
        except RuntimeError as exc:
            return False, None, str(exc)

        if headers is None:
            return False, None, "构建请求头失败"

        session = await runtime_account.get_global_session()
        try:
            async with session.post(
                url=self._build_request_url(self.ORDER_API_PATH),
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.ORDER_TIMEOUT_SECONDS),
            ) as response:
                status = response.status
                text = await response.text()
        except asyncio.TimeoutError:
            return False, None, "订单创建请求超时"
        except Exception as exc:
            return False, None, f"订单创建请求失败: {exc}"

        http_error = classify_c5_response_error(status=status, text=text)
        if http_error is not None:
            return False, None, http_error
        return self.parse_order_response(text)

    async def process_payment(
        self,
        *,
        runtime_account: RuntimeAccountAdapter,
        order_id: str,
        pay_amount: float,
        selected_steam_id: str,
        product_url: str,
    ) -> tuple[bool, int, str | None]:
        request_body = self.build_payment_request_body(
            order_id=order_id,
            pay_amount=pay_amount,
            selected_steam_id=selected_steam_id,
        )
        current_timestamp = self._build_timestamp()
        try:
            headers = self._build_headers(
                runtime_account=runtime_account,
                api_path=self.PAY_API_PATH,
                timestamp=current_timestamp,
                referer_url=product_url,
            )
        except RuntimeError as exc:
            return False, 0, str(exc)

        if headers is None:
            return False, 0, "构建请求头失败"

        session = await runtime_account.get_global_session()
        try:
            async with session.post(
                url=self._build_request_url(self.PAY_API_PATH),
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.PAY_TIMEOUT_SECONDS),
            ) as response:
                status = response.status
                text = await response.text()
        except asyncio.TimeoutError:
            return False, 0, "请求超时"
        except Exception as exc:
            return False, 0, f"请求失败: {exc}"

        http_error = classify_c5_response_error(status=status, text=text)
        if http_error is not None:
            return False, 0, http_error
        return self.parse_payment_response(text)

    @staticmethod
    def build_order_request_body(
        *,
        item_id: str,
        total_price: float,
        selected_steam_id: str,
        product_list: list[dict[str, Any]],
    ) -> dict[str, object]:
        return {
            "type": 4,
            "productId": str(item_id),
            "price": format(float(total_price), ".2f"),
            "delivery": 0,
            "pageSource": "",
            "receiveSteamId": str(selected_steam_id),
            "productList": product_list,
            "actRebateAmount": 0,
        }

    @staticmethod
    def build_payment_request_body(
        *,
        order_id: str,
        pay_amount: float,
        selected_steam_id: str,
    ) -> dict[str, object]:
        return {
            "bizOrderId": str(order_id),
            "orderType": 4,
            "payAmount": format(float(pay_amount), ".2f"),
            "receiveSteamId": str(selected_steam_id),
        }

    @classmethod
    def parse_order_response(cls, response_text: str) -> tuple[bool, str | None, str | None]:
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError:
            return False, None, "响应不是有效的JSON格式"
        except Exception as exc:
            return False, None, f"解析响应失败: {exc}"

        if not response_data.get("success", False):
            error_msg = response_data.get("errorMsg", "未知错误")
            return False, None, f"创建订单失败: {error_msg}"

        order_id = response_data.get("data")
        if not order_id:
            return False, None, "响应中没有订单号"
        return True, str(order_id), None

    @classmethod
    def parse_payment_response(cls, response_text: str) -> tuple[bool, int, str | None]:
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError:
            return False, 0, "响应不是有效的JSON格式"
        except Exception as exc:
            return False, 0, f"解析响应失败: {exc}"

        if not response_data.get("success", False):
            error_msg = response_data.get("errorMsg", "未知错误")
            return False, 0, f"支付失败: {error_msg}"

        data = response_data.get("data") or {}
        return True, int(data.get("successCount", 0) or 0), None

    def _build_headers(
        self,
        *,
        runtime_account: RuntimeAccountAdapter,
        api_path: str,
        timestamp: str,
        referer_url: str,
    ) -> OrderedDict[str, str] | None:
        access_token = runtime_account.get_x_access_token()
        device_id = runtime_account.get_x_device_id()

        try:
            x_sign = self._get_xsign_wrapper().generate(
                path=api_path,
                method="POST",
                timestamp=timestamp,
                token=access_token,
            )
        except Exception as exc:
            raise RuntimeError(f"生成x-sign失败: {exc}") from exc

        if not all([access_token, device_id, x_sign, referer_url]):
            return None

        headers: OrderedDict[str, str] = OrderedDict()
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = referer_url
        headers["Content-Type"] = "application/json"
        headers["Connection"] = "keep-alive"
        headers["Cookie"] = runtime_account.get_cookie_header_exact()
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "no-cors"
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["TE"] = "trailers"
        headers["x-app-channel"] = "WEB"
        headers["x-device-id"] = device_id
        headers["x-start-req-time"] = timestamp
        headers["x-source"] = "1"
        headers["x-sign"] = x_sign
        headers["x-access-token"] = access_token
        headers["Priority"] = "u=4"
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        return headers

    def _get_xsign_wrapper(self) -> Any:
        return self._xsign_wrapper or get_default_xsign_wrapper()

    @classmethod
    def _build_request_url(cls, api_path: str) -> str:
        return f"{cls.API_BASE_URL}/{api_path}"

    @staticmethod
    def _build_timestamp() -> str:
        return str(int(time.time() * 1000))

    @staticmethod
    def _build_error_result(status: str, error: str | None) -> PurchaseExecutionResult:
        if PurchaseExecutionGateway._is_auth_invalid(error):
            return PurchaseExecutionResult.auth_invalid(error or "Not login")
        return PurchaseExecutionResult(status=status, purchased_count=0, error=error)

    @staticmethod
    def _is_auth_invalid(error: str | None) -> bool:
        return is_auth_invalid_c5_error(error)


@lru_cache(maxsize=1)
def get_default_xsign_wrapper() -> XSignWrapper:
    repo_root = Path(__file__).resolve().parents[4]
    return XSignWrapper(wasm_path=str(repo_root / "test.wasm"), persistent=True, timeout=10)
