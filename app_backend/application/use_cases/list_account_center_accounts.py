from __future__ import annotations


class ListAccountCenterAccountsUseCase:
    def __init__(self, runtime_service, snapshot_service) -> None:
        self._runtime_service = runtime_service
        self._snapshot_service = snapshot_service

    def execute(self) -> list[dict[str, object]]:
        if self._runtime_service is not None:
            return self._runtime_service.list_account_center_accounts()
        return self._snapshot_service.list_account_center_accounts()
