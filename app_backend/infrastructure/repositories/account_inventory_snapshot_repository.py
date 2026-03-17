from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import sessionmaker

from app_backend.domain.models.account_inventory_snapshot import AccountInventorySnapshot
from app_backend.infrastructure.db.models import AccountInventorySnapshotRecord


class SqliteAccountInventorySnapshotRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get(self, account_id: str) -> AccountInventorySnapshot | None:
        with self._session_factory() as session:
            row = session.get(AccountInventorySnapshotRecord, account_id)
            return self._to_domain(row) if row is not None else None

    def save(
        self,
        *,
        account_id: str,
        selected_steam_id: str | None,
        inventories: list[dict[str, Any]],
        refreshed_at: str | None = None,
        last_error: str | None = None,
    ) -> AccountInventorySnapshot:
        with self._session_factory() as session:
            row = session.get(AccountInventorySnapshotRecord, account_id)
            if row is None:
                row = AccountInventorySnapshotRecord(account_id=account_id)
                session.add(row)
            row.selected_steam_id = selected_steam_id
            row.inventories_json = json.dumps(list(inventories), ensure_ascii=True)
            row.refreshed_at = refreshed_at
            row.last_error = last_error
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    @staticmethod
    def _to_domain(row: AccountInventorySnapshotRecord) -> AccountInventorySnapshot:
        try:
            raw_inventories: Any = json.loads(row.inventories_json or "[]")
        except json.JSONDecodeError:
            raw_inventories = []
        inventories = list(raw_inventories) if isinstance(raw_inventories, list) else []
        return AccountInventorySnapshot(
            account_id=row.account_id,
            selected_steam_id=row.selected_steam_id,
            inventories=inventories,
            refreshed_at=row.refreshed_at,
            last_error=row.last_error,
        )
