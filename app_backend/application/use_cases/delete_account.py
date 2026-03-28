from __future__ import annotations


class DeleteAccountUseCase:
    def __init__(self, repository, bundle_repository=None, account_update_hub=None) -> None:
        self._repository = repository
        self._bundle_repository = bundle_repository
        self._account_update_hub = account_update_hub

    def execute(self, account_id: str) -> bool:
        get_account = getattr(self._repository, "get_account", None)
        account = get_account(account_id) if callable(get_account) else None
        if account is None:
            return False
        if self._bundle_repository is not None:
            self._bundle_repository.delete_account_bundles(account_id)
        self._repository.delete_account(account_id)
        publish = getattr(self._account_update_hub, "publish", None)
        if callable(publish):
            publish(account_id=account_id, event="delete_account", payload={})
        return True
