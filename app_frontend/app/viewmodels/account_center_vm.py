from __future__ import annotations

from typing import Any

from app_frontend.app.formatters.account_display import purchase_capability_label, purchase_pool_label


class AccountCenterViewModel:
    def __init__(self) -> None:
        self._accounts: list[dict[str, Any]] = []
        self.selected_account_id: str | None = None
        self._detail_account_id: str | None = None

    def set_accounts(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(account) for account in accounts]
        account_ids = {account["account_id"] for account in self._accounts}
        if self.selected_account_id not in account_ids:
            self.selected_account_id = None
        if self._detail_account_id not in account_ids:
            self._detail_account_id = None

    @property
    def table_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "account_id": account["account_id"],
                "display_name": self._display_name(account),
                "query_capability": "已配置" if account.get("api_key") else "未配置",
                "purchase_capability": purchase_capability_label(account.get("purchase_capability_state", "unbound")),
                "purchase_pool_state": purchase_pool_label(account.get("purchase_pool_state", "not_connected")),
                "proxy": account.get("proxy_url") or "直连",
            }
            for account in self._accounts
        ]

    @property
    def detail_account(self) -> dict[str, Any] | None:
        if self._detail_account_id is None:
            return None
        return self._get_account(self._detail_account_id)

    @property
    def selected_account(self) -> dict[str, Any] | None:
        if self.selected_account_id is None:
            return None
        return self._get_account(self.selected_account_id)

    def select_account(self, account_id: str | None) -> None:
        self.selected_account_id = account_id

    def open_selected_account_detail(self) -> dict[str, Any] | None:
        if self.selected_account_id is None:
            return None
        self._detail_account_id = self.selected_account_id
        return self.detail_account

    def upsert_account(self, account: dict[str, Any]) -> None:
        replaced = False
        normalized = dict(account)
        normalized["display_name"] = self._display_name(normalized)
        for index, current in enumerate(self._accounts):
            if current["account_id"] == normalized["account_id"]:
                self._accounts[index] = normalized
                replaced = True
                break
        if not replaced:
            self._accounts.append(normalized)

    def remove_account(self, account_id: str) -> None:
        self._accounts = [account for account in self._accounts if account["account_id"] != account_id]
        if self.selected_account_id == account_id:
            self.selected_account_id = None
        if self._detail_account_id == account_id:
            self._detail_account_id = None

    def _get_account(self, account_id: str) -> dict[str, Any] | None:
        for account in self._accounts:
            if account["account_id"] == account_id:
                account_copy = dict(account)
                account_copy["display_name"] = self._display_name(account_copy)
                return account_copy
        return None

    @staticmethod
    def _display_name(account: dict[str, Any]) -> str:
        return (
            account.get("display_name")
            or account.get("remark_name")
            or account.get("c5_nick_name")
            or account.get("default_name")
            or ""
        )
