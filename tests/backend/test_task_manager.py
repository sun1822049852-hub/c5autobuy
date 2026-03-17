from __future__ import annotations


def test_task_manager_creates_task_and_keeps_ordered_events():
    from app_backend.workers.manager.task_manager import TaskManager

    manager = TaskManager()
    task = manager.create_task(task_type="login")

    manager.set_state(task.task_id, "starting_browser")
    manager.set_state(task.task_id, "waiting_for_scan")
    manager.set_result(task.task_id, {"account_id": "acc-1"}, state="succeeded")

    snapshot = manager.get_task(task.task_id)

    assert snapshot is not None
    assert snapshot.task_id
    assert snapshot.state == "succeeded"
    assert snapshot.result == {"account_id": "acc-1"}
    assert [event.state for event in snapshot.events] == [
        "pending",
        "starting_browser",
        "waiting_for_scan",
        "succeeded",
    ]


async def test_task_route_reads_current_state_over_http(app, client):
    task = app.state.task_manager.create_task(task_type="login")
    app.state.task_manager.set_state(task.task_id, "waiting_for_scan")

    response = await client.get(f"/tasks/{task.task_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task.task_id
    assert payload["task_type"] == "login"
    assert payload["state"] == "waiting_for_scan"
    assert [event["state"] for event in payload["events"]] == [
        "pending",
        "waiting_for_scan",
    ]
