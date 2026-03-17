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
        min_wear=0.1,
        detail_max_wear=0.7,
        max_wear=0.25,
        max_price=199.0,
        last_market_price=123.45,
    )

    updated = repository.update_item(
        item.query_item_id,
        max_wear=0.18,
        max_price=155.0,
    )
    stored = repository.get_config(config.config_id)

    assert updated.max_wear == 0.18
    assert updated.max_price == 155.0
    assert stored is not None
    assert stored.items[0].detail_max_wear == 0.7
    assert stored.items[0].max_wear == 0.18
    assert stored.items[0].max_price == 155.0

    repository.delete_item(item.query_item_id)
    stored_after_delete = repository.get_config(config.config_id)

    assert stored_after_delete is not None
    assert stored_after_delete.items == []


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
