from __future__ import annotations

from app_backend.domain.enums.query_modes import QueryMode


def normalize_mode_allocations(mode_allocations: dict[str, int] | None) -> dict[str, int]:
    normalized = {mode_type: 0 for mode_type in QueryMode.ALL}
    if not mode_allocations:
        return normalized

    for mode_type, value in mode_allocations.items():
        if mode_type not in normalized:
            continue
        allocation = int(value)
        if allocation < 0:
            raise ValueError("模式分配数必须大于等于 0")
        normalized[mode_type] = allocation
    return normalized


def validate_max_price(max_price: float | None) -> None:
    if max_price is None:
        return
    if float(max_price) < 0:
        raise ValueError("最高价格必须大于等于 0")
