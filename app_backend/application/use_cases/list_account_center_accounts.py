from __future__ import annotations


class ListAccountCenterAccountsUseCase:
    def __init__(self, runtime_service) -> None:
        self._runtime_service = runtime_service

    def execute(self) -> list[dict[str, object]]:
        return self._runtime_service.list_account_center_accounts()
