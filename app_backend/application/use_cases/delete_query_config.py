from __future__ import annotations


class DeleteQueryConfigUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, config_id: str) -> None:
        self._repository.delete_config(config_id)
