from __future__ import annotations

from datetime import datetime


class GetPurchaseRuntimeStatusUseCase:
    def __init__(
        self,
        runtime_service,
        query_runtime_service=None,
        *,
        query_config_repository=None,
        purchase_ui_preferences_repository=None,
        stats_repository=None,
        stats_flush_callback=None,
        now_provider=None,
        include_recent_events: bool = True,
    ) -> None:
        self._runtime_service = runtime_service
        self._query_runtime_service = query_runtime_service
        self._query_config_repository = query_config_repository
        self._purchase_ui_preferences_repository = purchase_ui_preferences_repository
        self._stats_repository = stats_repository
        self._stats_flush_callback = stats_flush_callback if callable(stats_flush_callback) else None
        self._now_provider = now_provider or datetime.now
        self._include_recent_events = bool(include_recent_events)

    def execute(self) -> dict[str, object]:
        purchase_snapshot = dict(self._read_runtime_status())
        if self._query_runtime_service is None:
            purchase_snapshot.setdefault("active_query_config", None)
            purchase_snapshot["item_rows"] = self._build_inactive_item_rows() or []
            return purchase_snapshot

        query_snapshot = self._query_runtime_service.get_status()
        if not isinstance(query_snapshot, dict):
            purchase_snapshot.setdefault("active_query_config", None)
            purchase_snapshot["item_rows"] = self._build_inactive_item_rows() or []
            return purchase_snapshot

        active_query_config = self._build_active_query_config(query_snapshot)
        purchase_snapshot["active_query_config"] = active_query_config
        if active_query_config is None:
            purchase_snapshot["item_rows"] = self._build_inactive_item_rows() or []
            return purchase_snapshot

        purchase_snapshot["item_rows"] = self._build_active_item_rows(
            active_query_config=active_query_config,
            raw_purchase_item_rows=purchase_snapshot.get("item_rows"),
            raw_query_item_rows=query_snapshot.get("item_rows"),
        ) or self._build_item_rows(
            purchase_snapshot.get("item_rows"),
            query_snapshot.get("item_rows"),
        )
        return purchase_snapshot

    def _read_runtime_status(self) -> dict[str, object]:
        get_status = getattr(self._runtime_service, "get_status", None)
        if not callable(get_status):
            return {}
        try:
            snapshot = get_status(include_recent_events=self._include_recent_events)
        except TypeError:
            snapshot = get_status()
        if not isinstance(snapshot, dict):
            return {}
        normalized_snapshot = dict(snapshot)
        if not self._include_recent_events:
            normalized_snapshot["recent_events"] = []
        return normalized_snapshot

    @staticmethod
    def _build_active_query_config(query_snapshot: dict[str, object]) -> dict[str, object] | None:
        config_id = str(query_snapshot.get("config_id") or "").strip()
        if not config_id:
            return None
        message = str(query_snapshot.get("message") or "")
        return {
            "config_id": config_id,
            "config_name": query_snapshot.get("config_name"),
            "state": "running" if bool(query_snapshot.get("running")) else ("waiting" if message == "等待购买账号恢复" else "idle"),
            "message": message,
        }

    def _build_inactive_item_rows(self) -> list[dict[str, object]]:
        config = self._resolve_selected_config()
        if config is None:
            return []

        daily_stats = self._load_daily_stats_by_external_item_id()
        rows: list[dict[str, object]] = []
        for item in getattr(config, "items", []) or []:
            stats_row = daily_stats.get(str(getattr(item, "external_item_id", "") or ""), {})
            source_mode_stats = self._normalize_hit_sources(stats_row.get("source_mode_stats"))
            rows.append(
                {
                    "query_item_id": str(getattr(item, "query_item_id", "") or ""),
                    "item_name": (
                        getattr(item, "item_name", None)
                        or getattr(item, "market_hash_name", None)
                        or str(getattr(item, "query_item_id", "") or "")
                    ),
                    "max_price": getattr(item, "max_price", None),
                    "min_wear": getattr(item, "min_wear", None),
                    "max_wear": getattr(item, "max_wear", None),
                    "detail_min_wear": getattr(item, "detail_min_wear", None),
                    "detail_max_wear": getattr(item, "detail_max_wear", None),
                    "manual_paused": bool(getattr(item, "manual_paused", False)),
                    "query_execution_count": int(stats_row.get("query_execution_count", 0)),
                    "matched_product_count": int(stats_row.get("matched_product_count", 0)),
                    "purchase_success_count": int(stats_row.get("purchase_success_count", 0)),
                    "purchase_failed_count": int(stats_row.get("purchase_failed_count", 0)),
                    "modes": {},
                    "source_mode_stats": source_mode_stats,
                    "recent_hit_sources": list(source_mode_stats),
                }
            )
        return rows

    def _build_active_item_rows(
        self,
        *,
        active_query_config: dict[str, object],
        raw_purchase_item_rows: object,
        raw_query_item_rows: object,
    ) -> list[dict[str, object]]:
        config = self._resolve_config_by_id(active_query_config.get("config_id"))
        if config is None:
            return []

        daily_stats = self._load_daily_stats_by_external_item_id()
        query_rows_by_id: dict[str, dict[str, object]] = {}
        if isinstance(raw_query_item_rows, list):
            for row in raw_query_item_rows:
                if not isinstance(row, dict):
                    continue
                query_item_id = str(row.get("query_item_id") or "").strip()
                if not query_item_id:
                    continue
                query_rows_by_id[query_item_id] = dict(row)

        purchase_rows_by_id: dict[str, dict[str, object]] = {}
        if isinstance(raw_purchase_item_rows, list):
            for row in raw_purchase_item_rows:
                if not isinstance(row, dict):
                    continue
                query_item_id = str(row.get("query_item_id") or "").strip()
                if not query_item_id:
                    continue
                purchase_rows_by_id[query_item_id] = dict(row)

        rows: list[dict[str, object]] = []
        for item in getattr(config, "items", []) or []:
            query_item_id = str(getattr(item, "query_item_id", "") or "")
            query_row = query_rows_by_id.get(query_item_id, {})
            purchase_row = purchase_rows_by_id.get(query_item_id, {})
            stats_row = daily_stats.get(str(getattr(item, "external_item_id", "") or ""), {})
            source_mode_stats = self._normalize_hit_sources(
                purchase_row.get("source_mode_stats")
                if purchase_row.get("source_mode_stats")
                else stats_row.get("source_mode_stats")
            )
            recent_hit_sources = self._normalize_hit_sources(
                purchase_row.get("recent_hit_sources")
                if purchase_row.get("recent_hit_sources")
                else source_mode_stats
            )
            rows.append(
                {
                    "query_item_id": query_item_id,
                    "item_name": (
                        query_row.get("item_name")
                        or getattr(item, "item_name", None)
                        or getattr(item, "market_hash_name", None)
                        or query_item_id
                    ),
                    "max_price": query_row.get("max_price", getattr(item, "max_price", None)),
                    "min_wear": query_row.get("min_wear", getattr(item, "min_wear", None)),
                    "max_wear": query_row.get("max_wear", getattr(item, "max_wear", None)),
                    "detail_min_wear": query_row.get("detail_min_wear", getattr(item, "detail_min_wear", None)),
                    "detail_max_wear": query_row.get("detail_max_wear", getattr(item, "detail_max_wear", None)),
                    "manual_paused": bool(query_row.get("manual_paused", getattr(item, "manual_paused", False))),
                    "query_execution_count": int(stats_row.get("query_execution_count", query_row.get("query_count", 0))),
                    "matched_product_count": int(
                        stats_row.get("matched_product_count", purchase_row.get("matched_product_count", 0))
                    ),
                    "purchase_success_count": int(
                        stats_row.get("purchase_success_count", purchase_row.get("purchase_success_count", 0))
                    ),
                    "purchase_failed_count": int(
                        stats_row.get("purchase_failed_count", purchase_row.get("purchase_failed_count", 0))
                    ),
                    "modes": self._normalize_modes(query_row.get("modes")),
                    "source_mode_stats": source_mode_stats,
                    "recent_hit_sources": recent_hit_sources,
                }
            )
        return rows

    def _resolve_selected_config(self):
        if self._query_config_repository is None or self._purchase_ui_preferences_repository is None:
            return self._resolve_last_runtime_config()
        get_preferences = getattr(self._purchase_ui_preferences_repository, "get", None)
        get_config = getattr(self._query_config_repository, "get_config", None)
        if not callable(get_preferences) or not callable(get_config):
            return self._resolve_last_runtime_config()
        preferences = get_preferences()
        config_id = str(getattr(preferences, "selected_config_id", "") or "").strip()
        if not config_id:
            return self._resolve_last_runtime_config()
        config = get_config(config_id)
        if config is not None:
            return config
        return self._resolve_last_runtime_config()

    def _resolve_last_runtime_config(self):
        if self._query_config_repository is None or self._query_runtime_service is None:
            return None
        get_config = getattr(self._query_config_repository, "get_config", None)
        last_config_id_getter = getattr(self._query_runtime_service, "get_last_known_config_id", None)
        if not callable(get_config) or not callable(last_config_id_getter):
            return None
        config_id = str(last_config_id_getter() or "").strip()
        if not config_id:
            return None
        return get_config(config_id)

    def _resolve_config_by_id(self, config_id: object):
        if self._query_config_repository is None:
            return None
        get_config = getattr(self._query_config_repository, "get_config", None)
        if not callable(get_config):
            return None
        normalized_config_id = str(config_id or "").strip()
        if not normalized_config_id:
            return None
        return get_config(normalized_config_id)

    def _load_daily_stats_by_external_item_id(self) -> dict[str, dict[str, object]]:
        if self._stats_repository is None:
            return {}
        list_query_item_stats = getattr(self._stats_repository, "list_query_item_stats", None)
        if not callable(list_query_item_stats):
            return {}
        self._flush_pending_stats()
        stat_date = self._current_stat_date()
        rows = list_query_item_stats(range_mode="day", date=stat_date)
        if not isinstance(rows, list):
            return {}
        stats_by_external_item_id: dict[str, dict[str, object]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            external_item_id = str(row.get("external_item_id") or "").strip()
            if not external_item_id:
                continue
            stats_by_external_item_id[external_item_id] = dict(row)
        return stats_by_external_item_id

    def _flush_pending_stats(self) -> None:
        flush_pending = self._stats_flush_callback
        if not callable(flush_pending):
            return

        for _ in range(1000):
            try:
                drained = int(flush_pending() or 0)
            except Exception:
                return
            if drained <= 0:
                return

    def _current_stat_date(self) -> str:
        now_value = self._now_provider()
        if isinstance(now_value, datetime):
            return now_value.date().isoformat()
        now_text = str(now_value or "").strip()
        if len(now_text) >= 10:
            return now_text[:10]
        return datetime.now().date().isoformat()

    @staticmethod
    def _build_item_rows(
        raw_purchase_item_rows: object,
        raw_query_item_rows: object,
    ) -> list[dict[str, object]]:
        purchase_rows_by_id: dict[str, dict[str, object]] = {}
        if isinstance(raw_purchase_item_rows, list):
            for row in raw_purchase_item_rows:
                if not isinstance(row, dict):
                    continue
                item_id = str(row.get("query_item_id") or "").strip()
                if not item_id:
                    continue
                purchase_rows_by_id[item_id] = dict(row)

        item_rows: list[dict[str, object]] = []
        seen_item_ids: set[str] = set()
        if isinstance(raw_query_item_rows, list):
            for query_row in raw_query_item_rows:
                if not isinstance(query_row, dict):
                    continue
                item_id = str(query_row.get("query_item_id") or "").strip()
                if not item_id:
                    continue
                purchase_row = purchase_rows_by_id.get(item_id, {})
                item_rows.append(
                    {
                        "query_item_id": item_id,
                        "item_name": query_row.get("item_name"),
                        "max_price": query_row.get("max_price"),
                        "min_wear": query_row.get("min_wear"),
                        "max_wear": query_row.get("max_wear"),
                        "detail_min_wear": query_row.get("detail_min_wear"),
                        "detail_max_wear": query_row.get("detail_max_wear"),
                        "manual_paused": bool(query_row.get("manual_paused", False)),
                        "query_execution_count": int(query_row.get("query_count", 0)),
                        "matched_product_count": int(purchase_row.get("matched_product_count", 0)),
                        "purchase_success_count": int(purchase_row.get("purchase_success_count", 0)),
                        "purchase_failed_count": int(purchase_row.get("purchase_failed_count", 0)),
                        "modes": GetPurchaseRuntimeStatusUseCase._normalize_modes(query_row.get("modes")),
                        "source_mode_stats": GetPurchaseRuntimeStatusUseCase._normalize_hit_sources(
                            purchase_row.get("source_mode_stats")
                        ),
                        "recent_hit_sources": GetPurchaseRuntimeStatusUseCase._normalize_hit_sources(
                            purchase_row.get("recent_hit_sources")
                        ),
                    }
                )
                seen_item_ids.add(item_id)

        for item_id, purchase_row in purchase_rows_by_id.items():
            if item_id in seen_item_ids:
                continue
            item_rows.append(
                {
                    "query_item_id": item_id,
                    "item_name": None,
                    "max_price": None,
                    "min_wear": None,
                    "max_wear": None,
                    "detail_min_wear": None,
                    "detail_max_wear": None,
                    "manual_paused": False,
                    "query_execution_count": 0,
                    "matched_product_count": int(purchase_row.get("matched_product_count", 0)),
                    "purchase_success_count": int(purchase_row.get("purchase_success_count", 0)),
                    "purchase_failed_count": int(purchase_row.get("purchase_failed_count", 0)),
                    "modes": {},
                    "source_mode_stats": GetPurchaseRuntimeStatusUseCase._normalize_hit_sources(
                        purchase_row.get("source_mode_stats")
                    ),
                    "recent_hit_sources": GetPurchaseRuntimeStatusUseCase._normalize_hit_sources(
                        purchase_row.get("recent_hit_sources")
                    ),
                }
            )
        return item_rows

    @staticmethod
    def _normalize_hit_sources(raw_rows: object) -> list[dict[str, object]]:
        if not isinstance(raw_rows, list):
            return []

        normalized: list[dict[str, object]] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            normalized.append(
                {
                    "mode_type": str(raw_row.get("mode_type") or ""),
                    "hit_count": int(raw_row.get("hit_count", 0)),
                    "last_hit_at": raw_row.get("last_hit_at"),
                    "account_id": raw_row.get("account_id"),
                    "account_display_name": raw_row.get("account_display_name"),
                }
            )
        return normalized

    @staticmethod
    def _normalize_modes(raw_modes: object) -> dict[str, dict[str, object]]:
        if not isinstance(raw_modes, dict):
            return {}

        normalized: dict[str, dict[str, object]] = {}
        for mode_type, raw_mode in raw_modes.items():
            if not isinstance(raw_mode, dict):
                continue
            normalized[str(mode_type)] = {
                "mode_type": str(raw_mode.get("mode_type") or mode_type or ""),
                "target_dedicated_count": int(raw_mode.get("target_dedicated_count", 0)),
                "actual_dedicated_count": int(raw_mode.get("actual_dedicated_count", 0)),
                "status": str(raw_mode.get("status") or ""),
                "status_message": str(raw_mode.get("status_message") or ""),
                "shared_available_count": int(raw_mode.get("shared_available_count", 0)),
            }
        return normalized
