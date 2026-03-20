from __future__ import annotations

from typing import Any


class PurchaseRuntimeViewModel:
    def __init__(self) -> None:
        self._status: dict[str, Any] = self._build_default_status()

    def load_status(self, status: dict[str, Any]) -> None:
        self._status = dict(status)

    @property
    def raw_status(self) -> dict[str, Any]:
        return dict(self._status)

    @property
    def summary(self) -> dict[str, str]:
        recovery_waiting_count = sum(
            1
            for account in (self._status.get("accounts") or [])
            if str(account.get("purchase_pool_state") or "") == "paused_no_inventory"
        )
        return {
            "running": "是" if self._status.get("running") else "否",
            "message": str(self._status.get("message") or "未运行"),
            "queue_size": str(int(self._status.get("queue_size", 0))),
            "active_account_count": str(int(self._status.get("active_account_count", 0))),
            "total_account_count": str(int(self._status.get("total_account_count", 0))),
            "recovery_waiting_count": str(recovery_waiting_count),
            "total_purchased_count": str(int(self._status.get("total_purchased_count", 0))),
            "started_at": str(self._status.get("started_at") or ""),
            "stopped_at": str(self._status.get("stopped_at") or ""),
        }

    @property
    def account_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for account in self._status.get("accounts") or []:
            rows.append(
                {
                    "account_id": str(account.get("account_id") or ""),
                    "display_name": str(account.get("display_name") or account.get("account_id") or ""),
                    "purchase_capability_state": str(account.get("purchase_capability_state") or ""),
                    "purchase_pool_state": str(account.get("purchase_pool_state") or ""),
                    "recovery_status": self._format_recovery_status(account),
                    "selected_steam_id": str(account.get("selected_steam_id") or ""),
                    "capacity_text": self._format_capacity_text(account),
                    "last_error": str(account.get("last_error") or ""),
                    "total_purchased_count": str(int(account.get("total_purchased_count", 0) or 0)),
                }
            )
        return rows

    @property
    def recent_event_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for event in self._status.get("recent_events") or []:
            rows.append(
                {
                    "occurred_at": str(event.get("occurred_at") or ""),
                    "status": str(event.get("status") or ""),
                    "status_text": self._format_event_status(str(event.get("status") or "")),
                    "message": str(event.get("message") or ""),
                    "account_display_name": str(
                        event.get("account_display_name") or event.get("account_id") or ""
                    ),
                    "query_item_name": str(event.get("query_item_name") or ""),
                    "total_price": event.get("total_price"),
                    "total_wear_sum": event.get("total_wear_sum"),
                    "source_mode_type": str(event.get("source_mode_type") or ""),
                }
            )
        return rows

    @staticmethod
    def _build_default_status() -> dict[str, Any]:
        return {
            "running": False,
            "message": "未运行",
            "started_at": None,
            "stopped_at": None,
            "queue_size": 0,
            "active_account_count": 0,
            "total_account_count": 0,
            "total_purchased_count": 0,
            "recent_events": [],
            "accounts": [],
        }

    @staticmethod
    def _format_recovery_status(account: dict[str, Any]) -> str:
        purchase_pool_state = str(account.get("purchase_pool_state") or "")
        purchase_capability_state = str(account.get("purchase_capability_state") or "")
        if purchase_capability_state == "expired" or purchase_pool_state == "paused_auth_invalid":
            return "登录已失效"
        if purchase_pool_state == "paused_no_inventory":
            return "等待恢复检查"
        if purchase_pool_state == "active":
            return "可参与购买"
        if purchase_pool_state == "not_connected":
            return "未接入运行时"
        return purchase_pool_state

    @staticmethod
    def _format_event_status(status: str) -> str:
        status_map = {
            "queued": "已入队",
            "success": "购买成功",
            "paused_no_inventory": "库存不足",
            "inventory_recovered": "库存恢复",
            "recovery_waiting": "等待恢复",
            "auth_invalid": "登录失效",
        }
        return status_map.get(status, status)

    @staticmethod
    def _format_capacity_text(account: dict[str, Any]) -> str:
        remaining = account.get("selected_inventory_remaining_capacity")
        maximum = account.get("selected_inventory_max")
        if remaining is None or maximum is None:
            return "-"
        return f"{int(remaining)}/{int(maximum)}"
