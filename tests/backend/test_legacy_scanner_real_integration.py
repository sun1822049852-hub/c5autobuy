from __future__ import annotations

import importlib
import json

from app_backend.domain.models.account import Account
from app_backend.domain.models.query_config import QueryItem


def build_account() -> Account:
    return Account(
        account_id="a1",
        default_name="account-a1",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
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


async def test_real_legacy_new_api_execute_query_smoke(monkeypatch):
    from app_backend.infrastructure.query.runtime.legacy_scanner_adapter import LegacyScannerAdapter
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    legacy_module = importlib.import_module("autobuy")
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

    async def fake_get_api_session(self, force_new: bool = False):
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "get_api_session", fake_get_api_session)
    adapter = LegacyScannerAdapter(legacy_module=legacy_module)

    result = await adapter.execute_query(
        mode_type="new_api",
        account=build_account(),
        query_item=build_item(),
    )

    assert result.success is True
    assert result.match_count == 1
    assert result.product_list[0]["productId"] == "p1"
    assert result.product_list[0]["actRebateAmount"] == 0
    assert session.calls[0]["params"] == {"app-key": "api-1"}


async def test_real_legacy_fast_api_execute_query_smoke(monkeypatch):
    from app_backend.infrastructure.query.runtime.legacy_scanner_adapter import LegacyScannerAdapter
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    legacy_module = importlib.import_module("autobuy")
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

    async def fake_get_api_session(self, force_new: bool = False):
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "get_api_session", fake_get_api_session)
    adapter = LegacyScannerAdapter(legacy_module=legacy_module)

    result = await adapter.execute_query(
        mode_type="fast_api",
        account=build_account(),
        query_item=build_item(),
    )

    assert result.success is True
    assert result.match_count == 1
    assert result.product_list[0]["productId"] == "p2"
    assert session.calls[0]["params"] == {"app-key": "api-1"}


async def test_real_legacy_token_execute_query_smoke(monkeypatch):
    from app_backend.infrastructure.query.runtime.legacy_scanner_adapter import LegacyScannerAdapter
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    legacy_module = importlib.import_module("autobuy")
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

    async def fake_get_global_session(self, force_new: bool = False):
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "get_global_session", fake_get_global_session)
    monkeypatch.setattr(legacy_module.GLOBAL_XSIGN_WRAPPER, "generate", lambda **kwargs: "fake-sign")
    adapter = LegacyScannerAdapter(legacy_module=legacy_module)

    result = await adapter.execute_query(
        mode_type="token",
        account=build_account(),
        query_item=build_item(),
    )

    assert result.success is True
    assert result.match_count == 1
    assert result.product_list[0]["productId"] == "p3"
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
