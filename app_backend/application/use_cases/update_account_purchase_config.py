from __future__ import annotations


class UpdateAccountPurchaseConfigUseCase:
    def __init__(self, runtime_service) -> None:
        self._runtime_service = runtime_service

    def execute(
        self,
        *,
        account_id: str,
        purchase_disabled: bool,
        selected_steam_id: str | None,
    ) -> dict[str, object]:
        return self._runtime_service.update_account_purchase_config(
            account_id=account_id,
            purchase_disabled=purchase_disabled,
            selected_steam_id=selected_steam_id,
        )
