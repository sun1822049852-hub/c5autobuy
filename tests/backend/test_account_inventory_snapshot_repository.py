from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
from app_backend.infrastructure.repositories.account_inventory_snapshot_repository import (
    SqliteAccountInventorySnapshotRepository,
)


def test_account_inventory_snapshot_round_trip(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteAccountInventorySnapshotRepository(build_session_factory(engine))

    saved = repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[
            {"steamId": "steam-1", "inventory_num": 930, "inventory_max": 1000},
            {"steamId": "steam-2", "inventory_num": 850, "inventory_max": 1000},
        ],
        refreshed_at="2026-03-16T20:00:00",
        last_error=None,
    )
    loaded = repository.get("a1")

    assert saved.account_id == "a1"
    assert saved.selected_steam_id == "steam-1"
    assert loaded is not None
    assert loaded.selected_steam_id == "steam-1"
    assert loaded.inventories[0]["steamId"] == "steam-1"
    assert loaded.refreshed_at == "2026-03-16T20:00:00"


def test_account_inventory_snapshot_returns_none_when_missing(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteAccountInventorySnapshotRepository(build_session_factory(engine))

    assert repository.get("missing") is None
