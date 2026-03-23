from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app_backend.api.schemas.tasks import TaskResponse

router = APIRouter()

_TERMINAL_STATES = {"succeeded", "failed", "cancelled", "conflict"}


@router.websocket("/ws/tasks/{task_id}")
async def task_stream(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    task_manager = websocket.app.state.task_manager
    queue = task_manager.subscribe(task_id)

    try:
        while True:
            snapshot = await queue.get()
            payload = TaskResponse.model_validate(snapshot).model_dump(mode="json")
            await websocket.send_json(payload)
            if payload["state"] in _TERMINAL_STATES:
                break
    except WebSocketDisconnect:
        return
    finally:
        task_manager.unsubscribe(task_id, queue)

