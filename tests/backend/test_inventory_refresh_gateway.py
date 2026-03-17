from __future__ import annotations

import asyncio
import json

import pytest

from app_backend.domain.models.account import Account


def build_account(
    *,
    cookie_raw: str = "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D",
) -> Account:
    return Account(
        account_id="a1",
        default_name="account-a1",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
        c5_user_id="10001",
        c5_nick_name="test-account",
        cookie_raw=cookie_raw,
        purchase_capability_state="bound",
        purchase_pool_state="active",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        disabled=False,
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


async def _build_gateway(monkeypatch, *, session, signer: FakeSigner):
    from app_backend.infrastructure.purchase.runtime.inventory_refresh_gateway import (
        InventoryRefreshGateway,
    )
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    async def fake_get_global_session(self, force_new: bool = False):
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "get_global_session", fake_get_global_session)
    return InventoryRefreshGateway(xsign_wrapper=signer)


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_fetches_preview_inventories(monkeypatch):
    session = FakeSession(
        responses=[
            (
                200,
                json.dumps(
                    {
                        "success": True,
                        "data": {
                            "receiveSteamList": [
                                {
                                    "nickname": "alpha",
                                    "steamId": "steam-1",
                                    "avatar": "https://example.com/1.png",
                                    "inventoryNum": 920,
                                    "inventoryMaxNum": 1000,
                                    "status": 0,
                                    "type": 1,
                                },
                                {
                                    "nickname": "beta",
                                    "steamId": "steam-2",
                                    "avatar": "https://example.com/2.png",
                                    "inventoryNum": 880,
                                    "inventoryMaxNum": 1000,
                                    "status": 0,
                                    "type": 1,
                                },
                            ]
                        },
                    }
                ),
            ),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.refresh(account=build_account())

    assert result.status == "success"
    assert result.error is None
    assert [item["steamId"] for item in result.inventories] == ["steam-1", "steam-2"]


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_returns_auth_invalid_when_cookie_missing_auth_fields(monkeypatch):
    session = FakeSession(responses=[])
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.refresh(account=build_account(cookie_raw="foo=bar"))

    assert result.status == "auth_invalid"
    assert result.error == "Not login"


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_returns_auth_invalid_when_session_missing(monkeypatch):
    gateway = await _build_gateway(monkeypatch, session=None, signer=FakeSigner(result="fake-sign"))

    result = await gateway.refresh(account=build_account())

    assert result.status == "auth_invalid"
    assert result.error == "Not login"


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_maps_not_login_to_auth_invalid(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": False, "errorMsg": "Not login"})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.refresh(account=build_account())

    assert result.status == "auth_invalid"
    assert "Not login" in str(result.error)


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_maps_403_to_auth_invalid(monkeypatch):
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": False, "errorMsg": "403 forbidden"})),
        ]
    )
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.refresh(account=build_account())

    assert result.status == "auth_invalid"
    assert "403" in str(result.error)


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_returns_xsign_error_text(monkeypatch):
    session = FakeSession(responses=[])
    gateway = await _build_gateway(
        monkeypatch,
        session=session,
        signer=FakeSigner(error=RuntimeError("boom")),
    )

    result = await gateway.refresh(account=build_account())

    assert result.status == "error"
    assert result.error == "x-sign生成失败: boom"


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_returns_timeout_text(monkeypatch):
    session = FakeSession(responses=[RaisingResponse(asyncio.TimeoutError())])
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.refresh(account=build_account())

    assert result.status == "error"
    assert result.error == "请求超时"


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_returns_request_failed_text(monkeypatch):
    session = FakeSession(responses=[RaisingResponse(RuntimeError("network down"))])
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.refresh(account=build_account())

    assert result.status == "error"
    assert result.error == "请求失败: network down"


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_returns_invalid_json_text(monkeypatch):
    session = FakeSession(responses=[(200, "{")])
    gateway = await _build_gateway(monkeypatch, session=session, signer=FakeSigner(result="fake-sign"))

    result = await gateway.refresh(account=build_account())

    assert result.status == "error"
    assert result.error == "响应不是有效的JSON格式"


@pytest.mark.asyncio
async def test_inventory_refresh_gateway_keeps_legacy_preview_request_shape(monkeypatch):
    session = FakeSession(
        responses=[
            (
                200,
                json.dumps(
                    {
                        "success": True,
                        "data": {"receiveSteamList": []},
                    }
                ),
            ),
        ]
    )
    signer = FakeSigner(result="fake-sign")
    gateway = await _build_gateway(monkeypatch, session=session, signer=signer)
    account = build_account()

    result = await gateway.refresh(account=account)

    assert result.status == "success"
    assert session.calls[0]["url"].endswith("/support/trade/product/batch/v1/preview/1380979899390267393")
    assert session.calls[0]["json"] == {"itemId": "1380979899390267393"}
    assert session.calls[0]["headers"]["Cookie"] == account.cookie_raw
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
    assert session.calls[0]["headers"]["x-access-token"] == "token-1"
    assert session.calls[0]["headers"]["x-device-id"] == "device-1"
    assert signer.calls[0]["path"] == "support/trade/product/batch/v1/preview/1380979899390267393"
