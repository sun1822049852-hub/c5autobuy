from app_backend.infrastructure.purchase.runtime.purchase_scheduler import PurchaseScheduler
from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch


def build_batch(name: str = "AK") -> PurchaseHitBatch:
    return PurchaseHitBatch(
        query_item_name=name,
        product_list=[{"productId": "1", "price": 123.45}],
        total_price=123.45,
        total_wear_sum=0.1234,
        source_mode_type="token",
    )


def test_purchase_scheduler_dispatches_hit_directly_to_ready_account():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=True)

    status = scheduler.submit(build_batch("AK"))

    assert status == "dispatched"
    assert scheduler.queue_size() == 1
    account_id, batch = scheduler.claim_next_dispatch()
    assert account_id == "a1"
    assert batch.query_item_name == "AK"
    assert scheduler.account_status("a1")["busy"] is True


def test_purchase_scheduler_queues_hit_when_no_ready_account_exists():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=True)
    scheduler.submit(build_batch("AK"))
    scheduler.claim_next_dispatch()

    status = scheduler.submit(build_batch("M4A1"))

    assert status == "queued"
    assert scheduler.queue_size() == 1
    assert scheduler.pending_queue_size() == 1


def test_purchase_scheduler_completion_immediately_dispatches_next_pending_hit():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=True)
    scheduler.submit(build_batch("AK"))
    scheduler.claim_next_dispatch()
    scheduler.submit(build_batch("M4A1"))

    dispatched = scheduler.finish_account("a1")

    assert dispatched is True
    account_id, batch = scheduler.claim_next_dispatch()
    assert account_id == "a1"
    assert batch.query_item_name == "M4A1"
    assert scheduler.pending_queue_size() == 0


def test_purchase_scheduler_returns_account_to_ready_pool_when_no_pending_hit_exists():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=True)
    scheduler.submit(build_batch("AK"))
    scheduler.claim_next_dispatch()

    dispatched = scheduler.finish_account("a1")

    assert dispatched is False
    assert scheduler.ready_account_ids() == ["a1"]
    assert scheduler.account_status("a1")["busy"] is False


def test_purchase_scheduler_removes_account_from_pool_without_dropping_registration():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=True)

    scheduler.mark_no_inventory("a1")

    assert scheduler.available_account_ids() == []
    assert scheduler.ready_account_ids() == []
    assert scheduler.account_status("a1")["available"] is False
    assert scheduler.account_status("a1")["disabled_reason"] == "no_available_inventory"


def test_purchase_scheduler_recovery_assigns_pending_hit_before_rejoining_ready_pool():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=False)
    scheduler.submit(build_batch("AK"))

    scheduler.mark_inventory_recovered("a1")

    account_id, batch = scheduler.claim_next_dispatch()
    assert account_id == "a1"
    assert batch.query_item_name == "AK"
    assert scheduler.ready_account_ids() == []


def test_purchase_scheduler_can_clear_backlog_batches():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=True)
    scheduler.submit(build_batch("AK"))
    scheduler.submit(build_batch("M4A1"))

    cleared = scheduler.clear_queue()

    assert cleared == 2
    assert scheduler.queue_size() == 0
