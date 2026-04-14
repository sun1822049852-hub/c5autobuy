from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

from app_backend.domain.models.query_config import QueryItem, QueryModeSetting


def build_mode(
    mode_type: str,
    *,
    enabled: bool = True,
    window_enabled: bool = False,
    start_hour: int = 0,
    start_minute: int = 0,
    end_hour: int = 0,
    end_minute: int = 0,
    item_min_cooldown_seconds: float = 0.5,
    item_min_cooldown_strategy: str = "divide_by_assigned_count",
) -> QueryModeSetting:
    return QueryModeSetting(
        mode_setting_id=f"{mode_type}-1",
        config_id="cfg-1",
        mode_type=mode_type,
        enabled=enabled,
        window_enabled=window_enabled,
        start_hour=start_hour,
        start_minute=start_minute,
        end_hour=end_hour,
        end_minute=end_minute,
        base_cooldown_min=1.0,
        base_cooldown_max=1.0,
        random_delay_enabled=False,
        random_delay_min=0.0,
        random_delay_max=0.0,
        item_min_cooldown_seconds=item_min_cooldown_seconds,
        item_min_cooldown_strategy=item_min_cooldown_strategy,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
    )


def build_item(item_id: str) -> QueryItem:
    return QueryItem(
        query_item_id=item_id,
        config_id="cfg-1",
        product_url=f"https://www.c5game.com/csgo/730/asset/{item_id}",
        external_item_id=item_id,
        item_name=f"商品-{item_id}",
        market_hash_name=f"Test Item {item_id}",
        min_wear=0.0,
        max_wear=0.25,
        max_price=100.0,
        last_market_price=90.0,
        last_detail_sync_at=None,
        sort_order=0,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
    )


def build_account(
    account_id: str,
    *,
    api_key: str | None = None,
    cookie_raw: str | None = None,
    new_api_enabled: bool = True,
    fast_api_enabled: bool = True,
    token_enabled: bool = True,
    disabled: bool = False,
    purchase_disabled: bool = False,
) -> object:
    return SimpleNamespace(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        display_name=f"账号-{account_id}",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=api_key,
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw=cookie_raw,
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        disabled=disabled,
        purchase_disabled=purchase_disabled,
        new_api_enabled=new_api_enabled,
        fast_api_enabled=fast_api_enabled,
        token_enabled=token_enabled,
    )


def test_mode_runner_uses_its_own_window_setting():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner

    runner = ModeRunner(
        build_mode(
            "new_api",
            window_enabled=True,
            start_hour=9,
            start_minute=30,
            end_hour=10,
            end_minute=0,
        ),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        now_provider=lambda: datetime(2026, 3, 16, 8, 0, 0),
    )

    snapshot = runner.snapshot()

    assert snapshot["enabled"] is True
    assert snapshot["in_window"] is False
    assert snapshot["next_window_start"] == "2026-03-16T09:30:00"
    assert snapshot["next_window_end"] == "2026-03-16T10:00:00"


def test_mode_runner_filters_accounts_by_preference_and_capability():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner

    runner = ModeRunner(
        build_mode("fast_api"),
        [
            build_account("a1", api_key="api-1"),
            build_account("a2", api_key="api-2", fast_api_enabled=False),
            build_account("a3"),
            build_account("a4", api_key="api-4", disabled=True),
        ],
        query_items=[build_item("1380979899390261111")],
    )

    snapshot = runner.snapshot()

    assert snapshot["eligible_account_count"] == 2
    assert snapshot["active_account_count"] == 0


def test_mode_runner_excludes_token_account_marked_not_login():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner

    blocked_account = build_account("a1", cookie_raw="NC5_accessToken=t; NC5_deviceId=d")
    blocked_account.last_error = "Not login"

    runner = ModeRunner(
        build_mode("token"),
        [blocked_account],
        query_items=[build_item("1380979899390261111")],
    )

    snapshot = runner.snapshot()

    assert snapshot["eligible_account_count"] == 0
    assert snapshot["active_account_count"] == 0


def test_mode_runner_ignores_removed_disabled_flag_and_keeps_purchase_disabled_account_query_eligible():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner

    runner = ModeRunner(
        build_mode("new_api"),
        [
            build_account("a1", api_key="api-1", purchase_disabled=True),
            build_account("a2", api_key="api-2", disabled=True),
        ],
        query_items=[build_item("1380979899390261111")],
    )

    snapshot = runner.snapshot()

    assert snapshot["eligible_account_count"] == 2
    assert snapshot["active_account_count"] == 0


def test_mode_runner_refresh_accounts_marks_existing_worker_inactive_when_account_becomes_ineligible():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner

    refresh_calls: list[tuple[str, bool]] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account
            self.active = True

        def refresh_account(self, account: Account, *, eligible: bool | None = None) -> None:
            self.account = account
            self.active = bool(eligible)
            refresh_calls.append((self.account.account_id, bool(eligible)))

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": self.active,
                "eligible": self.active,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    runner.refresh_accounts([build_account("a1", api_key="api-1", new_api_enabled=False, fast_api_enabled=False)])
    snapshot = runner.snapshot()

    assert refresh_calls == [("a1", False)]
    assert snapshot["eligible_account_count"] == 0
    assert snapshot["active_account_count"] == 0


def test_mode_runner_refresh_accounts_creates_worker_for_newly_eligible_account():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner

    created_workers: list[str] = []
    refresh_calls: list[tuple[str, bool]] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account
            self.active = True
            created_workers.append(self.account.account_id)

        def refresh_account(self, account: Account, *, eligible: bool | None = None) -> None:
            self.account = account
            self.active = bool(eligible)
            refresh_calls.append((self.account.account_id, bool(eligible)))

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": self.active,
                "eligible": self.active,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    runner.refresh_accounts(
        [
            build_account("a1", api_key="api-1"),
            build_account("a2", api_key="api-2"),
        ]
    )
    snapshot = runner.snapshot()

    assert created_workers == ["a1", "a2"]
    assert refresh_calls == [("a1", True)]
    assert {row["account_id"] for row in snapshot["group_rows"]} == {"a1", "a2"}


async def test_mode_runner_dispatches_one_item_per_active_worker():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    calls: list[tuple[str, str]] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            calls.append((self.account.account_id, query_item.query_item_id))
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                message="查询完成",
                match_count=1,
                latency_ms=12.0,
                error=None,
            )

    accounts = [
        build_account("a1", api_key="api-1"),
        build_account("a2", api_key="api-2"),
    ]
    items = [
        build_item("1380979899390261111"),
        build_item("1380979899390262222"),
    ]
    runner = ModeRunner(
        build_mode("new_api"),
        accounts,
        query_items=items,
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    await runner.run_once()
    snapshot = runner.snapshot()

    assert calls == [
        ("a1", "1380979899390261111"),
        ("a2", "1380979899390262222"),
    ]
    assert snapshot["active_account_count"] == 2
    assert snapshot["query_count"] == 2
    assert snapshot["found_count"] == 2


async def test_mode_runner_uses_shared_query_item_scheduler():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    expected_now = datetime(2026, 3, 16, 10, 0, 0)
    reserved_at: list[float] = []

    class FakeScheduler:
        def __init__(self) -> None:
            self._items = [
                build_item("1380979899390261111"),
                build_item("1380979899390262222"),
            ]
            self._index = 0

        def reset(self) -> None:
            self._index = 0

        async def reserve_next(self, *, now=None):
            item = self._items[self._index]
            self._index = (self._index + 1) % len(self._items)
            reserved_at.append(now.timestamp() if isinstance(now, datetime) else float(now))
            return type(
                "Reservation",
                (),
                {
                    "query_item": item,
                    "execute_at": now.timestamp() if isinstance(now, datetime) else float(now),
                },
            )()

    calls: list[tuple[str, str]] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            calls.append((self.account.account_id, query_item.query_item_id))
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                message="查询完成",
                match_count=1,
                latency_ms=12.0,
                error=None,
            )

    runner = ModeRunner(
        build_mode("new_api"),
        [
            build_account("a1", api_key="api-1"),
            build_account("a2", api_key="api-2"),
        ],
        query_items=[build_item("unused")],
        query_item_scheduler=FakeScheduler(),
        worker_factory=lambda mode_type, account: FakeWorker(account),
        now_provider=lambda: expected_now,
    )

    runner.start()
    await runner.run_once()

    assert reserved_at == [expected_now.timestamp(), expected_now.timestamp()]
    assert calls == [
        ("a1", "1380979899390261111"),
        ("a2", "1380979899390262222"),
    ]


async def test_mode_runner_keeps_dedicated_item_exclusive_when_no_shared_worker_exists():
    from app_backend.domain.enums.query_modes import QueryMode
    from app_backend.domain.models.query_config import QueryItemModeAllocation
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    calls: list[str] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            calls.append(query_item.query_item_id)
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                message="查询完成",
                match_count=1,
                latency_ms=12.0,
                error=None,
            )

    dedicated_item = build_item("1380979899390261111")
    dedicated_item.mode_allocations = [
        QueryItemModeAllocation(
            mode_type=mode_type,
            target_dedicated_count=(1 if mode_type == QueryMode.NEW_API else 0),
        )
        for mode_type in QueryMode.ALL
    ]
    shared_item = build_item("1380979899390262222")

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[dedicated_item, shared_item],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    await runner.run_once()
    await runner.run_once()

    assert calls == [
        "1380979899390261111",
        "1380979899390261111",
    ]


def test_mode_runner_preserves_dedicated_bindings_on_restart_when_requested():
    from app_backend.domain.enums.query_modes import QueryMode
    from app_backend.domain.models.query_config import QueryItemModeAllocation
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

    dedicated_item = build_item("1380979899390261111")
    dedicated_item.mode_allocations = [
        QueryItemModeAllocation(
            mode_type=mode_type,
            target_dedicated_count=(1 if mode_type == QueryMode.NEW_API else 0),
        )
        for mode_type in QueryMode.ALL
    ]
    shared_item = build_item("1380979899390262222")

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[dedicated_item, shared_item],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    first_snapshot = runner.snapshot()
    runner.stop()
    runner.start(preserve_allocation_state=True)
    second_snapshot = runner.snapshot()

    assert first_snapshot["item_rows"][0]["actual_dedicated_count"] == 1
    assert second_snapshot["item_rows"][0]["actual_dedicated_count"] == 1
    assert second_snapshot["item_rows"][1]["actual_dedicated_count"] == 0


async def test_mode_runner_resets_counts_on_restart_even_within_same_day():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                message="查询完成",
                match_count=1,
                latency_ms=12.0,
                error=None,
            )

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
        now_provider=lambda: datetime(2026, 3, 16, 10, 0, 0),
    )

    runner.start()
    await runner.run_once()

    before_restart = runner.snapshot()
    assert before_restart["query_count"] == 1
    assert before_restart["found_count"] == 1
    assert before_restart["item_rows"][0]["query_count"] == 1

    runner.stop()
    runner.start()
    after_restart = runner.snapshot()

    assert after_restart["query_count"] == 0
    assert after_restart["found_count"] == 0
    assert after_restart["item_rows"][0]["query_count"] == 0


async def test_mode_runner_run_loop_executes_cycle_and_stops_on_signal():
    import asyncio

    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    stop_event = asyncio.Event()
    calls: list[str] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            calls.append(query_item.query_item_id)
            stop_event.set()
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                message="查询完成",
                match_count=1,
                latency_ms=12.0,
                error=None,
            )

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    await runner.run_loop(stop_event)
    snapshot = runner.snapshot()

    assert calls == ["1380979899390261111"]
    assert snapshot["query_count"] == 1
    assert snapshot["found_count"] == 1


async def test_mode_runner_run_loop_starts_account_groups_independently():
    import asyncio

    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    stop_event = asyncio.Event()
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    allow_first_finish = asyncio.Event()

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            if self.account.account_id == "a1":
                first_started.set()
                await allow_first_finish.wait()
            else:
                second_started.set()
                stop_event.set()
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                message="查询完成",
                match_count=1,
                latency_ms=12.0,
                error=None,
            )

    runner = ModeRunner(
        build_mode("new_api"),
        [
            build_account("a1", api_key="api-1"),
            build_account("a2", api_key="api-2"),
        ],
        query_items=[
            build_item("1380979899390261111"),
            build_item("1380979899390262222"),
        ],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    task = asyncio.create_task(runner.run_loop(stop_event))

    await asyncio.wait_for(first_started.wait(), timeout=0.1)
    await asyncio.wait_for(second_started.wait(), timeout=0.1)
    allow_first_finish.set()
    await asyncio.wait_for(task, timeout=0.1)


async def test_mode_runner_run_loop_picks_up_worker_added_after_start():
    import asyncio

    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    stop_event = asyncio.Event()
    calls: list[str] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def refresh_account(self, account: Account, *, eligible: bool | None = None) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            calls.append(self.account.account_id)
            stop_event.set()
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                message="查询完成",
                match_count=1,
                latency_ms=12.0,
                error=None,
            )

    runner = ModeRunner(
        build_mode("new_api"),
        [],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    task = asyncio.create_task(runner.run_loop(stop_event))

    await asyncio.sleep(0.05)
    runner.refresh_accounts([build_account("a1", api_key="api-1")])

    await asyncio.wait_for(stop_event.wait(), timeout=0.3)
    await asyncio.wait_for(task, timeout=0.3)

    assert calls == ["a1"]


async def test_mode_runner_cleanup_closes_all_worker_sessions():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner

    cleanup_calls: list[str] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def cleanup(self) -> None:
            cleanup_calls.append(self.account.account_id)

    runner = ModeRunner(
        build_mode("new_api"),
        [
            build_account("a1", api_key="api-1"),
            build_account("a2", api_key="api-2"),
        ],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    await runner.cleanup()

    assert cleanup_calls == ["a1", "a2"]


async def test_mode_runner_keeps_recent_hit_and_error_events():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account
            self._events = [
                QueryExecutionEvent(
                    timestamp="2026-03-16T10:00:00",
                    level="info",
                    mode_type="new_api",
                    account_id=self.account.account_id,
                    account_display_name="白天主号",
                    query_item_id="1380979899390261111",
                    message="查询完成",
                    match_count=0,
                    query_item_name="商品-1380979899390261111",
                    latency_ms=10.0,
                    error=None,
                ),
                QueryExecutionEvent(
                    timestamp="2026-03-16T10:00:01",
                    level="info",
                    mode_type="new_api",
                    account_id=self.account.account_id,
                    account_display_name="白天主号",
                    query_item_id="1380979899390261111",
                    message="查询完成",
                    match_count=2,
                    product_list=[
                        {"productId": "p-1", "price": 88.5, "actRebateAmount": 0},
                        {"productId": "p-2", "price": 89.5, "actRebateAmount": 0},
                    ],
                    total_price=178.0,
                    total_wear_sum=0.1234,
                    query_item_name="商品-1380979899390261111",
                    latency_ms=11.0,
                    error=None,
                ),
                QueryExecutionEvent(
                    timestamp="2026-03-16T10:00:02",
                    level="error",
                    mode_type="new_api",
                    account_id=self.account.account_id,
                    account_display_name="白天主号",
                    query_item_id="1380979899390261111",
                    message="HTTP 429 Too Many Requests",
                    match_count=0,
                    query_item_name="商品-1380979899390261111",
                    latency_ms=12.0,
                    error="HTTP 429 Too Many Requests",
                ),
            ]

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            return self._events.pop(0)

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()

    await runner.run_once()
    assert runner.snapshot()["recent_events"] == []

    await runner.run_once()
    await runner.run_once()
    snapshot = runner.snapshot()

    assert len(snapshot["recent_events"]) == 2
    assert snapshot["recent_events"][0]["timestamp"] == "2026-03-16T10:00:02"
    assert snapshot["recent_events"][0]["error"] == "HTTP 429 Too Many Requests"
    assert snapshot["recent_events"][0]["account_display_name"] == "白天主号"
    assert snapshot["recent_events"][1]["match_count"] == 2
    assert snapshot["recent_events"][1]["total_price"] == 178.0
    assert snapshot["recent_events"][1]["total_wear_sum"] == 0.1234
    assert snapshot["recent_events"][1]["product_list"][0]["productId"] == "p-1"
    assert snapshot["recent_events"][1]["query_item_name"] == "商品-1380979899390261111"


async def test_mode_runner_limits_recent_events_to_five_hundred_entries():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: None,
    )

    for _ in range(525):
        index = _
        runner._record_event(
            QueryExecutionEvent(
                timestamp=f"2026-03-16T10:00:{index:03d}",
                level="info",
                mode_type="new_api",
                account_id="a1",
                query_item_id="1380979899390261111",
                query_item_name="商品-1380979899390261111",
                message=f"查询完成-{index}",
                match_count=1,
                latency_ms=10.0 + index,
                error=None,
            )
        )

    snapshot = runner.snapshot()

    assert len(snapshot["recent_events"]) == 500
    assert snapshot["recent_events"][0]["message"] == "查询完成-524"
    assert snapshot["recent_events"][-1]["message"] == "查询完成-25"


def test_mode_runner_apply_mode_setting_forwards_item_cooldown_strategy_to_scheduler():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner

    applied = []

    class FakeScheduler:
        def reset(self) -> None:
            return

        def apply_mode_setting(self, mode_setting: QueryModeSetting) -> None:
            applied.append(
                (
                    mode_setting.item_min_cooldown_seconds,
                    mode_setting.item_min_cooldown_strategy,
                )
            )

    runner = ModeRunner(
        build_mode("new_api", item_min_cooldown_seconds=0.5, item_min_cooldown_strategy="divide_by_assigned_count"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        query_item_scheduler=FakeScheduler(),
    )

    runner.apply_mode_setting(
        build_mode("new_api", item_min_cooldown_seconds=0.9, item_min_cooldown_strategy="fixed")
    )

    assert applied == [(0.9, "fixed")]


async def test_mode_runner_adds_rate_limit_increment_into_cycle_cooldown(monkeypatch):
    import asyncio

    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    stop_event = asyncio.Event()
    recorded_timeouts: list[float] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account
            self.rate_limit_increment = 0.0

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "backoff_until": None,
                "rate_limit_increment": self.rate_limit_increment,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": "HTTP 429 Too Many Requests" if self.rate_limit_increment else None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            self.rate_limit_increment = 0.05
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="error",
                mode_type="fast_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                message="HTTP 429 Too Many Requests",
                match_count=0,
                latency_ms=12.0,
                error="HTTP 429 Too Many Requests",
            )

    runner = ModeRunner(
        build_mode("fast_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    async def fake_wait_until(stop_event, execute_at: float) -> bool:
        return False

    async def fake_wait_for_stop(stop_event, timeout: float) -> bool:
        recorded_timeouts.append(timeout)
        return True

    runner.start()
    monkeypatch.setattr(runner, "_wait_until", fake_wait_until)
    monkeypatch.setattr(runner, "_wait_for_stop", fake_wait_for_stop)

    await runner.run_loop(stop_event)

    assert recorded_timeouts == [1.05]


async def test_mode_runner_forwards_not_login_event_to_event_sink():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    forwarded_events: list[dict[str, object]] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:02",
                level="error",
                mode_type="token",
                account_id=self.account.account_id,
                account_display_name="Token账号",
                query_item_id=query_item.query_item_id,
                query_item_name="商品-1380979899390261111",
                message="Not login",
                match_count=0,
                latency_ms=9.0,
                error="Not login",
            )

    runner = ModeRunner(
        build_mode("token"),
        [build_account("a1", cookie_raw="NC5_accessToken=t; NC5_deviceId=d")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
        event_sink=forwarded_events.append,
    )

    runner.start()
    await runner.run_once()

    assert forwarded_events == [
        {
            "timestamp": "2026-03-16T10:00:02",
            "level": "error",
            "mode_type": "token",
            "query_config_id": None,
            "runtime_session_id": None,
            "account_id": "a1",
            "account_display_name": "Token账号",
            "query_item_id": "1380979899390261111",
            "external_item_id": None,
            "product_url": None,
            "query_item_name": "商品-1380979899390261111",
            "message": "Not login",
            "match_count": 0,
                "product_list": [],
                "total_price": None,
                "total_wear_sum": None,
                "detail_min_wear": None,
                "detail_max_wear": None,
                "max_price": None,
            "latency_ms": 9.0,
            "error": "Not login",
            "status_code": None,
            "request_method": None,
            "request_path": None,
            "request_body": None,
            "response_text": None,
            }
        ]


async def test_mode_runner_forwards_hit_without_waiting_for_event_or_stats_side_effects():
    import asyncio

    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    hit_events: list[dict[str, object]] = []
    event_sink_started = asyncio.Event()
    event_sink_release = asyncio.Event()
    stats_sink_started = asyncio.Event()
    stats_sink_release = asyncio.Event()

    class FakeWorker:
        def __init__(self, account: object) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {
                "account_id": self.account.account_id,
                "active": True,
                "eligible": True,
                "disabled_reason": None,
                "last_query_at": None,
                "last_success_at": None,
                "last_error": None,
            }

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:02",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                account_display_name="查询账号",
                query_item_id=query_item.query_item_id,
                query_item_name="商品-1380979899390261111",
                message="query completed",
                match_count=1,
                product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                total_price=88.0,
                total_wear_sum=0.1234,
                latency_ms=9.0,
                error=None,
            )

    async def slow_event_sink(event: dict[str, object]) -> None:
        event_sink_started.set()
        await event_sink_release.wait()

    async def slow_stats_sink(_event: object) -> None:
        stats_sink_started.set()
        await stats_sink_release.wait()

    async def hit_sink(event: dict[str, object]) -> None:
        hit_events.append(event)

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
        hit_sink=hit_sink,
        event_sink=slow_event_sink,
        stats_sink=slow_stats_sink,
    )

    runner.start()
    task = asyncio.create_task(runner.run_once())

    await asyncio.sleep(0.05)

    assert len(hit_events) == 1
    assert task.done() is True
    assert event_sink_started.is_set() is True
    assert stats_sink_started.is_set() is True

    event_sink_release.set()
    stats_sink_release.set()
    await runner.cleanup()


async def test_mode_runner_returns_without_waiting_for_slow_hit_sink():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    hit_sink_started = asyncio.Event()
    hit_sink_release = asyncio.Event()
    hit_events: list[dict[str, object]] = []

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {"account_id": self.account.account_id, "active": True}

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:03",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                account_display_name="查询账号",
                query_item_id=query_item.query_item_id,
                query_item_name="商品-1380979899390261111",
                message="query completed",
                match_count=1,
                product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                total_price=88.0,
                total_wear_sum=0.1234,
                latency_ms=9.0,
                error=None,
            )

    async def slow_hit_sink(event: dict[str, object]) -> None:
        hit_events.append(event)
        hit_sink_started.set()
        await hit_sink_release.wait()

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
        hit_sink=slow_hit_sink,
    )

    runner.start()
    task = asyncio.create_task(runner.run_once())

    await asyncio.sleep(0.05)

    assert len(hit_events) == 1
    assert hit_sink_started.is_set() is True
    assert task.done() is True

    hit_sink_release.set()
    await runner.cleanup()


async def test_mode_runner_reuses_single_serialized_event_payload_across_fanout(monkeypatch):
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    class FakeWorker:
        def __init__(self, account: object) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {"account_id": self.account.account_id, "active": True}

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:04",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                account_display_name="查询账号",
                query_item_id=query_item.query_item_id,
                query_item_name="商品-1380979899390261111",
                message="query completed",
                match_count=1,
                product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                total_price=88.0,
                total_wear_sum=0.1234,
                latency_ms=9.0,
                error=None,
            )

    forwarded_hits: list[dict[str, object]] = []
    forwarded_events: list[dict[str, object]] = []
    stats_events: list[object] = []

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
        hit_sink=forwarded_hits.append,
        event_sink=forwarded_events.append,
        stats_sink=stats_events.append,
    )

    serialize_calls = 0
    original_serialize = runner._serialize_event

    def wrapped_serialize(event):
        nonlocal serialize_calls
        serialize_calls += 1
        return original_serialize(event)

    monkeypatch.setattr(runner, "_serialize_event", wrapped_serialize)

    runner.start()

    await runner.run_once()
    await runner.cleanup()

    assert len(forwarded_hits) == 1
    assert len(forwarded_events) == 1
    assert len(stats_events) == 2
    assert serialize_calls == 1


def test_mode_runner_reuses_serialized_payload_for_readonly_safe_hit_sink():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    received: list[dict[str, object]] = []

    def safe_hit_sink(payload: dict[str, object]) -> None:
        received.append(payload)

    safe_hit_sink._query_hit_readonly_safe = True

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: None,
        hit_sink=safe_hit_sink,
    )

    serialized_payload = {
        "query_item_name": "AK",
        "product_list": [{"productId": "p-1"}],
    }

    runner._dispatch_hit(
        QueryExecutionEvent(
            timestamp="2026-03-16T10:00:04",
            level="info",
            mode_type="new_api",
            account_id="a1",
            query_item_id="item-1",
            query_item_name="AK",
            message="query completed",
            match_count=1,
            latency_ms=9.0,
            error=None,
        ),
        serialized_event=serialized_payload,
    )

    assert received == [serialized_payload]
    assert received[0] is serialized_payload


def test_mode_runner_keeps_detached_payload_for_regular_hit_sink():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    received: list[dict[str, object]] = []

    def regular_hit_sink(payload: dict[str, object]) -> None:
        received.append(payload)

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1")],
        query_items=[build_item("1380979899390261111")],
        worker_factory=lambda mode_type, account: None,
        hit_sink=regular_hit_sink,
    )

    serialized_payload = {
        "query_item_name": "AK",
        "product_list": [{"productId": "p-1"}],
    }

    runner._dispatch_hit(
        QueryExecutionEvent(
            timestamp="2026-03-16T10:00:04",
            level="info",
            mode_type="new_api",
            account_id="a1",
            query_item_id="item-1",
            query_item_name="AK",
            message="query completed",
            match_count=1,
            latency_ms=9.0,
            error=None,
        ),
        serialized_event=serialized_payload,
    )

    assert received == [{"query_item_name": "AK", "product_list": [{"productId": "p-1"}]}]
    assert received[0] is not serialized_payload
    assert received[0]["product_list"] is not serialized_payload["product_list"]
