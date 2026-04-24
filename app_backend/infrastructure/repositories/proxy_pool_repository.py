from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app_backend.domain.models.proxy_pool_entry import ProxyPoolEntry
from app_backend.infrastructure.db.models import ProxyPoolRecord


class SqliteProxyPoolRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def list_all(self) -> list[ProxyPoolEntry]:
        with self._session_factory() as session:
            rows = session.scalars(select(ProxyPoolRecord).order_by(ProxyPoolRecord.created_at)).all()
            return [self._to_domain(row) for row in rows]

    def get(self, proxy_id: str) -> ProxyPoolEntry | None:
        with self._session_factory() as session:
            row = session.get(ProxyPoolRecord, proxy_id)
            return self._to_domain(row) if row else None

    def create(self, entry: ProxyPoolEntry) -> ProxyPoolEntry:
        with self._session_factory() as session:
            row = ProxyPoolRecord(
                proxy_id=entry.proxy_id,
                name=entry.name,
                scheme=entry.scheme,
                host=entry.host,
                port=entry.port,
                username=entry.username,
                password=entry.password,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def update(self, proxy_id: str, **changes) -> ProxyPoolEntry:
        with self._session_factory() as session:
            row = session.get(ProxyPoolRecord, proxy_id)
            if row is None:
                raise KeyError(proxy_id)
            for key, value in changes.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def delete(self, proxy_id: str) -> None:
        with self._session_factory() as session:
            row = session.get(ProxyPoolRecord, proxy_id)
            if row is None:
                return
            session.delete(row)
            session.commit()

    @staticmethod
    def _to_domain(row: ProxyPoolRecord) -> ProxyPoolEntry:
        return ProxyPoolEntry(
            proxy_id=row.proxy_id,
            name=row.name,
            scheme=row.scheme,
            host=row.host,
            port=row.port,
            username=row.username,
            password=row.password,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
