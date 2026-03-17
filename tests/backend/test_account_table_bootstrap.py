import sqlite3

from sqlalchemy import inspect

from app_backend.infrastructure.db.base import build_engine, create_schema


def test_create_schema_builds_accounts_table(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)

    inspector = inspect(engine)

    assert "accounts" in inspector.get_table_names()


def test_create_schema_adds_detail_max_wear_column_to_existing_query_config_items_table(tmp_path):
    db_path = tmp_path / "app.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE query_configs (
            config_id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE query_config_items (
            query_item_id TEXT PRIMARY KEY,
            config_id TEXT NOT NULL,
            product_url TEXT NOT NULL,
            external_item_id TEXT NOT NULL,
            item_name TEXT,
            market_hash_name TEXT,
            min_wear FLOAT,
            max_wear FLOAT,
            max_price FLOAT,
            last_market_price FLOAT,
            last_detail_sync_at TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()

    engine = build_engine(db_path)
    create_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("query_config_items")}

    assert "detail_max_wear" in columns
