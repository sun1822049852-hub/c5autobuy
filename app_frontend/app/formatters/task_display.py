from __future__ import annotations

from datetime import datetime
import json


def task_state_label(state: str | None) -> str:
    mapping = {
        "pending": "等待任务开始",
        "starting_browser": "正在启动浏览器",
        "waiting_for_scan": "等待扫码",
        "captured_login_info": "已捕获登录信息",
        "waiting_for_browser_close": "等待用户关闭浏览器",
        "saving_account": "正在保存账号",
        "succeeded": "登录完成",
        "failed": "登录失败",
        "cancelled": "用户取消",
        "conflict": "检测到账号冲突",
    }
    return mapping.get(state or "", state or "")


def task_event_label(event: dict) -> str:
    parts: list[str] = []
    timestamp = _task_event_time(event.get("timestamp"))
    if timestamp:
        parts.append(timestamp)
    parts.append(task_state_label(event.get("state")))
    label = " · ".join(parts)
    message = event.get("message") or ""
    payload = _task_event_payload(event.get("payload"))
    if message:
        label = f"{label} - {message}"
    if payload:
        return f"{label} [payload: {payload}]"
    return label


def task_meta_time_label(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def _task_event_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%H:%M:%S")
    except ValueError:
        return value


def _task_event_payload(value) -> str:
    if value in (None, "", [], {}):
        return ""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)
