from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


def _ensure_runtime_full_ready(websocket: WebSocket) -> None:
    ensure = getattr(websocket.app.state, "ensure_runtime_full_ready", None)
    if callable(ensure):
        ensure()


def _parse_since_version(raw_value: str | None) -> int | None:
    try:
        return max(int(str(raw_value or "").strip()), 0)
    except (TypeError, ValueError):
        return None


@router.websocket("/ws/runtime")
async def runtime_updates_stream(websocket: WebSocket) -> None:
    _ensure_runtime_full_ready(websocket)
    await websocket.accept()
    hub = websocket.app.state.runtime_update_hub
    subscription = hub.open_subscription(
        event="*",
        since_version=_parse_since_version(websocket.query_params.get("since_version")),
    )
    queue = subscription.queue

    try:
        if subscription.resync_event is not None:
            await websocket.send_json(asdict(subscription.resync_event))
            await websocket.close()
            return
        for replay_event in subscription.replay:
            await websocket.send_json(asdict(replay_event))
        while True:
            event = await queue.get()
            await websocket.send_json(asdict(event))
    except WebSocketDisconnect:
        return
    finally:
        hub.unsubscribe(queue, "*")
