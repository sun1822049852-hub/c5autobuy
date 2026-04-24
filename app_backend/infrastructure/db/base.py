from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app_backend.infrastructure.query.product_url_utils import normalize_c5_product_url


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
        AccountSessionBundleRecord,
        AccountCapabilityStatsDailyRecord,
        AccountCapabilityStatsTotalRecord,
        AccountInventorySnapshotRecord,
        ProxyPoolRecord,
        PurchaseUiPreferenceRecord,
        QueryConfigItemRecord,
        QueryItemModeAllocationRecord,
        QueryItemRuleStatsDailyRecord,
        QueryItemRuleStatsTotalRecord,
        QueryProductRecord,
        QueryConfigRecord,
        QueryItemStatsDailyRecord,
        QueryMatchedProductRecord,
        QueryItemStatsTotalRecord,
        QueryModeSettingRecord,
        QuerySettingsModeRecord,
        RuntimeSettingsRecord,
    )

    Base.metadata.create_all(
        bind=engine,
        tables=[
            AccountRecord.__table__,
            AccountSessionBundleRecord.__table__,
            AccountInventorySnapshotRecord.__table__,
            QueryConfigRecord.__table__,
            QueryProductRecord.__table__,
            QueryConfigItemRecord.__table__,
            QueryItemModeAllocationRecord.__table__,
            QueryModeSettingRecord.__table__,
            QuerySettingsModeRecord.__table__,
            PurchaseUiPreferenceRecord.__table__,
            RuntimeSettingsRecord.__table__,
            QueryItemStatsTotalRecord.__table__,
            QueryItemStatsDailyRecord.__table__,
            QueryMatchedProductRecord.__table__,
            QueryItemRuleStatsTotalRecord.__table__,
            QueryItemRuleStatsDailyRecord.__table__,
            AccountCapabilityStatsTotalRecord.__table__,
            AccountCapabilityStatsDailyRecord.__table__,
            ProxyPoolRecord.__table__,
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
    _ensure_query_mode_setting_columns(engine)
    _ensure_query_settings_mode_columns(engine)
    _ensure_account_columns(engine)
    _backfill_query_products(engine, had_detail_min_wear=had_detail_min_wear_before_migration)
    _normalize_legacy_c5_product_urls(engine)


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


def _ensure_query_mode_setting_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "query_mode_settings" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("query_mode_settings")}
    with engine.begin() as connection:
        if "item_min_cooldown_seconds" not in existing_columns:
            connection.execute(
                text("ALTER TABLE query_mode_settings ADD COLUMN item_min_cooldown_seconds FLOAT NOT NULL DEFAULT 0.5")
            )
        if "item_min_cooldown_strategy" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE query_mode_settings ADD COLUMN item_min_cooldown_strategy TEXT NOT NULL DEFAULT 'divide_by_assigned_count'"
                )
            )


def _ensure_query_settings_mode_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "query_settings_modes" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("query_settings_modes")}
    with engine.begin() as connection:
        if "item_min_cooldown_seconds" not in existing_columns:
            connection.execute(
                text("ALTER TABLE query_settings_modes ADD COLUMN item_min_cooldown_seconds FLOAT NOT NULL DEFAULT 0.5")
            )
        if "item_min_cooldown_strategy" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE query_settings_modes ADD COLUMN item_min_cooldown_strategy TEXT NOT NULL DEFAULT 'divide_by_assigned_count'"
                )
            )


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
        if "proxy_mode" in existing_columns or "proxy_url" in existing_columns or "proxy_public_ip" in existing_columns:
            _rebuild_accounts_table_for_dual_proxy(engine, existing_columns=existing_columns)
            inspector = inspect(engine)
            existing_columns = {column["name"] for column in inspector.get_columns("accounts")}
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
        if "api_query_disabled_reason" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN api_query_disabled_reason TEXT"))
        if "browser_query_disabled_reason" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN browser_query_disabled_reason TEXT"))
        if "api_ip_allow_list" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN api_ip_allow_list TEXT"))
        if "browser_public_ip" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN browser_public_ip TEXT"))
        if "api_public_ip" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN api_public_ip TEXT"))
        if "balance_amount" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN balance_amount FLOAT"))
        if "balance_source" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN balance_source TEXT"))
        if "balance_updated_at" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN balance_updated_at TEXT"))
        if "balance_refresh_after_at" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN balance_refresh_after_at TEXT"))
        if "balance_last_error" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN balance_last_error TEXT"))
        if "browser_proxy_id" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN browser_proxy_id TEXT"))
        if "api_proxy_id" not in existing_columns:
            connection.execute(text("ALTER TABLE accounts ADD COLUMN api_proxy_id TEXT"))


def _rebuild_accounts_table_for_dual_proxy(engine: Engine, *, existing_columns: set[str]) -> None:
    def _expr(name: str, fallback: str) -> str:
        return name if name in existing_columns else fallback

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(text("DROP TABLE IF EXISTS accounts__dual_proxy"))
        connection.execute(
            text(
                """
                CREATE TABLE accounts__dual_proxy (
                    account_id TEXT PRIMARY KEY,
                    default_name TEXT NOT NULL,
                    remark_name TEXT,
                    browser_proxy_mode TEXT NOT NULL,
                    browser_proxy_url TEXT,
                    api_proxy_mode TEXT NOT NULL,
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
                    token_enabled INTEGER NOT NULL DEFAULT 1,
                    api_query_disabled_reason TEXT,
                    browser_query_disabled_reason TEXT,
                    api_ip_allow_list TEXT,
                    browser_public_ip TEXT,
                    api_public_ip TEXT,
                    balance_amount FLOAT,
                    balance_source TEXT,
                    balance_updated_at TEXT,
                    balance_refresh_after_at TEXT,
                    balance_last_error TEXT
                )
                """
            )
        )
        connection.execute(
            text(
                f"""
                INSERT INTO accounts__dual_proxy (
                    account_id,
                    default_name,
                    remark_name,
                    browser_proxy_mode,
                    browser_proxy_url,
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
                    token_enabled,
                    api_query_disabled_reason,
                    browser_query_disabled_reason,
                    api_ip_allow_list,
                    browser_public_ip,
                    api_public_ip,
                    balance_amount,
                    balance_source,
                    balance_updated_at,
                    balance_refresh_after_at,
                    balance_last_error
                )
                SELECT
                    account_id,
                    default_name,
                    remark_name,
                    CASE
                        WHEN {_expr("browser_proxy_mode", "NULL")} IS NOT NULL THEN {_expr("browser_proxy_mode", "NULL")}
                        WHEN {_expr("proxy_url", "NULL")} IS NOT NULL THEN 'custom'
                        ELSE 'direct'
                    END,
                    COALESCE({_expr("browser_proxy_url", "NULL")}, {_expr("proxy_url", "NULL")}),
                    CASE
                        WHEN {_expr("api_proxy_mode", "NULL")} IS NOT NULL THEN {_expr("api_proxy_mode", "NULL")}
                        WHEN {_expr("proxy_url", "NULL")} IS NOT NULL THEN 'custom'
                        ELSE 'direct'
                    END,
                    COALESCE({_expr("api_proxy_url", "NULL")}, {_expr("proxy_url", "NULL")}),
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
                    {_expr("purchase_disabled", "0")},
                    {_expr("purchase_recovery_due_at", "NULL")},
                    {_expr("new_api_enabled", "1")},
                    {_expr("fast_api_enabled", "1")},
                    {_expr("token_enabled", "1")},
                    {_expr("api_query_disabled_reason", "NULL")},
                    {_expr("browser_query_disabled_reason", "NULL")},
                    {_expr("api_ip_allow_list", "NULL")},
                    {_expr("browser_public_ip", _expr("proxy_public_ip", "NULL"))},
                    {_expr("api_public_ip", _expr("proxy_public_ip", "NULL"))},
                    {_expr("balance_amount", "NULL")},
                    {_expr("balance_source", "NULL")},
                    {_expr("balance_updated_at", "NULL")},
                    {_expr("balance_refresh_after_at", "NULL")},
                    {_expr("balance_last_error", "NULL")}
                FROM accounts
                """
            )
        )
        connection.execute(text("DROP TABLE accounts"))
        connection.execute(text("ALTER TABLE accounts__dual_proxy RENAME TO accounts"))
        connection.execute(text("PRAGMA foreign_keys=ON"))


def _rebuild_accounts_table_without_disabled(engine: Engine, *, existing_columns: set[str]) -> None:
    column_expr = {
        "purchase_disabled": "purchase_disabled" if "purchase_disabled" in existing_columns else "0",
        "purchase_recovery_due_at": "purchase_recovery_due_at" if "purchase_recovery_due_at" in existing_columns else "NULL",
        "new_api_enabled": "new_api_enabled" if "new_api_enabled" in existing_columns else "1",
        "fast_api_enabled": "fast_api_enabled" if "fast_api_enabled" in existing_columns else "1",
        "token_enabled": "token_enabled" if "token_enabled" in existing_columns else "1",
        "api_query_disabled_reason": (
            "api_query_disabled_reason" if "api_query_disabled_reason" in existing_columns else "NULL"
        ),
        "browser_query_disabled_reason": (
            "browser_query_disabled_reason" if "browser_query_disabled_reason" in existing_columns else "NULL"
        ),
        "api_ip_allow_list": "api_ip_allow_list" if "api_ip_allow_list" in existing_columns else "NULL",
        "proxy_public_ip": "proxy_public_ip" if "proxy_public_ip" in existing_columns else "NULL",
        "balance_amount": "balance_amount" if "balance_amount" in existing_columns else "NULL",
        "balance_source": "balance_source" if "balance_source" in existing_columns else "NULL",
        "balance_updated_at": "balance_updated_at" if "balance_updated_at" in existing_columns else "NULL",
        "balance_refresh_after_at": (
            "balance_refresh_after_at" if "balance_refresh_after_at" in existing_columns else "NULL"
        ),
        "balance_last_error": "balance_last_error" if "balance_last_error" in existing_columns else "NULL",
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
                    token_enabled INTEGER NOT NULL DEFAULT 1,
                    api_query_disabled_reason TEXT,
                    browser_query_disabled_reason TEXT,
                    api_ip_allow_list TEXT,
                    proxy_public_ip TEXT,
                    balance_amount FLOAT,
                    balance_source TEXT,
                    balance_updated_at TEXT,
                    balance_refresh_after_at TEXT,
                    balance_last_error TEXT
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
                    token_enabled,
                    api_query_disabled_reason,
                    browser_query_disabled_reason,
                    api_ip_allow_list,
                    proxy_public_ip,
                    balance_amount,
                    balance_source,
                    balance_updated_at,
                    balance_refresh_after_at,
                    balance_last_error
                )
                SELECT
                    account_id,
                    default_name,
                    remark_name,
                    proxy_mode,
                    proxy_url,
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
                    {column_expr["token_enabled"]},
                    {column_expr["api_query_disabled_reason"]},
                    {column_expr["browser_query_disabled_reason"]},
                    {column_expr["api_ip_allow_list"]},
                    {column_expr["proxy_public_ip"]},
                    {column_expr["balance_amount"]},
                    {column_expr["balance_source"]},
                    {column_expr["balance_updated_at"]},
                    {column_expr["balance_refresh_after_at"]},
                    {column_expr["balance_last_error"]}
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


def _normalize_legacy_c5_product_urls(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    targets = (
        ("query_products", "external_item_id"),
        ("query_config_items", "query_item_id"),
    )
    with engine.begin() as connection:
        for table_name, identity_column in targets:
            if table_name not in table_names:
                continue
            rows = connection.execute(
                text(
                    f"""
                    SELECT {identity_column} AS row_id, product_url
                    FROM {table_name}
                    WHERE product_url LIKE 'http://%'
                    """
                )
            ).mappings()
            for row in rows:
                normalized_product_url = normalize_c5_product_url(row["product_url"])
                if normalized_product_url == row["product_url"]:
                    continue
                connection.execute(
                    text(
                        f"""
                        UPDATE {table_name}
                        SET product_url = :product_url
                        WHERE {identity_column} = :row_id
                        """
                    ),
                    {
                        "product_url": normalized_product_url,
                        "row_id": row["row_id"],
                    },
                )
