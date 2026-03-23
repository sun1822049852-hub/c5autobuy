from __future__ import annotations

from app_backend.domain.models.runtime_settings import normalize_query_settings_json


class UpdateQueryRuntimeSettingsUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, *, query_settings: dict[str, object]):
        return self._repository.save_query_settings(normalize_query_settings_json(query_settings))
