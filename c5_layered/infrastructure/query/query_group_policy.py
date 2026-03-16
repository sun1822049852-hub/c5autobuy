from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class QueryGroupPlan:
    enable_new: bool
    enable_fast: bool
    enable_old: bool


class LegacyQueryGroupPolicy:
    """
    Decides which legacy query groups should be created for an account.
    """

    def decide(
        self,
        *,
        account_manager: Any,
        product_items: list[Any],
    ) -> QueryGroupPlan:
        has_api_key = bool(account_manager.has_api_key())
        login_status = bool(getattr(account_manager, "login_status", True))
        has_market_hash = any(
            bool(getattr(item, "market_hash_name", None))
            for item in product_items
        )
        time_config = account_manager.get_query_time_config()
        old_enabled = bool(time_config and time_config.get("enabled"))

        enable_new = has_api_key and has_market_hash
        enable_fast = has_api_key and has_market_hash
        enable_old = login_status and old_enabled
        return QueryGroupPlan(
            enable_new=enable_new,
            enable_fast=enable_fast,
            enable_old=enable_old,
        )
