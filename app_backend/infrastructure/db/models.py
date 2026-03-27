from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app_backend.infrastructure.db.base import Base


class AccountRecord(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    default_name: Mapped[str] = mapped_column(Text, nullable=False)
    remark_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    browser_proxy_mode: Mapped[str] = mapped_column(Text, nullable=False)
    browser_proxy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_proxy_mode: Mapped[str] = mapped_column(Text, nullable=False)
    api_proxy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    c5_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    c5_nick_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    cookie_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_capability_state: Mapped[str] = mapped_column(Text, nullable=False)
    purchase_pool_state: Mapped[str] = mapped_column(Text, nullable=False)
    last_login_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    purchase_disabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_recovery_due_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_api_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fast_api_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    token_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    api_query_disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    browser_query_disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_ip_allow_list: Mapped[str | None] = mapped_column(Text, nullable=True)
    browser_public_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_public_ip: Mapped[str | None] = mapped_column(Text, nullable=True)


class AccountSessionBundleRecord(Base):
    __tablename__ = "account_session_bundles"

    bundle_id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.account_id"), nullable=True)
    captured_c5_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class QueryConfigRecord(Base):
    __tablename__ = "query_configs"

    config_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    items: Mapped[list["QueryConfigItemRecord"]] = relationship(
        back_populates="config",
        cascade="all, delete-orphan",
    )
    mode_settings: Mapped[list["QueryModeSettingRecord"]] = relationship(
        back_populates="config",
        cascade="all, delete-orphan",
    )


class QueryProductRecord(Base):
    __tablename__ = "query_products"

    external_item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_hash_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_detail_sync_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class QueryConfigItemRecord(Base):
    __tablename__ = "query_config_items"

    query_item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    config_id: Mapped[str] = mapped_column(ForeignKey("query_configs.config_id"), nullable=False)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    external_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_hash_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_min_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_max_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_detail_sync_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_paused: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    config: Mapped[QueryConfigRecord] = relationship(back_populates="items")
    mode_allocations: Mapped[list["QueryItemModeAllocationRecord"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )


class QueryItemModeAllocationRecord(Base):
    __tablename__ = "query_item_mode_allocations"

    query_item_id: Mapped[str] = mapped_column(
        ForeignKey("query_config_items.query_item_id"),
        primary_key=True,
    )
    mode_type: Mapped[str] = mapped_column(Text, primary_key=True)
    target_dedicated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    item: Mapped[QueryConfigItemRecord] = relationship(back_populates="mode_allocations")


class QueryModeSettingRecord(Base):
    __tablename__ = "query_mode_settings"

    mode_setting_id: Mapped[str] = mapped_column(Text, primary_key=True)
    config_id: Mapped[str] = mapped_column(ForeignKey("query_configs.config_id"), nullable=False)
    mode_type: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    window_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    base_cooldown_min: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    base_cooldown_max: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    item_min_cooldown_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    item_min_cooldown_strategy: Mapped[str] = mapped_column(Text, nullable=False, default="divide_by_assigned_count")
    random_delay_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    random_delay_min: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    random_delay_max: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    config: Mapped[QueryConfigRecord] = relationship(back_populates="mode_settings")


class QuerySettingsModeRecord(Base):
    __tablename__ = "query_settings_modes"

    mode_type: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    window_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    base_cooldown_min: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    base_cooldown_max: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    item_min_cooldown_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    item_min_cooldown_strategy: Mapped[str] = mapped_column(Text, nullable=False, default="divide_by_assigned_count")
    random_delay_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    random_delay_min: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    random_delay_max: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class AccountInventorySnapshotRecord(Base):
    __tablename__ = "account_inventory_snapshots"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), primary_key=True)
    selected_steam_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    inventories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    refreshed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseUiPreferenceRecord(Base):
    __tablename__ = "purchase_ui_preferences"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    selected_config_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class QueryItemStatsTotalRecord(Base):
    __tablename__ = "query_item_stats_total"

    external_item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    item_name_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_url_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_api_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fast_api_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    browser_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_hit_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_success_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_failure_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class QueryItemStatsDailyRecord(Base):
    __tablename__ = "query_item_stats_daily"

    external_item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    stat_date: Mapped[str] = mapped_column(Text, primary_key=True)
    item_name_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_url_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_api_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fast_api_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    browser_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class QueryItemRuleStatsTotalRecord(Base):
    __tablename__ = "query_item_rule_stats_total"

    external_item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    rule_fingerprint: Mapped[str] = mapped_column(Text, primary_key=True)
    detail_min_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_max_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    query_execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class QueryItemRuleStatsDailyRecord(Base):
    __tablename__ = "query_item_rule_stats_daily"

    external_item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    rule_fingerprint: Mapped[str] = mapped_column(Text, primary_key=True)
    stat_date: Mapped[str] = mapped_column(Text, primary_key=True)
    detail_min_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_max_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    query_execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class AccountCapabilityStatsTotalRecord(Base):
    __tablename__ = "account_capability_stats_total"

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    mode_type: Mapped[str] = mapped_column(Text, primary_key=True)
    phase: Mapped[str] = mapped_column(Text, primary_key=True)
    account_display_name_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    last_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class AccountCapabilityStatsDailyRecord(Base):
    __tablename__ = "account_capability_stats_daily"

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    mode_type: Mapped[str] = mapped_column(Text, primary_key=True)
    phase: Mapped[str] = mapped_column(Text, primary_key=True)
    stat_date: Mapped[str] = mapped_column(Text, primary_key=True)
    account_display_name_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    last_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
