from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(slots=True)
class RuntimeUpdateEvent:
    version: int
    event: str
    updated_at: str
    payload: dict[str, Any]


@dataclass(slots=True)
class _Subscriber:
    queue: asyncio.Queue[RuntimeUpdateEvent]
    loop: asyncio.AbstractEventLoop | None


@dataclass(slots=True)
class RuntimeUpdateSubscription:
    queue: asyncio.Queue[RuntimeUpdateEvent]
    replay: list[RuntimeUpdateEvent]
    resync_event: RuntimeUpdateEvent | None = None


class RuntimeUpdateHub:
    def __init__(self, *, history_limit: int = 512) -> None:
        self._version = 0
        self._subscribers: dict[str, list[_Subscriber]] = defaultdict(list)
        self._history: deque[RuntimeUpdateEvent] = deque(maxlen=max(int(history_limit), 1))
        self._lock = Lock()

    def current_version(self) -> int:
        with self._lock:
            return self._version

    def subscribe(self, event: str = "*") -> asyncio.Queue[RuntimeUpdateEvent]:
        return self.open_subscription(event=event).queue

    def open_subscription(
        self,
        *,
        event: str = "*",
        since_version: int | None = None,
    ) -> RuntimeUpdateSubscription:
        queue: asyncio.Queue[RuntimeUpdateEvent] = asyncio.Queue()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        with self._lock:
            resync_event = self._build_resync_event_locked(since_version=since_version)
            replay = [] if resync_event is not None else self._replay_updates_locked(event=event, since_version=since_version)
            self._subscribers[event].append(_Subscriber(queue=queue, loop=loop))
        return RuntimeUpdateSubscription(queue=queue, replay=replay, resync_event=resync_event)

    def unsubscribe(self, queue: asyncio.Queue[RuntimeUpdateEvent], event: str = "*") -> None:
        with self._lock:
            subscribers = self._subscribers.get(event)
            if not subscribers:
                return
            index = next(
                (offset for offset, subscriber in enumerate(subscribers) if subscriber.queue is queue),
                None,
            )
            if index is None:
                return
            subscribers.pop(index)
            if not subscribers:
                self._subscribers.pop(event, None)

    def publish(self, *, event: str, payload: dict[str, Any] | None = None) -> RuntimeUpdateEvent:
        stale_subscribers: list[tuple[str, asyncio.Queue[RuntimeUpdateEvent]]] = []
        with self._lock:
            self._version += 1
            update = RuntimeUpdateEvent(
                version=self._version,
                event=event,
                updated_at=_now(),
                payload=deepcopy(payload or {}),
            )
            self._history.append(deepcopy(update))
            subscribers = (
                [("*", subscriber) for subscriber in self._subscribers.get("*", [])]
                + [(event, subscriber) for subscriber in self._subscribers.get(event, [])]
            )
            for subscriber_event, subscriber in subscribers:
                try:
                    if subscriber.loop is None or not subscriber.loop.is_running():
                        subscriber.queue.put_nowait(deepcopy(update))
                    else:
                        subscriber.loop.call_soon_threadsafe(
                            self._deliver,
                            subscriber.queue,
                            deepcopy(update),
                        )
                except RuntimeError:
                    stale_subscribers.append((subscriber_event, subscriber.queue))
                except asyncio.QueueFull:
                    continue
        for subscriber_event, queue in stale_subscribers:
            self.unsubscribe(queue, subscriber_event)
        return update

    def _replay_updates_locked(
        self,
        *,
        event: str,
        since_version: int | None,
    ) -> list[RuntimeUpdateEvent]:
        if since_version is None:
            return []
        try:
            normalized_since_version = max(int(since_version), 0)
        except (TypeError, ValueError):
            return []
        if normalized_since_version >= self._version:
            return []
        return [
            deepcopy(update)
            for update in self._history
            if update.version > normalized_since_version and (event == "*" or update.event == event)
        ]

    def _build_resync_event_locked(self, *, since_version: int | None) -> RuntimeUpdateEvent | None:
        if since_version is None or not self._history:
            return None
        try:
            normalized_since_version = max(int(since_version), 0)
        except (TypeError, ValueError):
            return None
        if normalized_since_version >= self._version:
            return None
        oldest_available_version = self._history[0].version
        if normalized_since_version >= oldest_available_version - 1:
            return None
        return RuntimeUpdateEvent(
            version=self._version,
            event="runtime.resync_required",
            updated_at=_now(),
            payload={
                "reason": "history_overflow",
                "requested_version": normalized_since_version,
                "oldest_available_version": oldest_available_version,
                "current_version": self._version,
            },
        )

    @staticmethod
    def _deliver(queue: asyncio.Queue[RuntimeUpdateEvent], update: RuntimeUpdateEvent) -> None:
        try:
            queue.put_nowait(update)
        except asyncio.QueueFull:
            return
