from __future__ import annotations

import asyncio
import json

import pytest

from app_backend.domain.models.account import Account
from app_backend.domain.models.query_config import QueryItem
from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter


def build_account() -> Account:
    return Account(
        account_id="a1",
        default_name="account-a1",
        remark_name=None,
        browser_proxy_mode="direct",
        browser_proxy_url=None,
        api_proxy_mode="direct",
        api_proxy_url=None,
        api_key=None,
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw="foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D",
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
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


class FakeSigner:
    def __init__(self, *, result: str | None = None, error: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._result = result
        self._error = error

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._result


async def test_token_query_executor_parses_success_response_and_keeps_request_shape():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor

    signer = FakeSigner(result="fake-sign")
    session = FakeSession(
        status=200,
        text=json.dumps(
            {
                "success": True,
                "data": {
                    "matchCount": 1,
                    "sellList": [
                        {
                            "id": "p3",
                            "price": "77.70",
                            "assetInfo": {"wear": "0.1111"},
                        }
                    ],
                },
            }
        ),
    )
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    runtime_account = RuntimeAccountAdapter(build_account())

    result = await executor.execute_query(
        account=runtime_account,
        query_item=build_item(),
        session=session,
    )

    assert result.success is True
    assert result.match_count == 1
    assert result.product_list == [{"productId": "p3", "price": 77.7, "actRebateAmount": 0}]
    assert result.total_price == pytest.approx(77.7)
    assert result.total_wear_sum == pytest.approx(0.1111)
    assert signer.calls[0]["path"] == "support/trade/product/batch/v1/sell/query"
    assert signer.calls[0]["method"] == "POST"
    assert signer.calls[0]["token"] == "token-1"
    assert session.calls[0]["url"] == "https://www.c5game.com/api/v1/support/trade/product/batch/v1/sell/query"
    assert session.calls[0]["json"] == {
        "itemId": "1380979899390261111",
        "maxPrice": "100.0",
        "delivery": 0,
        "minWear": 0.1,
        "maxWear": 0.25,
        "limit": "200",
        "giftBuy": "",
    }
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
    assert session.calls[0]["headers"]["x-access-token"] == "token-1"
    assert session.calls[0]["headers"]["x-device-id"] == "device-1"
    assert session.calls[0]["headers"]["Cookie"] == build_account().cookie_raw
    assert session.calls[0]["headers"]["Referer"] == build_item().product_url


async def test_token_query_executor_returns_403_error_text():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor

    signer = FakeSigner(result="fake-sign")
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(status=403, text="{}"),
    )

    assert result.success is False
    assert result.error == "HTTP 403 Forbidden"


async def test_token_query_executor_returns_not_login_text_for_plain_response():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor

    signer = FakeSigner(result="fake-sign")
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(status=200, text="Not login"),
    )

    assert result.success is False
    assert result.error == "Not login"


async def test_token_query_executor_returns_error_when_session_missing():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor

    signer = FakeSigner(result="fake-sign")
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    runtime_account = RuntimeAccountAdapter(build_account())

    async def fake_get_global_session(force_new: bool = False):
        return None

    runtime_account.get_global_session = fake_get_global_session
    result = await executor.execute_query(
        account=runtime_account,
        query_item=build_item(),
        session=None,
    )

    assert result.success is False
    assert result.error == "无法创建浏览器会话"


async def test_token_query_executor_returns_xsign_error_text():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor

    signer = FakeSigner(error=RuntimeError("boom"))
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(),
    )

    assert result.success is False
    assert result.error == "x-sign生成失败: boom"


async def test_token_query_executor_returns_invalid_json_error_text():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor

    signer = FakeSigner(result="fake-sign")
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(status=200, text="{broken"),
    )

    assert result.success is False
    assert result.error == "响应不是有效的JSON格式"


async def test_token_query_executor_returns_timeout_error_text():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor

    signer = FakeSigner(result="fake-sign")
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(raised_error=asyncio.TimeoutError()),
    )

    assert result.success is False
    assert result.error == "请求超时"


async def test_token_query_executor_returns_request_error_text():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor

    signer = FakeSigner(result="fake-sign")
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(),
        session=FakeSession(raised_error=RuntimeError("boom")),
    )

    assert result.success is False
    assert result.error == "请求错误: boom"


async def test_token_query_executor_rejects_missing_final_detail_wear_range():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor

    signer = FakeSigner(result="fake-sign")
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    session = FakeSession(status=200, text=json.dumps({"success": True, "data": {"sellList": [], "matchCount": 0}}))

    result = await executor.execute_query(
        account=RuntimeAccountAdapter(build_account()),
        query_item=build_item(detail_min_wear=None, detail_max_wear=None),
        session=session,
    )

    assert result.success is False
    assert result.error == "查询配置缺少最终磨损范围"
    assert session.calls == []
