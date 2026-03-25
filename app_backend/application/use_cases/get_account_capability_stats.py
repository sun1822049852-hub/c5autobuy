from __future__ import annotations


class GetAccountCapabilityStatsUseCase:
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
        rows = self._repository.list_account_capability_stats(
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
            "items": self._build_rows(rows),
        }

    @classmethod
    def _build_rows(cls, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        rows_by_account: dict[str, dict[str, object]] = {}
        for raw_row in rows:
            if not isinstance(raw_row, dict):
                continue
            account_id = str(raw_row.get("account_id") or "").strip()
            if not account_id:
                continue
            row = rows_by_account.setdefault(
                account_id,
                {
                    "account_id": account_id,
                    "account_display_name": raw_row.get("account_display_name"),
                    "new_api": cls._empty_cell(),
                    "fast_api": cls._empty_cell(),
                    "browser": cls._empty_cell(),
                    "create_order": cls._empty_cell(),
                    "submit_order": cls._empty_cell(),
                },
            )
            if row.get("account_display_name") is None and raw_row.get("account_display_name") is not None:
                row["account_display_name"] = raw_row.get("account_display_name")
            field_name = cls._resolve_field_name(
                mode_type=str(raw_row.get("mode_type") or ""),
                phase=str(raw_row.get("phase") or ""),
            )
            if field_name is None:
                continue
            row[field_name] = cls._build_cell(raw_row)
        return [rows_by_account[account_id] for account_id in sorted(rows_by_account)]

    @staticmethod
    def _resolve_field_name(*, mode_type: str, phase: str) -> str | None:
        if phase == "query":
            if mode_type == "new_api":
                return "new_api"
            if mode_type == "fast_api":
                return "fast_api"
            if mode_type == "token":
                return "browser"
            return None
        if phase == "create_order":
            return "create_order"
        if phase == "submit_order":
            return "submit_order"
        return None

    @staticmethod
    def _build_cell(row: dict[str, object]) -> dict[str, object]:
        sample_count = int(row.get("sample_count", 0) or 0)
        total_latency_ms = float(row.get("total_latency_ms", 0.0) or 0.0)
        avg_latency_ms = round(total_latency_ms / sample_count, 3) if sample_count > 0 else None
        display_text = "--" if avg_latency_ms is None else f"{round(avg_latency_ms)}ms · {sample_count}次"
        return {
            "avg_latency_ms": avg_latency_ms,
            "sample_count": sample_count,
            "success_count": int(row.get("success_count", 0) or 0),
            "failure_count": int(row.get("failure_count", 0) or 0),
            "last_error": row.get("last_error"),
            "display_text": display_text,
        }

    @staticmethod
    def _empty_cell() -> dict[str, object]:
        return {
            "avg_latency_ms": None,
            "sample_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_error": None,
            "display_text": "--",
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
