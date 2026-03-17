from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
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
