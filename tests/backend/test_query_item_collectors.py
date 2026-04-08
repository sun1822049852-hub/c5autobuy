import pytest


def test_parse_c5_product_url_extracts_external_item_id():
    from app_backend.infrastructure.query.collectors.product_url_parser import ProductUrlParser

    parser = ProductUrlParser()

    result = parser.parse("https://www.c5game.com/csgo/730/asset/1380979899390267393")

    assert result.product_url == "https://www.c5game.com/csgo/730/asset/1380979899390267393"
    assert result.external_item_id == "1380979899390267393"


def test_parse_c5_product_url_normalizes_legacy_http_to_https():
    from app_backend.infrastructure.query.collectors.product_url_parser import ProductUrlParser

    parser = ProductUrlParser()

    result = parser.parse("http://www.c5game.com/csgo/730/asset/1380979899390267393")

    assert result.product_url == "https://www.c5game.com/csgo/730/asset/1380979899390267393"
    assert result.external_item_id == "1380979899390267393"


def test_parse_c5_product_url_rejects_invalid_url():
    from app_backend.infrastructure.query.collectors.product_url_parser import ProductUrlParser

    parser = ProductUrlParser()

    with pytest.raises(ValueError, match="无法从商品 URL 中解析 item_id"):
        parser.parse("https://www.c5game.com/csgo/730/asset/not-a-number")


async def test_product_detail_collector_normalizes_payload():
    from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetailCollector

    async def fake_fetcher(*, external_item_id: str, product_url: str):
        return {
            "external_item_id": external_item_id,
            "product_url": product_url,
            "item_name": "AK-47 | Redline",
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "min_wear": 0.1,
            "max_wear": 0.7,
            "last_market_price": 123.45,
        }

    collector = ProductDetailCollector(fetcher=fake_fetcher)

    detail = await collector.fetch_detail(
        external_item_id="1380979899390267393",
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390267393",
    )

    assert detail.external_item_id == "1380979899390267393"
    assert detail.item_name == "AK-47 | Redline"
    assert detail.market_hash_name == "AK-47 | Redline (Field-Tested)"
    assert detail.min_wear == 0.1
    assert detail.max_wear == 0.7
    assert detail.last_market_price == 123.45
