from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app_backend.infrastructure.db.models import PurchaseUiPreferenceRecord


@dataclass(slots=True)
class PurchaseUiPreferences:
    selected_config_id: str | None = None
    updated_at: str | None = None


class SqlitePurchaseUiPreferencesRepository:
    _ROW_ID = "purchase-ui-preferences"

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get(self) -> PurchaseUiPreferences:
        with self._session_factory() as session:
            row = session.get(PurchaseUiPreferenceRecord, self._ROW_ID)
            if row is None:
                return PurchaseUiPreferences()
            return PurchaseUiPreferences(
                selected_config_id=row.selected_config_id,
                updated_at=row.updated_at,
            )

    def set_selected_config(
        self,
        config_id: str,
        *,
        updated_at: str | None = None,
    ) -> PurchaseUiPreferences:
        timestamp = updated_at or datetime.now().isoformat(timespec="seconds")
        with self._session_factory() as session:
            row = session.get(PurchaseUiPreferenceRecord, self._ROW_ID)
            if row is None:
                row = PurchaseUiPreferenceRecord(
                    id=self._ROW_ID,
                    selected_config_id=config_id,
                    updated_at=timestamp,
                )
                session.add(row)
            else:
                row.selected_config_id = config_id
                row.updated_at = timestamp
            session.commit()
            session.refresh(row)
            return PurchaseUiPreferences(
                selected_config_id=row.selected_config_id,
                updated_at=row.updated_at,
            )

    def clear_selected_config(self, *, updated_at: str | None = None) -> PurchaseUiPreferences:
        timestamp = updated_at or datetime.now().isoformat(timespec="seconds")
        with self._session_factory() as session:
            row = session.get(PurchaseUiPreferenceRecord, self._ROW_ID)
            if row is None:
                row = PurchaseUiPreferenceRecord(
                    id=self._ROW_ID,
                    selected_config_id=None,
                    updated_at=timestamp,
                )
                session.add(row)
            else:
                row.selected_config_id = None
                row.updated_at = timestamp
            session.commit()
            session.refresh(row)
            return PurchaseUiPreferences(
                selected_config_id=row.selected_config_id,
                updated_at=row.updated_at,
            )
