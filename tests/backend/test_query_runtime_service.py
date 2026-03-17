import asyncio
import time

from app_backend.domain.models.account import Account
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
                max_wear=0.25,
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


class FakeQueryConfigRepository:
    def __init__(self, config: QueryConfig) -> None:
        self._config = config

    def get_config(self, config_id: str) -> QueryConfig | None:
        if config_id == self._config.config_id:
            return self._config
        return None


class FakeAccountRepository:
    def __init__(self, accounts=None) -> None:
        self._accounts = list(accounts or [])

    def list_accounts(self):
        return list(self._accounts)


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
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
    )

    started, _message = service.start(config_id="cfg-1")
    started_again, second_message = service.start(config_id="cfg-2")

    assert started is True
    assert started_again is False
    assert second_message == "已有查询任务在运行"


def test_runtime_service_returns_current_snapshot():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
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
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository([build_account("a1", api_key="api-1")]),
        runtime_factory=lambda config, accounts: FakeRuntimeWithEvents(config, accounts),
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


def test_runtime_service_stop_clears_running_state():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts: FakeRuntime(config, accounts),
    )

    service.start(config_id="cfg-1")
    stopped, message = service.stop()

    assert stopped is True
    assert message == "查询任务已停止"
    assert service.get_status()["running"] is False


def test_runtime_service_counts_eligible_accounts_by_mode():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    repository = FakeQueryConfigRepository(build_config("cfg-1"))
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
    )

    service.start(config_id="cfg-1")
    snapshot = service.get_status()

    assert snapshot["modes"]["new_api"]["eligible_account_count"] == 1
    assert snapshot["modes"]["fast_api"]["eligible_account_count"] == 2
    assert snapshot["modes"]["token"]["eligible_account_count"] == 2
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
    service = QueryRuntimeService(
        query_config_repository=repository,
        account_repository=FakeAccountRepository(
            [
                build_account("a1", api_key="api-1"),
                build_account("a2", api_key="api-2"),
            ]
        ),
    )

    service.start(config_id="cfg-1")
    snapshot = service.get_status()

    assert snapshot["modes"]["fast_api"]["enabled"] is False
    assert snapshot["modes"]["fast_api"]["eligible_account_count"] == 0
    assert snapshot["modes"]["fast_api"]["active_account_count"] == 0
    assert snapshot["modes"]["fast_api"]["in_window"] is False
    assert snapshot["modes"]["fast_api"]["query_count"] == 0
    assert snapshot["modes"]["fast_api"]["found_count"] == 0
