from __future__ import annotations

import time
import urllib.request


class PublicIpResolver:
    MAIN_SERVICE = "https://ipv4.seeip.org"
    BACKUP_SERVICES = (
        "https://api.ipify.org?format=text",
        "https://checkip.amazonaws.com",
        "https://ident.me",
        "https://api4.ipify.org",
        "https://v4.ident.me",
    )

    def __init__(
        self,
        *,
        timeout_seconds: float = 2.0,
        retry_times: int = 1,
        retry_delay_seconds: float = 0.0,
        opener_builder=None,
        sleep_func=None,
    ) -> None:
        self._timeout_seconds = float(timeout_seconds)
        self._retry_times = max(int(retry_times), 1)
        self._retry_delay_seconds = float(retry_delay_seconds)
        self._opener_builder = opener_builder or urllib.request.build_opener
        self._sleep = sleep_func or time.sleep

    def resolve(self, proxy_url: str | None = None) -> str | None:
        opener = self._build_opener(proxy_url)
        for attempt in range(self._retry_times):
            ip = self._fetch_from_service(opener, self.MAIN_SERVICE, timeout=self._timeout_seconds)
            if ip:
                return ip
            if attempt < self._retry_times - 1 and self._retry_delay_seconds > 0:
                self._sleep(self._retry_delay_seconds)

        for url in self.BACKUP_SERVICES:
            ip = self._fetch_from_service(opener, url, timeout=min(self._timeout_seconds, 2.0))
            if ip:
                return ip
        return None

    def _build_opener(self, proxy_url: str | None):
        proxy = str(proxy_url or "").strip()
        if not proxy:
            return self._opener_builder()
        return self._opener_builder(
            urllib.request.ProxyHandler({
                "http": proxy,
                "https": proxy,
            })
        )

    def _fetch_from_service(self, opener, url: str, *, timeout: float) -> str | None:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with opener.open(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", "ignore").strip()
        except Exception:
            return None
        return body if self.is_valid_public_ipv4(body) else None

    @staticmethod
    def is_valid_public_ipv4(ip: str | None) -> bool:
        value = str(ip or "").strip()
        if not value or "." not in value:
            return False
        parts = value.split(".")
        if len(parts) != 4:
            return False
        try:
            octets = [int(part) for part in parts]
        except ValueError:
            return False
        if any(octet < 0 or octet > 255 for octet in octets):
            return False
        first, second, *_ = octets
        if first == 10:
            return False
        if first == 172 and 16 <= second <= 31:
            return False
        if first == 192 and second == 168:
            return False
        if first == 169 and second == 254:
            return False
        if first == 127:
            return False
        return True
