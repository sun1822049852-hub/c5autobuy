from __future__ import annotations


class GetQueryConfigUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, config_id: str):
        return self._repository.get_config(config_id)
