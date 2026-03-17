from __future__ import annotations


class DeleteAccountUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, account_id: str) -> None:
        self._repository.delete_account(account_id)
