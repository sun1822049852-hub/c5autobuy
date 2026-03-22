from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
from app_backend.infrastructure.repositories.query_settings_repository import SqliteQuerySettingsRepository


def _mode_map(settings):
    return {
        mode.mode_type: mode
        for mode in settings.modes
    }


def test_query_settings_repository_bootstraps_default_modes(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteQuerySettingsRepository(build_session_factory(engine))

    settings = repository.get_settings()
    modes = _mode_map(settings)

    assert set(modes) == {"new_api", "fast_api", "token"}
    assert modes["new_api"].base_cooldown_min == 1.0
    assert modes["new_api"].base_cooldown_max == 1.0
    assert modes["new_api"].item_min_cooldown_seconds == 0.5
    assert modes["new_api"].item_min_cooldown_strategy == "divide_by_assigned_count"
    assert modes["fast_api"].base_cooldown_min == 0.2
    assert modes["fast_api"].base_cooldown_max == 0.2
    assert modes["fast_api"].item_min_cooldown_seconds == 0.5
    assert modes["fast_api"].item_min_cooldown_strategy == "divide_by_assigned_count"
    assert modes["token"].base_cooldown_min == 10.0
    assert modes["token"].base_cooldown_max == 10.0
    assert modes["token"].item_min_cooldown_seconds == 0.5
    assert modes["token"].item_min_cooldown_strategy == "divide_by_assigned_count"
    assert all(mode.enabled is True for mode in modes.values())
    assert all(mode.window_enabled is False for mode in modes.values())
    assert all(mode.random_delay_enabled is False for mode in modes.values())


def test_query_settings_repository_updates_and_persists_modes(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteQuerySettingsRepository(build_session_factory(engine))

    updated = repository.update_settings(
        [
            {
                "mode_type": "new_api",
                "enabled": True,
                "window_enabled": False,
                "start_hour": 0,
                "start_minute": 0,
                "end_hour": 0,
                "end_minute": 0,
                "base_cooldown_min": 1.5,
                "base_cooldown_max": 2.0,
                "item_min_cooldown_seconds": 0.8,
                "item_min_cooldown_strategy": "fixed",
                "random_delay_enabled": False,
                "random_delay_min": 0.0,
                "random_delay_max": 0.0,
            },
            {
                "mode_type": "fast_api",
                "enabled": True,
                "window_enabled": True,
                "start_hour": 9,
                "start_minute": 0,
                "end_hour": 18,
                "end_minute": 30,
                "base_cooldown_min": 0.3,
                "base_cooldown_max": 0.6,
                "item_min_cooldown_seconds": 0.4,
                "item_min_cooldown_strategy": "divide_by_assigned_count",
                "random_delay_enabled": True,
                "random_delay_min": 0.1,
                "random_delay_max": 0.4,
            },
            {
                "mode_type": "token",
                "enabled": False,
                "window_enabled": False,
                "start_hour": 0,
                "start_minute": 0,
                "end_hour": 0,
                "end_minute": 0,
                "base_cooldown_min": 8.0,
                "base_cooldown_max": 12.0,
                "item_min_cooldown_seconds": 11.0,
                "item_min_cooldown_strategy": "fixed",
                "random_delay_enabled": True,
                "random_delay_min": 1.0,
                "random_delay_max": 3.0,
            },
        ]
    )
    reloaded = repository.get_settings()
    updated_modes = _mode_map(updated)
    reloaded_modes = _mode_map(reloaded)

    assert updated_modes["fast_api"].window_enabled is True
    assert updated_modes["fast_api"].start_hour == 9
    assert updated_modes["fast_api"].base_cooldown_min == 0.3
    assert updated_modes["fast_api"].item_min_cooldown_seconds == 0.4
    assert updated_modes["fast_api"].item_min_cooldown_strategy == "divide_by_assigned_count"
    assert updated_modes["token"].enabled is False
    assert updated_modes["token"].random_delay_enabled is True
    assert updated_modes["token"].item_min_cooldown_seconds == 11.0
    assert reloaded_modes["new_api"].base_cooldown_max == 2.0
    assert reloaded_modes["new_api"].item_min_cooldown_strategy == "fixed"
    assert reloaded_modes["fast_api"].end_minute == 30
    assert reloaded_modes["token"].base_cooldown_min == 8.0
