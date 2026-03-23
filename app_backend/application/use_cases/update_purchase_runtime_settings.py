from __future__ import annotations

from app_backend.domain.models.runtime_settings import normalize_purchase_settings_json


class UpdatePurchaseRuntimeSettingsUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, *, purchase_settings: dict[str, object]):
        return self._repository.save_purchase_settings(normalize_purchase_settings_json(purchase_settings))
