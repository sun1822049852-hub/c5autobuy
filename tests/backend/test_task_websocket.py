from __future__ import annotations

from fastapi.testclient import TestClient


def test_task_websocket_streams_state_updates(app):
    task = app.state.task_manager.create_task(task_type="login")

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/tasks/{task.task_id}") as websocket:
            pending = websocket.receive_json()
            assert pending["state"] == "pending"

            app.state.task_manager.set_state(task.task_id, "waiting_for_scan")
            waiting = websocket.receive_json()
            assert waiting["state"] == "waiting_for_scan"

            app.state.task_manager.set_result(
                task.task_id,
                {"account_id": "a-1"},
                state="succeeded",
            )
            succeeded = websocket.receive_json()
            assert succeeded["state"] == "succeeded"
            assert succeeded["result"] == {"account_id": "a-1"}


def test_task_websocket_treats_conflict_as_terminal_state():
    from app_backend.api.websocket.tasks import _TERMINAL_STATES

    assert "conflict" in _TERMINAL_STATES
