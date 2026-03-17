from __future__ import annotations

import importlib
import json

from app_backend.domain.models.account import Account
from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch


def build_account() -> Account:
    return Account(
        account_id="a1",
        default_name="account-a1",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
        c5_user_id="10001",
        c5_nick_name="测试账号",
        cookie_raw="foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D",
        purchase_capability_state="bound",
        purchase_pool_state="active",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        disabled=False,
    )


def build_batch() -> PurchaseHitBatch:
    return PurchaseHitBatch(
        external_item_id="1380979899390261111",
        query_item_name="AK-47",
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
        product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
        total_price=88.0,
        total_wear_sum=0.1234,
        source_mode_type="token",
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
    def __init__(self, responses: list[tuple[int, str]]) -> None:
        self.closed = False
        self.calls: list[dict[str, object]] = []
        self._responses = list(responses)

    def post(self, **kwargs):
        self.calls.append(kwargs)
        status, text = self._responses.pop(0)
        return FakeResponse(status=status, text=text)


async def test_legacy_purchase_gateway_executes_order_then_payment(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.legacy_purchase_gateway import LegacyPurchaseGateway
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    legacy_module = importlib.import_module("autobuy")
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": True, "data": {"successCount": 2}})),
        ]
    )

    async def fake_get_global_session(self, force_new: bool = False):
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "get_global_session", fake_get_global_session)
    monkeypatch.setattr(legacy_module.GLOBAL_XSIGN_WRAPPER, "generate", lambda **kwargs: "fake-sign")
    gateway = LegacyPurchaseGateway(legacy_module=legacy_module)

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "success"
    assert result.purchased_count == 2
    assert session.calls[0]["url"].endswith("/support/trade/order/buy/v2/create")
    assert session.calls[0]["json"]["productId"] == "1380979899390261111"
    assert session.calls[0]["json"]["receiveSteamId"] == "steam-1"
    assert session.calls[1]["url"].endswith("/pay/order/v1/pay")
    assert session.calls[1]["json"]["receiveSteamId"] == "steam-1"
    assert session.calls[1]["headers"]["x-sign"] == "fake-sign"


async def test_legacy_purchase_gateway_maps_not_login_to_auth_invalid(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.legacy_purchase_gateway import LegacyPurchaseGateway
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    legacy_module = importlib.import_module("autobuy")
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": False, "errorMsg": "Not login"})),
        ]
    )

    async def fake_get_global_session(self, force_new: bool = False):
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "get_global_session", fake_get_global_session)
    monkeypatch.setattr(legacy_module.GLOBAL_XSIGN_WRAPPER, "generate", lambda **kwargs: "fake-sign")
    gateway = LegacyPurchaseGateway(legacy_module=legacy_module)

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "auth_invalid"
    assert result.purchased_count == 0
    assert "Not login" in str(result.error)
