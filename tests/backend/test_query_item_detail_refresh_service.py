from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app_backend.domain.models.query_config import QueryConfig, QueryItem, QueryModeSetting
from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetail


def build_item(
    query_item_id: str,
    *,
    external_item_id: str,
    last_detail_sync_at: str | None,
    min_wear: float | None = 0.0,
    max_wear: float | None = 0.7,
    detail_min_wear: float | None = 0.0,
    detail_max_wear: float | None = 0.25,
    max_price: float | None = 199.0,
    last_market_price: float | None = 90.0,
) -> QueryItem:
    return QueryItem(
        query_item_id=query_item_id,
        config_id="cfg-1",
        product_url=f"https://www.c5game.com/csgo/730/asset/{external_item_id}",
        external_item_id=external_item_id,
        item_name=f"商品-{query_item_id}",
        market_hash_name=f"Hash-{query_item_id}",
        min_wear=min_wear,
        max_wear=max_wear,
        detail_min_wear=detail_min_wear,
        detail_max_wear=detail_max_wear,
        max_price=max_price,
        last_market_price=last_market_price,
        last_detail_sync_at=last_detail_sync_at,
        sort_order=int(query_item_id.split("-")[-1]),
        created_at="2026-03-17T00:00:00",
        updated_at="2026-03-17T00:00:00",
    )


def build_config(items: list[QueryItem]) -> QueryConfig:
    return QueryConfig(
        config_id="cfg-1",
        name="白天配置",
        description="desc",
        enabled=True,
        created_at="2026-03-17T00:00:00",
        updated_at="2026-03-17T00:00:00",
        items=items,
        mode_settings=[
            QueryModeSetting(
                mode_setting_id="m1",
                config_id="cfg-1",
                mode_type="new_api",
                enabled=True,
                window_enabled=False,
                start_hour=0,
                start_minute=0,
                end_hour=0,
                end_minute=0,
                base_cooldown_min=0.0,
                base_cooldown_max=0.0,
                random_delay_enabled=False,
                random_delay_min=0.0,
                random_delay_max=0.0,
                created_at="2026-03-17T00:00:00",
                updated_at="2026-03-17T00:00:00",
            )
        ],
    )


class FakeQueryConfigRepository:
    def __init__(self, config: QueryConfig) -> None:
        self._config = config
        self.updated_calls: list[dict[str, object]] = []

    def get_config(self, config_id: str) -> QueryConfig | None:
        if config_id == self._config.config_id:
            return self._config
        return None

    def update_item_detail(
        self,
        query_item_id: str,
        *,
        item_name: str | None,
        market_hash_name: str | None,
        min_wear: float | None,
        max_wear: float | None,
        last_market_price: float | None,
        last_detail_sync_at: str,
    ) -> QueryItem:
        self.updated_calls.append(
            {
                "query_item_id": query_item_id,
                "item_name": item_name,
                "market_hash_name": market_hash_name,
                "min_wear": min_wear,
                "max_wear": max_wear,
                "last_market_price": last_market_price,
                "last_detail_sync_at": last_detail_sync_at,
            }
        )
        for item in self._config.items:
            if item.query_item_id != query_item_id:
                continue
            item.item_name = item_name
            item.market_hash_name = market_hash_name
            item.min_wear = min_wear
            item.max_wear = max_wear
            item.last_market_price = last_market_price
            item.last_detail_sync_at = last_detail_sync_at
            return item
        raise KeyError(query_item_id)


class FakeCollector:
    def __init__(self, payloads: dict[str, ProductDetail | Exception]) -> None:
        self._payloads = dict(payloads)
        self.calls: list[str] = []

    async def fetch_detail(self, *, external_item_id: str, product_url: str) -> ProductDetail:
        self.calls.append(external_item_id)
        payload = self._payloads[external_item_id]
        if isinstance(payload, Exception):
            raise payload
        return payload


@pytest.mark.asyncio
async def test_refresh_service_marks_items_without_sync_time_or_older_than_12_hours_as_stale():
    from app_backend.infrastructure.query.refresh.query_item_detail_refresh_service import QueryItemDetailRefreshService

    now = datetime(2026, 3, 17, 12, 0, 0)
    repository = FakeQueryConfigRepository(
        build_config(
            [
                build_item("item-1", external_item_id="1001", last_detail_sync_at=None),
                build_item(
                    "item-2",
                    external_item_id="1002",
                    last_detail_sync_at=(now - timedelta(hours=13)).isoformat(timespec="seconds"),
                ),
                build_item(
                    "item-3",
                    external_item_id="1003",
                    last_detail_sync_at=(now - timedelta(hours=2)).isoformat(timespec="seconds"),
                ),
            ]
        )
    )
    collector = FakeCollector(
        {
            "1001": ProductDetail("1001", "https://example.com/1001", "商品1", "Hash1", 0.1, 0.7, 101.0),
            "1002": ProductDetail("1002", "https://example.com/1002", "商品2", "Hash2", 0.2, 0.8, 202.0),
        }
    )
    service = QueryItemDetailRefreshService(
        repository=repository,
        collector=collector,
        now_provider=lambda: now,
    )

    summary = await service.prepare(config_id="cfg-1")

    assert summary["updated_count"] == 2
    assert summary["skipped_count"] == 1
    assert summary["failed_count"] == 0
    assert [item["status"] for item in summary["items"]] == ["updated", "updated", "skipped"]
    assert collector.calls == ["1001", "1002"]
    assert len(repository.updated_calls) == 2


@pytest.mark.asyncio
async def test_refresh_service_force_refresh_updates_all_items():
    from app_backend.infrastructure.query.refresh.query_item_detail_refresh_service import QueryItemDetailRefreshService

    now = datetime(2026, 3, 17, 12, 0, 0)
    repository = FakeQueryConfigRepository(
        build_config(
            [
                build_item(
                    "item-1",
                    external_item_id="1001",
                    last_detail_sync_at=(now - timedelta(hours=1)).isoformat(timespec="seconds"),
                ),
                build_item(
                    "item-2",
                    external_item_id="1002",
                    last_detail_sync_at=(now - timedelta(hours=2)).isoformat(timespec="seconds"),
                ),
            ]
        )
    )
    collector = FakeCollector(
        {
            "1001": ProductDetail("1001", "https://example.com/1001", "商品1", "Hash1", 0.1, 0.7, 101.0),
            "1002": ProductDetail("1002", "https://example.com/1002", "商品2", "Hash2", 0.2, 0.8, 202.0),
        }
    )
    service = QueryItemDetailRefreshService(
        repository=repository,
        collector=collector,
        now_provider=lambda: now,
    )

    summary = await service.prepare(config_id="cfg-1", force_refresh=True)

    assert summary["updated_count"] == 2
    assert summary["skipped_count"] == 0
    assert collector.calls == ["1001", "1002"]


@pytest.mark.asyncio
async def test_refresh_service_updates_detail_fields_without_overwriting_user_thresholds():
    from app_backend.infrastructure.query.refresh.query_item_detail_refresh_service import QueryItemDetailRefreshService

    now = datetime(2026, 3, 17, 12, 0, 0)
    repository = FakeQueryConfigRepository(
        build_config(
            [
                build_item(
                    "item-1",
                    external_item_id="1001",
                    last_detail_sync_at=(now - timedelta(hours=24)).isoformat(timespec="seconds"),
                    min_wear=0.0,
                    max_wear=0.77,
                    detail_min_wear=0.0,
                    detail_max_wear=0.25,
                    max_price=199.0,
                    last_market_price=80.0,
                )
            ]
        )
    )
    collector = FakeCollector(
        {
            "1001": ProductDetail(
                external_item_id="1001",
                product_url="https://example.com/1001",
                item_name="AK-47 | Redline",
                market_hash_name="AK-47 | Redline (Field-Tested)",
                min_wear=0.11,
                max_wear=0.77,
                last_market_price=123.45,
            )
        }
    )
    service = QueryItemDetailRefreshService(
        repository=repository,
        collector=collector,
        now_provider=lambda: now,
    )

    await service.prepare(config_id="cfg-1")
    item = repository.get_config("cfg-1").items[0]

    assert item.min_wear == 0.11
    assert item.max_wear == 0.77
    assert item.last_market_price == 123.45
    assert item.detail_min_wear == 0.0
    assert item.detail_max_wear == 0.25
    assert item.max_price == 199.0


@pytest.mark.asyncio
async def test_refresh_service_raises_when_no_eligible_account_exists_for_refresh():
    from app_backend.infrastructure.query.refresh.query_item_detail_refresh_service import QueryItemDetailRefreshService

    now = datetime(2026, 3, 17, 12, 0, 0)
    repository = FakeQueryConfigRepository(
        build_config(
            [
                build_item(
                    "item-1",
                    external_item_id="1001",
                    last_detail_sync_at=(now - timedelta(hours=24)).isoformat(timespec="seconds"),
                )
            ]
        )
    )
    collector = FakeCollector(
        {
            "1001": ValueError("没有可用于商品信息补全的已登录账号"),
        }
    )
    service = QueryItemDetailRefreshService(
        repository=repository,
        collector=collector,
        now_provider=lambda: now,
    )

    with pytest.raises(ValueError, match="没有可用于商品信息补全的已登录账号"):
        await service.prepare(config_id="cfg-1")


@pytest.mark.asyncio
async def test_refresh_service_refreshes_single_item_without_overwriting_user_thresholds():
    from app_backend.infrastructure.query.refresh.query_item_detail_refresh_service import QueryItemDetailRefreshService

    now = datetime(2026, 3, 17, 12, 0, 0)
    repository = FakeQueryConfigRepository(
        build_config(
            [
                build_item(
                    "item-1",
                    external_item_id="1001",
                    last_detail_sync_at=(now - timedelta(hours=24)).isoformat(timespec="seconds"),
                    min_wear=0.0,
                    max_wear=0.7,
                    detail_min_wear=0.0,
                    detail_max_wear=0.25,
                    max_price=199.0,
                    last_market_price=90.0,
                ),
                build_item(
                    "item-2",
                    external_item_id="1002",
                    last_detail_sync_at=(now - timedelta(hours=1)).isoformat(timespec="seconds"),
                    min_wear=0.1,
                    max_wear=0.8,
                    detail_min_wear=0.1,
                    detail_max_wear=0.35,
                    max_price=299.0,
                    last_market_price=190.0,
                ),
            ]
        )
    )
    collector = FakeCollector(
        {
            "1001": ProductDetail(
                external_item_id="1001",
                product_url="https://example.com/1001",
                item_name="AK-47 | Vulcan",
                market_hash_name="AK-47 | Vulcan (Field-Tested)",
                min_wear=0.12,
                max_wear=0.79,
                last_market_price=321.0,
            )
        }
    )
    service = QueryItemDetailRefreshService(
        repository=repository,
        collector=collector,
        now_provider=lambda: now,
    )

    item = await service.refresh_item(config_id="cfg-1", query_item_id="item-1")

    assert collector.calls == ["1001"]
    assert item.query_item_id == "item-1"
    assert item.item_name == "AK-47 | Vulcan"
    assert item.market_hash_name == "AK-47 | Vulcan (Field-Tested)"
    assert item.min_wear == 0.12
    assert item.max_wear == 0.79
    assert item.last_market_price == 321.0
    assert item.detail_min_wear == 0.0
    assert item.detail_max_wear == 0.25
    assert item.max_price == 199.0
    assert repository.get_config("cfg-1").items[1].item_name == "商品-item-2"
