from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Base declarative model for the account center database."""


def build_engine(db_path: Path) -> Engine:
    db_url = f"sqlite:///{db_path.as_posix()}"
    return create_engine(db_url, future=True)


def build_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def create_schema(engine: Engine) -> None:
    from app_backend.infrastructure.db.models import (
        AccountRecord,
        AccountInventorySnapshotRecord,
        PurchaseRuntimeSettingsRecord,
        QueryConfigItemRecord,
        QueryConfigRecord,
        QueryModeSettingRecord,
    )

    Base.metadata.create_all(
        bind=engine,
        tables=[
            AccountRecord.__table__,
            PurchaseRuntimeSettingsRecord.__table__,
            AccountInventorySnapshotRecord.__table__,
            QueryConfigRecord.__table__,
            QueryConfigItemRecord.__table__,
            QueryModeSettingRecord.__table__,
        ],
    )
    _ensure_query_config_item_columns(engine)


def _ensure_query_config_item_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "query_config_items" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("query_config_items")}
    if "detail_max_wear" in existing_columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE query_config_items ADD COLUMN detail_max_wear FLOAT"))
