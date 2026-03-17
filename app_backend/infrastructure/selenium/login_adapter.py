from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app_backend.infrastructure.selenium.selenium_login_runner import SeleniumLoginRunner

ProgressCallback = Callable[[str], Awaitable[None] | None]
LoginRunner = Callable[..., Awaitable["LoginCapture | dict[str, Any]"]]


async def _noop_emit(_: str) -> None:
    return None


@dataclass(slots=True)
class LoginCapture:
    c5_user_id: str
    c5_nick_name: str
    cookie_raw: str


class SeleniumLoginAdapter:
    def __init__(
        self,
        login_runner: LoginRunner | None = None,
        *,
        runner: SeleniumLoginRunner | None = None,
    ) -> None:
        self._runner = runner or SeleniumLoginRunner()
        self._login_runner = login_runner or self._runner.run

    async def run_login(
        self,
        *,
        proxy_url: str | None,
        emit_state: ProgressCallback | None = None,
    ) -> LoginCapture:
        callback = emit_state or _noop_emit
        payload = await self._login_runner(proxy_url=proxy_url, emit_state=callback)
        return self._normalize_payload(payload)

    @staticmethod
    def _normalize_payload(payload: LoginCapture | dict[str, Any]) -> LoginCapture:
        if isinstance(payload, LoginCapture):
            return payload

        return LoginCapture(
            c5_user_id=str(payload.get("c5_user_id") or ""),
            c5_nick_name=str(payload.get("c5_nick_name") or ""),
            cookie_raw=str(payload.get("cookie_raw") or ""),
        )
