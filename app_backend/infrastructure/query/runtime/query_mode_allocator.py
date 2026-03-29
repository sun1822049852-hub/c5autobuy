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
        self._has_initialized_bindings = False
        self._shared_pointer = 0

    def reset(self) -> None:
        with self._lock:
            self._dedicated_bindings = {}
            self._has_initialized_bindings = False
            self._shared_pointer = 0

    def sync_query_items(self, query_items: list[QueryItem]) -> None:
        with self._lock:
            self._sync_query_items_locked(query_items)

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
        return {
            "item_rows": item_rows,
            "shared_available_count": len(state["shared_worker_ids"]),
            "shared_candidate_count": len(state["shared_item_ids"]),
        }

    def apply_query_item_runtime(self, query_item: QueryItem) -> bool:
        item_id = str(query_item.query_item_id)
        with self._lock:
            next_items = list(self._query_items)
            for index, current_item in enumerate(self._query_items):
                if str(current_item.query_item_id) != item_id:
                    continue
                next_items[index] = query_item
                self._sync_query_items_locked(next_items)
                return True
            next_items.append(query_item)
            self._sync_query_items_locked(next_items)
            return True

    def apply_target_actual_counts(
        self,
        *,
        target_actual_counts: dict[str, int],
        active_workers: list[object],
    ) -> None:
        with self._lock:
            state = self._reconcile_locked(active_workers)
            items_by_id = state["items_by_id"]
            active_worker_ids = self._active_worker_ids(active_workers)
            dedicated_bindings = dict(state["dedicated_bindings"])
            dedicated_counts = dict(state["dedicated_counts"])
            normalized_targets: dict[str, int] = {}

            for item_id, raw_target in target_actual_counts.items():
                query_item = items_by_id.get(str(item_id))
                if query_item is None or query_item.manual_paused:
                    normalized_targets[str(item_id)] = 0
                    continue
                normalized_targets[str(item_id)] = max(int(raw_target), 0)

            for item_id, target_count in normalized_targets.items():
                current_count = int(dedicated_counts.get(item_id, 0))
                if current_count <= target_count:
                    continue
                bound_worker_ids = [
                    worker_id
                    for worker_id in active_worker_ids
                    if dedicated_bindings.get(worker_id) == item_id
                ]
                for worker_id in bound_worker_ids[target_count:]:
                    dedicated_bindings.pop(worker_id, None)
                    dedicated_counts[item_id] = max(int(dedicated_counts.get(item_id, 0)) - 1, 0)

            shared_worker_ids = [
                worker_id
                for worker_id in active_worker_ids
                if worker_id not in dedicated_bindings
            ]

            for item_id, target_count in normalized_targets.items():
                current_count = int(dedicated_counts.get(item_id, 0))
                while current_count < target_count and shared_worker_ids:
                    worker_id = shared_worker_ids.pop(0)
                    dedicated_bindings[worker_id] = item_id
                    current_count += 1
                    dedicated_counts[item_id] = current_count

            self._dedicated_bindings = dict(dedicated_bindings)
            if active_worker_ids:
                self._has_initialized_bindings = True
            if not shared_worker_ids:
                self._shared_pointer = 0

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
            if query_item is None or query_item.manual_paused:
                unbound_worker_ids.append(worker_id)
                continue
            dedicated_bindings[worker_id] = item_id
            dedicated_counts[item_id] += 1

        if not self._has_initialized_bindings and active_worker_ids:
            self._seed_initial_bindings_locked(
                dedicated_bindings=dedicated_bindings,
                dedicated_counts=dedicated_counts,
                items_by_id=items_by_id,
                raw_targets=raw_targets,
                unbound_worker_ids=unbound_worker_ids,
            )
            self._has_initialized_bindings = True

        self._dedicated_bindings = dict(dedicated_bindings)
        shared_item_ids = [
            item_id
            for item_id, query_item in items_by_id.items()
            if not query_item.manual_paused and dedicated_counts[item_id] == 0
        ]
        return {
            "items_by_id": items_by_id,
            "raw_targets": raw_targets,
            "dedicated_bindings": dedicated_bindings,
            "dedicated_counts": dedicated_counts,
            "shared_worker_ids": list(unbound_worker_ids),
            "shared_item_ids": shared_item_ids,
        }

    def _sync_query_items_locked(self, query_items: list[QueryItem]) -> None:
        self._query_items = list(query_items)
        valid_item_ids = {
            str(query_item.query_item_id)
            for query_item in self._query_items
        }
        self._dedicated_bindings = {
            worker_id: item_id
            for worker_id, item_id in self._dedicated_bindings.items()
            if item_id in valid_item_ids
        }
        if not self._query_items:
            self._shared_pointer = 0
            self._has_initialized_bindings = False
            return
        self._shared_pointer %= len(self._query_items)

    def _seed_initial_bindings_locked(
        self,
        *,
        dedicated_bindings: dict[str, str],
        dedicated_counts: dict[str, int],
        items_by_id: dict[str, QueryItem],
        raw_targets: dict[str, int],
        unbound_worker_ids: list[str],
    ) -> None:
        candidate_item_ids = [
            item_id
            for item_id, query_item in items_by_id.items()
            if not query_item.manual_paused and raw_targets.get(item_id, 0) > 0
        ]
        if not candidate_item_ids or not unbound_worker_ids:
            return

        while unbound_worker_ids:
            assigned_in_round = False
            for item_id in candidate_item_ids:
                target = max(int(raw_targets.get(item_id, 0)), 0)
                if dedicated_counts[item_id] >= target:
                    continue
                worker_id = unbound_worker_ids.pop(0)
                dedicated_bindings[worker_id] = item_id
                dedicated_counts[item_id] += 1
                assigned_in_round = True
                if not unbound_worker_ids:
                    break
            if not assigned_in_round:
                break

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
            "shared_available_count": shared_worker_count,
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
