from __future__ import annotations

import time

import aiohttp

from app_backend.infrastructure.proxy.value_objects import render_proxy_url


TEST_URL = "https://httpbin.org/ip"
TEST_TIMEOUT_SECONDS = 10


class ProxyTestService:
    async def test(
        self,
        *,
        scheme: str,
        host: str,
        port: str,
        username: str | None = None,
        password: str | None = None,
    ) -> dict:
        proxy_url = render_proxy_url(
            scheme=scheme,
            host=host,
            port=port,
            username=username,
            password=password,
        )
        start = time.monotonic()
        try:
            timeout = aiohttp.ClientTimeout(total=TEST_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(TEST_URL, proxy=proxy_url) as response:
                    latency_ms = round((time.monotonic() - start) * 1000)
                    body = await response.json()
                    return {
                        "reachable": True,
                        "latency_ms": latency_ms,
                        "public_ip": body.get("origin", ""),
                        "error": None,
                    }
        except Exception as exc:
            latency_ms = round((time.monotonic() - start) * 1000)
            return {
                "reachable": False,
                "latency_ms": latency_ms,
                "public_ip": None,
                "error": str(exc),
            }
