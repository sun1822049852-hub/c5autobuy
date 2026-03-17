from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AccountInventorySnapshot:
    account_id: str
    selected_steam_id: str | None = None
    inventories: list[dict[str, Any]] = field(default_factory=list)
    refreshed_at: str | None = None
    last_error: str | None = None
