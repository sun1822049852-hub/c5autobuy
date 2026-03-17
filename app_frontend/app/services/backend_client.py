from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx

try:
    from websockets.asyncio.client import connect as websockets_connect
except ImportError:  # pragma: no cover - compatibility fallback
    try:
        from websockets import connect as websockets_connect
    except ImportError:  # pragma: no cover - optional dependency
        websockets_connect = None


class BackendClient:
    def __init__(
        self,
        *,
        http_client=None,
        client_factory=None,
        ws_connect_factory=None,
        base_url: str | None = None,
        timeout: float = 30.0,
        poll_interval: float = 0.2,
    ) -> None:
        self._http_client = http_client
        self._client_factory = client_factory
        self._ws_connect_factory = ws_connect_factory
        self._base_url = base_url
        self._timeout = timeout
        self._poll_interval = poll_interval

    async def list_accounts(self) -> list[dict[str, Any]]:
        async with self._client() as http_client:
            response = await http_client.get("/accounts")
            response.raise_for_status()
            return response.json()

    async def get_account(self, account_id: str) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.get(f"/accounts/{account_id}")
            response.raise_for_status()
            return response.json()

    async def create_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post("/accounts", json=payload)
            response.raise_for_status()
            return response.json()

    async def update_account(self, account_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.patch(f"/accounts/{account_id}", json=payload)
            response.raise_for_status()
            return response.json()

    async def delete_account(self, account_id: str) -> None:
        async with self._client() as http_client:
            response = await http_client.delete(f"/accounts/{account_id}")
            response.raise_for_status()

    async def clear_purchase_capability(self, account_id: str) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post(f"/accounts/{account_id}/purchase-capability/clear")
            response.raise_for_status()
            return response.json()

    async def list_query_configs(self) -> list[dict[str, Any]]:
        async with self._client() as http_client:
            response = await http_client.get("/query-configs")
            response.raise_for_status()
            return response.json()

    async def create_query_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post("/query-configs", json=payload)
            response.raise_for_status()
            return response.json()

    async def update_query_mode_setting(self, config_id: str, mode_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.patch(f"/query-configs/{config_id}/modes/{mode_type}", json=payload)
            response.raise_for_status()
            return response.json()

    async def add_query_item(self, config_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post(f"/query-configs/{config_id}/items", json=payload)
            response.raise_for_status()
            return response.json()

    async def update_query_item(self, config_id: str, query_item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.patch(f"/query-configs/{config_id}/items/{query_item_id}", json=payload)
            response.raise_for_status()
            return response.json()

    async def delete_query_item(self, config_id: str, query_item_id: str) -> None:
        async with self._client() as http_client:
            response = await http_client.delete(f"/query-configs/{config_id}/items/{query_item_id}")
            response.raise_for_status()

    async def get_query_runtime_status(self) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.get("/query-runtime/status")
            response.raise_for_status()
            return response.json()

    async def start_query_runtime(self, config_id: str) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post("/query-runtime/start", json={"config_id": config_id})
            response.raise_for_status()
            return response.json()

    async def stop_query_runtime(self) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post("/query-runtime/stop")
            response.raise_for_status()
            return response.json()

    async def get_purchase_runtime_status(self) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.get("/purchase-runtime/status")
            response.raise_for_status()
            return response.json()

    async def get_purchase_runtime_inventory_detail(self, account_id: str) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.get(f"/purchase-runtime/accounts/{account_id}/inventory")
            response.raise_for_status()
            return response.json()

    async def start_purchase_runtime(self) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post("/purchase-runtime/start")
            response.raise_for_status()
            return response.json()

    async def stop_purchase_runtime(self) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post("/purchase-runtime/stop")
            response.raise_for_status()
            return response.json()

    async def get_purchase_runtime_settings(self) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.get("/purchase-runtime/settings")
            response.raise_for_status()
            return response.json()

    async def update_purchase_runtime_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.put("/purchase-runtime/settings", json=payload)
            response.raise_for_status()
            return response.json()

    async def start_login(self, account_id: str) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post(f"/accounts/{account_id}/login")
            response.raise_for_status()
            return response.json()

    async def resolve_login_conflict(
        self,
        account_id: str,
        *,
        task_id: str,
        action: str,
    ) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.post(
                f"/accounts/{account_id}/login/resolve",
                json={"task_id": task_id, "action": action},
            )
            response.raise_for_status()
            return response.json()

    async def get_task(self, task_id: str) -> dict[str, Any]:
        async with self._client() as http_client:
            response = await http_client.get(f"/tasks/{task_id}")
            response.raise_for_status()
            return response.json()

    async def watch_task(self, task_id: str) -> AsyncIterator[dict[str, Any]]:
        websocket_url = self._build_websocket_url(task_id)
        ws_connect_factory = self._resolve_ws_connect_factory()

        if websocket_url and ws_connect_factory is not None:
            try:
                async with ws_connect_factory(websocket_url, self._timeout) as websocket:
                    while True:
                        snapshot = json.loads(await websocket.recv())
                        yield snapshot
                        if snapshot["state"] in {"succeeded", "failed", "cancelled", "conflict"}:
                            return
            except Exception:
                # WebSocket 失败时回退到轮询，避免桌面端直接失联。
                pass

        last_signature: tuple[str, int, str | None, str | None] | None = None

        while True:
            snapshot = await self.get_task(task_id)
            signature = (
                snapshot["state"],
                len(snapshot["events"]),
                snapshot.get("error"),
                snapshot.get("updated_at"),
            )
            if signature != last_signature:
                yield snapshot
                last_signature = signature

            if snapshot["state"] in {"succeeded", "failed", "cancelled", "conflict"}:
                break

            await asyncio.sleep(self._poll_interval)

    @asynccontextmanager
    async def _client(self):
        if self._http_client is not None:
            yield self._http_client
            return

        if self._client_factory is not None:
            async with self._client_factory() as http_client:
                yield http_client
            return

        if self._base_url is None:
            raise RuntimeError("BackendClient 需要 http_client、client_factory 或 base_url 之一")

        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as http_client:
            yield http_client

    def _resolve_ws_connect_factory(self):
        if self._ws_connect_factory is not None:
            return self._ws_connect_factory

        if websockets_connect is None:
            return None

        return lambda url, timeout: websockets_connect(url, open_timeout=timeout, close_timeout=timeout)

    def _build_websocket_url(self, task_id: str) -> str | None:
        if self._base_url is None:
            return None

        parsed = urlparse(self._base_url)
        if not parsed.scheme or not parsed.netloc:
            return None

        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        return urlunparse((ws_scheme, parsed.netloc, f"/ws/tasks/{task_id}", "", "", ""))
