import sqlite3

from sqlalchemy import inspect

from app_backend.infrastructure.db.base import build_engine, create_schema


def test_create_schema_builds_accounts_table(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)

    inspector = inspect(engine)

    assert "accounts" in inspector.get_table_names()
    account_columns = {column["name"] for column in inspector.get_columns("accounts")}
    assert "purchase_disabled" in account_columns
    assert "purchase_recovery_due_at" in account_columns


def test_create_schema_backfills_query_products_and_config_threshold_columns_from_existing_query_config_items_table(tmp_path):
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
            detail_max_wear FLOAT,
            max_price FLOAT,
            last_market_price FLOAT,
            last_detail_sync_at TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO query_configs (
            config_id,
            name,
            description,
            enabled,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("cfg-1", "旧配置", "旧数据", 1, "2026-03-19T10:00:00", "2026-03-19T10:00:00"),
    )
    connection.execute(
        """
        INSERT INTO query_config_items (
            query_item_id,
            config_id,
            product_url,
            external_item_id,
            item_name,
            market_hash_name,
            min_wear,
            max_wear,
            detail_max_wear,
            max_price,
            last_market_price,
            last_detail_sync_at,
            sort_order,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "item-1",
            "cfg-1",
            "https://www.c5game.com/csgo/730/asset/1380979899390267001",
            "1380979899390267001",
            "AK-47 | Redline",
            "AK-47 | Redline (Field-Tested)",
            0.12,
            0.25,
            0.8,
            199.0,
            188.8,
            "2026-03-19T10:05:00",
            0,
            "2026-03-19T10:00:00",
            "2026-03-19T10:00:00",
        ),
    )
    connection.commit()
    connection.close()

    engine = build_engine(db_path)
    create_schema(engine)

    inspector = inspect(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("query_config_items")}
    assert "query_products" in inspector.get_table_names()
    assert "detail_min_wear" in columns
    assert "detail_max_wear" in columns
    assert "manual_paused" in columns

    migrated_connection = sqlite3.connect(db_path)
    item_row = migrated_connection.execute(
        """
        SELECT
            min_wear,
            max_wear,
            detail_min_wear,
            detail_max_wear,
            max_price
        FROM query_config_items
        WHERE query_item_id = ?
        """,
        ("item-1",),
    ).fetchone()
    product_row = migrated_connection.execute(
        """
        SELECT
            external_item_id,
            product_url,
            item_name,
            market_hash_name,
            min_wear,
            max_wear,
            last_market_price,
            last_detail_sync_at
        FROM query_products
        WHERE external_item_id = ?
        """,
        ("1380979899390267001",),
    ).fetchone()
    migrated_connection.close()

    assert item_row == (0.12, 0.8, 0.12, 0.25, 199.0)
    assert product_row == (
        "1380979899390267001",
        "https://www.c5game.com/csgo/730/asset/1380979899390267001",
        "AK-47 | Redline",
        "AK-47 | Redline (Field-Tested)",
        0.12,
        0.8,
        188.8,
        "2026-03-19T10:05:00",
    )
