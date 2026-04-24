from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Any

import aiohttp

from app_backend.infrastructure.query.product_url_utils import normalize_c5_product_url
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

    async def execute(
        self,
        *,
        account,
        batch,
        selected_steam_id: str,
        on_execute_started=None,
    ) -> PurchaseExecutionResult:
        if callable(on_execute_started):
            on_execute_started()
        runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
        item_id = str(getattr(batch, "external_item_id", None) or "")
        product_url = str(getattr(batch, "product_url", None) or "")
        product_list = list(getattr(batch, "product_list", []) or [])
        submitted_count = len(product_list)
        if not runtime_account.get_x_access_token() or not runtime_account.get_x_device_id():
            return PurchaseExecutionResult.auth_invalid(
                "Not login",
                submitted_count=submitted_count,
                request_method="POST",
                request_path=f"/{self.ORDER_API_PATH}",
            )

        if not item_id or not product_url:
            return PurchaseExecutionResult(
                status="invalid_batch",
                purchased_count=0,
                submitted_count=submitted_count,
                error="Missing external_item_id or product_url",
                request_method="POST",
                request_path=f"/{self.ORDER_API_PATH}",
            )

        if not product_list:
            return PurchaseExecutionResult(
                status="invalid_batch",
                purchased_count=0,
                submitted_count=0,
                error="Missing product_list",
                request_method="POST",
                request_path=f"/{self.ORDER_API_PATH}",
            )

        create_started_at = time.perf_counter()
        order_success, order_id, order_error, order_debug_details = await self.create_order(
            runtime_account=runtime_account,
            item_id=item_id,
            total_price=float(getattr(batch, "total_price", 0.0) or 0.0),
            selected_steam_id=selected_steam_id,
            product_list=product_list,
            product_url=product_url,
        )
        create_order_latency_ms = self._elapsed_ms(create_started_at)
        if not order_success:
            return self._build_error_result(
                "order_failed",
                order_error,
                submitted_count=submitted_count,
                create_order_latency_ms=create_order_latency_ms,
                debug_details=order_debug_details,
            )

        submit_started_at = time.perf_counter()
        payment_success, success_count, payment_error, payment_debug_details = await self.process_payment(
            runtime_account=runtime_account,
            order_id=str(order_id),
            pay_amount=float(getattr(batch, "total_price", 0.0) or 0.0),
            selected_steam_id=selected_steam_id,
            product_url=product_url,
        )
        submit_order_latency_ms = self._elapsed_ms(submit_started_at)
        if not payment_success:
            return self._build_error_result(
                "payment_failed",
                payment_error,
                submitted_count=submitted_count,
                create_order_latency_ms=create_order_latency_ms,
                submit_order_latency_ms=submit_order_latency_ms,
                debug_details=payment_debug_details,
            )

        purchased_count = int(success_count or 0)
        if purchased_count <= 0:
            return PurchaseExecutionResult(
                status="payment_success_no_items",
                purchased_count=0,
                submitted_count=submitted_count,
                error=None,
                create_order_latency_ms=create_order_latency_ms,
                submit_order_latency_ms=submit_order_latency_ms,
                status_code=payment_debug_details.get("status_code"),
                request_method=payment_debug_details.get("request_method"),
                request_path=payment_debug_details.get("request_path"),
                request_body=payment_debug_details.get("request_body"),
                response_text=payment_debug_details.get("response_text"),
            )
        return PurchaseExecutionResult.success(
            purchased_count=purchased_count,
            submitted_count=submitted_count,
            create_order_latency_ms=create_order_latency_ms,
            submit_order_latency_ms=submit_order_latency_ms,
        )

    async def create_order(
        self,
        *,
        runtime_account: RuntimeAccountAdapter,
        item_id: str,
        total_price: float,
        selected_steam_id: str,
        product_list: list[dict[str, Any]],
        product_url: str,
    ) -> tuple[bool, str | None, str | None, dict[str, object]]:
        request_body = self.build_order_request_body(
            item_id=item_id,
            total_price=total_price,
            selected_steam_id=selected_steam_id,
            product_list=product_list,
        )
        current_timestamp = self._build_timestamp()
        try:
            headers = await self._build_headers(
                runtime_account=runtime_account,
                api_path=self.ORDER_API_PATH,
                timestamp=current_timestamp,
                referer_url=product_url,
            )
        except RuntimeError as exc:
            return False, None, str(exc), {
                "request_method": "POST",
                "request_path": f"/{self.ORDER_API_PATH}",
                "request_body": request_body,
            }

        if headers is None:
            return False, None, "构建请求头失败", {
                "request_method": "POST",
                "request_path": f"/{self.ORDER_API_PATH}",
                "request_body": request_body,
            }

        session = await runtime_account.get_global_session()
        try:
            async with session.post(
                url=self._build_request_url(self.ORDER_API_PATH),
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.ORDER_TIMEOUT_SECONDS),
            ) as response:
                text = await response.text()
                success, order_id, error, details = self.parse_order_response(text, status_code=response.status)
                return success, order_id, error, self._merge_debug_details(
                    details,
                    request_method="POST",
                    request_path=f"/{self.ORDER_API_PATH}",
                    request_body=request_body,
                    status_code=response.status,
                    response_text=text,
                )
        except asyncio.TimeoutError:
            return False, None, "订单创建请求超时", {
                "request_method": "POST",
                "request_path": f"/{self.ORDER_API_PATH}",
                "request_body": request_body,
            }
        except Exception as exc:
            return False, None, f"订单创建请求失败: {exc}", {
                "request_method": "POST",
                "request_path": f"/{self.ORDER_API_PATH}",
                "request_body": request_body,
            }

    async def process_payment(
        self,
        *,
        runtime_account: RuntimeAccountAdapter,
        order_id: str,
        pay_amount: float,
        selected_steam_id: str,
        product_url: str,
    ) -> tuple[bool, int, str | None, dict[str, object]]:
        request_body = self.build_payment_request_body(
            order_id=order_id,
            pay_amount=pay_amount,
            selected_steam_id=selected_steam_id,
        )
        current_timestamp = self._build_timestamp()
        try:
            headers = await self._build_headers(
                runtime_account=runtime_account,
                api_path=self.PAY_API_PATH,
                timestamp=current_timestamp,
                referer_url=product_url,
            )
        except RuntimeError as exc:
            return False, 0, str(exc), {
                "request_method": "POST",
                "request_path": f"/{self.PAY_API_PATH}",
                "request_body": request_body,
            }

        if headers is None:
            return False, 0, "构建请求头失败", {
                "request_method": "POST",
                "request_path": f"/{self.PAY_API_PATH}",
                "request_body": request_body,
            }

        session = await runtime_account.get_global_session()
        try:
            async with session.post(
                url=self._build_request_url(self.PAY_API_PATH),
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.PAY_TIMEOUT_SECONDS),
            ) as response:
                text = await response.text()
                success, success_count, error, details = self.parse_payment_response(text, status_code=response.status)
                return success, success_count, error, self._merge_debug_details(
                    details,
                    request_method="POST",
                    request_path=f"/{self.PAY_API_PATH}",
                    request_body=request_body,
                    status_code=response.status,
                    response_text=text,
                )
        except asyncio.TimeoutError:
            return False, 0, "请求超时", {
                "request_method": "POST",
                "request_path": f"/{self.PAY_API_PATH}",
                "request_body": request_body,
            }
        except Exception as exc:
            return False, 0, f"请求失败: {exc}", {
                "request_method": "POST",
                "request_path": f"/{self.PAY_API_PATH}",
                "request_body": request_body,
            }

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
            "productList": list(product_list),
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
    def parse_order_response(
        cls,
        response_text: str,
        *,
        status_code: int | None = None,
    ) -> tuple[bool, str | None, str | None, dict[str, object]]:
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError:
            return False, None, "响应不是有效的JSON格式", {
                "status_code": status_code,
                "request_method": "POST",
                "request_path": f"/{cls.ORDER_API_PATH}",
                "response_text": response_text,
            }
        except Exception as exc:
            return False, None, f"解析响应失败: {exc}", {
                "status_code": status_code,
                "request_method": "POST",
                "request_path": f"/{cls.ORDER_API_PATH}",
                "response_text": response_text,
            }

        if not response_data.get("success", False):
            error_msg = cls._extract_error_message(response_data)
            return False, None, f"创建订单失败: {error_msg}", {
                "status_code": status_code,
                "request_method": "POST",
                "request_path": f"/{cls.ORDER_API_PATH}",
                "response_text": response_text,
            }

        order_id = response_data.get("data")
        if not order_id:
            return False, None, "响应中没有订单号", {
                "status_code": status_code,
                "request_method": "POST",
                "request_path": f"/{cls.ORDER_API_PATH}",
                "response_text": response_text,
            }
        return True, str(order_id), None, {}

    @classmethod
    def parse_payment_response(
        cls,
        response_text: str,
        *,
        status_code: int | None = None,
    ) -> tuple[bool, int, str | None, dict[str, object]]:
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError:
            return False, 0, "响应不是有效的JSON格式", {
                "status_code": status_code,
                "request_method": "POST",
                "request_path": f"/{cls.PAY_API_PATH}",
                "response_text": response_text,
            }
        except Exception as exc:
            return False, 0, f"解析响应失败: {exc}", {
                "status_code": status_code,
                "request_method": "POST",
                "request_path": f"/{cls.PAY_API_PATH}",
                "response_text": response_text,
            }

        if not response_data.get("success", False):
            error_msg = cls._extract_error_message(response_data)
            return False, 0, f"支付失败: {error_msg}", {
                "status_code": status_code,
                "request_method": "POST",
                "request_path": f"/{cls.PAY_API_PATH}",
                "response_text": response_text,
            }

        data = response_data.get("data") or {}
        return True, int(data.get("successCount", 0) or 0), None, {}

    async def _build_headers(
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
            xsign_wrapper = self._get_xsign_wrapper()
            x_sign = await asyncio.to_thread(
                xsign_wrapper.generate,
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
        headers["Referer"] = normalize_c5_product_url(referer_url)
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

    @classmethod
    def _build_error_result(
        cls,
        status: str,
        error: str | None,
        *,
        submitted_count: int,
        create_order_latency_ms: float | None = None,
        submit_order_latency_ms: float | None = None,
        debug_details: dict[str, object] | None = None,
    ) -> PurchaseExecutionResult:
        details = debug_details or {}
        if cls._is_auth_invalid(error):
            return PurchaseExecutionResult.auth_invalid(
                error or "Not login",
                submitted_count=submitted_count,
                create_order_latency_ms=create_order_latency_ms,
                submit_order_latency_ms=submit_order_latency_ms,
                status_code=details.get("status_code"),
                request_method=details.get("request_method"),
                request_path=details.get("request_path"),
                request_body=details.get("request_body"),
                response_text=details.get("response_text"),
            )
        normalized_status = cls._classify_error_status(
            status=status,
            error=error,
            response_text=details.get("response_text"),
        )
        return PurchaseExecutionResult(
            status=normalized_status,
            purchased_count=0,
            submitted_count=submitted_count,
            error=error,
            create_order_latency_ms=create_order_latency_ms,
            submit_order_latency_ms=submit_order_latency_ms,
            status_code=details.get("status_code"),
            request_method=details.get("request_method"),
            request_path=details.get("request_path"),
            request_body=details.get("request_body"),
            response_text=details.get("response_text"),
        )

    @staticmethod
    def _is_auth_invalid(error: str | None) -> bool:
        normalized = str(error or "").lower()
        return "not login" in normalized or "403" in normalized

    @staticmethod
    def _extract_error_message(response_data: dict[str, object]) -> str:
        for key in ("errorMsg", "error_msg", "message", "msg", "error"):
            value = response_data.get(key)
            text = str(value or "").strip()
            if text:
                return text
        return "未知错误"

    @classmethod
    def _classify_error_status(
        cls,
        *,
        status: str,
        error: str | None,
        response_text: object,
    ) -> str:
        if cls._is_item_unavailable_error(error=error, response_text=response_text):
            return "payment_success_no_items"
        return str(status or "")

    @staticmethod
    def _is_item_unavailable_error(*, error: str | None, response_text: object) -> bool:
        haystacks = [
            str(error or "").lower(),
            str(response_text or "").lower(),
        ]
        markers = (
            "订单数据发生变化",
            "请刷新页面重试",
            "sold out",
            "already sold",
            "item unavailable",
            "已被买走",
            "已售罄",
        )
        return any(marker in haystack for haystack in haystacks for marker in markers if haystack)

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((time.perf_counter() - float(started_at)) * 1000, 3)

    @staticmethod
    def _merge_debug_details(
        details: dict[str, object] | None,
        *,
        request_method: str,
        request_path: str,
        request_body: dict[str, object] | None = None,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> dict[str, object]:
        merged = dict(details or {})
        merged.setdefault("request_method", request_method)
        merged.setdefault("request_path", request_path)
        if request_body is not None:
            merged.setdefault("request_body", request_body)
        if status_code is not None:
            merged.setdefault("status_code", status_code)
        if response_text is not None:
            merged.setdefault("response_text", response_text)
        return merged


@lru_cache(maxsize=1)
def get_default_xsign_wrapper() -> XSignWrapper:
    repo_root = Path(__file__).resolve().parents[4]
    return XSignWrapper(wasm_path=str(repo_root / "test.wasm"), persistent=True, timeout=10)
