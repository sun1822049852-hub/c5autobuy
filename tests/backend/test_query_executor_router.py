from __future__ import annotations

from app_backend.domain.models.account import Account
from app_backend.domain.models.query_config import QueryItem


def build_account() -> Account:
    return Account(
        account_id="a1",
        default_name="账号-a1",
        remark_name=None,
        proxy_mode="custom",
        proxy_url="http://127.0.0.1:9000",
        api_key="api-1",
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw="foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D",
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        disabled=False,
    )


def build_item() -> QueryItem:
    item_id = "1380979899390261111"
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


def test_query_executor_router_build_scanner_raises_for_runtime_managed_modes():
    from app_backend.infrastructure.query.runtime.query_executor_router import QueryExecutorRouter

    router = QueryExecutorRouter()

    for mode_type in ("new_api", "fast_api", "token"):
        try:
            router.build_scanner(mode_type, account=build_account(), query_item=build_item())
        except ValueError as exc:
            assert "handled by runtime query executors" in str(exc)
        else:  # pragma: no cover - defensive guard
            raise AssertionError(f"{mode_type} should be managed by runtime executors")


async def test_query_executor_router_execute_query_accepts_runtime_account_adapter():
    from app_backend.infrastructure.query.runtime.query_executor_router import QueryExecutorRouter
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    class FakeTokenExecutor:
        async def execute_query(self, *, account, query_item, session=None):
            assert isinstance(account, RuntimeAccountAdapter)
            return QueryExecutionResult(
                success=True,
                match_count=1,
                product_list=[{"productId": "p1", "price": 88.8, "actRebateAmount": 0}],
                total_price=88.8,
                total_wear_sum=0.1,
                error=None,
                latency_ms=5.0,
            )

    router = QueryExecutorRouter(token_executor=FakeTokenExecutor())

    runtime_account = RuntimeAccountAdapter(build_account())
    result = await router.execute_query(
        mode_type="token",
        account=runtime_account,
        query_item=build_item(),
    )

    assert result.success is True
    assert result.match_count == 1


async def test_query_executor_router_routes_new_api_to_new_executor():
    from app_backend.infrastructure.query.runtime.query_executor_router import QueryExecutorRouter
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    class FakeNewApiExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def execute_query(self, *, account, query_item, session=None):
            self.calls.append((account.get_account_id(), str(query_item.external_item_id)))
            return QueryExecutionResult(
                success=True,
                match_count=1,
                product_list=[{"productId": "p1", "price": 88.8, "actRebateAmount": 0}],
                total_price=88.8,
                total_wear_sum=0.1234,
                error=None,
                latency_ms=5.0,
            )

    executor = FakeNewApiExecutor()
    router = QueryExecutorRouter(new_api_executor=executor)

    result = await router.execute_query(
        mode_type="new_api",
        account=build_account(),
        query_item=build_item(),
    )

    assert executor.calls == [("a1", "1380979899390261111")]
    assert result.success is True
    assert result.match_count == 1


async def test_query_executor_router_routes_fast_api_to_fast_executor():
    from app_backend.infrastructure.query.runtime.query_executor_router import QueryExecutorRouter
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    class FakeFastApiExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def execute_query(self, *, account, query_item, session=None):
            self.calls.append((account.get_account_id(), str(query_item.external_item_id)))
            return QueryExecutionResult(
                success=True,
                match_count=1,
                product_list=[{"productId": "p2", "price": 66.6, "actRebateAmount": 0}],
                total_price=66.6,
                total_wear_sum=0.2222,
                error=None,
                latency_ms=5.0,
            )

    executor = FakeFastApiExecutor()
    router = QueryExecutorRouter(fast_api_executor=executor)

    result = await router.execute_query(
        mode_type="fast_api",
        account=build_account(),
        query_item=build_item(),
    )

    assert executor.calls == [("a1", "1380979899390261111")]
    assert result.success is True
    assert result.match_count == 1


async def test_query_executor_router_routes_token_to_token_executor():
    from app_backend.infrastructure.query.runtime.query_executor_router import QueryExecutorRouter
    from app_backend.infrastructure.query.runtime.runtime_events import QueryExecutionResult

    class FakeTokenExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def execute_query(self, *, account, query_item, session=None):
            self.calls.append((account.get_account_id(), str(query_item.external_item_id)))
            return QueryExecutionResult(
                success=True,
                match_count=1,
                product_list=[{"productId": "p3", "price": 77.7, "actRebateAmount": 0}],
                total_price=77.7,
                total_wear_sum=0.1111,
                error=None,
                latency_ms=5.0,
            )

    executor = FakeTokenExecutor()
    router = QueryExecutorRouter(token_executor=executor)

    result = await router.execute_query(
        mode_type="token",
        account=build_account(),
        query_item=build_item(),
    )

    assert executor.calls == [("a1", "1380979899390261111")]
    assert result.success is True
    assert result.match_count == 1


async def test_query_executor_router_returns_unsupported_mode_error():
    from app_backend.infrastructure.query.runtime.query_executor_router import QueryExecutorRouter

    router = QueryExecutorRouter()

    result = await router.execute_query(
        mode_type="unknown_mode",
        account=build_account(),
        query_item=build_item(),
    )

    assert result.success is False
    assert result.error == "Unsupported mode_type: unknown_mode"
    assert result.match_count == 0


async def test_query_executor_router_converts_executor_exception_to_result():
    from app_backend.infrastructure.query.runtime.query_executor_router import QueryExecutorRouter

    class BoomTokenExecutor:
        async def execute_query(self, *, account, query_item, session=None):
            raise RuntimeError("boom")

    router = QueryExecutorRouter(token_executor=BoomTokenExecutor())

    result = await router.execute_query(
        mode_type="token",
        account=build_account(),
        query_item=build_item(),
    )

    assert result.success is False
    assert result.error == "boom"
    assert result.match_count == 0
