from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app_backend.domain.models.query_runtime import WindowState


@dataclass(slots=True)
class WindowScheduler:
    window_enabled: bool
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int

    def compute(self, *, now: datetime) -> WindowState:
        if not self.window_enabled:
            return WindowState(
                in_window=True,
                next_window_start=now,
                next_window_end=now + timedelta(days=1),
            )

        start_minutes = self.start_hour * 60 + self.start_minute
        end_minutes = self.end_hour * 60 + self.end_minute

        if start_minutes == end_minutes:
            return WindowState(
                in_window=True,
                next_window_start=now,
                next_window_end=now + timedelta(days=1),
            )

        today_start = now.replace(
            hour=self.start_hour,
            minute=self.start_minute,
            second=0,
            microsecond=0,
        )
        today_end = now.replace(
            hour=self.end_hour,
            minute=self.end_minute,
            second=0,
            microsecond=0,
        )

        if end_minutes > start_minutes:
            if today_start <= now < today_end:
                return WindowState(
                    in_window=True,
                    next_window_start=today_start,
                    next_window_end=today_end,
                )
            if now < today_start:
                return WindowState(
                    in_window=False,
                    next_window_start=today_start,
                    next_window_end=today_end,
                )
            next_start = today_start + timedelta(days=1)
            next_end = today_end + timedelta(days=1)
            return WindowState(
                in_window=False,
                next_window_start=next_start,
                next_window_end=next_end,
            )

        next_day_end = today_end + timedelta(days=1)
        yesterday_start = today_start - timedelta(days=1)

        if now >= today_start:
            return WindowState(
                in_window=True,
                next_window_start=today_start,
                next_window_end=next_day_end,
            )
        if now < today_end:
            return WindowState(
                in_window=True,
                next_window_start=yesterday_start,
                next_window_end=today_end,
            )
        return WindowState(
            in_window=False,
            next_window_start=today_start,
            next_window_end=next_day_end,
        )
