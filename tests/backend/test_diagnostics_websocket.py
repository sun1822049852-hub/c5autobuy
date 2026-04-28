from __future__ import annotations

from fastapi.testclient import TestClient

from tests.backend.test_diagnostics_routes import (
    FakePurchaseRuntimeService,
    FakeQueryRuntimeService,
    _build_purchase_status,
    _build_query_status,
)


def test_diagnostics_websocket_streams_snapshot_after_runtime_update(app):
    with TestClient(app) as client:
        app.state.query_runtime_service = FakeQueryRuntimeService(_build_query_status())
        app.state.purchase_runtime_service = FakePurchaseRuntimeService(_build_purchase_status())

        with client.websocket_connect("/ws/diagnostics/sidebar") as websocket:
            app.state.runtime_update_hub.publish(
                event="query_runtime.updated",
                payload={"running": True},
            )

            while True:
                payload = websocket.receive_json()
                if payload["summary"]["query_running"] and payload["query"]["config_name"] == "查询配置A":
                    break

    assert payload["summary"]["query_running"] is True
    assert payload["summary"]["purchase_running"] is True
    assert payload["query"]["config_name"] == "查询配置A"
    assert payload["purchase"]["message"] == "运行中"


def test_diagnostics_websocket_streams_snapshot_after_login_task_change(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/diagnostics/sidebar") as websocket:
            task = app.state.task_manager.create_task(task_type="login", message="创建任务")
            app.state.task_manager.set_state(task.task_id, "waiting_for_scan", message="等待扫码")

            while True:
                payload = websocket.receive_json()
                recent_tasks = payload["login_tasks"]["recent_tasks"]
                if recent_tasks and recent_tasks[0]["task_id"] == task.task_id:
                    break

    assert payload["login_tasks"]["running_count"] >= 1
    assert payload["login_tasks"]["recent_tasks"][0]["task_id"] == task.task_id
    assert payload["login_tasks"]["recent_tasks"][0]["state"] == "waiting_for_scan"
