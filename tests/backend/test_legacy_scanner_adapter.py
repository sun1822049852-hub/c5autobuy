from __future__ import annotations

from types import SimpleNamespace

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


def test_legacy_scanner_adapter_maps_mode_type_to_legacy_scanner():
    from app_backend.infrastructure.query.runtime.legacy_scanner_adapter import LegacyScannerAdapter

    class FakeNewScanner:
        def __init__(self, account_manager, product_item):
            self.account_manager = account_manager
            self.product_item = product_item

    class FakeFastScanner(FakeNewScanner):
        pass

    class FakeTokenScanner(FakeNewScanner):
        pass

    adapter = LegacyScannerAdapter(
        legacy_module=SimpleNamespace(
            C5MarketAPIScanner=FakeNewScanner,
            C5MarketAPIFastScanner=FakeFastScanner,
            ProductQueryScanner=FakeTokenScanner,
        )
    )

    assert adapter.build_scanner("new_api", account=build_account(), query_item=build_item()).__class__ is FakeNewScanner
    assert adapter.build_scanner("fast_api", account=build_account(), query_item=build_item()).__class__ is FakeFastScanner
    assert adapter.build_scanner("token", account=build_account(), query_item=build_item()).__class__ is FakeTokenScanner


def test_runtime_account_adapter_exposes_legacy_minimum_interface():
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    adapter = RuntimeAccountAdapter(build_account())

    assert adapter.current_user_id == "a1"
    assert adapter.get_api_key() == "api-1"
    assert adapter.has_api_key() is True
    assert adapter.get_x_access_token() == "token-1"
    assert adapter.get_x_device_id() == "device-1"
    assert adapter.get_cookie_header_exact() == "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D"
    assert adapter.get_cookie_header_with_decoded_csrf() == "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc="


async def test_legacy_scanner_adapter_execute_query_accepts_runtime_account_adapter():
    from app_backend.infrastructure.query.runtime.legacy_scanner_adapter import LegacyScannerAdapter
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    class FakeNewScanner:
        def __init__(self, account_manager, product_item):
            self.account_manager = account_manager
            self.product_item = product_item

        async def execute_query(self):
            assert isinstance(self.account_manager, RuntimeAccountAdapter)
            return True, 1, [{"productId": "p1", "price": 88.8, "actRebateAmount": 0}], 88.8, 0.1, None

    adapter = LegacyScannerAdapter(
        legacy_module=SimpleNamespace(
            C5MarketAPIScanner=FakeNewScanner,
            C5MarketAPIFastScanner=FakeNewScanner,
            ProductQueryScanner=FakeNewScanner,
        )
    )

    runtime_account = RuntimeAccountAdapter(build_account())
    result = await adapter.execute_query(
        mode_type="new_api",
        account=runtime_account,
        query_item=build_item(),
    )

    assert result.success is True
    assert result.match_count == 1
