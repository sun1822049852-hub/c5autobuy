from __future__ import annotations


class UpdateAccountPurchaseConfigUseCase:
    def __init__(self, runtime_service) -> None:
        self._runtime_service = runtime_service

    def execute(
        self,
        *,
        account_id: str,
        disabled: bool,
        selected_steam_id: str | None,
    ) -> dict[str, object]:
        return self._runtime_service.update_account_purchase_config(
            account_id=account_id,
            disabled=disabled,
            selected_steam_id=selected_steam_id,
        )
