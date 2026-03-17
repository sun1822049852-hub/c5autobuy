from __future__ import annotations


class ListQueryConfigsUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self):
        return self._repository.list_configs()
