from __future__ import annotations


class ClearPurchaseCapabilityUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, account_id: str):
        return self._repository.clear_purchase_capability(account_id)
