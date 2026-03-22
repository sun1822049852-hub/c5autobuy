from __future__ import annotations


class GetQueryItemStatsUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        range_mode: str,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, object]:
        self._validate_range_params(
            range_mode=range_mode,
            date=date,
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "range_mode": range_mode,
            "date": date,
            "start_date": start_date,
            "end_date": end_date,
            "items": self._repository.list_query_item_stats(
                range_mode=range_mode,
                date=date,
                start_date=start_date,
                end_date=end_date,
            ),
        }

    @staticmethod
    def _validate_range_params(
        *,
        range_mode: str,
        date: str | None,
        start_date: str | None,
        end_date: str | None,
    ) -> None:
        if range_mode == "total":
            return
        if range_mode == "day":
            if not date:
                raise ValueError("range_mode=day requires date")
            return
        if range_mode == "range":
            if not start_date or not end_date:
                raise ValueError("range_mode=range requires start_date and end_date")
            return
        raise ValueError("range_mode must be one of: total, day, range")
