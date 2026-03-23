from __future__ import annotations

import importlib
import json
import sqlite3
from pathlib import Path

from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema


def _build_expected_query_settings() -> dict[str, object]:
    return {
        "modes": {
            "new_api": {
                "enabled": True,
                "cooldown_min_seconds": 1.0,
                "cooldown_max_seconds": 1.0,
                "random_delay_enabled": False,
                "random_delay_min_seconds": 0.0,
                "random_delay_max_seconds": 0.0,
                "window_enabled": False,
                "start_hour": 0,
                "start_minute": 0,
                "end_hour": 0,
                "end_minute": 0,
            },
            "fast_api": {
                "enabled": True,
                "cooldown_min_seconds": 0.2,
                "cooldown_max_seconds": 0.2,
                "random_delay_enabled": False,
                "random_delay_min_seconds": 0.0,
                "random_delay_max_seconds": 0.0,
                "window_enabled": False,
                "start_hour": 0,
                "start_minute": 0,
                "end_hour": 0,
                "end_minute": 0,
            },
            "token": {
                "enabled": True,
                "cooldown_min_seconds": 10.0,
                "cooldown_max_seconds": 10.0,
                "random_delay_enabled": False,
                "random_delay_min_seconds": 0.0,
                "random_delay_max_seconds": 0.0,
                "window_enabled": False,
                "start_hour": 0,
                "start_minute": 0,
                "end_hour": 0,
                "end_minute": 0,
            },
        },
        "item_pacing": {
            "new_api": {
                "strategy": "fixed_divided_by_actual_allocated_workers",
                "fixed_seconds": 0.5,
            },
            "fast_api": {
                "strategy": "fixed_divided_by_actual_allocated_workers",
                "fixed_seconds": 0.5,
            },
            "token": {
                "strategy": "fixed_divided_by_actual_allocated_workers",
                "fixed_seconds": 0.5,
            },
        },
    }


def _build_expected_purchase_settings() -> dict[str, object]:
    return {"ip_bucket_limits": {}}


def _build_repository(tmp_path: Path):
    module = importlib.import_module("app_backend.infrastructure.repositories.runtime_settings_repository")
    repository_class = getattr(module, "SqliteRuntimeSettingsRepository")
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    return repository_class(build_session_factory(engine))


def _load_runtime_settings_rows(db_path: Path) -> list[tuple[str, dict[str, object], dict[str, object]]]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT settings_id, query_settings_json, purchase_settings_json
            FROM runtime_settings
            ORDER BY settings_id
            """
        ).fetchall()
    finally:
        connection.close()
    return [
        (
            settings_id,
            json.loads(query_settings_json),
            json.loads(purchase_settings_json),
        )
        for settings_id, query_settings_json, purchase_settings_json in rows
    ]


def test_repository_get_creates_default_runtime_settings_row_with_spec_defaults(tmp_path: Path):
    repository = _build_repository(tmp_path)
    db_path = tmp_path / "app.db"

    settings = repository.get()

    assert settings.settings_id == "default"
    assert settings.query_settings_json == _build_expected_query_settings()
    assert settings.purchase_settings_json == _build_expected_purchase_settings()
    assert _load_runtime_settings_rows(db_path) == [
        (
            "default",
            _build_expected_query_settings(),
            _build_expected_purchase_settings(),
        )
    ]


def test_save_query_settings_updates_only_query_settings_json(tmp_path: Path):
    repository = _build_repository(tmp_path)

    purchase_settings = {"ip_bucket_limits": {"direct": {"concurrency_limit": 3}}}
    repository.save_purchase_settings(purchase_settings)
    query_settings = _build_expected_query_settings()
    query_settings["modes"]["new_api"]["cooldown_min_seconds"] = 2.5
    query_settings["modes"]["new_api"]["cooldown_max_seconds"] = 2.5
    query_settings["item_pacing"]["token"]["fixed_seconds"] = 1.2

    saved = repository.save_query_settings(query_settings)

    assert saved.settings_id == "default"
    assert saved.query_settings_json == query_settings
    assert saved.purchase_settings_json == purchase_settings


def test_save_purchase_settings_updates_only_purchase_settings_json(tmp_path: Path):
    repository = _build_repository(tmp_path)

    query_settings = _build_expected_query_settings()
    query_settings["modes"]["token"]["enabled"] = False
    repository.save_query_settings(query_settings)
    purchase_settings = {
        "ip_bucket_limits": {
            "direct": {"concurrency_limit": 1},
            "proxy://bucket-a": {"concurrency_limit": 2},
        }
    }

    saved = repository.save_purchase_settings(purchase_settings)

    assert saved.settings_id == "default"
    assert saved.query_settings_json == query_settings
    assert saved.purchase_settings_json == purchase_settings


def test_repository_always_persists_single_default_settings_row(tmp_path: Path):
    repository = _build_repository(tmp_path)
    db_path = tmp_path / "app.db"

    repository.save_query_settings(_build_expected_query_settings())
    repository.save_purchase_settings(
        {"ip_bucket_limits": {"proxy://bucket-a": {"concurrency_limit": 4}}}
    )
    repository.get()

    assert _load_runtime_settings_rows(db_path) == [
        (
            "default",
            _build_expected_query_settings(),
            {"ip_bucket_limits": {"proxy://bucket-a": {"concurrency_limit": 4}}},
        )
    ]
