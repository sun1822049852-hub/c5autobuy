from __future__ import annotations


class RefreshPurchaseRuntimeInventoryDetailUseCase:
    def __init__(self, runtime_service) -> None:
        self._runtime_service = runtime_service

    def execute(self, *, account_id: str) -> dict[str, object] | None:
        return self._runtime_service.refresh_account_inventory_detail(account_id)
