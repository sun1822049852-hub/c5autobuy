from __future__ import annotations

import json

from app_backend.domain.models.account import Account
from app_backend.domain.models.query_config import QueryItem


def build_account() -> Account:
    return Account(
        account_id="a1",
        default_name="account-a1",
        remark_name=None,
        browser_proxy_mode="direct",
        browser_proxy_url=None,
        api_proxy_mode="direct",
        api_proxy_url=None,
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
    )


def build_item() -> QueryItem:
    item_id = "1380979899390261111"
    return QueryItem(
        query_item_id="item-1",
        config_id="cfg-1",
        product_url=f"https://www.c5game.com/csgo/730/asset/{item_id}",
        external_item_id=item_id,
        item_name="Test Item",
        market_hash_name="Test Item Name",
        min_wear=0.0,
        max_wear=0.25,
        max_price=100.0,
        last_market_price=90.0,
        last_detail_sync_at=None,
        sort_order=0,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        detail_min_wear=0.0,
        detail_max_wear=0.25,
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
    def __init__(self, *, status: int, text: str) -> None:
        self.closed = False
        self.calls: list[dict[str, object]] = []
        self._status = status
        self._text = text

    def post(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(status=self._status, text=self._text)


class FakeSigner:
    def __init__(self, *, result: str) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


async def test_new_api_executor_smoke_keeps_legacy_request_shape():
    from app_backend.infrastructure.query.runtime.new_api_query_executor import NewApiQueryExecutor
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    session = FakeSession(
        status=200,
        text=json.dumps(
            {
                "success": True,
                "data": {
                    "list": [
                        {
                            "productId": "p1",
                            "price": "88.80",
                            "assetInfo": {"floatWear": "0.1234"},
                        }
                    ]
                },
            }
        ),
    )
    executor = NewApiQueryExecutor()
    runtime_account = RuntimeAccountAdapter(build_account())

    result = await executor.execute_query(
        account=runtime_account,
        query_item=build_item(),
        session=session,
    )

    assert result.success is True
    assert result.match_count == 1
    assert result.product_list[0]["productId"] == "p1"
    assert result.product_list[0]["actRebateAmount"] == 0
    assert session.calls[0]["url"] == "https://openapi.c5game.com/merchant/market/v2/products/search"
    assert session.calls[0]["params"] == {"app-key": "api-1"}
    assert session.calls[0]["json"] == {
        "pageSize": 50,
        "appId": 730,
        "marketHashName": "Test Item Name",
        "priceMax": 100.0,
        "wearMin": 0.0,
        "wearMax": 0.25,
    }
    assert session.calls[0]["headers"]["Content-Type"] == "application/json"
    assert session.calls[0]["headers"]["Accept"] == "application/json"


async def test_fast_api_executor_smoke_keeps_legacy_request_shape():
    from app_backend.infrastructure.query.runtime.fast_api_query_executor import FastApiQueryExecutor
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    session = FakeSession(
        status=200,
        text=json.dumps(
            {
                "success": True,
                "data": {
                    "list": [
                        {
                            "productId": "p2",
                            "price": "66.60",
                            "assetInfo": {"floatWear": "0.2222"},
                        }
                    ],
                    "pageNum": 1,
                    "hasMore": False,
                },
            }
        ),
    )
    executor = FastApiQueryExecutor()
    runtime_account = RuntimeAccountAdapter(build_account())

    result = await executor.execute_query(
        account=runtime_account,
        query_item=build_item(),
        session=session,
    )

    assert result.success is True
    assert result.match_count == 1
    assert result.product_list[0]["productId"] == "p2"
    assert session.calls[0]["url"] == "https://openapi.c5game.com/merchant/market/v2/products/list"
    assert session.calls[0]["params"] == {"app-key": "api-1"}
    assert session.calls[0]["json"] == {
        "pageSize": 50,
        "pageNum": 1,
        "appId": 730,
        "marketHashName": "Test Item Name",
        "delivery": 1,
        "assetType": 1,
    }
    assert session.calls[0]["headers"]["Content-Type"] == "application/json"
    assert session.calls[0]["headers"]["Accept"] == "application/json"


async def test_token_executor_smoke_keeps_legacy_request_shape():
    from app_backend.infrastructure.query.runtime.token_query_executor import TokenQueryExecutor
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

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
    signer = FakeSigner(result="fake-sign")
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    runtime_account = RuntimeAccountAdapter(build_account())

    result = await executor.execute_query(
        account=runtime_account,
        query_item=build_item(),
        session=session,
    )

    assert result.success is True
    assert result.match_count == 1
    assert result.product_list[0]["productId"] == "p3"
    assert signer.calls[0]["path"] == "support/trade/product/batch/v1/sell/query"
    assert signer.calls[0]["method"] == "POST"
    assert signer.calls[0]["token"] == "token-1"
    assert session.calls[0]["url"] == "https://www.c5game.com/api/v1/support/trade/product/batch/v1/sell/query"
    assert session.calls[0]["json"] == {
        "itemId": "1380979899390261111",
        "maxPrice": "100.0",
        "delivery": 0,
        "minWear": 0.0,
        "maxWear": 0.25,
        "limit": "200",
        "giftBuy": "",
    }
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
    assert session.calls[0]["headers"]["x-access-token"] == "token-1"
    assert session.calls[0]["headers"]["x-device-id"] == "device-1"
    assert session.calls[0]["headers"]["Cookie"] == build_account().cookie_raw
    assert session.calls[0]["headers"]["Referer"] == build_item().product_url
