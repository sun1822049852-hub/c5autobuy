from __future__ import annotations


def validate_detail_min_wear(
    *,
    detail_min_wear: float | None,
    min_wear: float | None,
    max_wear: float | None,
) -> None:
    if detail_min_wear is None:
        return

    if not 0.0 <= detail_min_wear <= 1.0:
        raise ValueError("最小磨损必须在 0 到 1 之间")

    if min_wear is None or max_wear is None:
        return

    if not (min_wear <= detail_min_wear <= max_wear):
        raise ValueError(
            f"最小磨损值必须在范围 [{_format_wear_value(min_wear)}, {_format_wear_value(max_wear)}] 内"
        )


def validate_detail_max_wear(
    *,
    detail_max_wear: float | None,
    detail_min_wear: float | None,
    min_wear: float | None,
    max_wear: float | None,
) -> None:
    if detail_max_wear is None:
        return

    if not 0.0 <= detail_max_wear <= 1.0:
        raise ValueError("最大磨损必须在 0 到 1 之间")

    lower_bound = detail_min_wear if detail_min_wear is not None else min_wear
    if lower_bound is None or max_wear is None:
        return

    if not (lower_bound <= detail_max_wear <= max_wear):
        raise ValueError(
            f"最大磨损值必须在范围 [{_format_wear_value(lower_bound)}, {_format_wear_value(max_wear)}] 内"
        )


def _format_wear_value(value: float) -> str:
    return f"{value:g}"
