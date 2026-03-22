from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app_backend.domain.enums.query_modes import QueryMode
from app_backend.domain.models.query_settings import QuerySettings, QuerySettingsMode
from app_backend.infrastructure.db.models import QuerySettingsModeRecord


def _default_mode_payload(mode_type: str, now: str) -> dict[str, object]:
    if mode_type == QueryMode.NEW_API:
        cooldown = 1.0
    elif mode_type == QueryMode.FAST_API:
        cooldown = 0.2
    else:
        cooldown = 10.0
    return {
        "mode_type": mode_type,
        "enabled": 1,
        "window_enabled": 0,
        "start_hour": 0,
        "start_minute": 0,
        "end_hour": 0,
        "end_minute": 0,
        "base_cooldown_min": cooldown,
        "base_cooldown_max": cooldown,
        "item_min_cooldown_seconds": 0.5,
        "item_min_cooldown_strategy": "divide_by_assigned_count",
        "random_delay_enabled": 0,
        "random_delay_min": 0.0,
        "random_delay_max": 0.0,
        "created_at": now,
        "updated_at": now,
    }


class SqliteQuerySettingsRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get_settings(self) -> QuerySettings:
        with self._session_factory() as session:
            rows = self._ensure_default_rows(session)
            return self._to_settings(rows)

    def update_settings(self, modes: list[dict[str, object]]) -> QuerySettings:
        normalized_modes = {
            str(mode.get("mode_type") or ""): mode
            for mode in modes
            if str(mode.get("mode_type") or "")
        }
        with self._session_factory() as session:
            rows = self._ensure_default_rows(session)
            row_by_mode = {
                row.mode_type: row
                for row in rows
            }
            now = datetime.now().isoformat(timespec="seconds")
            for mode_type in QueryMode.ALL:
                payload = normalized_modes.get(mode_type)
                if payload is None:
                    continue
                row = row_by_mode[mode_type]
                row.enabled = int(bool(payload.get("enabled")))
                row.window_enabled = int(bool(payload.get("window_enabled")))
                row.start_hour = int(payload.get("start_hour", 0))
                row.start_minute = int(payload.get("start_minute", 0))
                row.end_hour = int(payload.get("end_hour", 0))
                row.end_minute = int(payload.get("end_minute", 0))
                row.base_cooldown_min = float(payload.get("base_cooldown_min", 0.0))
                row.base_cooldown_max = float(payload.get("base_cooldown_max", 0.0))
                row.item_min_cooldown_seconds = float(payload.get("item_min_cooldown_seconds", 0.5))
                row.item_min_cooldown_strategy = str(
                    payload.get("item_min_cooldown_strategy", "divide_by_assigned_count")
                )
                row.random_delay_enabled = int(bool(payload.get("random_delay_enabled")))
                row.random_delay_min = float(payload.get("random_delay_min", 0.0))
                row.random_delay_max = float(payload.get("random_delay_max", 0.0))
                row.updated_at = now
            session.commit()
            refreshed = session.scalars(
                select(QuerySettingsModeRecord).order_by(QuerySettingsModeRecord.mode_type)
            ).all()
            return self._to_settings(refreshed)

    def _ensure_default_rows(self, session) -> list[QuerySettingsModeRecord]:
        rows = session.scalars(
            select(QuerySettingsModeRecord).order_by(QuerySettingsModeRecord.mode_type)
        ).all()
        existing_modes = {
            row.mode_type
            for row in rows
        }
        missing_modes = [mode_type for mode_type in QueryMode.ALL if mode_type not in existing_modes]
        if missing_modes:
            now = datetime.now().isoformat(timespec="seconds")
            for mode_type in missing_modes:
                session.add(QuerySettingsModeRecord(**_default_mode_payload(mode_type, now)))
            session.commit()
            rows = session.scalars(
                select(QuerySettingsModeRecord).order_by(QuerySettingsModeRecord.mode_type)
            ).all()
        return rows

    @staticmethod
    def _to_settings(rows: list[QuerySettingsModeRecord]) -> QuerySettings:
        modes = [
            QuerySettingsMode(
                mode_type=row.mode_type,
                enabled=bool(row.enabled),
                window_enabled=bool(row.window_enabled),
                start_hour=row.start_hour,
                start_minute=row.start_minute,
                end_hour=row.end_hour,
                end_minute=row.end_minute,
                base_cooldown_min=row.base_cooldown_min,
                base_cooldown_max=row.base_cooldown_max,
                item_min_cooldown_seconds=float(getattr(row, "item_min_cooldown_seconds", 0.5)),
                item_min_cooldown_strategy=str(
                    getattr(row, "item_min_cooldown_strategy", "divide_by_assigned_count")
                ),
                random_delay_enabled=bool(row.random_delay_enabled),
                random_delay_min=row.random_delay_min,
                random_delay_max=row.random_delay_max,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        updated_at = max((mode.updated_at for mode in modes), default=None)
        return QuerySettings(modes=modes, updated_at=updated_at)
