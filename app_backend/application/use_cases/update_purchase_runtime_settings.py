from __future__ import annotations


class UpdatePurchaseRuntimeSettingsUseCase:
    def __init__(self, runtime_service) -> None:
        self._runtime_service = runtime_service

    def execute(self, *, query_only: bool, whitelist_account_ids: list[str]) -> dict[str, object]:
        return self._runtime_service.update_settings(
            query_only=query_only,
            whitelist_account_ids=whitelist_account_ids,
        )
