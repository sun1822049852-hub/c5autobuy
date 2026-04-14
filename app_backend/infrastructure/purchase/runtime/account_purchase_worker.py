from __future__ import annotations

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

from .inventory_state import InventoryState
from .runtime_events import PurchaseWorkerOutcome


class AccountPurchaseWorker:
    def __init__(
        self,
        *,
        account,
        inventory_state: InventoryState,
        execution_gateway,
        runtime_account: RuntimeAccountAdapter | None = None,
        should_process_generation=None,
        on_gateway_execute_start=None,
    ) -> None:
        self._account = account
        self._inventory_state = inventory_state
        self._execution_gateway = execution_gateway
        self._runtime_account = runtime_account or RuntimeAccountAdapter(account)
        self._should_process_generation = should_process_generation
        self._on_gateway_execute_start = on_gateway_execute_start

    async def process(
        self,
        batch,
        *,
        generation: int | None = None,
        on_gateway_execute_start=None,
    ) -> PurchaseWorkerOutcome:
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

        should_process_generation = self._should_process_generation
        if callable(should_process_generation) and generation is not None:
            if not should_process_generation(int(generation)):
                return PurchaseWorkerOutcome(
                    status="stale_generation",
                    purchased_count=0,
                    submitted_count=submitted_count,
                    selected_steam_id=selected_steam_id,
                    pool_state=getattr(self._account, "purchase_pool_state", PurchasePoolState.NOT_CONNECTED),
                    capability_state=getattr(
                        self._account,
                        "purchase_capability_state",
                        PurchaseCapabilityState.UNBOUND,
                    ),
                    requires_remote_refresh=False,
                    error=None,
                )

        result = await self._execution_gateway.execute(
            account=self._runtime_account,
            batch=batch,
            selected_steam_id=selected_steam_id,
            on_execute_started=on_gateway_execute_start or self._on_gateway_execute_start,
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
                request_body=getattr(result, "request_body", None),
                response_text=getattr(result, "response_text", None),
            )

        if result.status == "success":
            return PurchaseWorkerOutcome(
                status="success",
                purchased_count=result.purchased_count,
                submitted_count=submitted_count,
                selected_steam_id=selected_steam_id,
                pool_state=getattr(self._account, "purchase_pool_state", PurchasePoolState.ACTIVE),
                capability_state=getattr(self._account, "purchase_capability_state", PurchaseCapabilityState.BOUND),
                requires_remote_refresh=False,
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
            request_body=getattr(result, "request_body", None),
            response_text=getattr(result, "response_text", None),
        )

    @staticmethod
    def _resolve_submitted_count(batch, *, result=None) -> int:
        resolved = int(getattr(result, "submitted_count", 0) or 0)
        if resolved > 0:
            return resolved
        return len(list(getattr(batch, "product_list", []) or []))

    async def cleanup(self) -> None:
        await self._runtime_account.close_global_session()
