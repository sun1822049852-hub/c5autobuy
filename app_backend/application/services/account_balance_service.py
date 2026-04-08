from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
import json
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from random import randint
from typing import Any, Awaitable, Callable
from urllib.parse import quote

from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter
from xsign import XSignWrapper

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional in some unit tests
    aiohttp = None


OpenApiFetcher = Callable[[object], Awaitable[float]]
BalanceFetcher = Callable[[object], Awaitable[float]]
InFlightRefresh = asyncio.Task[dict[str, object]] | Future[dict[str, object]]


class AccountBalanceService:
    OPENAPI_URL = "https://openapi.c5game.com/merchant/account/v2/balance"
    BROWSER_BALANCE_URL = "https://www.c5game.com/api/v1/account/v1/my/account"
    BROWSER_BALANCE_PATH = "account/v1/my/account"

    def __init__(
        self,
        *,
        account_repository,
        account_update_hub=None,
        openapi_fetcher: Callable[[object], Awaitable[float]] | None = None,
        browser_balance_fetcher: Callable[[object], Awaitable[float]] | None = None,
        now_provider: Callable[[], datetime] | None = None,
        random_seconds_provider: Callable[[], int] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        api_key_wait_seconds: float = 10.0,
        api_key_poll_interval_seconds: float = 0.5,
        xsign_wrapper: Any | None = None,
        background_executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._account_repository = account_repository
        self._account_update_hub = account_update_hub
        self._now_provider = now_provider or datetime.now
        self._random_seconds_provider = random_seconds_provider or (lambda: randint(8 * 60, 10 * 60))
        self._sleep = sleep
        self._api_key_wait_seconds = float(api_key_wait_seconds)
        self._api_key_poll_interval_seconds = float(api_key_poll_interval_seconds)
        self._xsign_wrapper = xsign_wrapper
        self._openapi_fetcher = openapi_fetcher or self._fetch_openapi_balance
        self._browser_balance_fetcher = browser_balance_fetcher or self._fetch_browser_balance
        self._background_executor = background_executor or ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="account-balance-refresh",
        )
        self._inflight: dict[str, InFlightRefresh] = {}

    async def refresh_after_login(
        self,
        account_id: str,
        *,
        wait_for_api_key: bool = True,
    ) -> dict[str, object]:
        return await self.refresh_account(
            account_id,
            force=True,
            wait_for_api_key=wait_for_api_key,
        )

    def maybe_schedule_refresh(self, account_id: str) -> bool:
        account = self._account_repository.get_account(account_id)
        if account is None or not self._should_refresh(account):
            return False
        task = self._inflight.get(account_id)
        if task is not None and not task.done():
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            task = self._background_executor.submit(
                asyncio.run,
                self._run_refresh(account_id, force=False, wait_for_api_key=False),
            )
        else:
            task = loop.create_task(self._run_refresh(account_id, force=False, wait_for_api_key=False))
        self._inflight[account_id] = task
        task.add_done_callback(lambda _: self._inflight.pop(account_id, None))
        return True

    async def refresh_account(
        self,
        account_id: str,
        *,
        force: bool = False,
        wait_for_api_key: bool = False,
    ) -> dict[str, object]:
        task = self._inflight.get(account_id)
        if task is not None and not task.done():
            return await self._await_inflight(task)
        task = asyncio.create_task(self._run_refresh(account_id, force=force, wait_for_api_key=wait_for_api_key))
        self._inflight[account_id] = task
        task.add_done_callback(lambda _: self._inflight.pop(account_id, None))
        return await task

    @staticmethod
    async def _await_inflight(task: InFlightRefresh) -> dict[str, object]:
        if isinstance(task, asyncio.Task):
            return await task
        return await asyncio.wrap_future(task)

    async def _run_refresh(
        self,
        account_id: str,
        *,
        force: bool,
        wait_for_api_key: bool,
    ) -> dict[str, object]:
        account = self._account_repository.get_account(account_id)
        if account is None:
            return {"updated": False, "reason": "missing_account"}
        if not force and not self._should_refresh(account):
            return {"updated": False, "reason": "not_due"}

        if wait_for_api_key:
            account = await self._wait_for_api_key(account_id, initial_account=account)
            if account is None:
                return {"updated": False, "reason": "missing_account"}

        now = self._now_provider()
        next_refresh_after = (now + timedelta(seconds=int(self._random_seconds_provider()))).isoformat(timespec="seconds")
        amount: float | None = None
        source: str | None = None
        error_message: str | None = None

        try:
            if str(getattr(account, "api_key", "") or "").strip():
                amount = float(await self._openapi_fetcher(account, proxy_url=self._resolve_api_proxy_url(account)))
                source = "openapi"
            elif self._has_browser_session(account):
                amount = float(
                    await self._browser_balance_fetcher(account, proxy_url=self._resolve_browser_proxy_url(account))
                )
                source = "browser_session"
            else:
                error_message = "missing_api_key_and_session"
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)

        changes: dict[str, object] = {
            "balance_refresh_after_at": next_refresh_after,
            "balance_last_error": error_message,
            "updated_at": now.isoformat(timespec="seconds"),
        }
        if amount is not None and source is not None:
            changes.update(
                {
                    "balance_amount": amount,
                    "balance_source": source,
                    "balance_updated_at": now.isoformat(timespec="seconds"),
                    "balance_last_error": None,
                }
            )

        self._account_repository.update_account(account_id, **changes)
        self._publish_update(account_id, changes)
        return {"updated": True, "source": source, "error": error_message}

    async def _wait_for_api_key(self, account_id: str, *, initial_account=None):
        account = initial_account or self._account_repository.get_account(account_id)
        if account is None:
            return None
        if str(getattr(account, "api_key", "") or "").strip():
            return account

        deadline = time.monotonic() + self._api_key_wait_seconds
        while time.monotonic() < deadline:
            await self._sleep(self._api_key_poll_interval_seconds)
            account = self._account_repository.get_account(account_id)
            if account is None:
                return None
            if str(getattr(account, "api_key", "") or "").strip():
                return account
        return account

    def _should_refresh(self, account) -> bool:
        if not str(getattr(account, "api_key", "") or "").strip() and not self._has_browser_session(account):
            return False
        refresh_after = str(getattr(account, "balance_refresh_after_at", "") or "").strip()
        if not refresh_after:
            return True
        try:
            return datetime.fromisoformat(refresh_after) <= self._now_provider()
        except ValueError:
            return True

    @staticmethod
    def _has_browser_session(account) -> bool:
        adapter = RuntimeAccountAdapter(account)
        return bool(adapter.get_x_access_token() and adapter.get_x_device_id())

    @staticmethod
    def _resolve_api_proxy_url(account) -> str | None:
        if str(getattr(account, "api_proxy_mode", "") or "direct") == "direct":
            return None
        return str(getattr(account, "api_proxy_url", "") or "").strip() or None

    @staticmethod
    def _resolve_browser_proxy_url(account) -> str | None:
        if str(getattr(account, "browser_proxy_mode", "") or "direct") == "direct":
            return None
        return str(getattr(account, "browser_proxy_url", "") or "").strip() or None

    def _publish_update(self, account_id: str, payload: dict[str, object]) -> None:
        hub = self._account_update_hub
        publish = getattr(hub, "publish", None)
        if callable(publish):
            publish(account_id=account_id, event="write_balance", payload=payload)

    async def _fetch_openapi_balance(self, account, *, proxy_url: str | None) -> float:
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for account balance fetch")
        api_key = str(getattr(account, "api_key", "") or "").strip()
        if not api_key:
            raise RuntimeError("missing api_key")
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout, cookie_jar=None) as session:
            async with session.get(
                f"{self.OPENAPI_URL}?app-key={quote(api_key, safe='')}",
                proxy=proxy_url,
                headers={"Accept": "application/json"},
            ) as response:
                text = await response.text()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("invalid openapi balance payload") from exc
        if not payload.get("success", False):
            raise RuntimeError(str(payload.get("errorMsg") or "openapi balance failed"))
        data = payload.get("data") or {}
        amount = data.get("moneyAmount")
        if amount is None:
            raise RuntimeError("missing moneyAmount")
        return float(amount)

    async def _fetch_browser_balance(self, account, *, proxy_url: str | None) -> float:
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for account balance fetch")
        runtime_account = RuntimeAccountAdapter(account)
        access_token = runtime_account.get_x_access_token()
        device_id = runtime_account.get_x_device_id()
        if not access_token or not device_id:
            raise RuntimeError("Not login")
        timestamp = str(int(time.time() * 1000))
        x_sign = self._get_xsign_wrapper().generate(
            path=self.BROWSER_BALANCE_PATH,
            method="GET",
            timestamp=timestamp,
            token=access_token,
        )
        headers = self._build_browser_headers(
            runtime_account=runtime_account,
            timestamp=timestamp,
            x_sign=x_sign,
        )
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout, cookie_jar=None) as session:
            async with session.get(
                self.BROWSER_BALANCE_URL,
                proxy=proxy_url,
                headers=headers,
            ) as response:
                text = await response.text()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("invalid browser balance payload") from exc
        if not payload.get("success", False):
            raise RuntimeError(str(payload.get("errorMsg") or "browser balance failed"))
        data = payload.get("data") or {}
        amount = data.get("balance")
        if amount is None:
            raise RuntimeError("missing balance")
        return float(amount)

    @staticmethod
    def _build_browser_headers(
        *,
        runtime_account: RuntimeAccountAdapter,
        timestamp: str,
        x_sign: str,
    ) -> OrderedDict[str, str]:
        access_token = runtime_account.get_x_access_token()
        device_id = runtime_account.get_x_device_id()
        headers: OrderedDict[str, str] = OrderedDict()
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = "https://www.c5game.com/user/user/"
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

    def _get_xsign_wrapper(self) -> Any:
        return self._xsign_wrapper or get_default_xsign_wrapper()


@lru_cache(maxsize=1)
def get_default_xsign_wrapper() -> XSignWrapper:
    repo_root = Path(__file__).resolve().parents[3]
    return XSignWrapper(wasm_path=str(repo_root / "test.wasm"), persistent=True, timeout=10)
