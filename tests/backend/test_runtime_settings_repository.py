from __future__ import annotations

from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema


def test_runtime_settings_repository_returns_default_purchase_settings(tmp_path):
    from app_backend.infrastructure.repositories.runtime_settings_repository import (
        SqliteRuntimeSettingsRepository,
    )

    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteRuntimeSettingsRepository(build_session_factory(engine))

    settings = repository.get()

    assert settings.settings_id == "default"
    assert settings.purchase_settings_json == {
        "per_batch_ip_fanout_limit": 1,
        "max_inflight_per_account": 3,
    }
    assert settings.query_settings_json == {}
    assert settings.updated_at is None


def test_runtime_settings_repository_updates_only_purchase_settings(tmp_path):
    from app_backend.infrastructure.repositories.runtime_settings_repository import (
        SqliteRuntimeSettingsRepository,
    )

    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteRuntimeSettingsRepository(build_session_factory(engine))

    updated = repository.save_purchase_settings(
        {
            "per_batch_ip_fanout_limit": 4,
            "max_inflight_per_account": 2,
        }
    )
    reloaded = repository.get()

    assert updated.purchase_settings_json == {
        "per_batch_ip_fanout_limit": 4,
        "max_inflight_per_account": 2,
    }
    assert reloaded.purchase_settings_json == {
        "per_batch_ip_fanout_limit": 4,
        "max_inflight_per_account": 2,
    }
    assert reloaded.query_settings_json == {}
