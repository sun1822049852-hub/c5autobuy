from __future__ import annotations

from app_backend.domain.models.query_config import QueryItem


def build_item(item_id: str) -> QueryItem:
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
        created_at="2026-03-17T10:00:00",
        updated_at="2026-03-17T10:00:00",
    )


async def test_query_item_scheduler_round_robins_items_globally():
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler

    scheduler = QueryItemScheduler(
        [build_item("item-1"), build_item("item-2")],
        min_cooldown_seconds=0.1,
    )

    first = await scheduler.reserve_next(now=10.0)
    second = await scheduler.reserve_next(now=10.0)
    third = await scheduler.reserve_next(now=10.0)

    assert first is not None
    assert second is not None
    assert third is not None
    assert first.query_item.query_item_id == "item-1"
    assert second.query_item.query_item_id == "item-2"
    assert third.query_item.query_item_id == "item-1"


async def test_query_item_scheduler_delays_repeated_item_until_cooldown():
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler

    scheduler = QueryItemScheduler(
        [build_item("item-1")],
        min_cooldown_seconds=0.1,
    )

    first = await scheduler.reserve_next(now=10.0)
    second = await scheduler.reserve_next(now=10.0)

    assert first is not None
    assert second is not None
    assert first.query_item.query_item_id == "item-1"
    assert first.execute_at == 10.0
    assert second.query_item.query_item_id == "item-1"
    assert second.execute_at == 10.1
