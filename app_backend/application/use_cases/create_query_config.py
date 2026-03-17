from __future__ import annotations


class CreateQueryConfigUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, *, name: str, description: str | None):
        return self._repository.create_config(name=name, description=description)
