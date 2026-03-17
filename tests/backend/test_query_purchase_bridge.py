from __future__ import annotations

from app_backend.domain.models.account import Account
from app_backend.domain.models.query_config import QueryConfig, QueryItem, QueryModeSetting


def build_mode(mode_type: str) -> QueryModeSetting:
    return QueryModeSetting(
        mode_setting_id=f"{mode_type}-1",
        config_id="cfg-1",
        mode_type=mode_type,
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
    )


def build_item(item_id: str = "item-1", *, item_name: str = "AK") -> QueryItem:
    return QueryItem(
        query_item_id=item_id,
        config_id="cfg-1",
        product_url=f"https://www.c5game.com/csgo/730/asset/{item_id}",
        external_item_id=item_id,
        item_name=item_name,
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


def build_config() -> QueryConfig:
    return QueryConfig(
        config_id="cfg-1",
        name="Test Config",
        description="desc",
        enabled=True,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        items=[build_item()],
        mode_settings=[build_mode("new_api")],
    )


def build_account(account_id: str = "a1", *, api_key: str | None = "api-1") -> Account:
    return Account(
        account_id=account_id,
        default_name=f"Account-{account_id}",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=api_key,
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw=None,
        purchase_capability_state="bound",
        purchase_pool_state="active",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        disabled=False,
        new_api_enabled=True,
        fast_api_enabled=True,
        token_enabled=False,
    )


class StubPurchaseRuntimeService:
    def __init__(self, *, query_only: bool = False) -> None:
        self.query_only = query_only
        self.accepted_hits: list[dict[str, object]] = []
        self.blocked_hits = 0

    def accept_query_hit(self, hit: dict[str, object]) -> dict[str, object]:
        payload = dict(hit)
        if self.query_only:
            self.blocked_hits += 1
            return {"accepted": False, "status": "blocked_query_only"}
        self.accepted_hits.append(payload)
        return {"accepted": True, "status": "queued"}


class FakeQueryConfigRepository:
    def get_config(self, config_id: str) -> QueryConfig | None:
        if config_id == "cfg-1":
            return build_config()
        return None


class FakeAccountRepository:
    def list_accounts(self):
        return [build_account()]


async def test_mode_runner_forwards_positive_match_to_purchase_runtime():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    purchase_service = StubPurchaseRuntimeService()

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {"account_id": self.account.account_id, "active": True}

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                account_display_name=self.account.display_name,
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                product_url=query_item.product_url,
                query_item_name=query_item.item_name,
                message="query completed",
                match_count=1,
                product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                total_price=88.0,
                total_wear_sum=0.1234,
                latency_ms=12.0,
                error=None,
            )

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account()],
        query_items=[build_item(item_name="AK")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
        hit_sink=purchase_service.accept_query_hit,
    )

    runner.start()
    await runner.run_once()

    assert purchase_service.accepted_hits[0]["query_item_name"] == "AK"
    assert purchase_service.accepted_hits[0]["external_item_id"] == "item-1"
    assert purchase_service.accepted_hits[0]["product_url"] == "https://www.c5game.com/csgo/730/asset/item-1"
    assert purchase_service.accepted_hits[0]["mode_type"] == "new_api"
    assert purchase_service.accepted_hits[0]["product_list"][0]["productId"] == "p-1"


async def test_mode_runner_skips_hit_sink_for_zero_match_event():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    purchase_service = StubPurchaseRuntimeService()

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {"account_id": self.account.account_id, "active": True}

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                product_url=query_item.product_url,
                message="query completed",
                match_count=0,
                query_item_name=query_item.item_name,
                product_list=[],
                total_price=None,
                total_wear_sum=None,
                latency_ms=12.0,
                error=None,
            )

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account()],
        query_items=[build_item(item_name="AK")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
        hit_sink=purchase_service.accept_query_hit,
    )

    runner.start()
    await runner.run_once()

    assert purchase_service.accepted_hits == []
    assert purchase_service.blocked_hits == 0


async def test_mode_runner_marks_hit_blocked_when_query_only_enabled():
    from app_backend.infrastructure.query.runtime.mode_runner import ModeRunner
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionEvent

    purchase_service = StubPurchaseRuntimeService(query_only=True)

    class FakeWorker:
        def __init__(self, account: Account) -> None:
            self.account = account

        def snapshot(self) -> dict[str, object]:
            return {"account_id": self.account.account_id, "active": True}

        async def run_once(self, query_item: QueryItem) -> QueryExecutionEvent:
            return QueryExecutionEvent(
                timestamp="2026-03-16T10:00:00",
                level="info",
                mode_type="new_api",
                account_id=self.account.account_id,
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                product_url=query_item.product_url,
                query_item_name=query_item.item_name,
                message="query completed",
                match_count=1,
                product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                total_price=88.0,
                total_wear_sum=0.1234,
                latency_ms=12.0,
                error=None,
            )

    runner = ModeRunner(
        build_mode("new_api"),
        [build_account()],
        query_items=[build_item(item_name="AK")],
        worker_factory=lambda mode_type, account: FakeWorker(account),
        hit_sink=purchase_service.accept_query_hit,
    )

    runner.start()
    await runner.run_once()

    assert purchase_service.accepted_hits == []
    assert purchase_service.blocked_hits == 1


def test_query_task_runtime_passes_hit_sink_to_mode_runners():
    from app_backend.infrastructure.query.runtime.query_task_runtime import QueryTaskRuntime

    sink = object()
    captured_sinks: dict[str, object] = {}

    class FakeModeRunner:
        def __init__(self, mode_setting, accounts, *, query_items=None, query_item_scheduler=None, hit_sink=None) -> None:
            captured_sinks[mode_setting.mode_type] = hit_sink

        def snapshot(self) -> dict[str, object]:
            return {
                "mode_type": "new_api",
                "enabled": True,
                "eligible_account_count": 1,
                "active_account_count": 0,
                "in_window": True,
                "next_window_start": None,
                "next_window_end": None,
                "query_count": 0,
                "found_count": 0,
                "last_error": None,
                "recent_events": [],
            }

    QueryTaskRuntime(
        build_config(),
        [build_account()],
        hit_sink=sink,
        mode_runner_factory=lambda mode_setting, accounts, **kwargs: FakeModeRunner(mode_setting, accounts, **kwargs),
    )

    assert captured_sinks == {"new_api": sink}


def test_query_runtime_service_passes_purchase_hit_sink_into_runtime_factory():
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService

    purchase_service = StubPurchaseRuntimeService()
    captured_hit_sink = {}

    class FakeRuntime:
        def __init__(self, config, accounts, *, hit_sink=None) -> None:
            self.config = config
            self.started = False
            self.stopped = False
            captured_hit_sink["sink"] = hit_sink

        def start(self) -> None:
            self.started = True
            captured_hit_sink["sink"](
                {
                    "query_item_name": "AK",
                    "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                    "total_price": 88.0,
                    "total_wear_sum": 0.1234,
                    "mode_type": "new_api",
                }
            )

        def stop(self) -> None:
            self.stopped = True

        def snapshot(self) -> dict[str, object]:
            return {
                "running": self.started and not self.stopped,
                "config_id": self.config.config_id,
                "config_name": self.config.name,
                "message": "running" if self.started and not self.stopped else "stopped",
                "account_count": 1,
                "started_at": "2026-03-16T10:00:00" if self.started and not self.stopped else None,
                "stopped_at": None,
                "total_query_count": 1 if self.started and not self.stopped else 0,
                "total_found_count": 1 if self.started and not self.stopped else 0,
                "modes": {},
                "recent_events": [],
            }

    service = QueryRuntimeService(
        query_config_repository=FakeQueryConfigRepository(),
        account_repository=FakeAccountRepository(),
        runtime_factory=lambda config, accounts, **kwargs: FakeRuntime(config, accounts, **kwargs),
        purchase_runtime_service=purchase_service,
    )

    started, _message = service.start(config_id="cfg-1")

    assert started is True
    assert callable(captured_hit_sink["sink"])
    assert purchase_service.accepted_hits[0]["query_item_name"] == "AK"
