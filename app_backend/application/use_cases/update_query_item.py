from __future__ import annotations

from app_backend.application.services.query_item_threshold_service import validate_max_wear


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
        existing_item = self._repository.get_item(query_item_id)
        if existing_item is None:
            raise KeyError(query_item_id)
        validate_max_wear(
            max_wear=max_wear,
            min_wear=existing_item.min_wear,
            detail_max_wear=existing_item.detail_max_wear,
        )
        return self._repository.update_item(
            query_item_id,
            max_wear=max_wear,
            max_price=max_price,
        )
