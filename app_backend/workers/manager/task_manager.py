from __future__ import annotations

import asyncio
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(slots=True)
class TaskEvent:
    state: str
    timestamp: str
    message: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class TaskSnapshot:
    task_id: str
    task_type: str
    state: str
    created_at: str
    updated_at: str
    events: list[TaskEvent] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    pending_conflict: dict[str, Any] | None = None


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskSnapshot] = {}
        self._task_revisions: dict[str, int] = {}
        self._subscribers: dict[str, list[asyncio.Queue[TaskSnapshot]]] = defaultdict(list)
        self._lock = Lock()
        self._revision = 0

    def create_task(
        self,
        *,
        task_type: str,
        initial_state: str = "pending",
        message: str | None = None,
    ) -> TaskSnapshot:
        task_id = str(uuid4())
        timestamp = _now()
        snapshot = TaskSnapshot(
            task_id=task_id,
            task_type=task_type,
            state=initial_state,
            created_at=timestamp,
            updated_at=timestamp,
            events=[
                TaskEvent(
                    state=initial_state,
                    timestamp=timestamp,
                    message=message,
                )
            ],
        )

        with self._lock:
            self._tasks[task_id] = snapshot
            self._task_revisions[task_id] = self._next_revision()

        self._publish(task_id)
        return self.get_task(task_id)  # type: ignore[return-value]

    def set_state(
        self,
        task_id: str,
        state: str,
        *,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> TaskSnapshot:
        with self._lock:
            snapshot = self._require_task(task_id)
            snapshot.state = state
            snapshot.updated_at = _now()
            snapshot.events.append(
                TaskEvent(
                    state=state,
                    timestamp=snapshot.updated_at,
                    message=message,
                    payload=deepcopy(payload),
                )
            )
            self._task_revisions[task_id] = self._next_revision()

        self._publish(task_id)
        return self.get_task(task_id)  # type: ignore[return-value]

    def set_result(
        self,
        task_id: str,
        result: dict[str, Any] | None,
        *,
        state: str | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> TaskSnapshot:
        with self._lock:
            snapshot = self._require_task(task_id)
            if state:
                snapshot.state = state
                snapshot.updated_at = _now()
                snapshot.events.append(
                    TaskEvent(
                        state=state,
                        timestamp=snapshot.updated_at,
                        message=message,
                        payload=deepcopy(payload),
                    )
                )
            else:
                snapshot.updated_at = _now()

            snapshot.result = deepcopy(result)
            snapshot.error = None
            self._task_revisions[task_id] = self._next_revision()

        self._publish(task_id)
        return self.get_task(task_id)  # type: ignore[return-value]

    def set_error(
        self,
        task_id: str,
        error: str,
        *,
        state: str = "failed",
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> TaskSnapshot:
        with self._lock:
            snapshot = self._require_task(task_id)
            snapshot.state = state
            snapshot.updated_at = _now()
            snapshot.error = error
            snapshot.events.append(
                TaskEvent(
                    state=state,
                    timestamp=snapshot.updated_at,
                    message=message or error,
                    payload=deepcopy(payload),
                )
            )
            self._task_revisions[task_id] = self._next_revision()

        self._publish(task_id)
        return self.get_task(task_id)  # type: ignore[return-value]

    def set_pending_conflict(
        self,
        task_id: str,
        pending_conflict: dict[str, Any],
        *,
        message: str | None = None,
    ) -> TaskSnapshot:
        with self._lock:
            snapshot = self._require_task(task_id)
            snapshot.pending_conflict = deepcopy(pending_conflict)
            snapshot.state = "conflict"
            snapshot.updated_at = _now()
            snapshot.events.append(
                TaskEvent(
                    state="conflict",
                    timestamp=snapshot.updated_at,
                    message=message,
                    payload=deepcopy(pending_conflict),
                )
            )
            self._task_revisions[task_id] = self._next_revision()

        self._publish(task_id)
        return self.get_task(task_id)  # type: ignore[return-value]

    def clear_pending_conflict(self, task_id: str) -> TaskSnapshot:
        with self._lock:
            snapshot = self._require_task(task_id)
            snapshot.pending_conflict = None
            snapshot.updated_at = _now()
            self._task_revisions[task_id] = self._next_revision()

        self._publish(task_id)
        return self.get_task(task_id)  # type: ignore[return-value]

    def get_task(self, task_id: str) -> TaskSnapshot | None:
        with self._lock:
            snapshot = self._tasks.get(task_id)
            if snapshot is None:
                return None
            return deepcopy(snapshot)

    def list_recent_tasks(self, *, task_type: str | None = None, limit: int = 10) -> list[TaskSnapshot]:
        with self._lock:
            snapshots = [
                (deepcopy(snapshot), self._task_revisions.get(task_id, 0))
                for snapshot in self._tasks.values()
                for task_id in [snapshot.task_id]
                if task_type is None or snapshot.task_type == task_type
            ]

        snapshots.sort(
            key=lambda item: (item[1], item[0].updated_at, item[0].created_at),
            reverse=True,
        )
        return [snapshot for snapshot, _revision in snapshots[: max(int(limit), 0)]]

    def subscribe(self, task_id: str) -> asyncio.Queue[TaskSnapshot]:
        queue: asyncio.Queue[TaskSnapshot] = asyncio.Queue()
        with self._lock:
            self._subscribers[task_id].append(queue)
            snapshot = self._tasks.get(task_id)

        if task_id != "*" and snapshot is not None:
            queue.put_nowait(deepcopy(snapshot))
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue[TaskSnapshot]) -> None:
        with self._lock:
            subscribers = self._subscribers.get(task_id)
            if not subscribers:
                return
            try:
                subscribers.remove(queue)
            except ValueError:
                return
            if not subscribers:
                self._subscribers.pop(task_id, None)

    def _publish(self, task_id: str) -> None:
        with self._lock:
            snapshot = self._tasks.get(task_id)
            subscribers = list(self._subscribers.get("*", [])) + list(self._subscribers.get(task_id, []))

        if snapshot is None:
            return

        published_snapshot = deepcopy(snapshot)
        for queue in subscribers:
            try:
                queue.put_nowait(deepcopy(published_snapshot))
            except asyncio.QueueFull:
                continue

    def _require_task(self, task_id: str) -> TaskSnapshot:
        snapshot = self._tasks.get(task_id)
        if snapshot is None:
            raise KeyError(task_id)
        return snapshot

    def _next_revision(self) -> int:
        self._revision += 1
        return self._revision

