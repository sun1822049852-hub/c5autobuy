from __future__ import annotations


class UpdateQueryItemUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        query_item_id: str,
        max_wear: float | None,
        max_price: float | None,
    ):
        return self._repository.update_item(
            query_item_id,
            max_wear=max_wear,
            max_price=max_price,
        )
