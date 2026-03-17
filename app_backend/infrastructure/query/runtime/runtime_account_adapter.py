from __future__ import annotations

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
    def __init__(self, account: object) -> None:
        self._account = account
        self.current_user_id = str(getattr(account, "account_id"))
        self.current_account_name = getattr(account, "display_name", None) or getattr(account, "default_name", None)
        self.login_status = self.get_x_access_token() is not None
        self.account_proxies = {self.current_user_id: self._proxy_url_or_none}
        self._global_session = None
        self._api_session = None

    @property
    def _proxy_url_or_none(self) -> str | None:
        proxy_url = getattr(self._account, "proxy_url", None)
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
        if force_new or self._global_session is None or self._global_session.closed:
            await self.close_global_session()
            self._global_session = self._create_session(
                limit=30,
                limit_per_host=5,
                timeout_total=30,
                force_close=False,
            )
        return self._global_session

    async def get_api_session(self, force_new: bool = False):
        if not self.has_api_key():
            return None
        if force_new or self._api_session is None or self._api_session.closed:
            await self.close_api_session()
            self._api_session = self._create_session(
                limit=15,
                limit_per_host=3,
                timeout_total=20,
                force_close=False,
            )
        return self._api_session

    async def close_global_session(self) -> None:
        if self._global_session is not None and not self._global_session.closed:
            await self._global_session.close()
        self._global_session = None

    async def close_api_session(self) -> None:
        if self._api_session is not None and not self._api_session.closed:
            await self._api_session.close()
        self._api_session = None

    async def handle_account_not_login(self, account_id: str) -> None:
        if account_id == self.current_user_id:
            self.login_status = False

    def _create_session(
        self,
        *,
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
                proxy=self._proxy_url_or_none,
                timeout=timeout,
                cookie_jar=None,
            )
        except TypeError:
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                cookie_jar=None,
            )
            setattr(session, "_default_proxy", self._proxy_url_or_none)
            return session

    def _get_cookie_value(self, key: str) -> str | None:
        for part in self._parse_cookie_parts():
            if part.key == key and part.value:
                return part.value
        return None

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
