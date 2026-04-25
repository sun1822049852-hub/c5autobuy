from __future__ import annotations


class ListAccountCenterAccountsUseCase:
    def __init__(self, runtime_service, snapshot_service) -> None:
        self._runtime_service = runtime_service
        self._snapshot_service = snapshot_service

    def execute(self, *, trace=None) -> list[dict[str, object]]:
        if self._runtime_service is not None:
            if trace is not None:
                trace.set_detail("source", "runtime")
                return self._runtime_service.list_account_center_accounts(trace=trace)
            return self._runtime_service.list_account_center_accounts()
        if trace is not None:
            trace.set_detail("source", "snapshot")
            return self._snapshot_service.list_account_center_accounts(trace=trace)
        return self._snapshot_service.list_account_center_accounts()
