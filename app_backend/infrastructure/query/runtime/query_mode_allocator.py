from __future__ import annotations

from threading import RLock

from app_backend.domain.models.query_config import QueryItem

from .query_item_scheduler import QueryItemReservation, QueryItemScheduler


class QueryModeAllocator:
    def __init__(
        self,
        mode_type: str,
        query_items: list[QueryItem],
        *,
        query_item_scheduler: QueryItemScheduler,
    ) -> None:
        self._mode_type = mode_type
        self._query_items = list(query_items)
        self._query_item_scheduler = query_item_scheduler
        self._lock = RLock()
        self._dedicated_bindings: dict[str, str] = {}
        self._shared_pointer = 0

    def reset(self) -> None:
        with self._lock:
            self._dedicated_bindings = {}
            self._shared_pointer = 0

    async def reserve_next(
        self,
        worker: object,
        *,
        active_workers: list[object],
        now,
    ) -> QueryItemReservation | None:
        with self._lock:
            state = self._reconcile_locked(active_workers)
            worker_id = self._worker_id(worker)
            if not worker_id:
                return None

            item_id = state["dedicated_bindings"].get(worker_id)
            actual_assigned_count = 1
            if item_id:
                query_item = state["items_by_id"][item_id]
                actual_assigned_count = max(int(state["dedicated_counts"].get(item_id, 0)), 1)
            else:
                shared_item_ids = state["shared_item_ids"]
                if worker_id not in state["shared_worker_ids"] or not shared_item_ids:
                    return None
                index = self._shared_pointer % len(shared_item_ids)
                item_id = shared_item_ids[index]
                self._shared_pointer = (index + 1) % len(shared_item_ids)
                query_item = state["items_by_id"][item_id]
                if len(shared_item_ids) == 1:
                    actual_assigned_count = max(len(state["shared_worker_ids"]), 1)

        return await self._query_item_scheduler.reserve_item(
            query_item,
            now=now,
            actual_assigned_count=actual_assigned_count,
        )

    def snapshot(self, *, active_workers: list[object]) -> dict[str, object]:
        with self._lock:
            state = self._reconcile_locked(active_workers)
            item_rows = [
                self._build_item_row(query_item, state=state)
                for query_item in self._query_items
            ]
        return {"item_rows": item_rows}

    def apply_query_item_runtime(self, query_item: QueryItem) -> bool:
        item_id = str(query_item.query_item_id)
        with self._lock:
            for index, current_item in enumerate(self._query_items):
                if str(current_item.query_item_id) != item_id:
                    continue
                self._query_items[index] = query_item
                return True
        return False

    def _reconcile_locked(self, active_workers: list[object]) -> dict[str, object]:
        items_by_id = {
            str(query_item.query_item_id): query_item
            for query_item in self._query_items
        }
        raw_targets = {
            item_id: self._target_dedicated_count(query_item)
            for item_id, query_item in items_by_id.items()
        }
        active_worker_ids = self._active_worker_ids(active_workers)

        dedicated_bindings: dict[str, str] = {}
        dedicated_counts = {
            item_id: 0
            for item_id in items_by_id
        }
        unbound_worker_ids: list[str] = []

        for worker_id in active_worker_ids:
            item_id = self._dedicated_bindings.get(worker_id)
            query_item = items_by_id.get(item_id or "")
            if query_item is None or query_item.manual_paused or raw_targets.get(item_id or "", 0) <= 0:
                unbound_worker_ids.append(worker_id)
                continue
            if dedicated_counts[item_id] >= raw_targets[item_id]:
                unbound_worker_ids.append(worker_id)
                continue
            dedicated_bindings[worker_id] = item_id
            dedicated_counts[item_id] += 1

        for query_item in self._query_items:
            item_id = str(query_item.query_item_id)
            target = raw_targets[item_id]
            if query_item.manual_paused or target <= 0:
                continue

            current_count = dedicated_counts[item_id]
            missing_count = target - current_count
            if missing_count <= 0:
                continue

            if current_count == 0:
                if len(unbound_worker_ids) < target:
                    continue
            elif len(unbound_worker_ids) < missing_count:
                continue

            for _ in range(missing_count):
                worker_id = unbound_worker_ids.pop(0)
                dedicated_bindings[worker_id] = item_id
                dedicated_counts[item_id] += 1

        self._dedicated_bindings = dict(dedicated_bindings)
        shared_item_ids = [
            item_id
            for item_id, query_item in items_by_id.items()
            if not query_item.manual_paused and (raw_targets[item_id] == 0 or dedicated_counts[item_id] == 0)
        ]
        return {
            "items_by_id": items_by_id,
            "raw_targets": raw_targets,
            "dedicated_bindings": dedicated_bindings,
            "dedicated_counts": dedicated_counts,
            "shared_worker_ids": list(unbound_worker_ids),
            "shared_item_ids": shared_item_ids,
        }

    def _build_item_row(self, query_item: QueryItem, *, state: dict[str, object]) -> dict[str, object]:
        item_id = str(query_item.query_item_id)
        target = int(state["raw_targets"].get(item_id, 0))
        actual = int(state["dedicated_counts"].get(item_id, 0))
        shared_worker_count = len(state["shared_worker_ids"])
        in_shared_pool = item_id in state["shared_item_ids"]

        if query_item.manual_paused:
            status = "manual_paused"
            status_message = "手动暂停"
        elif actual > 0:
            status = "dedicated"
            status_message = f"专属中 {actual}/{target}"
        elif in_shared_pool and shared_worker_count > 0:
            status = "shared"
            status_message = "共享中"
        else:
            status = "unavailable"
            status_message = f"无可用账号 0/{target}" if target > 0 else "无可用账号"

        return {
            "query_item_id": item_id,
            "mode_type": self._mode_type,
            "target_dedicated_count": target,
            "actual_dedicated_count": actual,
            "status": status,
            "status_message": status_message,
        }

    def _target_dedicated_count(self, query_item: QueryItem) -> int:
        for allocation in query_item.mode_allocations:
            if allocation.mode_type == self._mode_type:
                return max(int(allocation.target_dedicated_count), 0)
        return 0

    @staticmethod
    def _worker_id(worker: object) -> str:
        account = getattr(worker, "account", None)
        account_id = getattr(account, "account_id", None)
        if account_id:
            return str(account_id)
        snapshot = getattr(worker, "snapshot", None)
        if callable(snapshot):
            data = snapshot()
            if isinstance(data, dict) and data.get("account_id"):
                return str(data["account_id"])
        return ""

    def _active_worker_ids(self, active_workers: list[object]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for worker in active_workers:
            worker_id = self._worker_id(worker)
            if not worker_id or worker_id in seen:
                continue
            seen.add(worker_id)
            ordered.append(worker_id)
        return ordered
