from __future__ import annotations


class GetPurchaseRuntimeStatusUseCase:
    def __init__(self, runtime_service, query_runtime_service=None) -> None:
        self._runtime_service = runtime_service
        self._query_runtime_service = query_runtime_service

    def execute(self) -> dict[str, object]:
        purchase_snapshot = dict(self._runtime_service.get_status())
        if self._query_runtime_service is None:
            purchase_snapshot.setdefault("active_query_config", None)
            purchase_snapshot.setdefault("item_rows", [])
            return purchase_snapshot

        query_snapshot = self._query_runtime_service.get_status()
        if not isinstance(query_snapshot, dict):
            purchase_snapshot.setdefault("active_query_config", None)
            purchase_snapshot.setdefault("item_rows", [])
            return purchase_snapshot

        purchase_snapshot["active_query_config"] = self._build_active_query_config(query_snapshot)
        purchase_snapshot["item_rows"] = self._build_item_rows(
            purchase_snapshot.get("item_rows"),
            query_snapshot.get("item_rows"),
        )
        return purchase_snapshot

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
                        "query_execution_count": int(query_row.get("query_count", 0)),
                        "matched_product_count": int(purchase_row.get("matched_product_count", 0)),
                        "purchase_success_count": int(purchase_row.get("purchase_success_count", 0)),
                        "purchase_failed_count": int(purchase_row.get("purchase_failed_count", 0)),
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
                    "query_execution_count": 0,
                    "matched_product_count": int(purchase_row.get("matched_product_count", 0)),
                    "purchase_success_count": int(purchase_row.get("purchase_success_count", 0)),
                    "purchase_failed_count": int(purchase_row.get("purchase_failed_count", 0)),
                }
            )
        return item_rows
