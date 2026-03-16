from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DashboardSummary:
    total_accounts: int
    logged_in_accounts: int
    api_key_accounts: int
    total_configs: int
    total_products: int

