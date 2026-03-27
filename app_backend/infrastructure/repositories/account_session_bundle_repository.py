from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app_backend.infrastructure.db.models import AccountSessionBundleRecord
from app_backend.infrastructure.session_bundle.models import (
    AccountSessionBundle,
    AccountSessionBundleState,
)
from app_backend.infrastructure.session_bundle.protection import dump_payload, load_payload


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SqliteAccountSessionBundleRepository:
    def __init__(self, session_factory: sessionmaker, *, storage_root: Path) -> None:
        self._session_factory = session_factory
        self._storage_root = Path(storage_root)
        self._storage_root.mkdir(parents=True, exist_ok=True)

    def stage_bundle(
        self,
        *,
        payload: dict[str, Any],
        account_id: str | None = None,
        captured_c5_user_id: str | None = None,
        schema_version: int = 1,
    ) -> AccountSessionBundle:
        bundle_id = str(uuid4())
        payload_path = self._payload_path(bundle_id)
        self._write_payload(payload_path, payload)
        timestamp = _now()

        with self._session_factory() as session:
            row = AccountSessionBundleRecord(
                bundle_id=bundle_id,
                account_id=account_id,
                captured_c5_user_id=captured_c5_user_id,
                state=AccountSessionBundleState.STAGED.value,
                schema_version=schema_version,
                payload_path=str(payload_path),
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def mark_bundle_verified(self, bundle_id: str) -> AccountSessionBundle:
        with self._session_factory() as session:
            row = session.get(AccountSessionBundleRecord, bundle_id)
            if row is None:
                raise KeyError(bundle_id)
            if row.state == AccountSessionBundleState.DELETED.value:
                raise ValueError("Cannot verify deleted bundle")
            row.state = AccountSessionBundleState.VERIFIED.value
            row.updated_at = _now()
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def activate_bundle(self, bundle_id: str, *, account_id: str) -> AccountSessionBundle:
        with self._session_factory() as session:
            row = session.get(AccountSessionBundleRecord, bundle_id)
            if row is None:
                raise KeyError(bundle_id)
            if row.state not in {
                AccountSessionBundleState.VERIFIED.value,
                AccountSessionBundleState.ACTIVE.value,
            }:
                raise ValueError("Bundle must be verified before activation")

            timestamp = _now()
            previous_rows = session.scalars(
                select(AccountSessionBundleRecord).where(
                    AccountSessionBundleRecord.account_id == account_id,
                    AccountSessionBundleRecord.state == AccountSessionBundleState.ACTIVE.value,
                    AccountSessionBundleRecord.bundle_id != bundle_id,
                )
            ).all()
            for previous in previous_rows:
                previous.state = AccountSessionBundleState.SUPERSEDED.value
                previous.updated_at = timestamp

            row.account_id = account_id
            row.state = AccountSessionBundleState.ACTIVE.value
            row.updated_at = timestamp
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def get_bundle(self, bundle_id: str) -> AccountSessionBundle | None:
        with self._session_factory() as session:
            row = session.get(AccountSessionBundleRecord, bundle_id)
            return self._to_domain(row) if row is not None else None

    def get_active_bundle(self, account_id: str) -> AccountSessionBundle | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(AccountSessionBundleRecord).where(
                    AccountSessionBundleRecord.account_id == account_id,
                    AccountSessionBundleRecord.state == AccountSessionBundleState.ACTIVE.value,
                )
            ).first()
            if row is None:
                return None
            bundle = self._to_domain(row)
            return bundle if bundle.payload else None

    def list_bundles(
        self,
        *,
        account_id: str | None = None,
        include_deleted: bool = False,
    ) -> list[AccountSessionBundle]:
        statement = select(AccountSessionBundleRecord).order_by(AccountSessionBundleRecord.created_at)
        if account_id is not None:
            statement = statement.where(AccountSessionBundleRecord.account_id == account_id)
        if not include_deleted:
            statement = statement.where(AccountSessionBundleRecord.state != AccountSessionBundleState.DELETED.value)

        with self._session_factory() as session:
            rows = session.scalars(statement).all()
            return [self._to_domain(row) for row in rows]

    def delete_bundle(self, bundle_id: str) -> None:
        with self._session_factory() as session:
            row = session.get(AccountSessionBundleRecord, bundle_id)
            if row is None:
                return
            payload_path = Path(row.payload_path)
            row.state = AccountSessionBundleState.DELETED.value
            row.updated_at = _now()
            session.commit()
        payload_path.unlink(missing_ok=True)

    def delete_account_bundles(self, account_id: str) -> None:
        with self._session_factory() as session:
            rows = session.scalars(
                select(AccountSessionBundleRecord).where(AccountSessionBundleRecord.account_id == account_id)
            ).all()
            if not rows:
                return
            payload_paths = [Path(row.payload_path) for row in rows]
            timestamp = _now()
            for row in rows:
                row.state = AccountSessionBundleState.DELETED.value
                row.updated_at = timestamp
            session.commit()

        for payload_path in payload_paths:
            payload_path.unlink(missing_ok=True)

    def _payload_path(self, bundle_id: str) -> Path:
        return self._storage_root / f"{bundle_id}.bin"

    def _write_payload(self, payload_path: Path, payload: dict[str, Any]) -> None:
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = payload_path.with_suffix(f"{payload_path.suffix}.{uuid4().hex}.tmp")
        temp_path.write_bytes(dump_payload(payload))
        temp_path.replace(payload_path)

    @staticmethod
    def _read_payload(payload_path: Path) -> dict[str, Any]:
        if not payload_path.exists():
            return {}
        return load_payload(payload_path.read_bytes())

    def _to_domain(self, row: AccountSessionBundleRecord) -> AccountSessionBundle:
        payload_path = Path(row.payload_path)
        return AccountSessionBundle(
            bundle_id=row.bundle_id,
            account_id=row.account_id,
            captured_c5_user_id=row.captured_c5_user_id,
            state=AccountSessionBundleState(row.state),
            schema_version=row.schema_version,
            payload_path=payload_path,
            payload=self._read_payload(payload_path),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
