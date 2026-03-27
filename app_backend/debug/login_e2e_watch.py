from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import httpx

from app_backend.main import create_app

TERMINAL_STATES = {"succeeded", "failed", "conflict"}
SENSITIVE_KEYS = {"api_key", "cookie_raw", "browser_proxy_url", "api_proxy_url"}


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _elapsed_seconds(started_at: float) -> float:
    return round(time.monotonic() - started_at, 3)


def _append_log(log_file: Path, started_at: float, phase: str, **payload: Any) -> None:
    record = {
        "timestamp": _timestamp(),
        "elapsed_seconds": _elapsed_seconds(started_at),
        "phase": phase,
    }
    for key, value in payload.items():
        if value is not None:
            record[key] = value

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _sanitize_value(value: Any, *, key: str | None = None) -> Any:
    if key in SENSITIVE_KEYS:
        return "[REDACTED]" if value else None
    if isinstance(value, Mapping):
        return {
            str(child_key): _sanitize_value(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _summarize_account(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "account_id": payload.get("account_id"),
        "remark_name": payload.get("remark_name"),
        "browser_proxy_mode": payload.get("browser_proxy_mode"),
        "api_proxy_mode": payload.get("api_proxy_mode"),
        "c5_user_id": payload.get("c5_user_id"),
        "c5_nick_name": payload.get("c5_nick_name"),
        "purchase_capability_state": payload.get("purchase_capability_state"),
        "purchase_pool_state": payload.get("purchase_pool_state"),
        "last_login_at": payload.get("last_login_at"),
        "last_error": payload.get("last_error"),
        "has_cookie_raw": bool(payload.get("cookie_raw")),
        "has_api_key": bool(payload.get("api_key")),
    }


def _load_sqlite_account_summary(db_path: Path, account_id: str) -> dict[str, Any]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT
                account_id,
                remark_name,
                browser_proxy_mode,
                api_proxy_mode,
                c5_user_id,
                c5_nick_name,
                purchase_capability_state,
                purchase_pool_state,
                last_login_at,
                last_error,
                updated_at,
                CASE WHEN cookie_raw IS NULL OR cookie_raw = '' THEN 0 ELSE 1 END AS has_cookie_raw,
                CASE WHEN api_key IS NULL OR api_key = '' THEN 0 ELSE 1 END AS has_api_key
            FROM accounts
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()

    if row is None:
        return {"account_id": account_id, "exists": False}

    summary = dict(row)
    summary["exists"] = True
    summary["has_cookie_raw"] = bool(summary["has_cookie_raw"])
    summary["has_api_key"] = bool(summary["has_api_key"])
    return summary


def _default_account_payload(
    *,
    remark_name: str,
    proxy_mode: str,
    proxy_url: str | None,
    api_key: str | None,
) -> dict[str, Any]:
    return {
        "remark_name": remark_name,
        "browser_proxy_mode": proxy_mode,
        "browser_proxy_url": proxy_url,
        "api_proxy_mode": "direct",
        "api_proxy_url": None,
        "api_key": api_key,
    }


def _default_paths() -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path("data")
    return (
        base_dir / f"login_verify_{stamp}.db",
        base_dir / f"login_verify_{stamp}.jsonl",
    )


def _instruction_lines() -> list[str]:
    debugger_address = str(os.environ.get("C5_EDGE_DEBUGGER_ADDRESS", "") or "").strip()
    if debugger_address:
        return [
            f"步骤: 当前为 attach 模式（{debugger_address}）。请在已启动的真实浏览器中完成登录。",
            "如登录成功后任务未自动结束，请在同一浏览器打开或刷新 https://www.c5game.com/user/user/ 。",
            "attach 模式无需关闭浏览器窗口。",
        ]
    return [
        "步骤: 浏览器打开后扫码登录，登录成功后关闭临时浏览器窗口，再把日志贴回。"
    ]


async def run_login_watch(
    *,
    db_path: Path,
    log_path: Path,
    app: Any | None = None,
    account_payload: Mapping[str, Any] | None = None,
    poll_interval_seconds: float = 0.5,
    heartbeat_interval_seconds: float = 5.0,
    timeout_seconds: float = 900.0,
) -> dict[str, Any]:
    started_at = time.monotonic()
    db_path = Path(db_path)
    log_path = Path(log_path)
    account_payload = account_payload or _default_account_payload(
        remark_name="登录验真",
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
    )
    app_instance = app or create_app(db_path=db_path)

    _append_log(
        log_path,
        started_at,
        "watch_started",
        db_path=str(db_path),
        log_path=str(log_path),
        account_template=_sanitize_value(dict(account_payload)),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_instance),
        base_url="http://login-watch.local",
    ) as client:
        create_response = await client.post("/accounts", json=dict(account_payload))
        create_response.raise_for_status()
        account = create_response.json()
        account_id = str(account["account_id"])
        _append_log(
            log_path,
            started_at,
            "account_created",
            account=_summarize_account(account),
        )

        login_response = await client.post(f"/accounts/{account_id}/login")
        login_response.raise_for_status()
        task_snapshot = login_response.json()
        task_id = str(task_snapshot["task_id"])
        _append_log(
            log_path,
            started_at,
            "task_started",
            task_id=task_id,
            state=task_snapshot.get("state"),
        )

        seen_events = 0
        last_heartbeat_at = 0.0
        deadline = time.monotonic() + float(timeout_seconds)

        while True:
            task_response = await client.get(f"/tasks/{task_id}")
            task_response.raise_for_status()
            task_snapshot = task_response.json()
            events = task_snapshot.get("events", [])

            for event in events[seen_events:]:
                _append_log(
                    log_path,
                    started_at,
                    "task_event",
                    task_id=task_id,
                    state=event.get("state"),
                    message=event.get("message"),
                    payload=_sanitize_value(event.get("payload")),
                )
            seen_events = len(events)

            current_state = str(task_snapshot.get("state") or "")
            if current_state in TERMINAL_STATES:
                _append_log(
                    log_path,
                    started_at,
                    "task_terminal",
                    task_id=task_id,
                    state=current_state,
                    error=task_snapshot.get("error"),
                    result=_sanitize_value(task_snapshot.get("result")),
                    pending_conflict=_sanitize_value(task_snapshot.get("pending_conflict")),
                )
                break

            now = time.monotonic()
            if heartbeat_interval_seconds > 0 and now - last_heartbeat_at >= heartbeat_interval_seconds:
                _append_log(
                    log_path,
                    started_at,
                    "task_heartbeat",
                    task_id=task_id,
                    state=current_state,
                    event_count=seen_events,
                )
                last_heartbeat_at = now

            if now >= deadline:
                _append_log(
                    log_path,
                    started_at,
                    "task_timeout",
                    task_id=task_id,
                    state=current_state,
                    event_count=seen_events,
                )
                raise TimeoutError(f"任务 {task_id} 在 {timeout_seconds} 秒内未结束")

            await asyncio.sleep(poll_interval_seconds)

        detail_response = await client.get(f"/accounts/{account_id}")
        if detail_response.status_code == 200:
            _append_log(
                log_path,
                started_at,
                "account_detail",
                account=_summarize_account(detail_response.json()),
            )
        else:
            _append_log(
                log_path,
                started_at,
                "account_detail_missing",
                account_id=account_id,
                status_code=detail_response.status_code,
            )

    sqlite_row = _load_sqlite_account_summary(db_path, account_id)
    _append_log(log_path, started_at, "sqlite_row", row=sqlite_row)

    summary = {
        "account_id": account_id,
        "task_id": task_id,
        "task_state": task_snapshot.get("state"),
        "db_path": str(db_path),
        "log_path": str(log_path),
    }
    _append_log(log_path, started_at, "watch_finished", summary=summary)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="写入 C5 登录闭环调试日志")
    parser.add_argument("--remark-name", default="登录验真")
    parser.add_argument("--proxy-mode", choices=("direct", "custom"))
    parser.add_argument("--proxy-url")
    parser.add_argument("--api-key")
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--heartbeat-interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    db_path, log_path = _default_paths()
    proxy_mode = args.proxy_mode or ("custom" if args.proxy_url else "direct")

    account_payload = _default_account_payload(
        remark_name=args.remark_name,
        proxy_mode=proxy_mode,
        proxy_url=args.proxy_url,
        api_key=args.api_key,
    )

    print(f"日志文件: {log_path}")
    print(f"数据库: {db_path}")
    for line in _instruction_lines():
        print(line)

    try:
        summary = asyncio.run(
            run_login_watch(
                db_path=db_path,
                log_path=log_path,
                account_payload=account_payload,
                poll_interval_seconds=args.poll_interval,
                heartbeat_interval_seconds=args.heartbeat_interval,
                timeout_seconds=args.timeout,
            )
        )
    except Exception as exc:
        _append_log(log_path, time.monotonic(), "watch_crashed", error=str(exc))
        print(f"执行失败: {exc}")
        return 1

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
