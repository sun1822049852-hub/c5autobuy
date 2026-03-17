from __future__ import annotations

from typing import Protocol

from .runtime_events import PurchaseExecutionResult, PurchaseHitBatch


class PurchaseExecutionGateway(Protocol):
    async def execute(
        self,
        *,
        account,
        batch: PurchaseHitBatch,
        selected_steam_id: str,
    ) -> PurchaseExecutionResult: ...
