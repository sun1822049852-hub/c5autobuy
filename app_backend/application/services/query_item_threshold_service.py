from __future__ import annotations


def validate_max_wear(
    *,
    max_wear: float | None,
    min_wear: float | None,
    detail_max_wear: float | None,
) -> None:
    if max_wear is None:
        return

    if not 0.0 <= max_wear <= 1.0:
        raise ValueError("最大磨损必须在 0 到 1 之间")

    if min_wear is None or detail_max_wear is None:
        return

    if not (min_wear < max_wear <= detail_max_wear):
        raise ValueError(
            f"最大磨损值必须在范围 ({_format_wear_value(min_wear)}, {_format_wear_value(detail_max_wear)}] 内"
        )


def _format_wear_value(value: float) -> str:
    return f"{value:g}"
