from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional dependency in unit tests
    aiohttp = None


@dataclass(slots=True)
class _CookiePart:
    key: str
    value: str


class RuntimeAccountAdapter:
    """Compatibility layer kept on purpose.

    This object now acts as the shared runtime account context for query, detail
    fetch, inventory refresh and purchase execution. The legacy-style method
    names are intentionally preserved until the wider runtime account cleanup is
    scheduled as its own task.
    """

    def __init__(self, account: object) -> None:
        self._account = account
        self.current_user_id = ""
        self.current_account_name = None
        self.login_status = False
        self.account_proxies: dict[str, str | None] = {}
        self._global_session = None
        self._api_session = None
        self.bind_account(account)

    def bind_account(self, account: object) -> None:
        self._account = account
        self.current_user_id = str(getattr(account, "account_id"))
        self.current_account_name = getattr(account, "display_name", None) or getattr(account, "default_name", None)
        self.login_status = self.get_x_access_token() is not None
        self.account_proxies = {self.current_user_id: self._browser_proxy_url_or_none}

    @property
    def _api_proxy_url_or_none(self) -> str | None:
        proxy_url = getattr(self._account, "api_proxy_url", None)
        return proxy_url or None

    @property
    def _browser_proxy_url_or_none(self) -> str | None:
        proxy_url = getattr(self._account, "browser_proxy_url", None)
        return proxy_url or None

    def get_account_id(self) -> str:
        return self.current_user_id

    def get_account_name(self) -> str | None:
        return self.current_account_name

    def get_api_key(self) -> str | None:
        api_key = getattr(self._account, "api_key", None)
        return api_key or None

    def has_api_key(self) -> bool:
        return bool(self.get_api_key())

    def get_x_access_token(self) -> str | None:
        return self._get_cookie_value("NC5_accessToken")

    def get_x_device_id(self) -> str | None:
        return self._get_cookie_value("NC5_deviceId")

    def get_cookie_header_exact(self) -> str:
        return getattr(self._account, "cookie_raw", None) or ""

    def get_cookie_header_with_decoded_csrf(self) -> str:
        items: list[str] = []
        for part in self._parse_cookie_parts():
            value = unquote(part.value) if part.key == "_csrf" and "%" in part.value else part.value
            items.append(f"{part.key}={value}")
        return "; ".join(items)

    async def get_global_session(self, force_new: bool = False):
        if not self.login_status:
            return None
        if force_new or self._session_requires_refresh(self._global_session):
            await self.close_global_session()
            self._global_session = self._create_session(
                proxy_url=self._browser_proxy_url_or_none,
                limit=30,
                limit_per_host=5,
                timeout_total=30,
                force_close=False,
            )
        return self._global_session

    async def get_api_session(self, force_new: bool = False):
        if not self.has_api_key():
            return None
        if force_new or self._session_requires_refresh(self._api_session):
            await self.close_api_session()
            self._api_session = self._create_session(
                proxy_url=self._api_proxy_url_or_none,
                limit=15,
                limit_per_host=3,
                timeout_total=20,
                force_close=False,
            )
        return self._api_session

    async def close_global_session(self) -> None:
        await self._close_session(self._global_session)
        self._global_session = None

    async def close_api_session(self) -> None:
        await self._close_session(self._api_session)
        self._api_session = None

    async def handle_account_not_login(self, account_id: str) -> None:
        if account_id == self.current_user_id:
            self.login_status = False

    def _create_session(
        self,
        *,
        proxy_url: str | None,
        limit: int,
        limit_per_host: int,
        timeout_total: float,
        force_close: bool,
    ):
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for runtime sessions")
        connector = aiohttp.TCPConnector(
            ssl=False,
            limit=limit,
            limit_per_host=limit_per_host,
            force_close=force_close,
        )
        timeout = aiohttp.ClientTimeout(total=timeout_total)
        try:
            return aiohttp.ClientSession(
                connector=connector,
                proxy=proxy_url,
                timeout=timeout,
                cookie_jar=None,
            )
        except TypeError:
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                cookie_jar=None,
            )
            setattr(session, "_default_proxy", proxy_url)
            return session

    def _get_cookie_value(self, key: str) -> str | None:
        for part in self._parse_cookie_parts():
            if part.key == key and part.value:
                return part.value
        return None

    @classmethod
    def _session_requires_refresh(cls, session) -> bool:
        if session is None:
            return True
        if getattr(session, "closed", False):
            return True
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        session_loop = cls._session_loop(session)
        if session_loop is None:
            return False
        if cls._loop_is_closed(session_loop):
            return True
        return session_loop is not current_loop

    @classmethod
    async def _close_session(cls, session) -> None:
        if session is None or getattr(session, "closed", False):
            return
        session_loop = cls._session_loop(session)
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if session_loop is not None and current_loop is not None and session_loop is not current_loop:
            if cls._loop_is_closed(session_loop):
                return
            is_running = getattr(session_loop, "is_running", None)
            if callable(is_running) and is_running():
                try:
                    future = asyncio.run_coroutine_threadsafe(session.close(), session_loop)
                    future.result(timeout=1.0)
                except Exception:
                    return
            return

        try:
            await session.close()
        except RuntimeError as exc:
            if "Event loop is closed" in str(exc):
                return
            raise

    @staticmethod
    def _session_loop(session):
        return getattr(session, "_loop", None)

    @staticmethod
    def _loop_is_closed(loop) -> bool:
        is_closed = getattr(loop, "is_closed", None)
        if not callable(is_closed):
            return False
        try:
            return bool(is_closed())
        except Exception:
            return False

    def _parse_cookie_parts(self) -> list[_CookiePart]:
        cookie_raw = getattr(self._account, "cookie_raw", None) or ""
        parts: list[_CookiePart] = []
        for raw_part in cookie_raw.split(";"):
            raw_part = raw_part.strip()
            if not raw_part or "=" not in raw_part:
                continue
            key, value = raw_part.split("=", 1)
            parts.append(_CookiePart(key=key.strip(), value=value.strip()))
        return parts
