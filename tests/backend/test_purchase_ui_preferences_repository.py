from __future__ import annotations

from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
from app_backend.infrastructure.repositories.purchase_ui_preferences_repository import (
    SqlitePurchaseUiPreferencesRepository,
)


def test_purchase_ui_preferences_repository_defaults_overwrites_and_clears(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqlitePurchaseUiPreferencesRepository(build_session_factory(engine))

    initial = repository.get()

    assert initial.selected_config_id is None
    assert initial.updated_at is None

    first = repository.set_selected_config("cfg-1", updated_at="2026-03-21T18:00:00")
    overwritten = repository.set_selected_config("cfg-2", updated_at="2026-03-21T18:05:00")
    cleared = repository.clear_selected_config(updated_at="2026-03-21T18:10:00")

    assert first.selected_config_id == "cfg-1"
    assert first.updated_at == "2026-03-21T18:00:00"
    assert overwritten.selected_config_id == "cfg-2"
    assert overwritten.updated_at == "2026-03-21T18:05:00"
    assert cleared.selected_config_id is None
    assert cleared.updated_at == "2026-03-21T18:10:00"
    assert repository.get().selected_config_id is None
