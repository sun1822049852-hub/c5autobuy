from __future__ import annotations

import json

from app_backend.domain.models.account import Account


def build_account(account_id: str, *, cookie_raw: str) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw=cookie_raw,
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-17T00:00:00",
        updated_at="2026-03-17T00:00:00",
        disabled=False,
        new_api_enabled=True,
        fast_api_enabled=True,
        token_enabled=True,
    )


class FakeSelector:
    def __init__(self, accounts: list[Account]) -> None:
        self._accounts = list(accounts)
        self.calls = 0

    def build_attempt_order(self) -> list[Account]:
        self.calls += 1
        return list(self._accounts)


class FakeSigner:
    def __init__(self, *, result: str = "fake-sign") -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self._result


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
    def __init__(self, *, post_responses: list[object], get_responses: list[object]) -> None:
        self.closed = False
        self.post_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []
        self._post_responses = list(post_responses)
        self._get_responses = list(get_responses)

    def post(self, **kwargs):
        self.post_calls.append(kwargs)
        response = self._post_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            status, text = response
            return FakeResponse(status=status, text=text)
        return response

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        response = self._get_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            status, text = response
            return FakeResponse(status=status, text=text)
        return response


class FakeRuntimeAccount:
    def __init__(self, account: Account, session: FakeSession | None) -> None:
        self.account = account
        self._session = session

    def get_x_access_token(self) -> str | None:
        return self._cookie_value("NC5_accessToken")

    def get_x_device_id(self) -> str | None:
        return self._cookie_value("NC5_deviceId")

    def get_cookie_header_exact(self) -> str:
        return self.account.cookie_raw or ""

    async def get_global_session(self, force_new: bool = False):
        return self._session

    def _cookie_value(self, key: str) -> str | None:
        for raw_part in (self.account.cookie_raw or "").split(";"):
            current_key, _, value = raw_part.strip().partition("=")
            if current_key == key and value:
                return value
        return None


async def test_product_detail_fetcher_merges_preview_and_market_hash_name():
    from app_backend.infrastructure.query.collectors.product_detail_fetcher import ProductDetailFetcher

    item_id = "1380979899390267393"
    product_url = f"https://www.c5game.com/csgo/730/asset/{item_id}"
    account = build_account(
        "a1",
        cookie_raw="foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D",
    )
    session = FakeSession(
        post_responses=[
            (
                200,
                json.dumps(
                    {
                        "success": True,
                        "data": {
                            "wearRange": [
                                {"start": 0.1, "end": 0.3},
                                {"start": 0.3, "end": 0.7},
                            ],
                            "minPrice": 123.45,
                            "itemName": "AK-47 | Redline",
                        },
                    }
                ),
            )
        ],
        get_responses=[
            (
                200,
                json.dumps(
                    {
                        "success": True,
                        "data": {
                            "list": [
                                {
                                    "itemName": "AK-47 | Redline",
                                    "marketHashName": "AK-47 | Redline (Field-Tested)",
                                    "itemInfo": {},
                                }
                            ]
                        },
                    }
                ),
            )
        ],
    )
    signer = FakeSigner()
    fetcher = ProductDetailFetcher(
        selector=FakeSelector([account]),
        xsign_wrapper=signer,
        runtime_account_factory=lambda current: FakeRuntimeAccount(current, session),
    )

    detail = await fetcher.fetch(external_item_id=item_id, product_url=product_url)

    assert detail["external_item_id"] == item_id
    assert detail["product_url"] == product_url
    assert detail["item_name"] == "AK-47 | Redline"
    assert detail["market_hash_name"] == "AK-47 | Redline (Field-Tested)"
    assert detail["min_wear"] == 0.1
    assert detail["max_wear"] == 0.7
    assert detail["last_market_price"] == 123.45
    assert signer.calls[0]["path"] == f"support/trade/product/batch/v1/preview/{item_id}"
    assert signer.calls[0]["method"] == "POST"
    assert signer.calls[1]["path"] == f"search/v2/sell/{item_id}/list"
    assert signer.calls[1]["method"] == "GET"
    assert session.post_calls[0]["json"] == {"itemId": item_id}
    assert session.post_calls[0]["headers"]["Referer"] == product_url
    assert session.post_calls[0]["headers"]["x-access-token"] == "token-1"
    assert session.post_calls[0]["headers"]["x-device-id"] == "device-1"
    assert session.get_calls[0]["params"] == {"itemId": item_id, "page": 1, "limit": 10}
    assert session.get_calls[0]["headers"]["Referer"] == product_url


async def test_product_detail_fetcher_switches_to_next_account_after_request_failure():
    from app_backend.infrastructure.query.collectors.product_detail_fetcher import ProductDetailFetcher

    item_id = "1380979899390267393"
    product_url = f"https://www.c5game.com/csgo/730/asset/{item_id}"
    first_account = build_account(
        "a1",
        cookie_raw="NC5_accessToken=token-1; NC5_deviceId=device-1",
    )
    second_account = build_account(
        "a2",
        cookie_raw="NC5_accessToken=token-2; NC5_deviceId=device-2",
    )
    first_session = FakeSession(
        post_responses=[RaisingResponse(RuntimeError("network down"))],
        get_responses=[],
    )
    second_session = FakeSession(
        post_responses=[
            (
                200,
                json.dumps(
                    {
                        "success": True,
                        "data": {
                            "wearRange": [{"start": 0.0, "end": 0.8}],
                            "minPrice": 88.0,
                            "itemName": "M4A1-S | Printstream",
                        },
                    }
                ),
            )
        ],
        get_responses=[
            (
                200,
                json.dumps(
                    {
                        "success": True,
                        "data": {
                            "list": [
                                {
                                    "itemName": "M4A1-S | Printstream",
                                    "marketHashName": "M4A1-S | Printstream (Field-Tested)",
                                    "itemInfo": {},
                                }
                            ]
                        },
                    }
                ),
            )
        ],
    )
    sessions = {
        "a1": first_session,
        "a2": second_session,
    }
    fetcher = ProductDetailFetcher(
        selector=FakeSelector([first_account, second_account]),
        xsign_wrapper=FakeSigner(),
        runtime_account_factory=lambda current: FakeRuntimeAccount(current, sessions[current.account_id]),
    )

    detail = await fetcher.fetch(external_item_id=item_id, product_url=product_url)

    assert detail["item_name"] == "M4A1-S | Printstream"
    assert detail["market_hash_name"] == "M4A1-S | Printstream (Field-Tested)"
    assert len(first_session.post_calls) == 1
    assert second_session.post_calls[0]["headers"]["x-access-token"] == "token-2"
    assert len(second_session.get_calls) == 1
