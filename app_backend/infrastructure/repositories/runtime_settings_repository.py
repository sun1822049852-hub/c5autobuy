from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app_backend.domain.models.runtime_settings import RuntimeSettings
from app_backend.infrastructure.db.models import RuntimeSettingsRecord


def _default_query_settings() -> dict[str, object]:
    return {}


def _default_purchase_settings() -> dict[str, object]:
    return {
        "per_batch_ip_fanout_limit": 1,
    }


class SqliteRuntimeSettingsRepository:
    _DEFAULT_SETTINGS_ID = "default"

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get(self) -> RuntimeSettings:
        with self._session_factory() as session:
            row = session.get(RuntimeSettingsRecord, self._DEFAULT_SETTINGS_ID)
            if row is None:
                return RuntimeSettings(
                    settings_id=self._DEFAULT_SETTINGS_ID,
                    query_settings_json=_default_query_settings(),
                    purchase_settings_json=_default_purchase_settings(),
                    updated_at=None,
                )
            return self._to_settings(row)

    def save_purchase_settings(self, purchase_settings: dict[str, object]) -> RuntimeSettings:
        with self._session_factory() as session:
            row = session.get(RuntimeSettingsRecord, self._DEFAULT_SETTINGS_ID)
            now = datetime.now().isoformat(timespec="seconds")
            if row is None:
                row = RuntimeSettingsRecord(
                    settings_id=self._DEFAULT_SETTINGS_ID,
                    query_settings_json=self._encode_json(_default_query_settings()),
                    purchase_settings_json=self._encode_json(_default_purchase_settings()),
                    updated_at=now,
                )
                session.add(row)
            row.purchase_settings_json = self._encode_json(purchase_settings)
            row.updated_at = now
            session.commit()
            session.refresh(row)
            return self._to_settings(row)

    @staticmethod
    def _encode_json(payload: dict[str, object]) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode_json(raw_value: str | None, *, fallback: dict[str, object]) -> dict[str, object]:
        if not raw_value:
            return dict(fallback)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            return dict(fallback)
        return value if isinstance(value, dict) else dict(fallback)

    @classmethod
    def _to_settings(cls, row: RuntimeSettingsRecord) -> RuntimeSettings:
        return RuntimeSettings(
            settings_id=row.settings_id,
            query_settings_json=cls._decode_json(
                row.query_settings_json,
                fallback=_default_query_settings(),
            ),
            purchase_settings_json=cls._decode_json(
                row.purchase_settings_json,
                fallback=_default_purchase_settings(),
            ),
            updated_at=row.updated_at,
        )
