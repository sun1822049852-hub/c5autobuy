from __future__ import annotations

from datetime import datetime
from typing import Any


def format_runtime_summary(status: dict[str, Any]) -> str:
    if status.get("running"):
        return (
            f"{status.get('message')}: {status.get('config_name')} "
            f"(账号 {status.get('account_count', 0)}, 查询 {status.get('total_query_count', 0)}, 命中 {status.get('total_found_count', 0)})"
        )
    return str(status.get("message") or "未运行")


def build_mode_rows(status: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for mode in (status.get("modes") or {}).values():
        rows.append(
            {
                "mode_type": str(mode.get("mode_type") or ""),
                "enabled": _format_mode_status(mode),
                "account_state": f"{mode.get('active_account_count', 0)}/{mode.get('eligible_account_count', 0)}",
                "query_state": f"{mode.get('query_count', 0)}/{mode.get('found_count', 0)}",
                "window_state": _format_window_state(mode),
                "last_error": str(mode.get("last_error") or "-"),
            }
        )
    return rows


def build_group_rows(status: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for group in status.get("group_rows") or []:
        if not isinstance(group, dict):
            continue
        rows.append(
            {
                "account_display_name": str(group.get("account_display_name") or group.get("account_id") or ""),
                "mode_type": str(group.get("mode_type") or ""),
                "status": _format_group_status(group),
                "window_state": "窗口内" if group.get("in_window") else "窗口外",
                "cooldown": _format_group_cooldown(group),
                "query_state": f"{group.get('query_count', 0)}/{group.get('found_count', 0)}",
                "last_success_at": _format_event_time(group.get("last_success_at")) if group.get("last_success_at") else "-",
                "last_error": str(group.get("last_error") or "-"),
            }
        )
    return rows


def build_event_rows(status: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for event in status.get("recent_events") or []:
        if not isinstance(event, dict):
            continue
        rows.append(
            {
                "timestamp": _format_event_time(event.get("timestamp")),
                "mode_type": str(event.get("mode_type") or ""),
                "account_id": str(event.get("account_display_name") or event.get("account_id") or ""),
                "query_item_name": str(event.get("query_item_name") or event.get("query_item_id") or ""),
                "result": _format_event_result(event),
                "message": str(event.get("error") or event.get("message") or "-"),
            }
        )
    return rows


def _format_mode_status(mode: dict[str, Any]) -> str:
    if not mode.get("enabled"):
        return "关闭"
    return "启用 / 窗口内" if mode.get("in_window") else "启用 / 窗口外"


def _format_group_status(group: dict[str, Any]) -> str:
    if group.get("disabled_reason"):
        return "已禁用"
    if group.get("cooldown_until") and float(group.get("rate_limit_increment", 0.0) or 0.0) > 0:
        return "限流退避"
    if group.get("cooldown_until"):
        return "冷却中"
    if not group.get("in_window"):
        return "窗口外等待"
    if group.get("active"):
        return "运行中"
    return "未启动"


def _format_window_state(mode: dict[str, Any]) -> str:
    start = mode.get("next_window_start")
    end = mode.get("next_window_end")
    if not start or not end:
        return "始终运行" if mode.get("enabled") else "-"
    return f"{_format_clock(start)} - {_format_clock(end)}"


def _format_group_cooldown(group: dict[str, Any]) -> str:
    cooldown_until = group.get("cooldown_until")
    if not cooldown_until:
        return "-"
    return _format_event_time(cooldown_until)


def _format_clock(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%H:%M")
    except ValueError:
        return str(value)


def _format_event_time(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%H:%M:%S")
    except ValueError:
        return str(value)


def _format_event_result(event: dict[str, Any]) -> str:
    if event.get("error"):
        return "错误"
    match_count = int(event.get("match_count", 0))
    if match_count > 0:
        return f"命中 {match_count}"
    return str(event.get("message") or "-")
