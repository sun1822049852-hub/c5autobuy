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


def test_task_manager_lists_recent_tasks_in_descending_update_order_and_returns_copies():
    from app_backend.workers.manager.task_manager import TaskManager

    manager = TaskManager()
    older = manager.create_task(task_type="login", message="older")
    newer = manager.create_task(task_type="login", message="newer")
    other_type = manager.create_task(task_type="inventory", message="inventory")

    manager.set_state(older.task_id, "waiting_for_scan")
    manager.set_state(newer.task_id, "succeeded")
    manager.set_state(other_type.task_id, "running")

    recent = manager.list_recent_tasks(task_type="login", limit=2)

    assert [task.task_id for task in recent] == [newer.task_id, older.task_id]

    # Returned snapshots must be detached copies so diagnostics reads cannot mutate manager state.
    recent[0].events.append(type(recent[0].events[0])(state="fake", timestamp="x"))
    current = manager.get_task(newer.task_id)
    assert current is not None
    assert [event.state for event in current.events] == ["pending", "succeeded"]
