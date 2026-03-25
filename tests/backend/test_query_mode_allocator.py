from __future__ import annotations

from app_backend.domain.enums.query_modes import QueryMode
from app_backend.domain.models.query_config import QueryItem, QueryItemModeAllocation


def build_item(
    item_id: str,
    *,
    target_new_api: int = 0,
    manual_paused: bool = False,
) -> QueryItem:
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
        manual_paused=manual_paused,
        mode_allocations=[
            QueryItemModeAllocation(
                mode_type=mode_type,
                target_dedicated_count=(target_new_api if mode_type == QueryMode.NEW_API else 0),
            )
            for mode_type in QueryMode.ALL
        ],
        sort_order=0,
        created_at="2026-03-19T10:00:00",
        updated_at="2026-03-19T10:00:00",
    )


class FakeWorker:
    def __init__(self, account_id: str) -> None:
        self.account = type("AccountRef", (), {"account_id": account_id})()


async def test_query_mode_allocator_prefers_dedicated_workers_and_skips_manual_paused_items():
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler
    from app_backend.infrastructure.query.runtime.query_mode_allocator import QueryModeAllocator

    dedicated_item = build_item("item-1", target_new_api=1)
    shared_item = build_item("item-2", target_new_api=0)
    paused_item = build_item("item-3", target_new_api=1, manual_paused=True)
    workers = [FakeWorker("a1"), FakeWorker("a2")]
    allocator = QueryModeAllocator(
        QueryMode.NEW_API,
        [dedicated_item, shared_item, paused_item],
        query_item_scheduler=QueryItemScheduler(
            [dedicated_item, shared_item, paused_item],
            min_cooldown_seconds=0.1,
        ),
    )

    first = await allocator.reserve_next(workers[0], active_workers=workers, now=10.0)
    second = await allocator.reserve_next(workers[1], active_workers=workers, now=10.0)
    snapshot = allocator.snapshot(active_workers=workers)
    rows = {
        row["query_item_id"]: row
        for row in snapshot["item_rows"]
    }

    assert first is not None
    assert second is not None
    assert first.query_item.query_item_id == "item-1"
    assert second.query_item.query_item_id == "item-2"
    assert rows["item-1"]["status"] == "dedicated"
    assert rows["item-1"]["status_message"] == "专属中 1/1"
    assert rows["item-1"]["actual_dedicated_count"] == 1
    assert rows["item-2"]["status"] == "shared"
    assert rows["item-2"]["status_message"] == "共享中"
    assert rows["item-3"]["status"] == "manual_paused"
    assert rows["item-3"]["status_message"] == "手动暂停"


async def test_query_mode_allocator_degrades_zero_dedicated_item_into_shared_pool_and_recovers_when_capacity_is_enough():
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler
    from app_backend.infrastructure.query.runtime.query_mode_allocator import QueryModeAllocator

    exclusive_item = build_item("item-1", target_new_api=2)
    shared_item = build_item("item-2", target_new_api=0)
    allocator = QueryModeAllocator(
        QueryMode.NEW_API,
        [exclusive_item, shared_item],
        query_item_scheduler=QueryItemScheduler(
            [exclusive_item, shared_item],
            min_cooldown_seconds=0.1,
        ),
    )

    full_workers = [FakeWorker("a1"), FakeWorker("a2"), FakeWorker("a3")]
    full_snapshot = allocator.snapshot(active_workers=full_workers)
    full_rows = {
        row["query_item_id"]: row
        for row in full_snapshot["item_rows"]
    }
    assert full_rows["item-1"]["status"] == "dedicated"
    assert full_rows["item-1"]["actual_dedicated_count"] == 2
    assert full_rows["item-2"]["status"] == "shared"

    degraded_workers = [FakeWorker("a3")]
    first = await allocator.reserve_next(degraded_workers[0], active_workers=degraded_workers, now=20.0)
    second = await allocator.reserve_next(degraded_workers[0], active_workers=degraded_workers, now=20.0)
    degraded_snapshot = allocator.snapshot(active_workers=degraded_workers)
    degraded_rows = {
        row["query_item_id"]: row
        for row in degraded_snapshot["item_rows"]
    }

    assert first is not None
    assert second is not None
    assert first.query_item.query_item_id == "item-1"
    assert second.query_item.query_item_id == "item-2"
    assert degraded_rows["item-1"]["status"] == "shared"
    assert degraded_rows["item-1"]["status_message"] == "共享中"
    assert degraded_rows["item-1"]["actual_dedicated_count"] == 0

    recovered_workers = [FakeWorker("a4"), FakeWorker("a5")]
    recovered_snapshot = allocator.snapshot(active_workers=recovered_workers)
    recovered_rows = {
        row["query_item_id"]: row
        for row in recovered_snapshot["item_rows"]
    }

    assert recovered_rows["item-1"]["status"] == "shared"
    assert recovered_rows["item-1"]["status_message"] == "共享中"
    assert recovered_rows["item-1"]["actual_dedicated_count"] == 0
    assert recovered_rows["item-2"]["status"] == "shared"


async def test_query_mode_allocator_applies_manual_actual_count_targets_by_releasing_before_reassigning():
    from app_backend.infrastructure.query.runtime.query_item_scheduler import QueryItemScheduler
    from app_backend.infrastructure.query.runtime.query_mode_allocator import QueryModeAllocator

    first_item = build_item("item-1", target_new_api=2)
    second_item = build_item("item-2", target_new_api=0)
    workers = [FakeWorker("a1"), FakeWorker("a2")]
    allocator = QueryModeAllocator(
        QueryMode.NEW_API,
        [first_item, second_item],
        query_item_scheduler=QueryItemScheduler(
            [first_item, second_item],
            min_cooldown_seconds=0.1,
        ),
    )

    initial_snapshot = allocator.snapshot(active_workers=workers)
    allocator.apply_target_actual_counts(
        target_actual_counts={
            "item-1": 1,
            "item-2": 1,
        },
        active_workers=workers,
    )
    adjusted_snapshot = allocator.snapshot(active_workers=workers)
    adjusted_rows = {
        row["query_item_id"]: row
        for row in adjusted_snapshot["item_rows"]
    }

    assert initial_snapshot["item_rows"][0]["actual_dedicated_count"] == 2
    assert adjusted_rows["item-1"]["actual_dedicated_count"] == 1
    assert adjusted_rows["item-1"]["status"] == "dedicated"
    assert adjusted_rows["item-2"]["actual_dedicated_count"] == 1
    assert adjusted_rows["item-2"]["status"] == "dedicated"
    assert adjusted_rows["item-1"]["shared_available_count"] == 0
    assert adjusted_rows["item-2"]["shared_available_count"] == 0
