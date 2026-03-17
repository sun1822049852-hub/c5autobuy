from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Any

import aiohttp

from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter
from xsign import XSignWrapper

from .runtime_events import InventoryRefreshResult


class InventoryRefreshGateway:
    PREVIEW_ITEM_ID = "1380979899390267393"
    PREVIEW_PRODUCT_URL = (
        "https://www.c5game.com/csgo/1380979899390267393/"
        "P90%20%7C%20%E6%BB%A1%E6%98%8F%E4%BD%9C%E5%93%81%20(%E4%B9%85%E7%BB%8F%E6%B2%99%E5%9C%BA)"
        "/sell?sort=0"
    )
    API_PATH = f"support/trade/product/batch/v1/preview/{PREVIEW_ITEM_ID}"
    API_BASE_URL = "https://www.c5game.com/api/v1"
    REQUEST_TIMEOUT_SECONDS = 8

    def __init__(self, *, xsign_wrapper: Any | None = None) -> None:
        self._xsign_wrapper = xsign_wrapper

    async def refresh(self, *, account) -> InventoryRefreshResult:
        runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
        access_token = runtime_account.get_x_access_token()
        device_id = runtime_account.get_x_device_id()
        if not access_token or not device_id:
            return InventoryRefreshResult.auth_invalid("Not login")

        current_timestamp = self._build_timestamp()
        try:
            x_sign = self._get_xsign_wrapper().generate(
                path=self.API_PATH,
                method="POST",
                timestamp=current_timestamp,
                token=access_token,
            )
        except Exception as exc:
            return InventoryRefreshResult(status="error", inventories=[], error=f"x-sign生成失败: {exc}")

        session = await runtime_account.get_global_session()
        if session is None:
            return InventoryRefreshResult.auth_invalid("Not login")

        headers = self._build_headers(
            runtime_account=runtime_account,
            timestamp=current_timestamp,
            x_sign=x_sign,
        )
        if headers is None:
            return InventoryRefreshResult(status="error", inventories=[], error="构建请求头失败")

        try:
            async with session.post(
                url=self._build_request_url(),
                json=self.build_request_body(),
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT_SECONDS),
            ) as response:
                return self.parse_response(await response.text())
        except asyncio.TimeoutError:
            return InventoryRefreshResult(status="error", inventories=[], error="请求超时")
        except Exception as exc:
            return InventoryRefreshResult(status="error", inventories=[], error=f"请求失败: {exc}")

    @classmethod
    def build_request_body(cls) -> dict[str, str]:
        return {"itemId": cls.PREVIEW_ITEM_ID}

    @classmethod
    def parse_response(cls, text: str) -> InventoryRefreshResult:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return InventoryRefreshResult(status="error", inventories=[], error="响应不是有效的JSON格式")

        if not payload.get("success", False):
            error_msg = str(payload.get("errorMsg") or "未知错误")
            normalized = error_msg.lower()
            if "not login" in normalized or "403" in normalized:
                return InventoryRefreshResult.auth_invalid(error_msg)
            return InventoryRefreshResult(status="error", inventories=[], error=f"请求失败: {error_msg}")

        receive_steam_list = payload.get("data", {}).get("receiveSteamList", [])
        inventories: list[dict[str, Any]] = []
        if isinstance(receive_steam_list, list):
            for item in receive_steam_list:
                inventories.append(
                    {
                        "nickname": item.get("nickname", ""),
                        "steamId": item.get("steamId", ""),
                        "avatar": item.get("avatar", ""),
                        "inventory_num": item.get("inventoryNum", 0),
                        "inventory_max": item.get("inventoryMaxNum", 1000),
                        "status": item.get("status", 0),
                        "type": item.get("type", 1),
                    }
                )
        return InventoryRefreshResult.success(inventories=inventories)

    def _build_headers(
        self,
        *,
        runtime_account: RuntimeAccountAdapter,
        timestamp: str,
        x_sign: str,
    ) -> OrderedDict[str, str] | None:
        access_token = runtime_account.get_x_access_token()
        device_id = runtime_account.get_x_device_id()
        if not all([access_token, device_id, x_sign]):
            return None

        headers: OrderedDict[str, str] = OrderedDict()
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = self.PREVIEW_PRODUCT_URL
        headers["Content-Type"] = "application/json"
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

    @classmethod
    def _build_request_url(cls) -> str:
        return f"{cls.API_BASE_URL}/{cls.API_PATH}"

    def _get_xsign_wrapper(self) -> Any:
        return self._xsign_wrapper or get_default_xsign_wrapper()

    @staticmethod
    def _build_timestamp() -> str:
        return str(int(time.time() * 1000))


@lru_cache(maxsize=1)
def get_default_xsign_wrapper() -> XSignWrapper:
    repo_root = Path(__file__).resolve().parents[4]
    return XSignWrapper(wasm_path=str(repo_root / "test.wasm"), persistent=True, timeout=10)
