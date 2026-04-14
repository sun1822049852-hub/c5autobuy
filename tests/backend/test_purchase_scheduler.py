import tracemalloc
import sys
import types

if "xsign" not in sys.modules:
    xsign_module = types.ModuleType("xsign")

    class _XSignWrapper:  # pragma: no cover - test bootstrap shim
        pass

    xsign_module.XSignWrapper = _XSignWrapper
    sys.modules["xsign"] = xsign_module

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


def test_purchase_scheduler_claims_idle_accounts_per_bucket_limit():
    scheduler = PurchaseScheduler()

    for index in range(2):
        scheduler.register_account(f"b1-{index}", available=True, bucket_key="bucket-1")
    for index in range(3):
        scheduler.register_account(f"b2-{index}", available=True, bucket_key="bucket-2")
    for index in range(6):
        scheduler.register_account(f"b3-{index}", available=True, bucket_key="bucket-3")
    for index in range(8):
        scheduler.register_account(f"b4-{index}", available=True, bucket_key="bucket-4")

    claimed = scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=4)

    assert len(claimed) == 13
    assert sum(1 for account_id in claimed if account_id.startswith("b1-")) == 2
    assert sum(1 for account_id in claimed if account_id.startswith("b2-")) == 3
    assert sum(1 for account_id in claimed if account_id.startswith("b3-")) == 4
    assert sum(1 for account_id in claimed if account_id.startswith("b4-")) == 4
    assert scheduler.account_status("b4-0")["busy"] is True


def test_purchase_scheduler_second_claim_uses_remaining_idle_accounts():
    scheduler = PurchaseScheduler()

    for index in range(6):
        scheduler.register_account(f"b1-{index}", available=True, bucket_key="bucket-1")
    for index in range(8):
        scheduler.register_account(f"b2-{index}", available=True, bucket_key="bucket-2")

    first = scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=4)
    second = scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=4)

    assert len(first) == 8
    assert len(second) == 6
    assert sum(1 for account_id in second if account_id.startswith("b1-")) == 2
    assert sum(1 for account_id in second if account_id.startswith("b2-")) == 4


def test_purchase_scheduler_claim_uses_idle_bucket_registry_instead_of_scanning_global_available_list():
    class GuardedAvailableList:
        def __init__(self, values: list[str]) -> None:
            self._values = list(values)

        def __len__(self) -> int:
            return len(self._values)

        def __contains__(self, item: object) -> bool:
            return item in self._values

        def append(self, value: str) -> None:
            self._values.append(value)

        def remove(self, value: str) -> None:
            self._values.remove(value)

        def index(self, value: str) -> int:
            return self._values.index(value)

        def __iter__(self):
            raise AssertionError("bucket claims should not scan the global available-account list")

        def __getitem__(self, index):
            raise AssertionError("bucket claims should not index into the global available-account list")

    scheduler = PurchaseScheduler()
    scheduler.register_account("b1-a1", available=True, bucket_key="bucket-1")
    scheduler.register_account("b1-a2", available=True, bucket_key="bucket-1")
    scheduler.register_account("b2-a1", available=True, bucket_key="bucket-2")
    scheduler._available_account_ids = GuardedAvailableList(["b1-a1", "b1-a2", "b2-a1"])

    claimed = scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=1)

    assert claimed == ["b1-a1", "b2-a1"]


def test_purchase_scheduler_claim_keeps_temporary_bucket_buffer_small():
    def _build_scheduler() -> PurchaseScheduler:
        scheduler = PurchaseScheduler()
        for index in range(40_000):
            scheduler.register_account(f"a-{index}", available=True)
        return scheduler

    def _measure_peak(action) -> int:
        tracemalloc.start()
        action()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return peak

    scheduler = _build_scheduler()

    def _scan_idle_accounts() -> None:
        for account_id in scheduler._available_account_ids:
            status = scheduler._account_status.get(account_id, {})
            inflight_count = int(status.get("inflight_count", 0) or 0)
            max_inflight = max(int(status.get("max_inflight", 1) or 1), 1)
            if not bool(status.get("available")) or inflight_count >= max_inflight:
                continue
            str(status.get("bucket_key") or "direct")

    scan_peak = _measure_peak(_scan_idle_accounts)

    scheduler = _build_scheduler()
    claimed: list[str] = []

    def _claim_idle_accounts() -> None:
        claimed[:] = scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=1)

    claim_peak = _measure_peak(_claim_idle_accounts)

    assert claimed == ["a-0"]
    # Should not allocate a whole per-bucket account copy beyond the baseline scan noise.
    assert claim_peak - scan_peak < 250_000


def test_purchase_scheduler_allows_multiple_inflight_tasks_per_account_until_capacity():
    scheduler = PurchaseScheduler()
    scheduler.register_account("a1", available=True, max_inflight=3)

    first = scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=1)
    second = scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=1)
    third = scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=1)
    fourth = scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=1)

    assert first == ["a1"]
    assert second == ["a1"]
    assert third == ["a1"]
    assert fourth == []
    assert scheduler.account_status("a1")["inflight_count"] == 3
    assert scheduler.account_status("a1")["busy"] is True

    scheduler.release_account("a1")

    assert scheduler.account_status("a1")["inflight_count"] == 2
    assert scheduler.account_status("a1")["busy"] is False
    assert scheduler.claim_idle_accounts_by_bucket(limit_per_bucket=1) == ["a1"]
