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


async def test_query_item_scheduler_round_robins_items_within_scheduler_instance():
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


async def test_query_item_scheduler_instances_do_not_share_cooldown_state():
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler

    scheduler_a = QueryItemScheduler(
        [build_item("item-1")],
        min_cooldown_seconds=0.1,
    )
    scheduler_b = QueryItemScheduler(
        [build_item("item-1")],
        min_cooldown_seconds=0.1,
    )

    first_a = await scheduler_a.reserve_next(now=10.0)
    first_b = await scheduler_b.reserve_next(now=10.0)
    second_a = await scheduler_a.reserve_next(now=10.0)

    assert first_a is not None
    assert first_b is not None
    assert second_a is not None
    assert first_a.execute_at == 10.0
    assert first_b.execute_at == 10.0
    assert second_a.execute_at == 10.1


async def test_query_item_scheduler_uses_dynamic_cooldown_when_one_item_has_multiple_assigned_workers():
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler

    item = build_item("item-1")
    scheduler = QueryItemScheduler(
        [item],
        min_cooldown_seconds=0.1,
    )

    first = await scheduler.reserve_item(
        item,
        now=10.0,
        actual_assigned_count=2,
    )
    second = await scheduler.reserve_item(
        item,
        now=10.0,
        actual_assigned_count=2,
    )

    assert first.execute_at == 10.0
    assert second.execute_at == 10.25


async def test_query_item_scheduler_uses_global_item_pacing_fixed_seconds_for_dynamic_cooldown():
    from app_backend.domain.models.runtime_settings import QueryItemPacingSetting
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler

    item = build_item("item-1")
    scheduler = QueryItemScheduler(
        [item],
        min_cooldown_seconds=0.1,
        item_pacing=QueryItemPacingSetting(
            mode_type="new_api",
            strategy="fixed_divided_by_actual_allocated_workers",
            fixed_seconds=2.0,
        ),
    )

    first = await scheduler.reserve_item(
        item,
        now=10.0,
        actual_assigned_count=4,
    )
    second = await scheduler.reserve_item(
        item,
        now=10.0,
        actual_assigned_count=4,
    )

    assert first.execute_at == 10.0
    assert second.execute_at == 10.5
