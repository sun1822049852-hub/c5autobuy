from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
from app_backend.infrastructure.repositories.purchase_runtime_settings_repository import (
    SqlitePurchaseRuntimeSettingsRepository,
)


def test_purchase_runtime_settings_round_trip(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqlitePurchaseRuntimeSettingsRepository(build_session_factory(engine))

    saved = repository.save(whitelist_account_ids=["a1", "a2"])
    loaded = repository.get()

    assert saved.whitelist_account_ids == ["a1", "a2"]
    assert loaded.whitelist_account_ids == ["a1", "a2"]


def test_purchase_runtime_settings_defaults_when_missing(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqlitePurchaseRuntimeSettingsRepository(build_session_factory(engine))

    settings = repository.get()

    assert settings.whitelist_account_ids == []
