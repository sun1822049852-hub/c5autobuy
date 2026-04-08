from __future__ import annotations


class UpdatePurchaseRuntimeSettingsUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, *, per_batch_ip_fanout_limit: int, max_inflight_per_account: int):
        limit = int(per_batch_ip_fanout_limit)
        inflight = int(max_inflight_per_account)
        if limit < 1:
            raise ValueError("per_batch_ip_fanout_limit 必须大于等于 1")
        if inflight < 1:
            raise ValueError("max_inflight_per_account 必须大于等于 1")
        return self._repository.save_purchase_settings(
            {
                "per_batch_ip_fanout_limit": limit,
                "max_inflight_per_account": inflight,
            }
        )
