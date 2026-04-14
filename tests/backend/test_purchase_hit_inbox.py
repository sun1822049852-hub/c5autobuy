import threading
import time

from app_backend.infrastructure.purchase.runtime.purchase_hit_inbox import PurchaseHitInbox


def _build_hit(total_wear_sum: float = 0.1234) -> dict[str, object]:
    return {
        "query_item_name": "AK-47",
        "external_item_id": "1380979899390261111",
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
        "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
        "total_price": 88.0,
        "total_wear_sum": total_wear_sum,
        "mode_type": "new_api",
    }


class _ManualClock:
    def __init__(self, start: float = 100.0) -> None:
        self.value = float(start)

    def __call__(self) -> float:
        return float(self.value)


def test_purchase_hit_inbox_forget_batch_allows_same_hit_again():
    inbox = PurchaseHitInbox(cache_duration=5.0, now_provider=time.monotonic)
    hit = _build_hit()

    first = inbox.accept(hit)
    second = inbox.accept(hit)
    inbox.forget_batch(first)
    third = inbox.accept(hit)

    assert first is not None
    assert second is None
    assert third is not None


def test_purchase_hit_inbox_blocks_same_wear_result_for_ten_seconds_by_default():
    clock = _ManualClock()
    inbox = PurchaseHitInbox(now_provider=clock)
    hit = _build_hit()

    first = inbox.accept(hit)
    clock.value += 6.0
    second = inbox.accept(hit)
    clock.value += 4.1
    third = inbox.accept(hit)

    assert first is not None
    assert second is None
    assert third is not None


def test_purchase_hit_inbox_hot_accept_does_not_need_full_cache_iteration():
    class GuardedCache(dict):
        def items(self):  # pragma: no cover - guard should never be touched once optimization lands
            raise AssertionError("hot accept should not iterate the whole dedupe cache")

    clock = _ManualClock()
    inbox = PurchaseHitInbox(now_provider=clock)

    first = inbox.accept(_build_hit(0.1234))
    assert first is not None

    inbox._cache = GuardedCache(inbox._cache)

    second = inbox.accept(_build_hit(0.2234))

    assert second is not None


def test_purchase_hit_inbox_accept_and_forget_are_thread_safe():
    inbox = PurchaseHitInbox(cache_duration=5.0, now_provider=time.monotonic)
    errors: list[BaseException] = []
    stop_event = threading.Event()

    def accept_worker() -> None:
        try:
            while not stop_event.is_set():
                batch = inbox.accept(_build_hit())
                if batch is not None:
                    inbox.forget_batch(batch)
        except BaseException as exc:  # pragma: no cover - concurrency smoke test
            errors.append(exc)

    threads = [threading.Thread(target=accept_worker, daemon=True) for _ in range(4)]
    for thread in threads:
        thread.start()

    time.sleep(0.05)
    stop_event.set()
    for thread in threads:
        thread.join(timeout=1.0)

    assert errors == []


def test_purchase_hit_inbox_builds_batch_outside_dedupe_lock():
    class _BlockingName:
        def __init__(self) -> None:
            self.entered = threading.Event()
            self.release = threading.Event()

        def __str__(self) -> str:
            self.entered.set()
            # Blocks batch field normalization long enough to detect lock scope.
            self.release.wait(timeout=1.0)
            return "AK-47"

    inbox = PurchaseHitInbox(cache_duration=5.0, now_provider=time.monotonic)
    blocking_name = _BlockingName()
    first_hit = _build_hit(0.1234)
    first_hit["query_item_name"] = blocking_name
    second_hit = _build_hit(0.2234)
    second_done = threading.Event()
    errors: list[BaseException] = []

    def first_worker() -> None:
        try:
            inbox.accept(first_hit)
        except BaseException as exc:  # pragma: no cover - concurrency guard
            errors.append(exc)

    def second_worker() -> None:
        try:
            inbox.accept(second_hit)
            second_done.set()
        except BaseException as exc:  # pragma: no cover - concurrency guard
            errors.append(exc)

    first_thread = threading.Thread(target=first_worker, daemon=True)
    second_thread = threading.Thread(target=second_worker, daemon=True)
    first_thread.start()
    assert blocking_name.entered.wait(timeout=1.0)

    second_thread.start()
    assert second_done.wait(timeout=0.1), "second accept should not wait for first batch field normalization"

    blocking_name.release.set()
    first_thread.join(timeout=1.0)
    second_thread.join(timeout=1.0)
    assert errors == []
