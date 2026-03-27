from __future__ import annotations

import asyncio
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(slots=True)
class AccountUpdateEvent:
    account_id: str
    event: str
    updated_at: str
    payload: dict[str, Any]


class AccountUpdateHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[AccountUpdateEvent]]] = defaultdict(list)
        self._lock = Lock()

    def subscribe(self, account_id: str = "*") -> asyncio.Queue[AccountUpdateEvent]:
        queue: asyncio.Queue[AccountUpdateEvent] = asyncio.Queue()
        with self._lock:
            self._subscribers[account_id].append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[AccountUpdateEvent], account_id: str = "*") -> None:
        with self._lock:
            subscribers = self._subscribers.get(account_id)
            if not subscribers:
                return
            try:
                subscribers.remove(queue)
            except ValueError:
                return
            if not subscribers:
                self._subscribers.pop(account_id, None)

    def publish(self, *, account_id: str, event: str, payload: dict[str, Any]) -> None:
        update = AccountUpdateEvent(
            account_id=account_id,
            event=event,
            updated_at=_now(),
            payload=deepcopy(payload),
        )
        with self._lock:
            subscribers = list(self._subscribers.get("*", [])) + list(self._subscribers.get(account_id, []))
        for queue in subscribers:
            try:
                queue.put_nowait(deepcopy(update))
            except asyncio.QueueFull:
                continue
