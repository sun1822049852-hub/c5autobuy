from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import sessionmaker

from app_backend.domain.models.purchase_runtime_settings import PurchaseRuntimeSettings
from app_backend.infrastructure.db.models import PurchaseRuntimeSettingsRecord


class SqlitePurchaseRuntimeSettingsRepository:
    _SETTINGS_ID = 1

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get(self) -> PurchaseRuntimeSettings:
        with self._session_factory() as session:
            row = session.get(PurchaseRuntimeSettingsRecord, self._SETTINGS_ID)
            if row is None:
                return PurchaseRuntimeSettings()
            return self._to_domain(row)

    def save(
        self,
        *,
        query_only: bool,
        whitelist_account_ids: list[str],
        updated_at: str | None = None,
    ) -> PurchaseRuntimeSettings:
        with self._session_factory() as session:
            row = session.get(PurchaseRuntimeSettingsRecord, self._SETTINGS_ID)
            if row is None:
                row = PurchaseRuntimeSettingsRecord(settings_id=self._SETTINGS_ID)
                session.add(row)
            row.query_only = int(bool(query_only))
            row.whitelist_account_ids_json = json.dumps(list(whitelist_account_ids), ensure_ascii=True)
            row.updated_at = updated_at
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    @staticmethod
    def _to_domain(row: PurchaseRuntimeSettingsRecord) -> PurchaseRuntimeSettings:
        whitelist_account_ids: list[str]
        try:
            raw_value: Any = json.loads(row.whitelist_account_ids_json or "[]")
        except json.JSONDecodeError:
            raw_value = []
        whitelist_account_ids = [str(account_id) for account_id in raw_value] if isinstance(raw_value, list) else []
        return PurchaseRuntimeSettings(
            query_only=bool(row.query_only),
            whitelist_account_ids=whitelist_account_ids,
            updated_at=row.updated_at,
        )
