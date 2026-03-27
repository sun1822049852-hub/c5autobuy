from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Sequence

from app_backend.infrastructure.browser_runtime.cdp_session_reader import read_attached_session
from app_backend.infrastructure.browser_runtime.login_adapter import BrowserLoginAdapter


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="附着到本地 Edge 调试会话，读取当前登录 Cookie 与用户信息",
    )
    parser.add_argument("--debugger-address")
    return parser


def _resolve_debugger_address(cli_value: str | None) -> str | None:
    cli_value = str(cli_value or "").strip()
    if cli_value:
        return cli_value
    env_value = str(os.environ.get("C5_EDGE_DEBUGGER_ADDRESS", "") or "").strip()
    return env_value or None


def _build_local_edge_adapter(debugger_address: str) -> BrowserLoginAdapter:
    async def _run_login(*, proxy_url: str | None, emit_state=None):
        del proxy_url
        if emit_state is not None:
            maybe_result = emit_state("attached_to_browser")
            if asyncio.iscoroutine(maybe_result):
                await maybe_result
        return read_attached_session(debugger_address)

    return BrowserLoginAdapter(login_runner=_run_login)


async def _run(adapter: BrowserLoginAdapter) -> dict[str, object]:
    result = adapter.run_login(proxy_url=None)
    payload = await result if asyncio.iscoroutine(result) else result
    c5_user_id = getattr(payload, "c5_user_id", None)
    c5_nick_name = getattr(payload, "c5_nick_name", None)
    cookie_raw = getattr(payload, "cookie_raw", None)
    if isinstance(payload, dict):
        c5_user_id = payload.get("c5_user_id")
        c5_nick_name = payload.get("c5_nick_name")
        cookie_raw = payload.get("cookie_raw")
    return {
        "c5_user_id": str(c5_user_id or ""),
        "c5_nick_name": str(c5_nick_name or ""),
        "cookie_raw_preview": str(cookie_raw or ""),
        "has_cookie_raw": bool(cookie_raw),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    debugger_address = _resolve_debugger_address(args.debugger_address)
    if not debugger_address:
        print("缺少 Edge 调试地址，请传 --debugger-address 或设置 C5_EDGE_DEBUGGER_ADDRESS", file=sys.stderr)
        return 2

    adapter = _build_local_edge_adapter(debugger_address)
    payload = asyncio.run(_run(adapter))
    payload["debugger_address"] = debugger_address
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

