from __future__ import annotations


class DeleteQueryItemUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, *, query_item_id: str) -> None:
        self._repository.delete_item(query_item_id)
