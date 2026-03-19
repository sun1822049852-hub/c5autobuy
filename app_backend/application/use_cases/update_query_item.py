from __future__ import annotations

from app_backend.application.services.query_item_settings_service import normalize_mode_allocations, validate_max_price
from app_backend.application.services.query_item_threshold_service import (
    ensure_final_detail_wear_range,
    validate_detail_max_wear,
    validate_detail_min_wear,
)


class UpdateQueryItemUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        query_item_id: str,
        detail_min_wear: float | None,
        detail_max_wear: float | None,
        max_price: float | None,
        manual_paused: bool | None = None,
        mode_allocations: dict[str, int] | None = None,
    ):
        existing_item = self._repository.get_item(query_item_id)
        if existing_item is None:
            raise KeyError(query_item_id)
        next_detail_min_wear = (
            existing_item.detail_min_wear
            if existing_item.detail_min_wear is not None
            else existing_item.min_wear
        )
        if detail_min_wear is not None:
            next_detail_min_wear = detail_min_wear
        next_detail_max_wear = (
            existing_item.detail_max_wear
            if existing_item.detail_max_wear is not None
            else existing_item.max_wear
        )
        if detail_max_wear is not None:
            next_detail_max_wear = detail_max_wear
        next_max_price = existing_item.max_price if max_price is None else max_price
        ensure_final_detail_wear_range(
            detail_min_wear=next_detail_min_wear,
            detail_max_wear=next_detail_max_wear,
        )
        validate_detail_min_wear(
            detail_min_wear=next_detail_min_wear,
            min_wear=existing_item.min_wear,
            max_wear=existing_item.max_wear,
        )
        validate_detail_max_wear(
            detail_max_wear=next_detail_max_wear,
            detail_min_wear=next_detail_min_wear,
            min_wear=existing_item.min_wear,
            max_wear=existing_item.max_wear,
        )
        validate_max_price(next_max_price)
        next_manual_paused = existing_item.manual_paused if manual_paused is None else bool(manual_paused)
        current_allocations = {
            allocation.mode_type: allocation.target_dedicated_count
            for allocation in existing_item.mode_allocations
        }
        next_mode_allocations = current_allocations if mode_allocations is None else normalize_mode_allocations(mode_allocations)
        return self._repository.update_item(
            query_item_id,
            detail_min_wear=next_detail_min_wear,
            detail_max_wear=next_detail_max_wear,
            max_price=next_max_price,
            manual_paused=next_manual_paused,
            mode_allocations=next_mode_allocations,
        )
