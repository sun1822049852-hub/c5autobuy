from datetime import datetime


def test_same_day_window_returns_wait_until_start():
    from app_backend.infrastructure.query.runtime.window_scheduler import WindowScheduler

    scheduler = WindowScheduler(
        window_enabled=True,
        start_hour=9,
        start_minute=0,
        end_hour=18,
        end_minute=0,
    )

    state = scheduler.compute(now=datetime(2026, 3, 16, 8, 30, 0))

    assert state.in_window is False
    assert state.next_window_start == datetime(2026, 3, 16, 9, 0, 0)
    assert state.next_window_end == datetime(2026, 3, 16, 18, 0, 0)


def test_cross_day_window_reports_in_window():
    from app_backend.infrastructure.query.runtime.window_scheduler import WindowScheduler

    scheduler = WindowScheduler(
        window_enabled=True,
        start_hour=22,
        start_minute=0,
        end_hour=2,
        end_minute=0,
    )

    state = scheduler.compute(now=datetime(2026, 3, 16, 23, 30, 0))

    assert state.in_window is True
    assert state.next_window_start == datetime(2026, 3, 16, 22, 0, 0)
    assert state.next_window_end == datetime(2026, 3, 17, 2, 0, 0)


def test_same_start_and_end_means_full_day_window():
    from app_backend.infrastructure.query.runtime.window_scheduler import WindowScheduler

    scheduler = WindowScheduler(
        window_enabled=True,
        start_hour=0,
        start_minute=0,
        end_hour=0,
        end_minute=0,
    )

    state = scheduler.compute(now=datetime(2026, 3, 16, 12, 0, 0))

    assert state.in_window is True
    assert state.next_window_start == datetime(2026, 3, 16, 12, 0, 0)
    assert state.next_window_end == datetime(2026, 3, 17, 12, 0, 0)
