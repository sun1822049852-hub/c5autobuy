from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/accounts/updates")
async def account_updates_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    hub = websocket.app.state.account_update_hub
    queue = hub.subscribe("*")
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(asdict(event))
    except WebSocketDisconnect:
        return
    finally:
        hub.unsubscribe(queue, "*")
