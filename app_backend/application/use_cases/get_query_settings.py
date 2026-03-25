from __future__ import annotations


class GetQuerySettingsUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self):
        return self._repository.get_settings()
