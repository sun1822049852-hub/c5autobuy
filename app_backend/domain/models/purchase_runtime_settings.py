from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PurchaseRuntimeSettings:
    whitelist_account_ids: list[str] = field(default_factory=list)
    updated_at: str | None = None
