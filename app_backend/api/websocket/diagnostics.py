from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app_backend.api.routes.diagnostics import build_sidebar_diagnostics_response_from_state

router = APIRouter()


def _ensure_diagnostics_runtime_ready(app_state) -> None:
    required_attrs = (
        "query_runtime_service",
        "purchase_runtime_service",
        "task_manager",
    )
    if all(hasattr(app_state, name) for name in required_attrs):
        return
    ensure = getattr(app_state, "ensure_runtime_full_ready", None)
    if callable(ensure):
        ensure()


async def _wait_for_any_change(*queues: asyncio.Queue) -> None:
    readers = [asyncio.create_task(queue.get()) for queue in queues]
    try:
        done, pending = await asyncio.wait(readers, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        for task in pending:
            task.cancel()
        for task in pending:
            with suppress(asyncio.CancelledError):
                await task
    finally:
        for task in readers:
            if task.done():
                continue
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


async def _wait_for_change_or_disconnect(websocket: WebSocket, *queues: asyncio.Queue) -> bool:
    change_tasks = [asyncio.create_task(queue.get()) for queue in queues]
    disconnect_task = asyncio.create_task(websocket.receive())
    readers = change_tasks + [disconnect_task]

    try:
        done, pending = await asyncio.wait(readers, return_when=asyncio.FIRST_COMPLETED)
        if disconnect_task in done:
            message = disconnect_task.result()
            return message.get("type") != "websocket.disconnect"

        for task in done:
            if task is disconnect_task:
                continue
            task.result()
        return True
    finally:
        for task in readers:
            if task.done():
                continue
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


@router.websocket("/ws/diagnostics/sidebar")
async def diagnostics_sidebar_stream(websocket: WebSocket) -> None:
    _ensure_diagnostics_runtime_ready(websocket.app.state)

    runtime_queue = websocket.app.state.runtime_update_hub.subscribe("*")
    account_queue = websocket.app.state.account_update_hub.subscribe("*")
    task_queue = websocket.app.state.task_manager.subscribe("*")
    await websocket.accept()

    try:
        while True:
            changed = await _wait_for_change_or_disconnect(
                websocket,
                runtime_queue,
                account_queue,
                task_queue,
            )
            if not changed:
                return
            payload = build_sidebar_diagnostics_response_from_state(websocket.app.state)
            await websocket.send_json(payload.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
    finally:
        websocket.app.state.runtime_update_hub.unsubscribe(runtime_queue, "*")
        websocket.app.state.account_update_hub.unsubscribe(account_queue, "*")
        websocket.app.state.task_manager.unsubscribe("*", task_queue)
