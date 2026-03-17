from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app_backend.domain.enums.query_modes import QueryMode
from app_backend.domain.models.query_config import QueryConfig, QueryItem, QueryModeSetting
from app_backend.infrastructure.db.models import (
    QueryConfigItemRecord,
    QueryConfigRecord,
    QueryModeSettingRecord,
)


class SqliteQueryConfigRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def list_configs(self) -> list[QueryConfig]:
        with self._session_factory() as session:
            rows = session.scalars(select(QueryConfigRecord).order_by(QueryConfigRecord.created_at)).all()
            return [self._to_domain(row) for row in rows]

    def get_config(self, config_id: str) -> QueryConfig | None:
        with self._session_factory() as session:
            row = session.get(QueryConfigRecord, config_id)
            return self._to_domain(row) if row else None

    def get_item(self, query_item_id: str) -> QueryItem | None:
        with self._session_factory() as session:
            row = session.get(QueryConfigItemRecord, query_item_id)
            return self._to_item_domain(row) if row else None

    def create_config(self, *, name: str, description: str | None) -> QueryConfig:
        now = datetime.now().isoformat(timespec="seconds")
        config_id = str(uuid4())
        with self._session_factory() as session:
            row = QueryConfigRecord(
                config_id=config_id,
                name=name,
                description=description,
                enabled=1,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            for mode_type in QueryMode.ALL:
                session.add(
                    QueryModeSettingRecord(
                        mode_setting_id=str(uuid4()),
                        config_id=config_id,
                        mode_type=mode_type,
                        enabled=1,
                        window_enabled=0,
                        start_hour=0,
                        start_minute=0,
                        end_hour=0,
                        end_minute=0,
                        base_cooldown_min=0,
                        base_cooldown_max=0,
                        random_delay_enabled=0,
                        random_delay_min=0,
                        random_delay_max=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
            session.commit()
            created = session.scalar(select(QueryConfigRecord).where(QueryConfigRecord.config_id == config_id))
            if created is None:
                raise RuntimeError("Failed to create query config")
            return self._to_domain(created)

    def update_config(self, config_id: str, *, name: str, description: str | None) -> QueryConfig:
        with self._session_factory() as session:
            row = session.get(QueryConfigRecord, config_id)
            if row is None:
                raise KeyError(config_id)

            row.name = name
            row.description = description
            row.updated_at = datetime.now().isoformat(timespec="seconds")
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def delete_config(self, config_id: str) -> None:
        with self._session_factory() as session:
            row = session.get(QueryConfigRecord, config_id)
            if row is None:
                raise KeyError(config_id)
            session.delete(row)
            session.commit()

    def update_mode_setting(self, config_id: str, mode_type: str, **changes) -> QueryModeSetting:
        with self._session_factory() as session:
            row = session.scalar(
                select(QueryModeSettingRecord).where(
                    QueryModeSettingRecord.config_id == config_id,
                    QueryModeSettingRecord.mode_type == mode_type,
                )
            )
            if row is None:
                raise KeyError((config_id, mode_type))

            for key, value in changes.items():
                if hasattr(row, key):
                    setattr(row, key, value)

            session.commit()
            session.refresh(row)
            return QueryModeSetting(
                mode_setting_id=row.mode_setting_id,
                config_id=row.config_id,
                mode_type=row.mode_type,
                enabled=bool(row.enabled),
                window_enabled=bool(row.window_enabled),
                start_hour=row.start_hour,
                start_minute=row.start_minute,
                end_hour=row.end_hour,
                end_minute=row.end_minute,
                base_cooldown_min=row.base_cooldown_min,
                base_cooldown_max=row.base_cooldown_max,
                random_delay_enabled=bool(row.random_delay_enabled),
                random_delay_min=row.random_delay_min,
                random_delay_max=row.random_delay_max,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def add_item(
        self,
        *,
        config_id: str,
        product_url: str,
        external_item_id: str,
        item_name: str | None,
        market_hash_name: str | None,
        min_wear: float | None,
        detail_max_wear: float | None = None,
        max_wear: float | None,
        max_price: float | None,
        last_market_price: float | None,
    ) -> QueryItem:
        now = datetime.now().isoformat(timespec="seconds")
        with self._session_factory() as session:
            config = session.get(QueryConfigRecord, config_id)
            if config is None:
                raise KeyError(config_id)

            sort_order = len(config.items)
            row = QueryConfigItemRecord(
                query_item_id=str(uuid4()),
                config_id=config_id,
                product_url=product_url,
                external_item_id=external_item_id,
                item_name=item_name,
                market_hash_name=market_hash_name,
                min_wear=min_wear,
                detail_max_wear=detail_max_wear,
                max_wear=max_wear,
                max_price=max_price,
                last_market_price=last_market_price,
                last_detail_sync_at=now,
                sort_order=sort_order,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_item_domain(row)

    def update_item(self, query_item_id: str, **changes) -> QueryItem:
        with self._session_factory() as session:
            row = session.get(QueryConfigItemRecord, query_item_id)
            if row is None:
                raise KeyError(query_item_id)

            for key, value in changes.items():
                if hasattr(row, key):
                    setattr(row, key, value)

            row.updated_at = datetime.now().isoformat(timespec="seconds")
            session.commit()
            session.refresh(row)
            return self._to_item_domain(row)

    def update_item_detail(
        self,
        query_item_id: str,
        *,
        item_name: str | None,
        market_hash_name: str | None,
        min_wear: float | None,
        detail_max_wear: float | None,
        last_market_price: float | None,
        last_detail_sync_at: str,
    ) -> QueryItem:
        with self._session_factory() as session:
            row = session.get(QueryConfigItemRecord, query_item_id)
            if row is None:
                raise KeyError(query_item_id)

            row.item_name = item_name
            row.market_hash_name = market_hash_name
            row.min_wear = min_wear
            row.detail_max_wear = detail_max_wear
            row.last_market_price = last_market_price
            row.last_detail_sync_at = last_detail_sync_at
            row.updated_at = datetime.now().isoformat(timespec="seconds")
            session.commit()
            session.refresh(row)
            return self._to_item_domain(row)

    def delete_item(self, query_item_id: str) -> None:
        with self._session_factory() as session:
            row = session.get(QueryConfigItemRecord, query_item_id)
            if row is None:
                return
            session.delete(row)
            session.commit()

    @staticmethod
    def _to_domain(row: QueryConfigRecord) -> QueryConfig:
        return QueryConfig(
            config_id=row.config_id,
            name=row.name,
            description=row.description,
            enabled=bool(row.enabled),
            created_at=row.created_at,
            updated_at=row.updated_at,
            items=[
                SqliteQueryConfigRepository._to_item_domain(item)
                for item in sorted(row.items, key=lambda value: value.sort_order)
            ],
            mode_settings=[
                QueryModeSetting(
                    mode_setting_id=mode.mode_setting_id,
                    config_id=mode.config_id,
                    mode_type=mode.mode_type,
                    enabled=bool(mode.enabled),
                    window_enabled=bool(mode.window_enabled),
                    start_hour=mode.start_hour,
                    start_minute=mode.start_minute,
                    end_hour=mode.end_hour,
                    end_minute=mode.end_minute,
                    base_cooldown_min=mode.base_cooldown_min,
                    base_cooldown_max=mode.base_cooldown_max,
                    random_delay_enabled=bool(mode.random_delay_enabled),
                    random_delay_min=mode.random_delay_min,
                    random_delay_max=mode.random_delay_max,
                    created_at=mode.created_at,
                    updated_at=mode.updated_at,
                )
                for mode in sorted(row.mode_settings, key=lambda value: value.mode_type)
            ],
        )

    @staticmethod
    def _to_item_domain(row: QueryConfigItemRecord) -> QueryItem:
        return QueryItem(
            query_item_id=row.query_item_id,
            config_id=row.config_id,
            product_url=row.product_url,
            external_item_id=row.external_item_id,
            item_name=row.item_name,
            market_hash_name=row.market_hash_name,
            min_wear=row.min_wear,
            max_wear=row.max_wear,
            max_price=row.max_price,
            last_market_price=row.last_market_price,
            last_detail_sync_at=row.last_detail_sync_at,
            sort_order=row.sort_order,
            created_at=row.created_at,
            updated_at=row.updated_at,
            detail_max_wear=row.detail_max_wear,
        )
