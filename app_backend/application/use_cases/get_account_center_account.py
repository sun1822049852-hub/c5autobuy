from __future__ import annotations


class GetAccountCenterAccountUseCase:
    def __init__(self, runtime_service, snapshot_service) -> None:
        self._runtime_service = runtime_service
        self._snapshot_service = snapshot_service

    def execute(self, account_id: str) -> dict[str, object] | None:
        if self._runtime_service is not None:
            return self._runtime_service.get_account_center_account(account_id)
        return self._snapshot_service.get_account_center_account(account_id)
