from __future__ import annotations

from datetime import datetime


def purchase_capability_label(state: str | None) -> str:
    mapping = {
        "unbound": "未绑定",
        "bound": "已绑定",
        "expired": "登录失效",
    }
    return mapping.get(state or "", state or "")


def purchase_pool_label(state: str | None) -> str:
    mapping = {
        "not_connected": "未接入",
        "active": "运行中",
        "available": "可用",
        "paused_no_inventory": "库存不足暂停",
        "paused_not_login": "未登录暂停",
        "paused_auth_invalid": "鉴权失效暂停",
    }
    return mapping.get(state or "", state or "")


def format_last_login(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value
