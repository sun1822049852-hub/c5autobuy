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


def test_purchase_scheduler_round_robins_across_active_accounts():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=True)
    scheduler.register_account("a2", available=True)

    assert scheduler.select_next_account_id() == "a1"
    assert scheduler.select_next_account_id() == "a2"
    assert scheduler.select_next_account_id() == "a1"


def test_purchase_scheduler_removes_account_from_pool_without_dropping_registration():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=True)

    scheduler.mark_no_inventory("a1")

    assert scheduler.available_account_ids() == []
    assert scheduler.account_status("a1")["available"] is False
    assert scheduler.account_status("a1")["disabled_reason"] == "no_available_inventory"


def test_purchase_scheduler_recovers_account_to_pool():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=False)

    scheduler.mark_inventory_recovered("a1")

    assert scheduler.available_account_ids() == ["a1"]
    assert scheduler.account_status("a1")["available"] is True
    assert scheduler.account_status("a1")["disabled_reason"] is None


def test_purchase_scheduler_queues_batches():
    scheduler = PurchaseScheduler()

    scheduler.submit(build_batch("AK"))
    scheduler.submit(build_batch("M4A1"))

    assert scheduler.queue_size() == 2
    assert scheduler.pop_next_batch().query_item_name == "AK"
    assert scheduler.pop_next_batch().query_item_name == "M4A1"


def test_purchase_scheduler_can_clear_backlog_batches():
    scheduler = PurchaseScheduler()

    scheduler.submit(build_batch("AK"))
    scheduler.submit(build_batch("M4A1"))

    cleared = scheduler.clear_queue()

    assert cleared == 2
    assert scheduler.queue_size() == 0
