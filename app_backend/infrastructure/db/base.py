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
        QueryItemModeAllocationRecord,
        QueryProductRecord,
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
            QueryProductRecord.__table__,
            QueryConfigItemRecord.__table__,
            QueryItemModeAllocationRecord.__table__,
            QueryModeSettingRecord.__table__,
        ],
    )
    inspector = inspect(engine)
    had_detail_min_wear_before_migration = False
    if "query_config_items" in inspector.get_table_names():
        had_detail_min_wear_before_migration = any(
            column["name"] == "detail_min_wear"
            for column in inspector.get_columns("query_config_items")
    )
    _ensure_query_config_item_columns(engine)
    _ensure_account_columns(engine)
    _backfill_query_products(engine, had_detail_min_wear=had_detail_min_wear_before_migration)


def _ensure_query_config_item_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "query_config_items" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("query_config_items")}
    with engine.begin() as connection:
        if "detail_max_wear" not in existing_columns:
            connection.execute(text("ALTER TABLE query_config_items ADD COLUMN detail_max_wear FLOAT"))
        if "detail_min_wear" not in existing_columns:
            connection.execute(text("ALTER TABLE query_config_items ADD COLUMN detail_min_wear FLOAT"))
        if "manual_paused" not in existing_columns:
            connection.execute(text("ALTER TABLE query_config_items ADD COLUMN manual_paused INTEGER NOT NULL DEFAULT 0"))


def _ensure_account_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "accounts" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("accounts")}
    with engine.begin() as connection:
        if "purchase_disabled" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN purchase_disabled INTEGER NOT NULL DEFAULT 0"))
        if "purchase_recovery_due_at" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN purchase_recovery_due_at TEXT"))


def _backfill_query_products(engine: Engine, *, had_detail_min_wear: bool) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "query_config_items" not in table_names or "query_products" not in table_names:
        return

    with engine.begin() as connection:
        if had_detail_min_wear:
            connection.execute(
                text(
                    """
                    INSERT INTO query_products (
                        external_item_id,
                        product_url,
                        item_name,
                        market_hash_name,
                        min_wear,
                        max_wear,
                        last_market_price,
                        last_detail_sync_at,
                        created_at,
                        updated_at
                    )
                    SELECT
                        external_item_id,
                        product_url,
                        item_name,
                        market_hash_name,
                        min_wear,
                        max_wear,
                        last_market_price,
                        last_detail_sync_at,
                        created_at,
                        updated_at
                    FROM query_config_items
                    WHERE external_item_id IS NOT NULL AND TRIM(external_item_id) <> ''
                    ON CONFLICT(external_item_id) DO UPDATE SET
                        product_url = excluded.product_url,
                        item_name = excluded.item_name,
                        market_hash_name = excluded.market_hash_name,
                        min_wear = excluded.min_wear,
                        max_wear = excluded.max_wear,
                        last_market_price = excluded.last_market_price,
                        last_detail_sync_at = excluded.last_detail_sync_at,
                        updated_at = excluded.updated_at
                    """
                )
            )
            connection.execute(
                text(
                    """
                    UPDATE query_config_items
                    SET detail_min_wear = COALESCE(detail_min_wear, min_wear),
                        detail_max_wear = COALESCE(detail_max_wear, max_wear)
                    """
                )
            )
            return

        connection.execute(
            text(
                """
                INSERT INTO query_products (
                    external_item_id,
                    product_url,
                    item_name,
                    market_hash_name,
                    min_wear,
                    max_wear,
                    last_market_price,
                    last_detail_sync_at,
                    created_at,
                    updated_at
                )
                SELECT
                    external_item_id,
                    product_url,
                    item_name,
                    market_hash_name,
                    min_wear,
                    COALESCE(detail_max_wear, max_wear),
                    last_market_price,
                    last_detail_sync_at,
                    created_at,
                    updated_at
                FROM query_config_items
                WHERE external_item_id IS NOT NULL AND TRIM(external_item_id) <> ''
                ON CONFLICT(external_item_id) DO UPDATE SET
                    product_url = excluded.product_url,
                    item_name = excluded.item_name,
                    market_hash_name = excluded.market_hash_name,
                    min_wear = excluded.min_wear,
                    max_wear = excluded.max_wear,
                    last_market_price = excluded.last_market_price,
                    last_detail_sync_at = excluded.last_detail_sync_at,
                    updated_at = excluded.updated_at
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE query_config_items
                SET detail_min_wear = COALESCE(detail_min_wear, min_wear),
                    detail_max_wear = COALESCE(max_wear, detail_max_wear),
                    max_wear = COALESCE(
                        (
                            SELECT query_products.max_wear
                            FROM query_products
                            WHERE query_products.external_item_id = query_config_items.external_item_id
                        ),
                        detail_max_wear,
                        max_wear
                    ),
                    product_url = COALESCE(
                        (
                            SELECT query_products.product_url
                            FROM query_products
                            WHERE query_products.external_item_id = query_config_items.external_item_id
                        ),
                        product_url
                    ),
                    item_name = COALESCE(
                        (
                            SELECT query_products.item_name
                            FROM query_products
                            WHERE query_products.external_item_id = query_config_items.external_item_id
                        ),
                        item_name
                    ),
                    market_hash_name = COALESCE(
                        (
                            SELECT query_products.market_hash_name
                            FROM query_products
                            WHERE query_products.external_item_id = query_config_items.external_item_id
                        ),
                        market_hash_name
                    ),
                    min_wear = COALESCE(
                        (
                            SELECT query_products.min_wear
                            FROM query_products
                            WHERE query_products.external_item_id = query_config_items.external_item_id
                        ),
                        min_wear
                    ),
                    last_market_price = COALESCE(
                        (
                            SELECT query_products.last_market_price
                            FROM query_products
                            WHERE query_products.external_item_id = query_config_items.external_item_id
                        ),
                        last_market_price
                    ),
                    last_detail_sync_at = COALESCE(
                        (
                            SELECT query_products.last_detail_sync_at
                            FROM query_products
                            WHERE query_products.external_item_id = query_config_items.external_item_id
                        ),
                        last_detail_sync_at
                    )
                """
            )
        )
