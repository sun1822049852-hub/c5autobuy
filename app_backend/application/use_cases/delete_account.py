from __future__ import annotations


class DeleteAccountUseCase:
    def __init__(self, repository, bundle_repository=None) -> None:
        self._repository = repository
        self._bundle_repository = bundle_repository

    def execute(self, account_id: str) -> None:
        if self._bundle_repository is not None:
            self._bundle_repository.delete_account_bundles(account_id)
        self._repository.delete_account(account_id)
