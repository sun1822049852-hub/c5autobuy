from __future__ import annotations

from app_backend.domain.models.account import Account
from app_backend.domain.models.query_config import QueryItem


def build_account(
    account_id: str,
    *,
    cookie_raw: str | None = None,
    api_key: str | None = None,
    remark_name: str | None = None,
) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=remark_name,
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
    )


def build_item(item_id: str = "1380979899390261111") -> QueryItem:
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


async def test_account_worker_returns_query_success_event():
    from app_backend.infrastructure.query.runtime.account_query_worker import AccountQueryWorker
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    class FakeAdapter:
        async def execute_query(self, *, mode_type, account, query_item):
            return QueryExecutionResult(
                success=True,
                match_count=2,
                product_list=[{"id": "p1"}, {"id": "p2"}],
                total_price=100.0,
                total_wear_sum=0.2,
                error=None,
                latency_ms=25.0,
            )

    worker = AccountQueryWorker(
        mode_type="new_api",
        account=build_account("a1", api_key="api-1", remark_name="备注-a1"),
        scanner_adapter=FakeAdapter(),
    )

    event = await worker.run_once(build_item())
    snapshot = worker.snapshot()

    assert event is not None
    assert event.mode_type == "new_api"
    assert event.account_id == "a1"
    assert event.account_display_name == "备注-a1"
    assert event.query_item_id == "1380979899390261111"
    assert event.match_count == 2
    assert event.total_price == 100.0
    assert event.total_wear_sum == 0.2
    assert event.product_list == [{"id": "p1"}, {"id": "p2"}]
    assert snapshot["query_count"] == 1
    assert snapshot["found_count"] == 2
    assert snapshot["disabled_reason"] is None


async def test_account_worker_disables_account_on_403():
    from app_backend.infrastructure.query.runtime.account_query_worker import AccountQueryWorker
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    class FakeAdapter:
        async def execute_query(self, *, mode_type, account, query_item):
            return QueryExecutionResult(
                success=False,
                match_count=0,
                product_list=[],
                total_price=0.0,
                total_wear_sum=0.0,
                error="HTTP 403 Forbidden",
                latency_ms=10.0,
            )

    worker = AccountQueryWorker(
        mode_type="token",
        account=build_account("a1", cookie_raw="NC5_accessToken=t; NC5_deviceId=d"),
        scanner_adapter=FakeAdapter(),
    )

    event = await worker.run_once(build_item())
    snapshot = worker.snapshot()

    assert event is not None
    assert event.error == "HTTP 403 Forbidden"
    assert snapshot["disabled_reason"] == "HTTP 403 Forbidden"
    assert snapshot["active"] is False


async def test_account_worker_adds_rate_limit_increment_on_429_without_disabling_worker():
    from app_backend.infrastructure.query.runtime.account_query_worker import AccountQueryWorker
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    class FakeAdapter:
        async def execute_query(self, *, mode_type, account, query_item):
            return QueryExecutionResult(
                success=False,
                match_count=0,
                product_list=[],
                total_price=0.0,
                total_wear_sum=0.0,
                error="HTTP 429 Too Many Requests",
                latency_ms=10.0,
            )

    worker = AccountQueryWorker(
        mode_type="fast_api",
        account=build_account("a1", api_key="api-1"),
        scanner_adapter=FakeAdapter(),
        now_provider=lambda: 100.0,
    )

    await worker.run_once(build_item())
    snapshot = worker.snapshot()

    assert snapshot["disabled_reason"] is None
    assert snapshot["active"] is True
    assert snapshot["backoff_until"] is None
    assert snapshot["rate_limit_increment"] == 0.05


async def test_account_worker_accumulates_429_increment_and_resets_after_rate_limit_window():
    from app_backend.infrastructure.query.runtime.account_query_worker import AccountQueryWorker
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    now_holder = {"value": 100.0}

    class FakeAdapter:
        async def execute_query(self, *, mode_type, account, query_item):
            return QueryExecutionResult(
                success=False,
                match_count=0,
                product_list=[],
                total_price=0.0,
                total_wear_sum=0.0,
                error="HTTP 429 Too Many Requests",
                latency_ms=10.0,
            )

    worker = AccountQueryWorker(
        mode_type="fast_api",
        account=build_account("a1", api_key="api-1"),
        scanner_adapter=FakeAdapter(),
        now_provider=lambda: now_holder["value"],
    )

    await worker.run_once(build_item())
    now_holder["value"] = 200.0
    await worker.run_once(build_item("1380979899390262222"))
    limited_snapshot = worker.snapshot()

    assert limited_snapshot["active"] is True
    assert limited_snapshot["rate_limit_increment"] == 0.1

    now_holder["value"] = 801.0
    reset_snapshot = worker.snapshot()

    assert reset_snapshot["active"] is True
    assert reset_snapshot["backoff_until"] is None
    assert reset_snapshot["rate_limit_increment"] == 0.0


async def test_account_worker_disables_account_on_not_login():
    from app_backend.infrastructure.query.runtime.account_query_worker import AccountQueryWorker
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    class FakeAdapter:
        async def execute_query(self, *, mode_type, account, query_item):
            return QueryExecutionResult(
                success=False,
                match_count=0,
                product_list=[],
                total_price=0.0,
                total_wear_sum=0.0,
                error="Not login",
                latency_ms=10.0,
            )

    worker = AccountQueryWorker(
        mode_type="token",
        account=build_account("a1", cookie_raw="NC5_accessToken=t; NC5_deviceId=d"),
        scanner_adapter=FakeAdapter(),
    )

    await worker.run_once(build_item())
    snapshot = worker.snapshot()

    assert snapshot["disabled_reason"] == "Not login"
    assert snapshot["active"] is False


async def test_account_worker_reuses_runtime_account_adapter_across_runs():
    from app_backend.infrastructure.query.runtime.account_query_worker import AccountQueryWorker
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    seen_accounts = []

    class FakeAdapter:
        async def execute_query(self, *, mode_type, account, query_item):
            seen_accounts.append(account)
            return QueryExecutionResult(
                success=True,
                match_count=1,
                product_list=[{"id": "p1"}],
                total_price=50.0,
                total_wear_sum=0.1,
                error=None,
                latency_ms=5.0,
            )

    worker = AccountQueryWorker(
        mode_type="new_api",
        account=build_account("a1", api_key="api-1", remark_name="备注-a1"),
        scanner_adapter=FakeAdapter(),
    )

    await worker.run_once(build_item("1380979899390261111"))
    await worker.run_once(build_item("1380979899390262222"))

    assert len(seen_accounts) == 2
    assert isinstance(seen_accounts[0], RuntimeAccountAdapter)
    assert seen_accounts[0] is seen_accounts[1]


async def test_account_worker_cleanup_keeps_shared_runtime_account_sessions_open(monkeypatch):
    from app_backend.infrastructure.query.runtime.account_query_worker import AccountQueryWorker
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    closed = {"global": 0, "api": 0}

    async def fake_close_global_session(self):
        closed["global"] += 1

    async def fake_close_api_session(self):
        closed["api"] += 1

    monkeypatch.setattr(RuntimeAccountAdapter, "close_global_session", fake_close_global_session)
    monkeypatch.setattr(RuntimeAccountAdapter, "close_api_session", fake_close_api_session)

    shared_runtime_account = RuntimeAccountAdapter(build_account("a1", api_key="api-1"))
    worker = AccountQueryWorker(
        mode_type="new_api",
        account=build_account("a1", api_key="api-1"),
        runtime_account=shared_runtime_account,
    )

    await worker.cleanup()

    assert closed == {"global": 0, "api": 0}


async def test_account_worker_cleanup_closes_reused_sessions(monkeypatch):
    from app_backend.infrastructure.query.runtime.account_query_worker import AccountQueryWorker
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    closed = {"global": 0, "api": 0}

    async def fake_close_global_session(self):
        closed["global"] += 1

    async def fake_close_api_session(self):
        closed["api"] += 1

    monkeypatch.setattr(RuntimeAccountAdapter, "close_global_session", fake_close_global_session)
    monkeypatch.setattr(RuntimeAccountAdapter, "close_api_session", fake_close_api_session)

    worker = AccountQueryWorker(
        mode_type="new_api",
        account=build_account("a1", api_key="api-1"),
    )

    await worker.cleanup()

    assert closed == {"global": 1, "api": 1}


def test_account_worker_defaults_to_query_executor_router():
    from app_backend.infrastructure.query.runtime.account_query_worker import AccountQueryWorker
    from app_backend.infrastructure.query.runtime.query_executor_router import QueryExecutorRouter

    worker = AccountQueryWorker(
        mode_type="new_api",
        account=build_account("a1", api_key="api-1"),
    )

    assert isinstance(worker._scanner_adapter, QueryExecutorRouter)
