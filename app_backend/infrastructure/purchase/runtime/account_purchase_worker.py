from __future__ import annotations

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState

from .inventory_state import InventoryState
from .runtime_events import PurchaseWorkerOutcome


class AccountPurchaseWorker:
    def __init__(
        self,
        *,
        account,
        inventory_state: InventoryState,
        execution_gateway,
    ) -> None:
        self._account = account
        self._inventory_state = inventory_state
        self._execution_gateway = execution_gateway

    async def process(self, batch) -> PurchaseWorkerOutcome:
        selected_steam_id = self._inventory_state.selected_steam_id
        if not selected_steam_id:
            return PurchaseWorkerOutcome(
                status="no_inventory",
                purchased_count=0,
                selected_steam_id=None,
                pool_state=PurchasePoolState.PAUSED_NO_INVENTORY,
                capability_state=getattr(self._account, "purchase_capability_state", PurchaseCapabilityState.UNBOUND),
                requires_remote_refresh=True,
                error="No selected inventory",
            )

        result = await self._execution_gateway.execute(
            account=self._account,
            batch=batch,
            selected_steam_id=selected_steam_id,
        )

        if result.status == "auth_invalid":
            return PurchaseWorkerOutcome(
                status="auth_invalid",
                purchased_count=0,
                selected_steam_id=selected_steam_id,
                pool_state=PurchasePoolState.PAUSED_AUTH_INVALID,
                capability_state=PurchaseCapabilityState.EXPIRED,
                requires_remote_refresh=False,
                error=result.error,
            )

        if result.status == "success":
            transition = self._inventory_state.apply_purchase_success(purchased_count=result.purchased_count)
            return PurchaseWorkerOutcome(
                status="success",
                purchased_count=result.purchased_count,
                selected_steam_id=self._inventory_state.selected_steam_id,
                pool_state=(
                    PurchasePoolState.PAUSED_NO_INVENTORY
                    if transition.became_unavailable
                    else PurchasePoolState.ACTIVE
                ),
                capability_state=getattr(self._account, "purchase_capability_state", PurchaseCapabilityState.BOUND),
                requires_remote_refresh=transition.requires_remote_refresh,
                error=None,
            )

        return PurchaseWorkerOutcome(
            status=result.status,
            purchased_count=int(result.purchased_count),
            selected_steam_id=selected_steam_id,
            pool_state=getattr(self._account, "purchase_pool_state", PurchasePoolState.NOT_CONNECTED),
            capability_state=getattr(self._account, "purchase_capability_state", PurchaseCapabilityState.UNBOUND),
            requires_remote_refresh=False,
            error=result.error,
        )
