from __future__ import annotations

import json
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
    from app_backend.domain.models.runtime_settings import (
        build_default_purchase_settings_json,
        build_default_query_settings_json,
    )
    from app_backend.infrastructure.db.models import (
        AccountRecord,
        AccountInventorySnapshotRecord,
        QueryConfigItemRecord,
        QueryItemModeAllocationRecord,
        QueryProductRecord,
        QueryConfigRecord,
        QueryModeSettingRecord,
        RuntimeSettingsRecord,
    )

    Base.metadata.create_all(
        bind=engine,
        tables=[
            AccountRecord.__table__,
            AccountInventorySnapshotRecord.__table__,
            QueryConfigRecord.__table__,
            QueryProductRecord.__table__,
            QueryConfigItemRecord.__table__,
            QueryItemModeAllocationRecord.__table__,
            QueryModeSettingRecord.__table__,
            RuntimeSettingsRecord.__table__,
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
    _ensure_runtime_settings_columns(
        engine,
        default_query_settings_json=json.dumps(
            build_default_query_settings_json(),
            ensure_ascii=False,
            sort_keys=True,
        ),
        default_purchase_settings_json=json.dumps(
            build_default_purchase_settings_json(),
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
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
    if "disabled" in existing_columns:
        _rebuild_accounts_table_without_disabled(engine, existing_columns=existing_columns)
        inspector = inspect(engine)
        existing_columns = {column["name"] for column in inspector.get_columns("accounts")}
    with engine.begin() as connection:
        if "account_proxy_mode" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN account_proxy_mode TEXT"))
        if "account_proxy_url" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN account_proxy_url TEXT"))
        if "api_proxy_mode" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN api_proxy_mode TEXT"))
        if "api_proxy_url" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN api_proxy_url TEXT"))
        if "purchase_disabled" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN purchase_disabled INTEGER NOT NULL DEFAULT 0"))
        if "purchase_recovery_due_at" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN purchase_recovery_due_at TEXT"))
        if "new_api_enabled" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN new_api_enabled INTEGER NOT NULL DEFAULT 1"))
        if "fast_api_enabled" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN fast_api_enabled INTEGER NOT NULL DEFAULT 1"))
        if "token_enabled" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN token_enabled INTEGER NOT NULL DEFAULT 1"))
        connection.execute(
            text(
                """
                UPDATE accounts
                SET account_proxy_mode = COALESCE(NULLIF(account_proxy_mode, ''), proxy_mode, 'direct'),
                    account_proxy_url = COALESCE(account_proxy_url, proxy_url)
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE accounts
                SET api_proxy_mode = COALESCE(NULLIF(api_proxy_mode, ''), account_proxy_mode, proxy_mode, 'direct'),
                    api_proxy_url = COALESCE(api_proxy_url, account_proxy_url, proxy_url)
                """
            )
        )


def _ensure_runtime_settings_columns(
    engine: Engine,
    *,
    default_query_settings_json: str,
    default_purchase_settings_json: str,
) -> None:
    inspector = inspect(engine)
    if "runtime_settings" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("runtime_settings")}
    with engine.begin() as connection:
        if "query_settings_json" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE runtime_settings ADD COLUMN query_settings_json TEXT NOT NULL "
                    f"DEFAULT '{default_query_settings_json}'"
                )
            )
        if "purchase_settings_json" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE runtime_settings ADD COLUMN purchase_settings_json TEXT NOT NULL "
                    f"DEFAULT '{default_purchase_settings_json}'"
                )
            )
        if "updated_at" not in existing_columns:
            connection.execute(
                text("ALTER TABLE runtime_settings ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
            )


def _rebuild_accounts_table_without_disabled(engine: Engine, *, existing_columns: set[str]) -> None:
    column_expr = {
        "account_proxy_mode": "account_proxy_mode" if "account_proxy_mode" in existing_columns else "proxy_mode",
        "account_proxy_url": "account_proxy_url" if "account_proxy_url" in existing_columns else "proxy_url",
        "api_proxy_mode": (
            "api_proxy_mode"
            if "api_proxy_mode" in existing_columns
            else ("account_proxy_mode" if "account_proxy_mode" in existing_columns else "proxy_mode")
        ),
        "api_proxy_url": (
            "api_proxy_url"
            if "api_proxy_url" in existing_columns
            else ("account_proxy_url" if "account_proxy_url" in existing_columns else "proxy_url")
        ),
        "purchase_disabled": "purchase_disabled" if "purchase_disabled" in existing_columns else "0",
        "purchase_recovery_due_at": "purchase_recovery_due_at" if "purchase_recovery_due_at" in existing_columns else "NULL",
        "new_api_enabled": "new_api_enabled" if "new_api_enabled" in existing_columns else "1",
        "fast_api_enabled": "fast_api_enabled" if "fast_api_enabled" in existing_columns else "1",
        "token_enabled": "token_enabled" if "token_enabled" in existing_columns else "1",
    }

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(
            text(
                """
                CREATE TABLE accounts__new (
                    account_id TEXT PRIMARY KEY,
                    default_name TEXT NOT NULL,
                    remark_name TEXT,
                    proxy_mode TEXT NOT NULL,
                    proxy_url TEXT,
                    account_proxy_mode TEXT NOT NULL DEFAULT 'direct',
                    account_proxy_url TEXT,
                    api_proxy_mode TEXT NOT NULL DEFAULT 'direct',
                    api_proxy_url TEXT,
                    api_key TEXT,
                    c5_user_id TEXT,
                    c5_nick_name TEXT,
                    cookie_raw TEXT,
                    purchase_capability_state TEXT NOT NULL,
                    purchase_pool_state TEXT NOT NULL,
                    last_login_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    purchase_disabled INTEGER NOT NULL DEFAULT 0,
                    purchase_recovery_due_at TEXT,
                    new_api_enabled INTEGER NOT NULL DEFAULT 1,
                    fast_api_enabled INTEGER NOT NULL DEFAULT 1,
                    token_enabled INTEGER NOT NULL DEFAULT 1
                )
                """
            )
        )
        connection.execute(
            text(
                f"""
                INSERT INTO accounts__new (
                    account_id,
                    default_name,
                    remark_name,
                    proxy_mode,
                    proxy_url,
                    account_proxy_mode,
                    account_proxy_url,
                    api_proxy_mode,
                    api_proxy_url,
                    api_key,
                    c5_user_id,
                    c5_nick_name,
                    cookie_raw,
                    purchase_capability_state,
                    purchase_pool_state,
                    last_login_at,
                    last_error,
                    created_at,
                    updated_at,
                    purchase_disabled,
                    purchase_recovery_due_at,
                    new_api_enabled,
                    fast_api_enabled,
                    token_enabled
                )
                SELECT
                    account_id,
                    default_name,
                    remark_name,
                    proxy_mode,
                    proxy_url,
                    {column_expr["account_proxy_mode"]},
                    {column_expr["account_proxy_url"]},
                    {column_expr["api_proxy_mode"]},
                    {column_expr["api_proxy_url"]},
                    api_key,
                    c5_user_id,
                    c5_nick_name,
                    cookie_raw,
                    purchase_capability_state,
                    purchase_pool_state,
                    last_login_at,
                    last_error,
                    created_at,
                    updated_at,
                    {column_expr["purchase_disabled"]},
                    {column_expr["purchase_recovery_due_at"]},
                    {column_expr["new_api_enabled"]},
                    {column_expr["fast_api_enabled"]},
                    {column_expr["token_enabled"]}
                FROM accounts
                """
            )
        )
        connection.execute(text("DROP TABLE accounts"))
        connection.execute(text("ALTER TABLE accounts__new RENAME TO accounts"))
        connection.execute(text("PRAGMA foreign_keys=ON"))


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
