from __future__ import annotations

import importlib
import json

from app_backend.domain.models.account import Account


def build_account() -> Account:
    return Account(
        account_id="a1",
        default_name="account-a1",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
        c5_user_id="10001",
        c5_nick_name="test-account",
        cookie_raw="foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D",
        purchase_capability_state="bound",
        purchase_pool_state="active",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
        disabled=False,
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


async def test_legacy_inventory_refresh_gateway_fetches_preview_inventories(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.legacy_inventory_refresh_gateway import (
        LegacyInventoryRefreshGateway,
    )
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    legacy_module = importlib.import_module("autobuy")
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

    async def fake_get_global_session(self, force_new: bool = False):
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "get_global_session", fake_get_global_session)
    monkeypatch.setattr(legacy_module.GLOBAL_XSIGN_WRAPPER, "generate", lambda **kwargs: "fake-sign")
    gateway = LegacyInventoryRefreshGateway(legacy_module=legacy_module)

    result = await gateway.refresh(account=build_account())

    assert result.status == "success"
    assert result.error is None
    assert [item["steamId"] for item in result.inventories] == ["steam-1", "steam-2"]
    assert session.calls[0]["url"].endswith("/support/trade/product/batch/v1/preview/1380979899390267393")
    assert session.calls[0]["json"] == {"itemId": "1380979899390267393"}
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
    assert session.calls[0]["headers"]["x-access-token"] == "token-1"
    assert session.calls[0]["headers"]["x-device-id"] == "device-1"


async def test_legacy_inventory_refresh_gateway_maps_not_login_to_auth_invalid(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.legacy_inventory_refresh_gateway import (
        LegacyInventoryRefreshGateway,
    )
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
    gateway = LegacyInventoryRefreshGateway(legacy_module=legacy_module)

    result = await gateway.refresh(account=build_account())

    assert result.status == "auth_invalid"
    assert result.inventories == []
    assert "Not login" in str(result.error)
