from __future__ import annotations

import asyncio
import base64
import json
from typing import Any, Awaitable, Callable

import aiohttp
import websockets

HttpGet = Callable[[str], Awaitable[dict[str, Any]]]
WebSocketFactory = Callable[[str], Any]


class NetworkCaptureClient:
    USERINFO_PATH_FRAGMENT = "/api/v1/user/v2/userInfo"

    def __init__(
        self,
        *,
        debug_port: int,
        host: str = "127.0.0.1",
        http_get: HttpGet | None = None,
        websocket_factory: WebSocketFactory | None = None,
    ) -> None:
        self._debug_port = int(debug_port)
        self._host = host
        self._http_get = http_get or self._default_http_get
        self._websocket_factory = websocket_factory or websockets.connect

    async def resolve_target_websocket_url(self) -> str:
        version_payload = await self._http_get(
            f"http://{self._host}:{self._debug_port}/json/version"
        )
        browser_websocket_url = str(version_payload.get("webSocketDebuggerUrl") or "")
        if not browser_websocket_url:
            raise RuntimeError("未找到 DevTools browser websocket")

        async with self._websocket_factory(browser_websocket_url) as websocket:
            target_result = await self._send_command(
                websocket,
                {
                    "id": 1,
                    "method": "Target.getTargets",
                    "params": {},
                },
            )

        target_id = self._choose_target_id(target_result.get("targetInfos") or [])
        if not target_id:
            raise RuntimeError("未找到 DevTools page target")
        return self._page_websocket_url(browser_websocket_url, target_id)

    async def capture_userinfo_payload(
        self,
        *,
        timeout_seconds: float,
    ) -> dict[str, object] | None:
        timeout_seconds = float(timeout_seconds)
        if timeout_seconds <= 0:
            return None

        websocket_url = await self.resolve_target_websocket_url()
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        request_cookies: dict[str, str] = {}
        request_urls: dict[str, str] = {}

        async with self._websocket_factory(websocket_url) as websocket:
            await websocket.send(
                json.dumps(
                    {
                        "id": 1,
                        "method": "Network.enable",
                    }
                )
            )

            while True:
                message = await self._recv_json_until_deadline(websocket, deadline)
                if message is None:
                    return None

                method = str(message.get("method") or "")
                params = message.get("params") if isinstance(message.get("params"), dict) else {}

                if method == "Network.requestWillBeSent":
                    request = params.get("request") if isinstance(params.get("request"), dict) else {}
                    url = str(request.get("url") or "")
                    if not self._is_userinfo_url(url):
                        continue
                    request_id = str(params.get("requestId") or "")
                    headers = request.get("headers") if isinstance(request.get("headers"), dict) else {}
                    if request_id:
                        request_urls[request_id] = url
                        request_cookies[request_id] = str(
                            headers.get("Cookie") or headers.get("cookie") or ""
                        )
                    continue

                if method != "Network.responseReceived":
                    continue

                response = params.get("response") if isinstance(params.get("response"), dict) else {}
                request_id = str(params.get("requestId") or "")
                url = str(response.get("url") or request_urls.get(request_id) or "")
                status = int(response.get("status") or 0)
                if not request_id or status != 200 or not self._is_userinfo_url(url):
                    continue

                await websocket.send(
                    json.dumps(
                        {
                            "id": 2,
                            "method": "Network.getResponseBody",
                            "params": {"requestId": request_id},
                        }
                    )
                )
                body_message = await self._recv_message_for_id(
                    websocket,
                    command_id=2,
                    deadline=deadline,
                )
                if body_message is None:
                    return None

                result = body_message.get("result") if isinstance(body_message.get("result"), dict) else {}
                body = str(result.get("body") or "")
                if result.get("base64Encoded"):
                    body = base64.b64decode(body).decode("utf-8", errors="ignore")
                return {
                    "response": body,
                    "cookies": request_cookies.get(request_id, ""),
                    "url": url,
                }

    @staticmethod
    async def _default_http_get(url: str) -> dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                payload = await response.json()
        return payload if isinstance(payload, dict) else {}

    async def _send_command(
        self,
        websocket: Any,
        message: dict[str, object],
    ) -> dict[str, Any]:
        command_id = int(message.get("id") or 0)
        method = str(message.get("method") or "")
        await websocket.send(json.dumps(message))
        response = await self._recv_message_for_id(
            websocket,
            command_id=command_id,
            deadline=asyncio.get_running_loop().time() + 5.0,
        )
        if response is None:
            raise RuntimeError(f"等待 DevTools 响应超时: {method}")
        result = response.get("result")
        return result if isinstance(result, dict) else {}

    async def _recv_message_for_id(
        self,
        websocket: Any,
        *,
        command_id: int,
        deadline: float,
    ) -> dict[str, Any] | None:
        while True:
            message = await self._recv_json_until_deadline(websocket, deadline)
            if message is None:
                return None
            if int(message.get("id") or 0) == command_id:
                return message

    @staticmethod
    async def _recv_json_until_deadline(
        websocket: Any,
        deadline: float,
    ) -> dict[str, Any] | None:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return None
        raw_message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
        payload = json.loads(raw_message)
        return payload if isinstance(payload, dict) else None

    def _choose_target_id(self, target_infos: list[dict[str, object]]) -> str | None:
        page_targets = [
            target
            for target in target_infos
            if str(target.get("type") or "") == "page"
        ]
        target_id = self._first_target_id(
            page_targets,
            predicate=lambda url: "c5game.com" in url,
        )
        if target_id:
            return target_id
        target_id = self._first_target_id(
            page_targets,
            predicate=lambda url: not url.startswith(("edge://", "devtools://", "chrome://")),
        )
        if target_id:
            return target_id
        return self._first_target_id(page_targets, predicate=lambda _url: True)

    @staticmethod
    def _first_target_id(
        targets: list[dict[str, object]],
        *,
        predicate: Callable[[str], bool],
    ) -> str | None:
        for target in targets:
            url = str(target.get("url") or "")
            if not predicate(url):
                continue
            target_id = str(target.get("targetId") or "")
            if target_id:
                return target_id
        return None

    @staticmethod
    def _page_websocket_url(browser_websocket_url: str, target_id: str) -> str:
        prefix, separator, _suffix = browser_websocket_url.partition("/devtools/browser/")
        if not separator:
            raise RuntimeError("非法 DevTools browser websocket 地址")
        return f"{prefix}/devtools/page/{target_id}"

    @classmethod
    def _is_userinfo_url(cls, url: str) -> bool:
        return bool(
            url
            and (
                cls.USERINFO_PATH_FRAGMENT in url
                or "user/v2/userInfo" in url
            )
        )
