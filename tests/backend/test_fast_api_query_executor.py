from __future__ import annotations

import asyncio
import json

import pytest

from app_backend.domain.models.account import Account
from app_backend.domain.models.query_config import QueryItem
from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

try:
    from aiohttp import ClientError
except ModuleNotFoundError:  # pragma: no cover - optional dependency in unit tests
    ClientError = RuntimeError


def build_account(*, api_key: str | None = "api-1") -> Account:
    return Account(
        account_id="a1",
        default_name="account-a1",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=api_key,
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw=None,
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        disabled=False,
    )


def build_item(
    *,
    min_wear: float | None = 0.0,
    max_wear: float | None = 0.8,
    detail_min_wear: float | None = 0.1,
    detail_max_wear: float | None = 0.25,
) -> QueryItem:
    item_id = "1380979899390261111"
    return QueryItem(
        query_item_id="item-1",
        config_id="cfg-1",
        product_url=f"https://www.c5game.com/csgo/730/asset/{item_id}",
        external_item_id=item_id,
        item_name="Test Item",
        market_hash_name="Test Item Name",
        min_wear=min_wear,
        max_wear=max_wear,
        detail_min_wear=detail_min_wear,
        detail_max_wear=detail_max_wear,
        max_price=100.0,
        last_market_price=90.0,
        last_detail_sync_at=None,
        sort_order=0,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
    )


class FakeResponse:
    def __init__(self, *, status: int, text: str) -> None:
        self.status = status
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def text(self) -> str:
        return self._text


class FakeSession:
    def __init__(
        self,
        *,
        status: int = 200,
        text: str = "{}",
        raised_error: BaseException | None = None,
    ) -> None:
        self.closed = False
        self.calls: list[dict[str, object]] = []
        self._status = status
        self._text = text
        self._raised_error = raised_error

    def post(self, **kwargs):
        self.calls.append(kwargs)
        if self._raised_error is not None:
            raise self._raised_error
        return FakeResponse(status=self._status, text=self._text)


async def test_fast_api_query_executor_filters_response_client_side():
    from app_backend.infrastructure.query.runtime.fast_api_query_executor import FastApiQueryExecutor

    executor = FastApiQueryExecutor()
    session = FakeSession(
        status=200,
        text=json.dumps(
            {
                "success": True,
                "data": {
                    "list": [
                        {"productId": "too-low-wear", "price": "88.80", "assetInfo": {"floatWear": "0.0500"}},
                        {"productId": "ok-1", "price": "88.80", "assetInfo": {"floatWear": "0.1234"}},
                        {"productId": "expensive", "price": "188.80", "assetInfo": {"floatWear": "0.1234"}},
                        {"productId": "bad-wear", "price": "66.60", "assetInfo": {"floatWear": "0.9000"}},
                        {"productId": "missing-wear", "price": "55.50"},
                    ],
                    "pageNum": 1,
                    "hasMore": False,
                },
            }
        ),
    )

    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=session,
    )

    assert result.success is True
    assert result.match_count == 1
    assert result.product_list == [{"productId": "ok-1", "price": 88.8, "actRebateAmount": 0}]
    assert result.total_price == pytest.approx(88.8)
    assert result.total_wear_sum == pytest.approx(0.1234)


async def test_fast_api_query_executor_returns_legacy_429_error_text():
    from app_backend.infrastructure.query.runtime.fast_api_query_executor import FastApiQueryExecutor

    executor = FastApiQueryExecutor()
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(status=429, text="{}"),
    )

    assert result.success is False
    assert result.error == "HTTP 429 Too Many Requests"


async def test_fast_api_query_executor_returns_legacy_403_error_text():
    from app_backend.infrastructure.query.runtime.fast_api_query_executor import FastApiQueryExecutor

    executor = FastApiQueryExecutor()
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(status=403, text="{}"),
    )

    assert result.success is False
    assert result.error == "HTTP 403 请求失败 (可能IP未加入白名单)"


async def test_fast_api_query_executor_returns_error_when_session_missing():
    from app_backend.infrastructure.query.runtime.fast_api_query_executor import FastApiQueryExecutor

    executor = FastApiQueryExecutor()
    runtime_account = RuntimeAccountAdapter(build_account())

    async def fake_get_api_session(force_new: bool = False):
        return None

    runtime_account.get_api_session = fake_get_api_session
    result = await executor.execute_query(
        account=runtime_account,
        query_item=build_item(),
        session=None,
    )

    assert result.success is False
    assert result.error == "无法创建OpenAPI会话"


async def test_fast_api_query_executor_returns_string_error_for_invalid_json():
    from app_backend.infrastructure.query.runtime.fast_api_query_executor import FastApiQueryExecutor

    executor = FastApiQueryExecutor()
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(status=200, text="{broken"),
    )

    assert result.success is False
    assert result.error == "响应不是有效的JSON格式"


async def test_fast_api_query_executor_returns_timeout_error_text():
    from app_backend.infrastructure.query.runtime.fast_api_query_executor import FastApiQueryExecutor

    executor = FastApiQueryExecutor()
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(raised_error=asyncio.TimeoutError()),
    )

    assert result.success is False
    assert result.error == "请求超时 (8秒)"


async def test_fast_api_query_executor_returns_network_error_text():
    from app_backend.infrastructure.query.runtime.fast_api_query_executor import FastApiQueryExecutor

    executor = FastApiQueryExecutor()
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(raised_error=ClientError("boom")),
    )

    assert result.success is False
    assert result.error == "网络错误: boom"


async def test_fast_api_query_executor_rejects_missing_final_detail_wear_range():
    from app_backend.infrastructure.query.runtime.fast_api_query_executor import FastApiQueryExecutor

    executor = FastApiQueryExecutor()
    session = FakeSession(status=200, text=json.dumps({"success": True, "data": {"list": []}}))

    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(detail_min_wear=None, detail_max_wear=None),
        session=session,
    )

    assert result.success is False
    assert result.error == "查询配置缺少最终磨损范围"
    assert session.calls == []
