from app_backend.infrastructure.purchase.runtime.purchase_hit_inbox import PurchaseHitInbox


def build_hit(*, total_wear_sum, query_item_name: str = "AK", total_price: float = 123.45) -> dict:
    return {
        "external_item_id": "1380979899390261111",
        "query_item_name": query_item_name,
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
        "product_list": [{"productId": "1", "price": 123.45}],
        "total_price": total_price,
        "total_wear_sum": total_wear_sum,
        "mode_type": "token",
    }


def test_purchase_hit_inbox_deduplicates_same_wear_sum_within_window():
    now_values = iter([100.0, 101.0, 107.0])
    inbox = PurchaseHitInbox(cache_duration=5.0, now_provider=lambda: next(now_values))

    assert inbox.accept(build_hit(total_wear_sum=1.2345)) is not None
    assert inbox.accept(build_hit(total_wear_sum=1.2345)) is None
    assert inbox.accept(build_hit(total_wear_sum=1.2345)) is not None


def test_purchase_hit_inbox_passes_hits_without_wear_sum():
    inbox = PurchaseHitInbox()

    accepted = inbox.accept(build_hit(total_wear_sum=None))

    assert accepted is not None
    assert accepted.total_wear_sum is None


def test_purchase_hit_inbox_preserves_selected_purchase_fields():
    inbox = PurchaseHitInbox()

    accepted = inbox.accept(build_hit(total_wear_sum=0.4567, query_item_name="M4A1"))

    assert accepted is not None
    assert accepted.query_item_name == "M4A1"
    assert accepted.external_item_id == "1380979899390261111"
    assert accepted.product_url == "https://www.c5game.com/csgo/730/asset/1380979899390261111"
    assert accepted.source_mode_type == "token"
    assert accepted.product_list[0]["productId"] == "1"
