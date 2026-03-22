import asyncio
import time
from types import SimpleNamespace

from app_backend.domain.models.query_config import QueryConfig, QueryItem, QueryModeSetting


def build_config(config_id: str = "cfg-1") -> QueryConfig:
    return QueryConfig(
        config_id=config_id,
        name="测试配置",
        description="desc",
        enabled=True,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        items=[
            QueryItem(
                query_item_id="item-1",
                config_id=config_id,
                product_url="https://www.c5game.com/csgo/730/asset/item-1",
                external_item_id="1380979899390261111",
                item_name="商品-1",
                market_hash_name="Test Item 1",
                min_wear=0.0,
                max_wear=0.7,
                detail_min_wear=0.0,
                detail_max_wear=0.25,
                max_price=100.0,
                last_market_price=90.0,
                last_detail_sync_at=None,
                sort_order=0,
                created_at="2026-03-16T10:00:00",
                updated_at="2026-03-16T10:00:00",
            )
        ],
        mode_settings=[
            QueryModeSetting(
                mode_setting_id="m1",
                config_id=config_id,
                mode_type="new_api",
                enabled=True,
                window_enabled=False,
                start_hour=0,
                start_minute=0,
                end_hour=0,
                end_minute=0,
                base_cooldown_min=1.0,
                base_cooldown_max=1.0,
                random_delay_enabled=False,
                random_delay_min=0.0,
                random_delay_max=0.0,
                created_at="2026-03-16T10:00:00",
                updated_at="2026-03-16T10:00:00",
            ),
            QueryModeSetting(
                mode_setting_id="m2",
                config_id=config_id,
                mode_type="fast_api",
                enabled=True,
                window_enabled=False,
                start_hour=0,
                start_minute=0,
                end_hour=0,
                end_minute=0,
                base_cooldown_min=1.0,
                base_cooldown_max=1.0,
                random_delay_enabled=False,
                random_delay_min=0.0,
                random_delay_max=0.0,
                created_at="2026-03-16T10:00:00",
                updated_at="2026-03-16T10:00:00",
            ),
            QueryModeSetting(
                mode_setting_id="m3",
                config_id=config_id,
                mode_type="token",
                enabled=True,
                window_enabled=False,
                start_hour=0,
                start_minute=0,
                end_hour=0,
                end_minute=0,
                base_cooldown_min=1.0,
                base_cooldown_max=1.0,
                random_delay_enabled=False,
                random_delay_min=0.0,
                random_delay_max=0.0,
                created_at="2026-03-16T10:00:00",
                updated_at="2026-03-16T10:00:00",
            ),
        ],
    )


def build_account(
    account_id: str,
    *,
    api_key: str | None = None,
    cookie_raw: str | None = None,
    disabled: bool = False,
    new_api_enabled: bool = True,
    fast_api_enabled: bool = True,
    token_enabled: bool = True,
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
        new_api_enabled=new_api_enabled,
        fast_api_enabled=fast_api_enabled,
        token_enabled=token_enabled,
    )


class FakeQueryConfigRepository:
    def __init__(self, config: QueryConfig) -> None:
        self._config = config

    def get_config(self, config_id: str) -> QueryConfig | None:
        if config_id == self._config.config_id:
            return self._config
        return None


class MultiQueryConfigRepository:
    def __init__(self, configs: list[QueryConfig]) -> None:
        self._configs = {
            config.config_id: config
            for config in configs
        }

    def get_config(self, config_id: str) -> QueryConfig | None:
        return self._configs.get(config_id)

    def replace_config(self, config: QueryConfig) -> None:
        self._configs[config.config_id] = config


class FakeAccountRepository:
    def __init__(self, accounts=None) -> None:
        self._accounts = list(accounts or [])

    def list_accounts(self):
        return list(self._accounts)

    def get_account(self, account_id: str):
        for account in self._accounts:
            if account.account_id == account_id:
                return account
        return None

    def update_account(self, account_id: str, **changes):
        account = self.get_account(account_id)
        if account is None:
            raise KeyError(account_id)
        for key, value in changes.items():
            if hasattr(account, key):
                setattr(account, key, value)
        return account


class FakeRuntime:
    def __init__(self, config, accounts) -> None:
        self.config = config
        self.accounts = accounts
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def snapshot(self) -> dict:
        return {
            "running": self.started and not self.stopped,
            "config_id": self.config.config_id,
            "config_name": self.config.name,
            "message": "运行中" if self.started and not self.stopped else "未运行",
        }


class FakePurchaseRuntimeService:
    def __init__(
        self,
        *,
        start_result: tuple[bool, str] = (True, "购买运行时已启动"),
        stop_result: tuple[bool, str] = (True, "购买运行时已停止"),
        active_account_count: int = 1,
    ) -> None:
        self.start_calls = 0
        self.stop_calls = 0
        self.mark_auth_invalid_calls: list[dict[str, str | None]] = []
        self._start_result = start_result
        self._stop_result = stop_result
        self._active_account_count = active_account_count
        self._running = False
        self._on_no_available_accounts = None
        self._on_accounts_available = None

    def start(self) -> tuple[bool, str]:
        self.start_calls += 1
        if self._start_result[0] or self._start_result[1] == "已有购买运行时在运行":
            self._running = True
        return self._start_result

    def stop(self) -> tuple[bool, str]:
        self.stop_calls += 1
        if self._stop_result[0]:
            self._running = False
        return self._stop_result

    def get_status(self) -> dict[str, object]:
        return {
            "running": self._running,
            "active_account_count": self._active_account_count,
        }

    def has_available_accounts(self) -> bool:
        return self._active_account_count > 0

    def register_availability_callbacks(
        self,
        *,
        on_no_available_accounts=None,
        on_accounts_available=None,
    ) -> None:
        self._on_no_available_accounts = on_no_available_accounts
        self._on_accounts_available = on_accounts_available

    def emit_all_accounts_unavailable(self) -> None:
        self._active_account_count = 0
        if callable(self._on_no_available_accounts):
            self._on_no_available_accounts()

    def emit_accounts_recovered(self, *, active_account_count: int = 1) -> None:
        self._active_account_count = active_account_count
        if callable(self._on_accounts_available):
            self._on_accounts_available()

    def mark_account_auth_invalid(self, *, account_id: str, error: str | None = None) -> None:
        self.mark_auth_invalid_calls.append({"account_id": account_id, "error": error})


def set_mode_target(query_item: QueryItem, mode_type: str, target: int) -> None:
    for allocation in query_item.mode_allocations:
        if allocation.mode_type == mode_type:
            allocation.target_dedicated_count = target
            return
    raise AssertionError(f"mode allocation not found: {mode_type}")


def build_active_worker(account_id: str) -> object:
    return SimpleNamespace(account=SimpleNamespace(account_id=account_id))


def test_query_task_runtime_starts_mode_runners_and_aggregates_snapshot():
    from app_backend.infrastructure.query.runtime.query_task_runtime import QueryTaskRuntime

    created_runners = []

    class FakeModeRunner:
        def __init__(self, mode_setting, accounts, *, query_items=None, query_item_scheduler=None) -> None:
            self.mode_type = mode_setting.mode_type
            self.accounts = list(accounts)
            self.query_items = list(query_items or [])
            self.query_item_scheduler = query_item_scheduler
            self.started = False
            self.stopped = False
            created_runners.append(self)

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        def snapshot(self) -> dict[str, object]:
            return {
                "mode_type": self.mode_type,
                "enabled": True,
                "eligible_account_count": len(self.accounts),
                "active_account_count": 1 if self.started and not self.stopped else 0,
                "in_window": True,
                "next_window_start": None,
                "next_window_end": None,
                "query_count": 2 if self.started and not self.stopped else 0,
                "found_count": 3 if self.started and not self.stopped else 0,
                "last_error": None,
                "recent_events": [
                    {
                        "timestamp": f"2026-03-16T10:00:0{index + 1}",
                        "level": "info",
                        "mode_type": self.mode_type,
                        "account_id": "a1",
                        "account_display_name": "白天主号",
                        "query_item_id": "item-1",
                        "query_item_name": "商品-1",
                        "message": "查询完成",
                        "match_count": index + 1,
                        "product_list": [{"productId": f"p-{index + 1}", "price": 88.0 + index, "actRebateAmount": 0}],
                        "total_price": 88.0 + index,
                        "total_wear_sum": 0.1 + index,
                        "latency_ms": 10.0 + index,
                        "error": None,
                    }
                    for index in range(2)
                ],
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "mode_type": self.mode_type,
                        "query_count": 2 if self.started and not self.stopped else 0,
                        "target_dedicated_count": 1 if self.mode_type == "new_api" else 0,
                        "actual_dedicated_count": 1 if self.mode_type == "new_api" else 0,
                        "status": "dedicated" if self.mode_type == "new_api" else "shared",
                        "status_message": "专属中 1/1" if self.mode_type == "new_api" else "共享中",
                    }
                ],
            }

    config = build_config("cfg-1")
    runtime = QueryTaskRuntime(
        config,
        [build_account("a1", api_key="api-1")],
        mode_runner_factory=lambda mode_setting, accounts, **kwargs: FakeModeRunner(mode_setting, accounts, **kwargs),
    )

    runtime.start()
    snapshot = runtime.snapshot()

    assert len(created_runners) == 3
    assert all(runner.started is True for runner in created_runners)
    assert all(len(runner.query_items) == 1 for runner in created_runners)
    assert set(snapshot["modes"]) == {"new_api", "fast_api", "token"}
    assert snapshot["total_query_count"] == 6
    assert snapshot["total_found_count"] == 9
    assert len(snapshot["recent_events"]) == 6
    assert snapshot["recent_events"][0]["timestamp"] == "2026-03-16T10:00:02"
    assert snapshot["recent_events"][0]["account_display_name"] == "白天主号"
    assert snapshot["recent_events"][0]["query_item_name"] == "商品-1"
    assert snapshot["recent_events"][0]["product_list"][0]["productId"] == "p-2"
    assert snapshot["item_rows"] == [
        {
            "query_item_id": "item-1",
            "item_name": "商品-1",
            "max_price": 100.0,
            "min_wear": 0.0,
            "max_wear": 0.7,
            "detail_min_wear": 0.0,
            "detail_max_wear": 0.25,
            "manual_paused": False,
            "query_count": 6,
            "modes": {
                "new_api": {
                    "mode_type": "new_api",
                    "target_dedicated_count": 1,
                    "actual_dedicated_count": 1,
                    "status": "dedicated",
                    "status_message": "专属中 1/1",
                },
                "fast_api": {
                    "mode_type": "fast_api",
                    "target_dedicated_count": 0,
                    "actual_dedicated_count": 0,
                    "status": "shared",
                    "status_message": "共享中",
                },
                "token": {
                    "mode_type": "token",
                    "target_dedicated_count": 0,
                    "actual_dedicated_count": 0,
                    "status": "shared",
                    "status_message": "共享中",
                },
            },
        }
    ]


async def test_query_mode_allocator_spreads_initial_assignments_before_filling_remaining_targets():
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler
    from app_backend.infrastructure.query.runtime.query_mode_allocator import QueryModeAllocator

    item_one = build_config("cfg-1").items[0]
    item_two = build_config("cfg-1").items[0]
    item_two.query_item_id = "item-2"
    item_two.external_item_id = "item-2"
    item_two.item_name = "商品-2"
    item_two.market_hash_name = "Test Item 2"
    item_two.product_url = "https://www.c5game.com/csgo/730/asset/item-2"

    set_mode_target(item_one, "new_api", 2)
    set_mode_target(item_two, "new_api", 1)

    allocator = QueryModeAllocator(
        "new_api",
        [item_one, item_two],
        query_item_scheduler=QueryItemScheduler([item_one, item_two]),
    )

    snapshot = allocator.snapshot(
        active_workers=[build_active_worker("a1"), build_active_worker("a2")],
    )
    rows = {
        row["query_item_id"]: row
        for row in snapshot["item_rows"]
    }

    assert rows["item-1"]["actual_dedicated_count"] == 1
    assert rows["item-2"]["actual_dedicated_count"] == 1
    assert rows["item-1"]["status"] == "dedicated"
    assert rows["item-2"]["status"] == "dedicated"


async def test_query_mode_allocator_released_dedicated_workers_fall_back_to_shared_pool_instead_of_rebalancing_targets():
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler
    from app_backend.infrastructure.query.runtime.query_mode_allocator import QueryModeAllocator

    item_one = build_config("cfg-1").items[0]
    item_two = build_config("cfg-1").items[0]
    item_two.query_item_id = "item-2"
    item_two.external_item_id = "item-2"
    item_two.item_name = "商品-2"
    item_two.market_hash_name = "Test Item 2"
    item_two.product_url = "https://www.c5game.com/csgo/730/asset/item-2"

    set_mode_target(item_one, "new_api", 1)
    set_mode_target(item_two, "new_api", 2)

    allocator = QueryModeAllocator(
        "new_api",
        [item_one, item_two],
        query_item_scheduler=QueryItemScheduler([item_one, item_two]),
    )

    workers = [build_active_worker("a1"), build_active_worker("a2")]
    allocator.snapshot(active_workers=workers)

    item_one.manual_paused = True
    allocator.apply_query_item_runtime(item_one)

    snapshot = allocator.snapshot(active_workers=workers)
    rows = {
        row["query_item_id"]: row
        for row in snapshot["item_rows"]
    }

    assert rows["item-1"]["status"] == "manual_paused"
    assert rows["item-2"]["actual_dedicated_count"] == 1
    assert rows["item-2"]["status"] == "dedicated"


def test_query_task_runtime_builds_one_query_item_scheduler_per_mode():
    from app_backend.infrastructure.query.runtime.query_task_runtime import QueryTaskRuntime

    seen_schedulers = {}

    class FakeModeRunner:
        def __init__(self, mode_setting, accounts, *, query_items=None, query_item_scheduler=None) -> None:
            self.mode_type = mode_setting.mode_type
            seen_schedulers[self.mode_type] = query_item_scheduler

        def start(self) -> None:
            return

        def stop(self) -> None:
            return

        def snapshot(self) -> dict[str, object]:
            return {
                "mode_type": self.mode_type,
                "enabled": True,
                "eligible_account_count": 0,
                "active_account_count": 0,
                "in_window": True,
                "next_window_start": None,
                "next_window_end": None,
                "query_count": 0,
                "found_count": 0,
                "last_error": None,
                "recent_events": [],
            }

    runtime = QueryTaskRuntime(
        build_config("cfg-1"),
        [build_account("a1", api_key="api-1")],
        mode_runner_factory=lambda mode_setting, accounts, **kwargs: FakeModeRunner(mode_setting, accounts, **kwargs),
    )

    runtime.start()

    assert set(seen_schedulers) == {"new_api", "fast_api", "token"}
    assert seen_schedulers["new_api"] is not None
    assert seen_schedulers["fast_api"] is not None
    assert seen_schedulers["token"] is not None
    assert seen_schedulers["new_api"] is not seen_schedulers["fast_api"]
    assert seen_schedulers["fast_api"] is not seen_schedulers["token"]
    assert seen_schedulers["new_api"] is not seen_schedulers["token"]


def test_query_task_runtime_stop_stops_all_mode_runners():
    from app_backend.infrastructure.query.runtime.query_task_runtime import QueryTaskRuntime

    created_runners = []

    class FakeModeRunner:
        def __init__(self, mode_setting, accounts, *, query_items=None, query_item_scheduler=None) -> None:
            self.mode_type = mode_setting.mode_type
            self.started = False
            self.stopped = False
            self.query_item_scheduler = query_item_scheduler
            created_runners.append(self)

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        def snapshot(self) -> dict[str, object]:
            return {
                "mode_type": self.mode_type,
                "enabled": True,
                "eligible_account_count": 0,
                "active_account_count": 0,
                "in_window": True,
                "next_window_start": None,
                "next_window_end": None,
                "query_count": 0,
                "found_count": 0,
                "last_error": None,
            }

    runtime = QueryTaskRuntime(
        build_config("cfg-1"),
        [build_account("a1", api_key="api-1")],
        mode_runner_factory=lambda mode_setting, accounts, **kwargs: FakeModeRunner(mode_setting, accounts, **kwargs),
    )

    runtime.start()
    runtime.stop()

    assert all(runner.started is True for runner in created_runners)
    assert all(runner.stopped is True for runner in created_runners)


def test_query_task_runtime_runs_mode_loops_in_background_until_stopped():
    from app_backend.infrastructure.query.runtime.query_task_runtime import QueryTaskRuntime

    created_runners = []

    class FakeModeRunner:
        def __init__(self, mode_setting, accounts, *, query_items=None, query_item_scheduler=None) -> None:
            self.mode_type = mode_setting.mode_type
            self.started = False
            self.stopped = False
            self.query_count = 0
            self.query_item_scheduler = query_item_scheduler
            created_runners.append(self)

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        async def run_loop(self, stop_event) -> None:
            while not stop_event.is_set():
                self.query_count += 1
                await asyncio.sleep(0.01)

        def snapshot(self) -> dict[str, object]:
            return {
                "mode_type": self.mode_type,
                "enabled": True,
                "eligible_account_count": 1,
                "active_account_count": 1 if self.query_count > 0 else 0,
                "in_window": True,
                "next_window_start": None,
                "next_window_end": None,
                "query_count": self.query_count,
                "found_count": self.query_count,
                "last_error": None,
            }

    runtime = QueryTaskRuntime(
        build_config("cfg-1"),
        [build_account("a1", api_key="api-1")],
        mode_runner_factory=lambda mode_setting, accounts, **kwargs: FakeModeRunner(mode_setting, accounts, **kwargs),
    )

    runtime.start()
    deadline = time.time() + 1.0
    snapshot = runtime.snapshot()
    while snapshot["total_query_count"] == 0 and time.time() < deadline:
        time.sleep(0.02)
        snapshot = runtime.snapshot()

    assert snapshot["running"] is True
    assert snapshot["total_query_count"] > 0

    runtime.stop()
    stopped_counts = [runner.query_count for runner in created_runners]
    time.sleep(0.05)

    assert all(runner.started is True for runner in created_runners)
    assert all(runner.stopped is True for runner in created_runners)
    assert [runner.query_count for runner in created_runners] == stopped_counts


def test_query_task_runtime_stop_runs_runner_cleanup_before_return():
    from app_backend.infrastructure.query.runtime.query_task_runtime import QueryTaskRuntime

    cleaned = []

    class FakeModeRunner:
        def __init__(self, mode_setting, accounts, *, query_items=None, query_item_scheduler=None) -> None:
            self.mode_type = mode_setting.mode_type
            self.started = False
            self.stopped = False
            self.query_item_scheduler = query_item_scheduler

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        async def run_loop(self, stop_event) -> None:
            await stop_event.wait()

        async def cleanup(self) -> None:
            cleaned.append(self.mode_type)

        def snapshot(self) -> dict[str, object]:
            return {
                "mode_type": self.mode_type,
                "enabled": True,
                "eligible_account_count": 0,
                "active_account_count": 0,
                "in_window": True,
                "next_window_start": None,
                "next_window_end": None,
                "query_count": 0,
                "found_count": 0,
                "last_error": None,
            }

    runtime = QueryTaskRuntime(
        build_config("cfg-1"),
        [build_account("a1", api_key="api-1")],
        mode_runner_factory=lambda mode_setting, accounts, **kwargs: FakeModeRunner(mode_setting, accounts, **kwargs),
    )

    runtime.start()
    runtime.stop()

    assert cleaned == ["new_api", "fast_api", "token"]


def test_runtime_service_rejects_second_running_task():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    started, _message = service.start(config_id="cfg-1")
    started_again, second_message = service.start(config_id="cfg-2")

    assert started is True
    assert started_again is False
    assert second_message == "已有查询任务在运行"


def test_runtime_service_returns_current_snapshot():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    service.start(config_id="cfg-1")
    snapshot = service.get_status()

    assert snapshot["running"] is True
    assert snapshot["config_id"] == "cfg-1"
    assert snapshot["config_name"] == "测试配置"
    assert snapshot["total_query_count"] == 0
    assert snapshot["total_found_count"] == 0
    assert snapshot["modes"]["new_api"]["active_account_count"] == 0
    assert snapshot["modes"]["new_api"]["in_window"] is True
    assert snapshot["modes"]["new_api"]["query_count"] == 0
    assert snapshot["modes"]["new_api"]["found_count"] == 0
    assert snapshot["modes"]["new_api"]["last_error"] is None
    assert snapshot["group_rows"] == []
    assert snapshot["recent_events"] == []


def test_runtime_service_normalizes_recent_events():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    class FakeRuntimeWithEvents(FakeRuntime):
        def snapshot(self) -> dict:
            return {
                "running": self.started and not self.stopped,
                "config_id": self.config.config_id,
                "config_name": self.config.name,
                "message": "运行中",
                "account_count": 1,
                "started_at": "2026-03-16T10:00:00",
                "stopped_at": None,
                "total_query_count": 2,
                "total_found_count": 1,
                "modes": {
                    "new_api": {
                        "mode_type": "new_api",
                        "enabled": True,
                        "eligible_account_count": 1,
                        "active_account_count": 1,
                        "in_window": True,
                        "next_window_start": None,
                        "next_window_end": None,
                        "query_count": 2,
                        "found_count": 1,
                        "last_error": None,
                    }
                },
                "recent_events": [
                    {
                        "timestamp": "2026-03-16T10:00:02",
                        "level": "error",
                        "mode_type": "new_api",
                        "account_id": "a1",
                        "account_display_name": "白天主号",
                        "query_item_id": "item-1",
                        "query_item_name": "商品-1",
                        "message": "HTTP 429 Too Many Requests",
                        "match_count": 0,
                        "product_list": [],
                        "total_price": None,
                        "total_wear_sum": None,
                        "latency_ms": 12,
                        "error": "HTTP 429 Too Many Requests",
                    },
                    {
                        "timestamp": "2026-03-16T10:00:01",
                        "level": "info",
                        "mode_type": "new_api",
                        "account_id": "a1",
                        "account_display_name": "白天主号",
                        "query_item_id": "item-1",
                        "query_item_name": "商品-1",
                        "message": "查询完成",
                        "match_count": 1,
                        "product_list": [{"productId": "p-1", "price": 88.5, "actRebateAmount": 0}],
                        "total_price": 88.5,
                        "total_wear_sum": 0.1,
                        "latency_ms": 10.5,
                        "error": None,
                    },
                ],
            }

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository([build_account("a1", api_key="api-1")]),
        runtime_factory=lambda config, accounts: FakeRuntimeWithEvents(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    service.start(config_id="cfg-1")
    snapshot = service.get_status()

    assert len(snapshot["recent_events"]) == 2
    assert snapshot["recent_events"][0]["level"] == "error"
    assert snapshot["recent_events"][0]["latency_ms"] == 12.0
    assert snapshot["recent_events"][0]["account_display_name"] == "白天主号"
    assert snapshot["recent_events"][0]["product_list"] == []
    assert snapshot["recent_events"][1]["query_item_name"] == "商品-1"
    assert snapshot["recent_events"][1]["total_price"] == 88.5
    assert snapshot["recent_events"][1]["product_list"][0]["productId"] == "p-1"


def test_runtime_service_normalizes_item_rows():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    class FakeRuntimeWithItemRows(FakeRuntime):
        def snapshot(self) -> dict:
            return {
                "running": self.started and not self.stopped,
                "config_id": self.config.config_id,
                "config_name": self.config.name,
                "message": "运行中",
                "account_count": 1,
                "started_at": "2026-03-16T10:00:00",
                "stopped_at": None,
                "total_query_count": 0,
                "total_found_count": 0,
                "modes": {},
                "group_rows": [],
                "recent_events": [],
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "item_name": "商品-1",
                        "max_price": 100,
                        "min_wear": 0,
                        "max_wear": 0.7,
                        "detail_min_wear": 0.0,
                        "detail_max_wear": 0.25,
                        "manual_paused": False,
                        "query_count": 7,
                        "modes": {
                            "new_api": {
                                "mode_type": "new_api",
                                "target_dedicated_count": 1,
                                "actual_dedicated_count": 1,
                                "status": "dedicated",
                                "status_message": "专属中 1/1",
                            }
                        },
                    }
                ],
            }

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository([build_account("a1", api_key="api-1")]),
        runtime_factory=lambda config, accounts: FakeRuntimeWithItemRows(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    service.start(config_id="cfg-1")
    snapshot = service.get_status()

    assert snapshot["item_rows"] == [
        {
            "query_item_id": "item-1",
            "item_name": "商品-1",
            "max_price": 100.0,
            "min_wear": 0.0,
            "max_wear": 0.7,
            "detail_min_wear": 0.0,
            "detail_max_wear": 0.25,
            "manual_paused": False,
            "query_count": 7,
            "modes": {
                "new_api": {
                    "mode_type": "new_api",
                    "target_dedicated_count": 1,
                    "actual_dedicated_count": 1,
                    "status": "dedicated",
                    "status_message": "专属中 1/1",
                }
            },
        }
    ]


def test_runtime_service_stop_clears_running_state():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    service.start(config_id="cfg-1")
    stopped, message = service.stop()

    assert stopped is True
    assert message == "查询任务已停止"
    assert service.get_status()["running"] is False
    assert purchase_service.stop_calls == 1


def test_runtime_service_starts_purchase_runtime_before_query_runtime():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    started, message = service.start(config_id="cfg-1")

    assert started is True
    assert message == "查询任务已启动"
    assert purchase_service.start_calls == 1


def test_runtime_service_switches_running_config_when_starting_a_different_config():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = MultiQueryConfigRepository([build_config("cfg-1"), build_config("cfg-2")])
    purchase_service = FakePurchaseRuntimeService()
    created_runtimes: list[FakeRuntime] = []

    def runtime_factory(config, accounts):
      runtime = FakeRuntime(config, accounts)
      created_runtimes.append(runtime)
      return runtime

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=runtime_factory,
        purchase_runtime_service=purchase_service,
    )

    started_first, message_first = service.start(config_id="cfg-1")
    started_second, message_second = service.start(config_id="cfg-2")
    snapshot = service.get_status()

    assert started_first is True
    assert message_first == "查询任务已启动"
    assert started_second is True
    assert message_second == "查询任务已启动"
    assert len(created_runtimes) == 2
    assert created_runtimes[0].stopped is True
    assert created_runtimes[1].started is True
    assert snapshot["running"] is True
    assert snapshot["config_id"] == "cfg-2"
    assert snapshot["config_name"] == "测试配置"


def test_runtime_service_reuses_runtime_account_adapter_across_config_switch_and_closes_it_on_stop(monkeypatch):
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    repository = MultiQueryConfigRepository([build_config("cfg-1"), build_config("cfg-2")])
    purchase_service = FakePurchaseRuntimeService()
    account_repository = FakeAccountRepository([build_account("a1", api_key="api-1")])
    created_runtimes: list[FakeRuntime] = []
    closed: list[tuple[str, str]] = []

    async def fake_close_global_session(self):
        closed.append(("global", self.current_user_id))

    async def fake_close_api_session(self):
        closed.append(("api", self.current_user_id))

    monkeypatch.setattr(RuntimeAccountAdapter, "close_global_session", fake_close_global_session)
    monkeypatch.setattr(RuntimeAccountAdapter, "close_api_session", fake_close_api_session)

    class FakeRuntimeWithSharedAccounts(FakeRuntime):
        def __init__(self, config, accounts, *, runtime_account_provider=None) -> None:
            super().__init__(config, accounts)
            assert callable(runtime_account_provider)
            self.runtime_accounts = [runtime_account_provider(account) for account in accounts]
            created_runtimes.append(self)

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=account_repository,
        runtime_factory=lambda config, accounts, runtime_account_provider=None: FakeRuntimeWithSharedAccounts(
            config,
            accounts,
            runtime_account_provider=runtime_account_provider,
        ),
        purchase_runtime_service=purchase_service,
    )

    started_first, message_first = service.start(config_id="cfg-1")
    started_second, message_second = service.start(config_id="cfg-2")
    stopped, stop_message = service.stop()

    assert started_first is True
    assert message_first == "查询任务已启动"
    assert started_second is True
    assert message_second == "查询任务已启动"
    assert len(created_runtimes) == 2
    assert created_runtimes[0].runtime_accounts[0] is created_runtimes[1].runtime_accounts[0]
    assert closed.count(("global", "a1")) == 1
    assert closed.count(("api", "a1")) == 1
    assert len(closed) == 2
    assert stopped is True
    assert stop_message == "查询任务已停止"


def test_runtime_service_enters_waiting_state_when_no_purchase_accounts_are_available():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService(active_account_count=0)
    created_runtimes: list[FakeRuntime] = []

    def runtime_factory(config, accounts):
        runtime = FakeRuntime(config, accounts)
        created_runtimes.append(runtime)
        return runtime

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=runtime_factory,
        purchase_runtime_service=purchase_service,
    )

    started, message = service.start(config_id="cfg-1")
    snapshot = service.get_status()

    assert started is True
    assert message == "查询任务已启动，等待购买账号恢复"
    assert created_runtimes == []
    assert snapshot["running"] is False
    assert snapshot["config_id"] == "cfg-1"
    assert snapshot["config_name"] == "测试配置"
    assert snapshot["message"] == "等待购买账号恢复"
    assert snapshot["item_rows"][0]["query_count"] == 0


def test_runtime_service_starts_in_waiting_state_and_auto_recovers_when_purchase_accounts_return():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService(active_account_count=0)
    created_runtimes: list[FakeRuntime] = []

    def runtime_factory(config, accounts):
        runtime = FakeRuntime(config, accounts)
        created_runtimes.append(runtime)
        return runtime

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=runtime_factory,
        purchase_runtime_service=purchase_service,
    )

    started, message = service.start(config_id="cfg-1")
    assert started is True
    assert message == "查询任务已启动，等待购买账号恢复"
    assert created_runtimes == []

    purchase_service.emit_accounts_recovered()
    snapshot = service.get_status()

    assert len(created_runtimes) == 1
    assert created_runtimes[0].started is True
    assert snapshot["running"] is True
    assert snapshot["config_id"] == "cfg-1"
    assert snapshot["config_name"] == "测试配置"


def test_runtime_service_apply_query_item_runtime_updates_live_runtime_without_stop():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    before_config = build_config("cfg-1")
    after_config = build_config("cfg-1")
    after_config.items[0].detail_max_wear = 0.13
    after_config.items[0].manual_paused = True
    for allocation in after_config.items[0].mode_allocations:
        if allocation.mode_type == "new_api":
            allocation.target_dedicated_count = 2

    repository = MultiQueryConfigRepository([before_config])
    purchase_service = FakePurchaseRuntimeService()
    created_runtimes: list[FakeRuntime] = []

    class FakeRuntimeWithApply(FakeRuntime):
        def __init__(self, config, accounts) -> None:
            super().__init__(config, accounts)
            self.runtime_session_id = "run-apply-1"
            self.apply_calls: list[dict[str, object]] = []
            created_runtimes.append(self)

        def snapshot(self) -> dict:
            mode_target = 0
            for allocation in self.config.items[0].mode_allocations:
                if allocation.mode_type == "new_api":
                    mode_target = allocation.target_dedicated_count
            return {
                "running": self.started and not self.stopped,
                "config_id": self.config.config_id,
                "config_name": self.config.name,
                "runtime_session_id": self.runtime_session_id,
                "message": "运行中" if self.started and not self.stopped else "未运行",
                "account_count": 0,
                "started_at": "2026-03-16T10:00:00" if self.started and not self.stopped else None,
                "stopped_at": None,
                "total_query_count": 0,
                "total_found_count": 0,
                "modes": {},
                "group_rows": [],
                "recent_events": [],
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "item_name": self.config.items[0].item_name,
                        "max_price": self.config.items[0].max_price,
                        "min_wear": self.config.items[0].min_wear,
                        "max_wear": self.config.items[0].max_wear,
                        "detail_min_wear": self.config.items[0].detail_min_wear,
                        "detail_max_wear": self.config.items[0].detail_max_wear,
                        "manual_paused": self.config.items[0].manual_paused,
                        "query_count": 0,
                        "modes": {
                            "new_api": {
                                "mode_type": "new_api",
                                "target_dedicated_count": mode_target,
                                "actual_dedicated_count": 0,
                                "status": "manual_paused" if self.config.items[0].manual_paused else "shared",
                                "status_message": "手动暂停" if self.config.items[0].manual_paused else "共享中",
                            }
                        },
                    }
                ],
            }

        def apply_query_item_runtime(self, *, config, query_item_id: str) -> None:
            self.apply_calls.append(
                {
                    "config_id": config.config_id,
                    "query_item_id": query_item_id,
                    "detail_max_wear": config.items[0].detail_max_wear,
                    "manual_paused": config.items[0].manual_paused,
                }
            )
            self.config = config

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository([build_account("a1", api_key="api-1")]),
        runtime_factory=lambda config, accounts: FakeRuntimeWithApply(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    started, message = service.start(config_id="cfg-1")
    repository.replace_config(after_config)
    result = service.apply_query_item_runtime(config_id="cfg-1", query_item_id="item-1")
    snapshot = service.get_status()

    assert started is True
    assert message == "查询任务已启动"
    assert result == {
        "status": "applied",
        "message": "当前运行配置已热应用",
        "config_id": "cfg-1",
        "query_item_id": "item-1",
    }
    assert len(created_runtimes) == 1
    assert created_runtimes[0].stopped is False
    assert created_runtimes[0].runtime_session_id == "run-apply-1"
    assert created_runtimes[0].apply_calls == [
        {
            "config_id": "cfg-1",
            "query_item_id": "item-1",
            "detail_max_wear": 0.13,
            "manual_paused": True,
        }
    ]
    assert snapshot["item_rows"][0]["detail_max_wear"] == 0.13
    assert snapshot["item_rows"][0]["manual_paused"] is True
    assert snapshot["item_rows"][0]["modes"]["new_api"]["target_dedicated_count"] == 2


def test_runtime_service_apply_query_item_runtime_returns_waiting_resume_when_query_is_paused():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    before_config = build_config("cfg-1")
    after_config = build_config("cfg-1")
    after_config.items[0].detail_max_wear = 0.11
    after_config.items[0].manual_paused = True
    repository = MultiQueryConfigRepository([before_config])
    purchase_service = FakePurchaseRuntimeService(active_account_count=0)
    created_runtimes: list[FakeRuntime] = []

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository([build_account("a1", api_key="api-1")]),
        runtime_factory=lambda config, accounts: created_runtimes.append(FakeRuntime(config, accounts)) or created_runtimes[-1],
        purchase_runtime_service=purchase_service,
    )

    started, message = service.start(config_id="cfg-1")
    repository.replace_config(after_config)
    result = service.apply_query_item_runtime(config_id="cfg-1", query_item_id="item-1")
    snapshot = service.get_status()

    assert started is True
    assert message == "查询任务已启动，等待购买账号恢复"
    assert created_runtimes == []
    assert result == {
        "status": "applied_waiting_resume",
        "message": "当前配置等待恢复运行，已记录热应用",
        "config_id": "cfg-1",
        "query_item_id": "item-1",
    }
    assert snapshot["message"] == "等待购买账号恢复"
    assert snapshot["item_rows"][0]["detail_max_wear"] == 0.11
    assert snapshot["item_rows"][0]["manual_paused"] is True


def test_runtime_service_apply_query_item_runtime_skips_when_config_is_inactive():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = MultiQueryConfigRepository([build_config("cfg-1"), build_config("cfg-2")])
    purchase_service = FakePurchaseRuntimeService()
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository([build_account("a1", api_key="api-1")]),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    service.start(config_id="cfg-1")
    result = service.apply_query_item_runtime(config_id="cfg-2", query_item_id="item-1")

    assert result == {
        "status": "skipped_inactive",
        "message": "当前配置未在运行，已跳过热应用",
        "config_id": "cfg-2",
        "query_item_id": "item-1",
    }


def test_runtime_service_apply_query_item_runtime_reports_failed_after_save_when_refresh_crashes():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = MultiQueryConfigRepository([build_config("cfg-1")])
    purchase_service = FakePurchaseRuntimeService()
    created_runtimes: list[FakeRuntime] = []

    class FakeRuntimeApplyCrash(FakeRuntime):
        def __init__(self, config, accounts) -> None:
            super().__init__(config, accounts)
            created_runtimes.append(self)

        def apply_query_item_runtime(self, *, config, query_item_id: str) -> None:
            raise RuntimeError("allocator refresh failed")

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository([build_account("a1", api_key="api-1")]),
        runtime_factory=lambda config, accounts: FakeRuntimeApplyCrash(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    service.start(config_id="cfg-1")
    result = service.apply_query_item_runtime(config_id="cfg-1", query_item_id="item-1")

    assert result == {
        "status": "failed_after_save",
        "message": "配置已保存，但热应用失败：allocator refresh failed",
        "config_id": "cfg-1",
        "query_item_id": "item-1",
    }
    assert len(created_runtimes) == 1
    assert created_runtimes[0].stopped is False


def test_runtime_service_reuses_runtime_account_adapter_after_purchase_pause_and_recovery(monkeypatch):
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    account_repository = FakeAccountRepository([build_account("a1", api_key="api-1")])
    created_runtimes: list[FakeRuntime] = []
    closed: list[tuple[str, str]] = []

    async def fake_close_global_session(self):
        closed.append(("global", self.current_user_id))

    async def fake_close_api_session(self):
        closed.append(("api", self.current_user_id))

    monkeypatch.setattr(RuntimeAccountAdapter, "close_global_session", fake_close_global_session)
    monkeypatch.setattr(RuntimeAccountAdapter, "close_api_session", fake_close_api_session)

    class FakeRuntimeWithSharedAccounts(FakeRuntime):
        def __init__(self, config, accounts, *, runtime_account_provider=None) -> None:
            super().__init__(config, accounts)
            assert callable(runtime_account_provider)
            self.runtime_accounts = [runtime_account_provider(account) for account in accounts]
            created_runtimes.append(self)

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=account_repository,
        runtime_factory=lambda config, accounts, runtime_account_provider=None: FakeRuntimeWithSharedAccounts(
            config,
            accounts,
            runtime_account_provider=runtime_account_provider,
        ),
        purchase_runtime_service=purchase_service,
    )

    started, message = service.start(config_id="cfg-1")
    purchase_service.emit_all_accounts_unavailable()
    purchase_service.emit_accounts_recovered()
    stopped, stop_message = service.stop()

    assert started is True
    assert message == "查询任务已启动"
    assert len(created_runtimes) == 2
    assert created_runtimes[0].runtime_accounts[0] is created_runtimes[1].runtime_accounts[0]
    assert closed.count(("global", "a1")) == 1
    assert closed.count(("api", "a1")) == 1
    assert len(closed) == 2
    assert stopped is True
    assert stop_message == "查询任务已停止"


def test_runtime_service_pauses_query_when_purchase_accounts_become_unavailable():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    created_runtimes: list[FakeRuntime] = []

    def runtime_factory(config, accounts):
        runtime = FakeRuntime(config, accounts)
        created_runtimes.append(runtime)
        return runtime

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=runtime_factory,
        purchase_runtime_service=purchase_service,
    )

    started, _message = service.start(config_id="cfg-1")

    assert started is True

    purchase_service.emit_all_accounts_unavailable()
    snapshot = service.get_status()

    assert created_runtimes[0].stopped is True
    assert snapshot["running"] is False
    assert snapshot["config_id"] == "cfg-1"
    assert snapshot["config_name"] == "测试配置"
    assert snapshot["message"] == "等待购买账号恢复"
    assert purchase_service.stop_calls == 0


def test_runtime_service_auto_restarts_query_when_purchase_accounts_recover():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    created_runtimes: list[FakeRuntime] = []

    def runtime_factory(config, accounts):
        runtime = FakeRuntime(config, accounts)
        created_runtimes.append(runtime)
        return runtime

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=runtime_factory,
        purchase_runtime_service=purchase_service,
    )

    started, _message = service.start(config_id="cfg-1")
    assert started is True

    purchase_service.emit_all_accounts_unavailable()
    purchase_service.emit_accounts_recovered()
    snapshot = service.get_status()

    assert len(created_runtimes) == 2
    assert created_runtimes[0].stopped is True
    assert created_runtimes[1].started is True
    assert snapshot["running"] is True
    assert snapshot["config_id"] == "cfg-1"
    assert snapshot["config_name"] == "测试配置"


def test_runtime_service_allows_query_start_when_purchase_runtime_is_already_running():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService(start_result=(False, "已有购买运行时在运行"))
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    started, message = service.start(config_id="cfg-1")

    assert started is True
    assert message == "查询任务已启动"
    assert purchase_service.start_calls == 1


def test_runtime_service_rejects_query_start_when_purchase_runtime_cannot_start():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService(start_result=(False, "购买运行时启动失败"))
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
        purchase_runtime_service=purchase_service,
    )

    started, message = service.start(config_id="cfg-1")

    assert started is False
    assert message == "购买运行时启动失败"
    assert service.get_status()["running"] is False


def test_runtime_service_counts_eligible_accounts_by_mode():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    purchase_service = FakePurchaseRuntimeService()
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(
            [
                build_account("a1", api_key="api-1"),
                build_account(
                    "a2",
                    api_key="api-2",
                    cookie_raw="foo=bar; NC5_accessToken=token-2",
                    new_api_enabled=False,
                ),
                build_account("a3", cookie_raw="foo=bar; NC5_accessToken=token-3"),
                build_account(
                    "a4",
                    api_key="api-4",
                    cookie_raw="foo=bar; NC5_accessToken=token-4",
                    disabled=True,
                ),
            ]
        ),
        purchase_runtime_service=purchase_service,
    )

    service.start(config_id="cfg-1")
    snapshot = service.get_status()

    assert snapshot["modes"]["new_api"]["eligible_account_count"] == 2
    assert snapshot["modes"]["fast_api"]["eligible_account_count"] == 3
    assert snapshot["modes"]["token"]["eligible_account_count"] == 3
    assert snapshot["modes"]["token"]["active_account_count"] == 0
    assert snapshot["modes"]["token"]["in_window"] is True
    assert snapshot["modes"]["token"]["query_count"] == 0
    assert snapshot["modes"]["token"]["found_count"] == 0
    assert {
        (row["account_id"], row["mode_type"])
        for row in snapshot["group_rows"]
    } == {
        ("a1", "new_api"),
        ("a1", "fast_api"),
        ("a2", "fast_api"),
        ("a2", "token"),
        ("a3", "token"),
        ("a4", "new_api"),
        ("a4", "fast_api"),
        ("a4", "token"),
    }
    assert snapshot["group_rows"][0]["account_display_name"].startswith("账号-")
    assert snapshot["group_rows"][0]["cooldown_until"] is None
    assert snapshot["group_rows"][0]["query_count"] == 0
    assert snapshot["group_rows"][0]["found_count"] == 0


def test_runtime_service_respects_mode_enabled_flag():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    config = build_config("cfg-1")
    config.mode_settings[1].enabled = False
    repository = FakeQueryConfigRepository(config)
    purchase_service = FakePurchaseRuntimeService()
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(
            [
                build_account("a1", api_key="api-1"),
                build_account("a2", api_key="api-2"),
            ]
        ),
        purchase_runtime_service=purchase_service,
    )

    service.start(config_id="cfg-1")
    snapshot = service.get_status()

    assert snapshot["modes"]["fast_api"]["enabled"] is False
    assert snapshot["modes"]["fast_api"]["eligible_account_count"] == 0
    assert snapshot["modes"]["fast_api"]["active_account_count"] == 0
    assert snapshot["modes"]["fast_api"]["in_window"] is False
    assert snapshot["modes"]["fast_api"]["query_count"] == 0
    assert snapshot["modes"]["fast_api"]["found_count"] == 0


def test_runtime_service_propagates_not_login_event_to_account_repository_and_purchase_runtime():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    account_repository = FakeAccountRepository(
        [build_account("a1", cookie_raw="foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1")]
    )
    purchase_service = FakePurchaseRuntimeService()

    class FakeRuntimeWithEventSink(FakeRuntime):
        def __init__(self, config, accounts, *, event_sink=None) -> None:
            super().__init__(config, accounts)
            self._event_sink = event_sink

        def start(self) -> None:
            super().start()
            if callable(self._event_sink):
                self._event_sink(
                    {
                        "timestamp": "2026-03-18T12:00:00",
                        "level": "error",
                        "mode_type": "token",
                        "account_id": "a1",
                        "account_display_name": "账号-a1",
                        "query_item_id": "item-1",
                        "query_item_name": "商品-1",
                        "message": "Not login",
                        "match_count": 0,
                        "product_list": [],
                        "total_price": None,
                        "total_wear_sum": None,
                        "latency_ms": 9.0,
                        "error": "Not login",
                    }
                )

    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=account_repository,
        runtime_factory=lambda config, accounts, event_sink=None: FakeRuntimeWithEventSink(
            config,
            accounts,
            event_sink=event_sink,
        ),
        purchase_runtime_service=purchase_service,
    )

    started, message = service.start(config_id="cfg-1")

    assert started is True
    assert message == "查询任务已启动"
    account = account_repository.get_account("a1")
    assert account is not None
    assert account.purchase_capability_state == "expired"
    assert account.purchase_pool_state == "paused_auth_invalid"
    assert account.last_error == "Not login"
    assert purchase_service.mark_auth_invalid_calls == [
        {"account_id": "a1", "error": "Not login"}
    ]
