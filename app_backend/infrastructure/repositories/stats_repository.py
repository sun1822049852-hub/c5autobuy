from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app_backend.infrastructure.db.models import (
    AccountCapabilityStatsDailyRecord,
    AccountCapabilityStatsTotalRecord,
    QueryItemRuleStatsDailyRecord,
    QueryItemRuleStatsTotalRecord,
    QueryItemStatsDailyRecord,
    QueryItemStatsTotalRecord,
)


class SqliteStatsRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def apply_query_execution_event(self, event: object) -> None:
        timestamp = self._get_str(event, "timestamp")
        stat_date = self._stat_date(timestamp)
        with self._session_factory() as session:
            total_row = self._ensure_query_item_total(session, event, timestamp=timestamp)
            daily_row = self._ensure_query_item_daily(session, event, stat_date=stat_date, timestamp=timestamp)
            total_row.query_execution_count += 1
            daily_row.query_execution_count += 1

            rule_total = self._ensure_query_item_rule_total(session, event, timestamp=timestamp)
            rule_daily = self._ensure_query_item_rule_daily(session, event, stat_date=stat_date, timestamp=timestamp)
            rule_total.query_execution_count += 1
            rule_daily.query_execution_count += 1

            self._update_account_capability_row(
                row=self._ensure_account_capability_total(
                    session,
                    event,
                    mode_type=self._get_str(event, "mode_type"),
                    phase="query",
                    timestamp=timestamp,
                ),
                latency_ms=self._get_float(event, "latency_ms"),
                succeeded=bool(getattr(event, "success", False)),
                error=self._get_optional_str(event, "error"),
                timestamp=timestamp,
            )
            self._update_account_capability_row(
                row=self._ensure_account_capability_daily(
                    session,
                    event,
                    mode_type=self._get_str(event, "mode_type"),
                    phase="query",
                    stat_date=stat_date,
                    timestamp=timestamp,
                ),
                latency_ms=self._get_float(event, "latency_ms"),
                succeeded=bool(getattr(event, "success", False)),
                error=self._get_optional_str(event, "error"),
                timestamp=timestamp,
            )
            session.commit()

    def apply_query_hit_event(self, event: object) -> None:
        timestamp = self._get_str(event, "timestamp")
        stat_date = self._stat_date(timestamp)
        matched_count = max(int(getattr(event, "matched_count", 0) or 0), 0)
        if matched_count <= 0:
            return
        mode_type = self._get_str(event, "mode_type")
        with self._session_factory() as session:
            total_row = self._ensure_query_item_total(session, event, timestamp=timestamp)
            daily_row = self._ensure_query_item_daily(session, event, stat_date=stat_date, timestamp=timestamp)
            total_row.matched_product_count += matched_count
            daily_row.matched_product_count += matched_count
            self._increment_source_counter(total_row, mode_type, matched_count)
            self._increment_source_counter(daily_row, mode_type, matched_count)
            total_row.last_hit_at = self._latest_timestamp(total_row.last_hit_at, timestamp)

            rule_total = self._ensure_query_item_rule_total(session, event, timestamp=timestamp)
            rule_daily = self._ensure_query_item_rule_daily(session, event, stat_date=stat_date, timestamp=timestamp)
            rule_total.matched_product_count += matched_count
            rule_daily.matched_product_count += matched_count
            session.commit()

    def apply_purchase_create_order_event(self, event: object) -> None:
        timestamp = self._get_str(event, "timestamp")
        stat_date = self._stat_date(timestamp)
        succeeded = self._status_is_success(self._get_optional_str(event, "status"))
        error = self._get_optional_str(event, "error")
        latency_ms = self._get_float(event, "create_order_latency_ms")
        with self._session_factory() as session:
            self._update_account_capability_row(
                row=self._ensure_account_capability_total(
                    session,
                    event,
                    mode_type="purchase",
                    phase="create_order",
                    timestamp=timestamp,
                ),
                latency_ms=latency_ms,
                succeeded=succeeded,
                error=error,
                timestamp=timestamp,
            )
            self._update_account_capability_row(
                row=self._ensure_account_capability_daily(
                    session,
                    event,
                    mode_type="purchase",
                    phase="create_order",
                    stat_date=stat_date,
                    timestamp=timestamp,
                ),
                latency_ms=latency_ms,
                succeeded=succeeded,
                error=error,
                timestamp=timestamp,
            )
            session.commit()

    def apply_purchase_submit_order_event(self, event: object) -> None:
        timestamp = self._get_str(event, "timestamp")
        stat_date = self._stat_date(timestamp)
        success_count = max(int(getattr(event, "success_count", 0) or 0), 0)
        failed_count = max(int(getattr(event, "failed_count", 0) or 0), 0)
        succeeded = self._status_is_success(self._get_optional_str(event, "status"))
        error = self._get_optional_str(event, "error")
        latency_ms = self._get_float(event, "submit_order_latency_ms")
        with self._session_factory() as session:
            total_row = self._ensure_query_item_total(session, event, timestamp=timestamp)
            daily_row = self._ensure_query_item_daily(session, event, stat_date=stat_date, timestamp=timestamp)
            total_row.purchase_success_count += success_count
            total_row.purchase_failed_count += failed_count
            daily_row.purchase_success_count += success_count
            daily_row.purchase_failed_count += failed_count
            if success_count > 0:
                total_row.last_success_at = self._latest_timestamp(total_row.last_success_at, timestamp)
            if failed_count > 0:
                total_row.last_failure_at = self._latest_timestamp(total_row.last_failure_at, timestamp)

            rule_total = self._ensure_query_item_rule_total(session, event, timestamp=timestamp)
            rule_daily = self._ensure_query_item_rule_daily(session, event, stat_date=stat_date, timestamp=timestamp)
            rule_total.purchase_success_count += success_count
            rule_total.purchase_failed_count += failed_count
            rule_daily.purchase_success_count += success_count
            rule_daily.purchase_failed_count += failed_count

            self._update_account_capability_row(
                row=self._ensure_account_capability_total(
                    session,
                    event,
                    mode_type="purchase",
                    phase="submit_order",
                    timestamp=timestamp,
                ),
                latency_ms=latency_ms,
                succeeded=succeeded,
                error=error,
                timestamp=timestamp,
            )
            self._update_account_capability_row(
                row=self._ensure_account_capability_daily(
                    session,
                    event,
                    mode_type="purchase",
                    phase="submit_order",
                    stat_date=stat_date,
                    timestamp=timestamp,
                ),
                latency_ms=latency_ms,
                succeeded=succeeded,
                error=error,
                timestamp=timestamp,
            )
            session.commit()

    def list_query_item_stats(
        self,
        *,
        range_mode: str,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, object]]:
        with self._session_factory() as session:
            if range_mode == "total":
                rows = session.scalars(
                    select(QueryItemStatsTotalRecord).order_by(QueryItemStatsTotalRecord.external_item_id)
                ).all()
                return [self._serialize_query_item_stats_row(row) for row in rows]
            if range_mode == "day":
                rows = session.scalars(
                    select(QueryItemStatsDailyRecord)
                    .where(QueryItemStatsDailyRecord.stat_date == date)
                    .order_by(QueryItemStatsDailyRecord.external_item_id)
                ).all()
                return [self._serialize_query_item_stats_row(row) for row in rows]
            if range_mode == "range":
                rows = session.scalars(
                    select(QueryItemStatsDailyRecord)
                    .where(QueryItemStatsDailyRecord.stat_date >= str(start_date))
                    .where(QueryItemStatsDailyRecord.stat_date <= str(end_date))
                    .order_by(QueryItemStatsDailyRecord.external_item_id, QueryItemStatsDailyRecord.stat_date)
                ).all()
                return self._aggregate_query_item_daily_rows(rows)
        raise ValueError(f"Unsupported range_mode: {range_mode}")

    def list_account_capability_stats(
        self,
        *,
        range_mode: str,
        date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, object]]:
        with self._session_factory() as session:
            if range_mode == "total":
                rows = session.scalars(
                    select(AccountCapabilityStatsTotalRecord).order_by(
                        AccountCapabilityStatsTotalRecord.account_id,
                        AccountCapabilityStatsTotalRecord.phase,
                        AccountCapabilityStatsTotalRecord.mode_type,
                    )
                ).all()
                return [self._serialize_account_capability_row(row) for row in rows]
            if range_mode == "day":
                rows = session.scalars(
                    select(AccountCapabilityStatsDailyRecord)
                    .where(AccountCapabilityStatsDailyRecord.stat_date == date)
                    .order_by(
                        AccountCapabilityStatsDailyRecord.account_id,
                        AccountCapabilityStatsDailyRecord.phase,
                        AccountCapabilityStatsDailyRecord.mode_type,
                    )
                ).all()
                return [self._serialize_account_capability_row(row) for row in rows]
            if range_mode == "range":
                rows = session.scalars(
                    select(AccountCapabilityStatsDailyRecord)
                    .where(AccountCapabilityStatsDailyRecord.stat_date >= str(start_date))
                    .where(AccountCapabilityStatsDailyRecord.stat_date <= str(end_date))
                    .order_by(
                        AccountCapabilityStatsDailyRecord.account_id,
                        AccountCapabilityStatsDailyRecord.phase,
                        AccountCapabilityStatsDailyRecord.mode_type,
                        AccountCapabilityStatsDailyRecord.stat_date,
                    )
                ).all()
                return self._aggregate_account_capability_daily_rows(rows)
        raise ValueError(f"Unsupported range_mode: {range_mode}")

    @staticmethod
    def _get_str(payload: object, field_name: str) -> str:
        value = getattr(payload, field_name, "")
        return str(value or "")

    @staticmethod
    def _get_optional_str(payload: object, field_name: str) -> str | None:
        value = getattr(payload, field_name, None)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _get_float(payload: object, field_name: str) -> float:
        value = getattr(payload, field_name, 0) or 0
        return float(value)

    @staticmethod
    def _stat_date(timestamp: str) -> str:
        return str(timestamp or "")[:10]

    @staticmethod
    def _latest_timestamp(current: str | None, candidate: str | None) -> str | None:
        if not candidate:
            return current
        if not current:
            return candidate
        return candidate if candidate >= current else current

    @staticmethod
    def _status_is_success(status: str | None) -> bool:
        return str(status or "").lower() in {"success", "payment_success_no_items"}

    @staticmethod
    def _increment_source_counter(row: QueryItemStatsTotalRecord | QueryItemStatsDailyRecord, mode_type: str, count: int) -> None:
        if mode_type == "new_api":
            row.new_api_hit_count += count
        elif mode_type == "fast_api":
            row.fast_api_hit_count += count
        else:
            row.browser_hit_count += count

    def _ensure_query_item_total(self, session, event: object, *, timestamp: str) -> QueryItemStatsTotalRecord:
        external_item_id = self._get_str(event, "external_item_id")
        row = session.get(QueryItemStatsTotalRecord, external_item_id)
        if row is None:
            row = QueryItemStatsTotalRecord(
                external_item_id=external_item_id,
                item_name_snapshot=self._get_optional_str(event, "item_name"),
                product_url_snapshot=self._get_optional_str(event, "product_url"),
                query_execution_count=0,
                matched_product_count=0,
                purchase_success_count=0,
                purchase_failed_count=0,
                new_api_hit_count=0,
                fast_api_hit_count=0,
                browser_hit_count=0,
                updated_at=timestamp,
            )
            session.add(row)
        self._update_item_snapshots(row, event, timestamp=timestamp)
        return row

    def _ensure_query_item_daily(
        self,
        session,
        event: object,
        *,
        stat_date: str,
        timestamp: str,
    ) -> QueryItemStatsDailyRecord:
        external_item_id = self._get_str(event, "external_item_id")
        row = session.get(
            QueryItemStatsDailyRecord,
            {"external_item_id": external_item_id, "stat_date": stat_date},
        )
        if row is None:
            row = QueryItemStatsDailyRecord(
                external_item_id=external_item_id,
                stat_date=stat_date,
                item_name_snapshot=self._get_optional_str(event, "item_name"),
                product_url_snapshot=self._get_optional_str(event, "product_url"),
                query_execution_count=0,
                matched_product_count=0,
                purchase_success_count=0,
                purchase_failed_count=0,
                new_api_hit_count=0,
                fast_api_hit_count=0,
                browser_hit_count=0,
                updated_at=timestamp,
            )
            session.add(row)
        self._update_item_snapshots(row, event, timestamp=timestamp)
        return row

    def _ensure_query_item_rule_total(self, session, event: object, *, timestamp: str) -> QueryItemRuleStatsTotalRecord:
        external_item_id = self._get_str(event, "external_item_id")
        rule_fingerprint = self._get_str(event, "rule_fingerprint")
        row = session.get(
            QueryItemRuleStatsTotalRecord,
            {"external_item_id": external_item_id, "rule_fingerprint": rule_fingerprint},
        )
        if row is None:
            row = QueryItemRuleStatsTotalRecord(
                external_item_id=external_item_id,
                rule_fingerprint=rule_fingerprint,
                detail_min_wear=getattr(event, "detail_min_wear", None),
                detail_max_wear=getattr(event, "detail_max_wear", None),
                max_price=getattr(event, "max_price", None),
                query_execution_count=0,
                matched_product_count=0,
                purchase_success_count=0,
                purchase_failed_count=0,
                updated_at=timestamp,
            )
            session.add(row)
        self._update_rule_row(row, event, timestamp=timestamp)
        return row

    def _ensure_query_item_rule_daily(
        self,
        session,
        event: object,
        *,
        stat_date: str,
        timestamp: str,
    ) -> QueryItemRuleStatsDailyRecord:
        external_item_id = self._get_str(event, "external_item_id")
        rule_fingerprint = self._get_str(event, "rule_fingerprint")
        row = session.get(
            QueryItemRuleStatsDailyRecord,
            {
                "external_item_id": external_item_id,
                "rule_fingerprint": rule_fingerprint,
                "stat_date": stat_date,
            },
        )
        if row is None:
            row = QueryItemRuleStatsDailyRecord(
                external_item_id=external_item_id,
                rule_fingerprint=rule_fingerprint,
                stat_date=stat_date,
                detail_min_wear=getattr(event, "detail_min_wear", None),
                detail_max_wear=getattr(event, "detail_max_wear", None),
                max_price=getattr(event, "max_price", None),
                query_execution_count=0,
                matched_product_count=0,
                purchase_success_count=0,
                purchase_failed_count=0,
                updated_at=timestamp,
            )
            session.add(row)
        self._update_rule_row(row, event, timestamp=timestamp)
        return row

    def _ensure_account_capability_total(
        self,
        session,
        event: object,
        *,
        mode_type: str,
        phase: str,
        timestamp: str,
    ) -> AccountCapabilityStatsTotalRecord:
        account_id = self._get_str(event, "account_id")
        row = session.get(
            AccountCapabilityStatsTotalRecord,
            {"account_id": account_id, "mode_type": mode_type, "phase": phase},
        )
        if row is None:
            row = AccountCapabilityStatsTotalRecord(
                account_id=account_id,
                mode_type=mode_type,
                phase=phase,
                account_display_name_snapshot=self._get_optional_str(event, "account_display_name"),
                sample_count=0,
                success_count=0,
                failure_count=0,
                total_latency_ms=0,
                max_latency_ms=0,
                updated_at=timestamp,
            )
            session.add(row)
        self._update_account_capability_metadata(row, event, timestamp=timestamp)
        return row

    def _ensure_account_capability_daily(
        self,
        session,
        event: object,
        *,
        mode_type: str,
        phase: str,
        stat_date: str,
        timestamp: str,
    ) -> AccountCapabilityStatsDailyRecord:
        account_id = self._get_str(event, "account_id")
        row = session.get(
            AccountCapabilityStatsDailyRecord,
            {
                "account_id": account_id,
                "mode_type": mode_type,
                "phase": phase,
                "stat_date": stat_date,
            },
        )
        if row is None:
            row = AccountCapabilityStatsDailyRecord(
                account_id=account_id,
                mode_type=mode_type,
                phase=phase,
                stat_date=stat_date,
                account_display_name_snapshot=self._get_optional_str(event, "account_display_name"),
                sample_count=0,
                success_count=0,
                failure_count=0,
                total_latency_ms=0,
                max_latency_ms=0,
                updated_at=timestamp,
            )
            session.add(row)
        self._update_account_capability_metadata(row, event, timestamp=timestamp)
        return row

    def _update_account_capability_row(
        self,
        *,
        row: AccountCapabilityStatsTotalRecord | AccountCapabilityStatsDailyRecord,
        latency_ms: float,
        succeeded: bool,
        error: str | None,
        timestamp: str,
    ) -> None:
        row.sample_count += 1
        if succeeded:
            row.success_count += 1
        else:
            row.failure_count += 1
        row.total_latency_ms += latency_ms
        row.max_latency_ms = max(float(row.max_latency_ms or 0), latency_ms)
        row.last_latency_ms = latency_ms
        row.last_error = error
        row.updated_at = timestamp

    def _update_item_snapshots(
        self,
        row: QueryItemStatsTotalRecord | QueryItemStatsDailyRecord,
        event: object,
        *,
        timestamp: str,
    ) -> None:
        item_name = self._get_optional_str(event, "item_name")
        product_url = self._get_optional_str(event, "product_url")
        if item_name is not None:
            row.item_name_snapshot = item_name
        if product_url is not None:
            row.product_url_snapshot = product_url
        row.updated_at = timestamp

    @staticmethod
    def _update_rule_row(
        row: QueryItemRuleStatsTotalRecord | QueryItemRuleStatsDailyRecord,
        event: object,
        *,
        timestamp: str,
    ) -> None:
        if getattr(event, "detail_min_wear", None) is not None:
            row.detail_min_wear = float(getattr(event, "detail_min_wear"))
        if getattr(event, "detail_max_wear", None) is not None:
            row.detail_max_wear = float(getattr(event, "detail_max_wear"))
        if getattr(event, "max_price", None) is not None:
            row.max_price = float(getattr(event, "max_price"))
        row.updated_at = timestamp

    def _update_account_capability_metadata(
        self,
        row: AccountCapabilityStatsTotalRecord | AccountCapabilityStatsDailyRecord,
        event: object,
        *,
        timestamp: str,
    ) -> None:
        display_name = self._get_optional_str(event, "account_display_name")
        if display_name is not None:
            row.account_display_name_snapshot = display_name
        row.updated_at = timestamp

    def _serialize_query_item_stats_row(
        self,
        row: QueryItemStatsTotalRecord | QueryItemStatsDailyRecord,
    ) -> dict[str, object]:
        return {
            "external_item_id": row.external_item_id,
            "item_name": row.item_name_snapshot,
            "product_url": row.product_url_snapshot,
            "query_execution_count": int(row.query_execution_count),
            "matched_product_count": int(row.matched_product_count),
            "purchase_success_count": int(row.purchase_success_count),
            "purchase_failed_count": int(row.purchase_failed_count),
            "source_mode_stats": self._serialize_source_mode_stats(row),
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _serialize_source_mode_stats(
        row: QueryItemStatsTotalRecord | QueryItemStatsDailyRecord,
    ) -> list[dict[str, object]]:
        sources = []
        if int(row.new_api_hit_count) > 0:
            sources.append({"mode_type": "new_api", "hit_count": int(row.new_api_hit_count)})
        if int(row.fast_api_hit_count) > 0:
            sources.append({"mode_type": "fast_api", "hit_count": int(row.fast_api_hit_count)})
        if int(row.browser_hit_count) > 0:
            sources.append({"mode_type": "browser", "hit_count": int(row.browser_hit_count)})
        sources.sort(key=lambda source: (-int(source["hit_count"]), str(source["mode_type"])))
        return sources

    def _aggregate_query_item_daily_rows(self, rows: list[QueryItemStatsDailyRecord]) -> list[dict[str, object]]:
        grouped: dict[str, dict[str, object]] = {}
        for row in rows:
            target = grouped.setdefault(
                row.external_item_id,
                {
                    "external_item_id": row.external_item_id,
                    "item_name": row.item_name_snapshot,
                    "product_url": row.product_url_snapshot,
                    "query_execution_count": 0,
                    "matched_product_count": 0,
                    "purchase_success_count": 0,
                    "purchase_failed_count": 0,
                    "new_api_hit_count": 0,
                    "fast_api_hit_count": 0,
                    "browser_hit_count": 0,
                    "updated_at": row.updated_at,
                },
            )
            target["item_name"] = row.item_name_snapshot or target["item_name"]
            target["product_url"] = row.product_url_snapshot or target["product_url"]
            target["query_execution_count"] += int(row.query_execution_count)
            target["matched_product_count"] += int(row.matched_product_count)
            target["purchase_success_count"] += int(row.purchase_success_count)
            target["purchase_failed_count"] += int(row.purchase_failed_count)
            target["new_api_hit_count"] += int(row.new_api_hit_count)
            target["fast_api_hit_count"] += int(row.fast_api_hit_count)
            target["browser_hit_count"] += int(row.browser_hit_count)
            target["updated_at"] = self._latest_timestamp(str(target["updated_at"]), row.updated_at)

        result = []
        for row in grouped.values():
            result.append(
                {
                    "external_item_id": row["external_item_id"],
                    "item_name": row["item_name"],
                    "product_url": row["product_url"],
                    "query_execution_count": row["query_execution_count"],
                    "matched_product_count": row["matched_product_count"],
                    "purchase_success_count": row["purchase_success_count"],
                    "purchase_failed_count": row["purchase_failed_count"],
                    "source_mode_stats": self._serialize_source_counts(
                        new_api_hit_count=int(row["new_api_hit_count"]),
                        fast_api_hit_count=int(row["fast_api_hit_count"]),
                        browser_hit_count=int(row["browser_hit_count"]),
                    ),
                    "updated_at": row["updated_at"],
                }
            )
        result.sort(key=lambda row: str(row["external_item_id"]))
        return result

    def _serialize_account_capability_row(
        self,
        row: AccountCapabilityStatsTotalRecord | AccountCapabilityStatsDailyRecord,
    ) -> dict[str, object]:
        return {
            "account_id": row.account_id,
            "account_display_name": row.account_display_name_snapshot,
            "mode_type": row.mode_type,
            "phase": row.phase,
            "sample_count": int(row.sample_count),
            "success_count": int(row.success_count),
            "failure_count": int(row.failure_count),
            "total_latency_ms": float(row.total_latency_ms),
            "max_latency_ms": float(row.max_latency_ms),
            "last_latency_ms": float(row.last_latency_ms) if row.last_latency_ms is not None else None,
            "last_error": row.last_error,
            "updated_at": row.updated_at,
        }

    def _aggregate_account_capability_daily_rows(
        self,
        rows: list[AccountCapabilityStatsDailyRecord],
    ) -> list[dict[str, object]]:
        grouped: dict[tuple[str, str, str], dict[str, object]] = {}
        for row in rows:
            key = (row.account_id, row.mode_type, row.phase)
            target = grouped.setdefault(
                key,
                {
                    "account_id": row.account_id,
                    "account_display_name": row.account_display_name_snapshot,
                    "mode_type": row.mode_type,
                    "phase": row.phase,
                    "sample_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "total_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                    "last_latency_ms": None,
                    "last_error": None,
                    "updated_at": row.updated_at,
                },
            )
            target["account_display_name"] = row.account_display_name_snapshot or target["account_display_name"]
            target["sample_count"] += int(row.sample_count)
            target["success_count"] += int(row.success_count)
            target["failure_count"] += int(row.failure_count)
            target["total_latency_ms"] += float(row.total_latency_ms)
            target["max_latency_ms"] = max(float(target["max_latency_ms"]), float(row.max_latency_ms))
            target["last_latency_ms"] = row.last_latency_ms
            target["last_error"] = row.last_error
            target["updated_at"] = self._latest_timestamp(str(target["updated_at"]), row.updated_at)

        result = list(grouped.values())
        result.sort(key=lambda row: (str(row["account_id"]), str(row["phase"]), str(row["mode_type"])))
        return result

    @staticmethod
    def _serialize_source_counts(
        *,
        new_api_hit_count: int,
        fast_api_hit_count: int,
        browser_hit_count: int,
    ) -> list[dict[str, object]]:
        rows = []
        if new_api_hit_count > 0:
            rows.append({"mode_type": "new_api", "hit_count": new_api_hit_count})
        if fast_api_hit_count > 0:
            rows.append({"mode_type": "fast_api", "hit_count": fast_api_hit_count})
        if browser_hit_count > 0:
            rows.append({"mode_type": "browser", "hit_count": browser_hit_count})
        rows.sort(key=lambda row: (-int(row["hit_count"]), str(row["mode_type"])))
        return rows
