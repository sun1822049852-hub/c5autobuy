from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app_backend.infrastructure.db.base import Base


class AccountRecord(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    default_name: Mapped[str] = mapped_column(Text, nullable=False)
    remark_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    proxy_mode: Mapped[str] = mapped_column(Text, nullable=False)
    proxy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    disabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_api_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fast_api_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    token_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


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


class QueryConfigItemRecord(Base):
    __tablename__ = "query_config_items"

    query_item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    config_id: Mapped[str] = mapped_column(ForeignKey("query_configs.config_id"), nullable=False)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    external_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_hash_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_max_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_wear: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_detail_sync_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    config: Mapped[QueryConfigRecord] = relationship(back_populates="items")


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
    random_delay_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    random_delay_min: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    random_delay_max: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    config: Mapped[QueryConfigRecord] = relationship(back_populates="mode_settings")


class PurchaseRuntimeSettingsRecord(Base):
    __tablename__ = "purchase_runtime_settings"

    settings_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    whitelist_account_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class AccountInventorySnapshotRecord(Base):
    __tablename__ = "account_inventory_snapshots"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), primary_key=True)
    selected_steam_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    inventories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    refreshed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
