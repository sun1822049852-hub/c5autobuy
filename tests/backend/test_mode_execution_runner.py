from __future__ import annotations

from datetime import datetime

from app_backend.domain.models.account import Account
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
) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
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

    assert snapshot["eligible_account_count"] == 1
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
            "latency_ms": 9.0,
            "error": "Not login",
        }
    ]
