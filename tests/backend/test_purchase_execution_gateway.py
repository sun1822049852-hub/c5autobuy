from __future__ import annotations

import asyncio
import json

import pytest

from app_backend.domain.models.account import Account
from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch


def build_account(
    *,
    cookie_raw: str = "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D",
) -> Account:
    return Account(
        account_id="a1",
        default_name="account-a1",
        remark_name=None,
        browser_proxy_mode="direct",
        browser_proxy_url=None,
        api_proxy_mode="direct",
        api_proxy_url=None,
        api_key=None,
        c5_user_id="10001",
        c5_nick_name="测试账号",
        cookie_raw=cookie_raw,
        purchase_capability_state="bound",
        purchase_pool_state="active",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
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


class FakeSigner:
    def __init__(self, *, result: str | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[dict[str, object]] = []

    def generate(self, *, path: str, method: str, timestamp: str, token: str) -> str:
        self.calls.append(
            {
                "path": path,
                "method": method,
                "timestamp": timestamp,
                "token": token,
            }
        )
        if self._error is not None:
            raise self._error
        return str(self._result)


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


class RaisingResponse:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def __aenter__(self):
        raise self._error

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeSession:
    def __init__(self, responses: list[object]) -> None:
        self.closed = False
        self.calls: list[dict[str, object]] = []
        self._responses = list(responses)

    def post(self, **kwargs):
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            status, text = response
            return FakeResponse(status=status, text=text)
        return response


async def _build_gateway(monkeypatch, *, session: FakeSession, signer: FakeSigner):
    from app_backend.infrastructure.purchase.runtime.purchase_execution_gateway import (
        PurchaseExecutionGateway,
    )
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    async def fake_get_global_session(self, force_new: bool = False):
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "get_global_session", fake_get_global_session)
    return PurchaseExecutionGateway(xsign_wrapper=signer)


@pytest.mark.asyncio
async def test_purchase_execution_gateway_executes_order_then_payment(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": True, "data": {"successCount": 2}})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "success"
    assert result.purchased_count == 2
    assert session.calls[0]["url"].endswith("/support/trade/order/buy/v2/create")
    assert session.calls[1]["url"].endswith("/pay/order/v1/pay")


@pytest.mark.asyncio
async def test_purchase_execution_gateway_returns_stage_latencies_on_success(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": True, "data": {"successCount": 1}})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))
    perf_values = iter([1.0, 1.025, 2.0, 2.045])
    monkeypatch.setattr(
        "app_backend.infrastructure.purchase.runtime.purchase_execution_gateway.time.perf_counter",
        lambda: next(perf_values),
    )

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.submitted_count == 1
    assert result.create_order_latency_ms == 25.0
    assert result.submit_order_latency_ms == 45.0


@pytest.mark.asyncio
async def test_purchase_execution_gateway_keeps_create_order_latency_when_order_creation_fails(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": False, "errorMsg": "库存不足"})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))
    perf_values = iter([1.0, 1.025])
    monkeypatch.setattr(
        "app_backend.infrastructure.purchase.runtime.purchase_execution_gateway.time.perf_counter",
        lambda: next(perf_values),
    )

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "order_failed"
    assert result.submitted_count == 1
    assert result.create_order_latency_ms == 25.0
    assert result.submit_order_latency_ms is None


@pytest.mark.asyncio
async def test_purchase_execution_gateway_keeps_both_stage_latencies_when_payment_fails(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": False, "errorMsg": "余额不足"})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))
    perf_values = iter([1.0, 1.025, 2.0, 2.045])
    monkeypatch.setattr(
        "app_backend.infrastructure.purchase.runtime.purchase_execution_gateway.time.perf_counter",
        lambda: next(perf_values),
    )

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "payment_failed"
    assert result.submitted_count == 1
    assert result.create_order_latency_ms == 25.0
    assert result.submit_order_latency_ms == 45.0


@pytest.mark.asyncio
async def test_purchase_execution_gateway_maps_order_not_login_to_auth_invalid(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": False, "errorMsg": "Not login"})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "auth_invalid"
    assert "Not login" in str(result.error)


@pytest.mark.asyncio
async def test_purchase_execution_gateway_maps_payment_not_login_to_auth_invalid(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": False, "errorMsg": "403 forbidden"})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "auth_invalid"
    assert "403" in str(result.error)


@pytest.mark.asyncio
async def test_purchase_execution_gateway_returns_order_failed_for_regular_order_error(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": False, "errorMsg": "库存不足"})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "order_failed"
    assert "库存不足" in str(result.error)


@pytest.mark.asyncio
async def test_purchase_execution_gateway_returns_payment_failed_for_regular_payment_error(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": False, "errorMsg": "余额不足"})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "payment_failed"
    assert "余额不足" in str(result.error)


@pytest.mark.asyncio
async def test_purchase_execution_gateway_classifies_order_changed_payment_as_item_unavailable(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (409, json.dumps({"success": False, "errorMsg": "订单数据发生变化,请刷新页面重试"})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "item_unavailable"
    assert result.status_code == 409
    assert result.error == "支付失败: 订单数据发生变化,请刷新页面重试"


@pytest.mark.asyncio
async def test_purchase_execution_gateway_returns_payment_success_no_items_when_success_count_zero(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": True, "data": {"successCount": 0}})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "payment_success_no_items"


@pytest.mark.asyncio
async def test_purchase_execution_gateway_returns_xsign_error_text(monkeypatch):
    session = FakeSession(responses=[])
    gateway = await _build_gateway(
        monkeypatch,
        session=session,
        signer=FakeSigner(error=RuntimeError("boom")),
    )

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "order_failed"
    assert "生成x-sign失败: boom" == result.error


@pytest.mark.asyncio
async def test_purchase_execution_gateway_returns_order_timeout_text(monkeypatch):
    session = FakeSession(responses=[RaisingResponse(asyncio.TimeoutError())])
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "order_failed"
    assert result.error == "订单创建请求超时"


@pytest.mark.asyncio
async def test_purchase_execution_gateway_returns_payment_request_failed_text(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            RaisingResponse(RuntimeError("network down")),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "payment_failed"
    assert result.error == "请求失败: network down"


@pytest.mark.asyncio
async def test_purchase_execution_gateway_keeps_legacy_order_body_and_headers(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": True, "data": {"successCount": 1}})),
        ]
    )
    signer = FakeSigner(result="fake-sign")
    gateway = await _build_gateway(monkeypatch, session=session, signer=signer)
    account = build_account()
    batch = build_batch()

    await gateway.execute(
        account=account,
        batch=batch,
        selected_steam_id="steam-1",
    )

    assert session.calls[0]["json"]["productList"] == batch.product_list
    assert session.calls[0]["json"]["price"] == "88.00"
    assert session.calls[0]["json"]["receiveSteamId"] == "steam-1"
    assert session.calls[0]["headers"]["Cookie"] == account.cookie_raw
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
    assert session.calls[0]["headers"]["x-access-token"] == "token-1"
    assert session.calls[0]["headers"]["x-device-id"] == "device-1"
    assert signer.calls[0]["path"] == "support/trade/order/buy/v2/create"


@pytest.mark.asyncio
async def test_purchase_execution_gateway_keeps_legacy_payment_body_and_headers(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": True, "data": {"successCount": 1}})),
        ]
    )
    signer = FakeSigner(result="fake-sign")
    gateway = await _build_gateway(monkeypatch, session=session, signer=signer)

    await gateway.execute(
        account=build_account(),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert session.calls[1]["json"]["bizOrderId"] == "order-1"
    assert session.calls[1]["json"]["payAmount"] == "88.00"
    assert session.calls[1]["json"]["receiveSteamId"] == "steam-1"
    assert session.calls[1]["headers"]["x-sign"] == "fake-sign"
    assert signer.calls[1]["path"] == "pay/order/v1/pay"


@pytest.mark.asyncio
async def test_purchase_execution_gateway_returns_auth_invalid_when_cookie_missing_access_token_or_device_id(
    monkeypatch,
):
    session = FakeSession(responses=[])
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.execute(
        account=build_account(cookie_raw="foo=bar"),
        batch=build_batch(),
        selected_steam_id="steam-1",
    )

    assert result.status == "auth_invalid"
    assert result.error == "Not login"
