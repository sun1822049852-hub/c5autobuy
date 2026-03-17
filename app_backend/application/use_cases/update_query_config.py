from __future__ import annotations


class UpdateQueryConfigUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, *, config_id: str, name: str, description: str | None):
        return self._repository.update_config(
            config_id,
            name=name,
            description=description,
        )
