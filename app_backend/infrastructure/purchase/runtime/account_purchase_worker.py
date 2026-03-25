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
        submitted_count = self._resolve_submitted_count(batch)
        selected_steam_id = self._inventory_state.selected_steam_id
        if not selected_steam_id:
            return PurchaseWorkerOutcome(
                status="no_inventory",
                purchased_count=0,
                submitted_count=submitted_count,
                selected_steam_id=None,
                pool_state=PurchasePoolState.PAUSED_NO_INVENTORY,
                capability_state=getattr(self._account, "purchase_capability_state", PurchaseCapabilityState.UNBOUND),
                requires_remote_refresh=True,
                create_order_latency_ms=None,
                submit_order_latency_ms=None,
                error="No selected inventory",
            )

        result = await self._execution_gateway.execute(
            account=self._account,
            batch=batch,
            selected_steam_id=selected_steam_id,
        )
        submitted_count = self._resolve_submitted_count(batch, result=result)

        if result.status == "auth_invalid":
            return PurchaseWorkerOutcome(
                status="auth_invalid",
                purchased_count=0,
                submitted_count=submitted_count,
                selected_steam_id=selected_steam_id,
                pool_state=PurchasePoolState.PAUSED_AUTH_INVALID,
                capability_state=PurchaseCapabilityState.EXPIRED,
                requires_remote_refresh=False,
                create_order_latency_ms=getattr(result, "create_order_latency_ms", None),
                submit_order_latency_ms=getattr(result, "submit_order_latency_ms", None),
                error=result.error,
                status_code=getattr(result, "status_code", None),
                request_method=getattr(result, "request_method", None),
                request_path=getattr(result, "request_path", None),
                response_text=getattr(result, "response_text", None),
            )

        if result.status == "success":
            transition = self._inventory_state.apply_purchase_success(purchased_count=result.purchased_count)
            return PurchaseWorkerOutcome(
                status="success",
                purchased_count=result.purchased_count,
                submitted_count=submitted_count,
                selected_steam_id=self._inventory_state.selected_steam_id,
                pool_state=(
                    PurchasePoolState.PAUSED_NO_INVENTORY
                    if transition.became_unavailable
                    else PurchasePoolState.ACTIVE
                ),
                capability_state=getattr(self._account, "purchase_capability_state", PurchaseCapabilityState.BOUND),
                requires_remote_refresh=transition.requires_remote_refresh,
                create_order_latency_ms=getattr(result, "create_order_latency_ms", None),
                submit_order_latency_ms=getattr(result, "submit_order_latency_ms", None),
                error=None,
            )

        return PurchaseWorkerOutcome(
            status=result.status,
            purchased_count=int(result.purchased_count),
            submitted_count=submitted_count,
            selected_steam_id=selected_steam_id,
            pool_state=getattr(self._account, "purchase_pool_state", PurchasePoolState.NOT_CONNECTED),
            capability_state=getattr(self._account, "purchase_capability_state", PurchaseCapabilityState.UNBOUND),
            requires_remote_refresh=False,
            create_order_latency_ms=getattr(result, "create_order_latency_ms", None),
            submit_order_latency_ms=getattr(result, "submit_order_latency_ms", None),
            error=result.error,
            status_code=getattr(result, "status_code", None),
            request_method=getattr(result, "request_method", None),
            request_path=getattr(result, "request_path", None),
            response_text=getattr(result, "response_text", None),
        )

    @staticmethod
    def _resolve_submitted_count(batch, *, result=None) -> int:
        resolved = int(getattr(result, "submitted_count", 0) or 0)
        if resolved > 0:
            return resolved
        return len(list(getattr(batch, "product_list", []) or []))
