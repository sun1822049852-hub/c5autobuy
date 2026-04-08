from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
from app_backend.infrastructure.repositories.query_config_repository import SqliteQueryConfigRepository


def test_create_query_config_persists_three_mode_settings(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteQueryConfigRepository(build_session_factory(engine))

    config = repository.create_config(name="日间配置", description="白天跑")

    assert config.name == "日间配置"
    assert config.description == "白天跑"
    assert config.items == []
    assert {mode.mode_type for mode in config.mode_settings} == {"new_api", "fast_api", "token"}
    assert all(mode.enabled is True for mode in config.mode_settings)


def test_update_and_delete_query_item(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteQueryConfigRepository(build_session_factory(engine))

    config = repository.create_config(name="商品配置", description="用于商品")
    item = repository.add_item(
        config_id=config.config_id,
        product_url="https://www.c5game.com/csgo/730/asset/123",
        external_item_id="123",
        item_name="AK-47 | Redline",
        market_hash_name="AK-47 | Redline (Field-Tested)",
        min_wear=0.0,
        max_wear=0.7,
        detail_min_wear=0.1,
        detail_max_wear=0.25,
        max_price=199.0,
        last_market_price=123.45,
    )

    updated = repository.update_item(
        item.query_item_id,
        detail_min_wear=0.12,
        detail_max_wear=0.18,
        max_price=155.0,
    )
    stored = repository.get_config(config.config_id)

    assert updated.min_wear == 0.0
    assert updated.max_wear == 0.7
    assert updated.detail_min_wear == 0.12
    assert updated.detail_max_wear == 0.18
    assert updated.max_price == 155.0
    assert stored is not None
    assert stored.items[0].min_wear == 0.0
    assert stored.items[0].max_wear == 0.7
    assert stored.items[0].detail_min_wear == 0.12
    assert stored.items[0].detail_max_wear == 0.18
    assert stored.items[0].max_price == 155.0

    repository.delete_item(item.query_item_id)
    stored_after_delete = repository.get_config(config.config_id)

    assert stored_after_delete is not None
    assert stored_after_delete.items == []


def _allocation_pairs(item) -> list[tuple[str | None, int | None]]:
    allocations = getattr(item, "mode_allocations", None) or []
    return sorted(
        (
            getattr(allocation, "mode_type", None),
            getattr(allocation, "target_dedicated_count", None),
        )
        for allocation in allocations
    )


def test_query_item_defaults_and_updates_mode_allocations(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteQueryConfigRepository(build_session_factory(engine))

    config = repository.create_config(name="带分配配置", description="用于分配")
    item = repository.add_item(
        config_id=config.config_id,
        product_url="https://www.c5game.com/csgo/730/asset/456",
        external_item_id="456",
        item_name="M4A1-S | Printstream",
        market_hash_name="M4A1-S | Printstream (Field-Tested)",
        min_wear=0.02,
        max_wear=0.8,
        detail_min_wear=0.02,
        detail_max_wear=0.2,
        max_price=666.0,
        last_market_price=555.0,
    )

    updated = repository.update_item(
        item.query_item_id,
        detail_min_wear=0.05,
        detail_max_wear=0.18,
        max_price=600.0,
        manual_paused=True,
        mode_allocations={
            "new_api": 2,
            "fast_api": 1,
            "token": 0,
        },
    )
    stored = repository.get_config(config.config_id)

    assert getattr(item, "manual_paused", None) is False
    assert _allocation_pairs(item) == [
        ("fast_api", 0),
        ("new_api", 0),
        ("token", 0),
    ]
    assert item.detail_min_wear == 0.02
    assert item.detail_max_wear == 0.2
    assert getattr(updated, "manual_paused", None) is True
    assert updated.detail_min_wear == 0.05
    assert updated.detail_max_wear == 0.18
    assert _allocation_pairs(updated) == [
        ("fast_api", 1),
        ("new_api", 2),
        ("token", 0),
    ]
    assert stored is not None
    assert getattr(stored.items[0], "manual_paused", None) is True
    assert stored.items[0].detail_min_wear == 0.05
    assert stored.items[0].detail_max_wear == 0.18
    assert _allocation_pairs(stored.items[0]) == [
        ("fast_api", 1),
        ("new_api", 2),
        ("token", 0),
    ]


def test_upsert_product_reuses_shared_product_cache(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteQueryConfigRepository(build_session_factory(engine))

    first = repository.upsert_product(
        external_item_id="456",
        product_url="https://www.c5game.com/csgo/730/asset/456",
        item_name="M4A1-S | Printstream",
        market_hash_name="M4A1-S | Printstream (Field-Tested)",
        min_wear=0.02,
        max_wear=0.8,
        last_market_price=555.0,
        last_detail_sync_at="2026-03-19T10:00:00",
    )
    second = repository.get_product("456")

    assert first.external_item_id == "456"
    assert first.min_wear == 0.02
    assert first.max_wear == 0.8
    assert second is not None
    assert second.product_url == "https://www.c5game.com/csgo/730/asset/456"
    assert second.item_name == "M4A1-S | Printstream"
    assert second.market_hash_name == "M4A1-S | Printstream (Field-Tested)"


def test_update_item_detail_normalizes_legacy_http_product_url(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteQueryConfigRepository(build_session_factory(engine))

    config = repository.create_config(name="商品配置", description="用于商品")
    item = repository.add_item(
        config_id=config.config_id,
        product_url="http://www.c5game.com/csgo/730/asset/123",
        external_item_id="123",
        item_name="AK-47 | Redline",
        market_hash_name="AK-47 | Redline (Field-Tested)",
        min_wear=0.0,
        max_wear=0.7,
        detail_min_wear=0.1,
        detail_max_wear=0.25,
        max_price=199.0,
        last_market_price=123.45,
    )

    updated = repository.update_item_detail(
        item.query_item_id,
        item_name="AK-47 | Redline",
        market_hash_name="AK-47 | Redline (Field-Tested)",
        min_wear=0.0,
        max_wear=0.7,
        last_market_price=111.11,
        last_detail_sync_at="2026-03-19T12:00:00",
    )
    stored = repository.get_config(config.config_id)
    product = repository.get_product("123")

    assert updated.product_url == "https://www.c5game.com/csgo/730/asset/123"
    assert stored is not None
    assert stored.items[0].product_url == "https://www.c5game.com/csgo/730/asset/123"
    assert product is not None
    assert product.product_url == "https://www.c5game.com/csgo/730/asset/123"


def test_update_and_delete_query_config(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteQueryConfigRepository(build_session_factory(engine))

    config = repository.create_config(name="旧配置", description="旧描述")

    updated = repository.update_config(
        config.config_id,
        name="新配置",
        description="新描述",
    )
    stored = repository.get_config(config.config_id)

    assert updated.name == "新配置"
    assert updated.description == "新描述"
    assert stored is not None
    assert stored.name == "新配置"
    assert stored.description == "新描述"

    repository.delete_config(config.config_id)

    assert repository.get_config(config.config_id) is None
