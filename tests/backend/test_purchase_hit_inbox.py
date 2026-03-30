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
