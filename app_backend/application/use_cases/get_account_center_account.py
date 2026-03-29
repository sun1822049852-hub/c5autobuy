from __future__ import annotations


class GetAccountCenterAccountUseCase:
    def __init__(self, runtime_service) -> None:
        self._runtime_service = runtime_service

    def execute(self, account_id: str) -> dict[str, object] | None:
        return self._runtime_service.get_account_center_account(account_id)
