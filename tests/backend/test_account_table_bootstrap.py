from sqlalchemy import inspect

from app_backend.infrastructure.db.base import build_engine, create_schema


def test_create_schema_builds_accounts_table(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)

    inspector = inspect(engine)

    assert "accounts" in inspector.get_table_names()
