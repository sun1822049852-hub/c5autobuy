from __future__ import annotations

import asyncio
import importlib
import json
import time
from collections import OrderedDict
from typing import Any

import aiohttp

from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

from .runtime_events import InventoryRefreshResult


class LegacyInventoryRefreshGateway:
    _PREVIEW_ITEM_ID = "1380979899390267393"
    _PREVIEW_PRODUCT_URL = (
        "https://www.c5game.com/csgo/1380979899390267393/"
        "P90%20%7C%20%E6%BB%A1%E6%98%8F%E4%BD%9C%E5%93%81%20(%E4%B9%85%E7%BB%8F%E6%B2%99%E5%9C%BA)"
        "/sell?sort=0"
    )

    def __init__(self, *, legacy_module: Any | None = None) -> None:
        self._legacy_module = legacy_module

    async def refresh(self, *, account) -> InventoryRefreshResult:
        runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
        access_token = runtime_account.get_x_access_token()
        device_id = runtime_account.get_x_device_id()
        if not access_token or not device_id:
            return InventoryRefreshResult.auth_invalid("Not login")

        timestamp = str(int(time.time() * 1000))
        try:
            x_sign = self._get_legacy_module().GLOBAL_XSIGN_WRAPPER.generate(
                path=self._api_path,
                method="POST",
                timestamp=timestamp,
                token=access_token,
            )
        except Exception as exc:
            return InventoryRefreshResult(status="error", inventories=[], error=f"x-sign generate failed: {exc}")

        session = await runtime_account.get_global_session()
        if session is None:
            return InventoryRefreshResult.auth_invalid("Not login")

        try:
            async with session.post(
                url=self._request_url,
                json={"itemId": self._PREVIEW_ITEM_ID},
                headers=self._build_headers(
                    runtime_account=runtime_account,
                    timestamp=timestamp,
                    x_sign=x_sign,
                ),
                timeout=aiohttp.ClientTimeout(total=8),
            ) as response:
                text = await response.text()
        except asyncio.TimeoutError:
            return InventoryRefreshResult(status="error", inventories=[], error="request timeout")
        except Exception as exc:
            return InventoryRefreshResult(status="error", inventories=[], error=f"request failed: {exc}")

        return self._parse_response(text)

    @property
    def _api_path(self) -> str:
        return f"support/trade/product/batch/v1/preview/{self._PREVIEW_ITEM_ID}"

    @property
    def _request_url(self) -> str:
        return f"https://www.c5game.com/api/v1/{self._api_path}"

    def _build_headers(self, *, runtime_account: RuntimeAccountAdapter, timestamp: str, x_sign: str) -> OrderedDict:
        headers: OrderedDict[str, str] = OrderedDict()
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        )
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = self._PREVIEW_PRODUCT_URL
        headers["Content-Type"] = "application/json"
        headers["Connection"] = "keep-alive"
        headers["Cookie"] = runtime_account.get_cookie_header_exact()
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "no-cors"
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["TE"] = "trailers"
        headers["x-app-channel"] = "WEB"
        headers["x-device-id"] = str(runtime_account.get_x_device_id() or "")
        headers["x-start-req-time"] = timestamp
        headers["x-source"] = "1"
        headers["x-sign"] = x_sign
        headers["x-access-token"] = str(runtime_account.get_x_access_token() or "")
        headers["Priority"] = "u=4"
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        return headers

    def _parse_response(self, text: str) -> InventoryRefreshResult:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return InventoryRefreshResult(status="error", inventories=[], error="invalid json response")

        if not payload.get("success", False):
            error = str(payload.get("errorMsg") or "unknown error")
            if "not login" in error.lower():
                return InventoryRefreshResult.auth_invalid(error)
            return InventoryRefreshResult(status="error", inventories=[], error=error)

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

    def _get_legacy_module(self) -> Any:
        if self._legacy_module is None:
            self._legacy_module = importlib.import_module("autobuy")
        return self._legacy_module
