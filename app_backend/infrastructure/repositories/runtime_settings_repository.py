from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app_backend.domain.models.runtime_settings import (
    DEFAULT_RUNTIME_SETTINGS_ID,
    RuntimeSettings,
    build_default_runtime_settings,
)
from app_backend.infrastructure.db.models import RuntimeSettingsRecord


class SqliteRuntimeSettingsRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get(self) -> RuntimeSettings:
        with self._session_factory() as session:
            row, created = self._get_or_create_default_row(session)
            if created:
                session.commit()
                session.refresh(row)
            return self._to_domain(row)

    def save_query_settings(self, query_settings: dict[str, Any]) -> RuntimeSettings:
        with self._session_factory() as session:
            row, _ = self._get_or_create_default_row(session)
            settings = build_default_runtime_settings()
            row.query_settings_json = self._serialize(query_settings)
            row.updated_at = settings.updated_at
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def save_purchase_settings(self, purchase_settings: dict[str, Any]) -> RuntimeSettings:
        with self._session_factory() as session:
            row, _ = self._get_or_create_default_row(session)
            settings = build_default_runtime_settings()
            row.purchase_settings_json = self._serialize(purchase_settings)
            row.updated_at = settings.updated_at
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    @staticmethod
    def _get_or_create_default_row(session: Session) -> tuple[RuntimeSettingsRecord, bool]:
        row = session.get(RuntimeSettingsRecord, DEFAULT_RUNTIME_SETTINGS_ID)
        if row is not None:
            return row, False

        settings = build_default_runtime_settings()
        row = RuntimeSettingsRecord(
            settings_id=settings.settings_id,
            query_settings_json=SqliteRuntimeSettingsRepository._serialize(settings.query_settings_json),
            purchase_settings_json=SqliteRuntimeSettingsRepository._serialize(settings.purchase_settings_json),
            updated_at=settings.updated_at,
        )
        session.add(row)
        session.flush()
        return row, True

    @staticmethod
    def _to_domain(row: RuntimeSettingsRecord) -> RuntimeSettings:
        return RuntimeSettings(
            settings_id=row.settings_id,
            query_settings_json=json.loads(row.query_settings_json),
            purchase_settings_json=json.loads(row.purchase_settings_json),
            updated_at=row.updated_at,
        )

    @staticmethod
    def _serialize(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
