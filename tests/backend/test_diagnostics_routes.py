from __future__ import annotations


def _build_query_status(*, recent_event_count: int = 2, abnormal_row_count: int = 2) -> dict[str, object]:
    recent_events = [
        {
            "timestamp": f"2026-03-25T10:00:{index:02d}",
            "level": "error" if index % 2 else "info",
            "mode_type": "token" if index % 2 else "new_api",
            "account_id": f"query-{index}",
            "account_display_name": f"查询账号-{index}",
            "query_item_id": f"item-{index}",
            "query_item_name": "AK-47 | Redline",
            "message": f"查询事件-{index}",
            "match_count": 1,
            "product_list": [],
            "total_price": 123.45,
            "total_wear_sum": 0.12,
            "latency_ms": 88.0,
            "error": "token invalid" if index % 2 else None,
        }
        for index in range(recent_event_count)
    ]
    group_rows = [
        {
            "account_id": f"query-bad-{index}",
            "account_display_name": f"异常查询账号-{index}",
            "mode_type": "token" if index % 2 else "new_api",
            "active": False,
            "in_window": True,
            "cooldown_until": None,
            "last_query_at": f"2026-03-25T09:59:{index:02d}",
            "last_success_at": None,
            "query_count": 10 + index,
            "found_count": index,
            "disabled_reason": None if index % 2 else "Not login",
            "last_error": "token invalid" if index % 2 else None,
            "rate_limit_increment": 0.0,
        }
        for index in range(abnormal_row_count)
    ]
    group_rows.append(
        {
            "account_id": "query-good-1",
            "account_display_name": "正常查询账号",
            "mode_type": "fast_api",
            "active": True,
            "in_window": True,
            "cooldown_until": None,
            "last_query_at": "2026-03-25T10:05:00",
            "last_success_at": "2026-03-25T10:05:00",
            "query_count": 99,
            "found_count": 12,
            "disabled_reason": None,
            "last_error": None,
            "rate_limit_increment": 0.0,
        }
    )
    return {
        "running": True,
        "config_id": "cfg-1",
        "config_name": "查询配置A",
        "message": "运行中",
        "account_count": 3,
        "started_at": "2026-03-25T10:00:00",
        "stopped_at": None,
        "total_query_count": 42,
        "total_found_count": 8,
        "modes": {
            "new_api": {
                "mode_type": "new_api",
                "enabled": True,
                "eligible_account_count": 1,
                "active_account_count": 1,
                "in_window": True,
                "next_window_start": None,
                "next_window_end": None,
                "query_count": 12,
                "found_count": 3,
                "last_error": None,
            },
            "token": {
                "mode_type": "token",
                "enabled": True,
                "eligible_account_count": 2,
                "active_account_count": 0,
                "in_window": True,
                "next_window_start": None,
                "next_window_end": None,
                "query_count": 30,
                "found_count": 5,
                "last_error": "token invalid",
            },
        },
        "group_rows": group_rows,
        "recent_events": recent_events,
        "item_rows": [],
    }


def _build_purchase_status(*, recent_event_count: int = 2, abnormal_account_count: int = 2) -> dict[str, object]:
    recent_events = [
        {
            "occurred_at": f"2026-03-25T10:01:{index:02d}",
            "status": "success" if index % 2 == 0 else "failed",
            "message": f"购买事件-{index}",
            "query_item_name": "AK-47 | Redline",
            "product_list": [],
            "total_price": 123.45,
            "total_wear_sum": 0.12,
            "source_mode_type": "token",
        }
        for index in range(recent_event_count)
    ]
    accounts = [
        {
            "account_id": f"purchase-bad-{index}",
            "display_name": f"异常购买账号-{index}",
            "purchase_capability_state": "bound",
            "purchase_pool_state": "paused_no_inventory",
            "purchase_disabled": bool(index % 2 == 0),
            "selected_steam_id": f"steam-{index}",
            "selected_inventory_name": "主仓",
            "selected_inventory_remaining_capacity": 0 if index % 2 == 0 else 50,
            "selected_inventory_max": 1000,
            "last_error": "库存刷新失败" if index % 2 else None,
            "total_purchased_count": index,
            "submitted_product_count": index,
            "purchase_success_count": 0,
            "purchase_failed_count": index,
        }
        for index in range(abnormal_account_count)
    ]
    accounts.append(
        {
            "account_id": "purchase-good-1",
            "display_name": "正常购买账号",
            "purchase_capability_state": "bound",
            "purchase_pool_state": "active",
            "purchase_disabled": False,
            "selected_steam_id": "steam-good",
            "selected_inventory_name": "主仓",
            "selected_inventory_remaining_capacity": 100,
            "selected_inventory_max": 1000,
            "last_error": None,
            "total_purchased_count": 5,
            "submitted_product_count": 8,
            "purchase_success_count": 5,
            "purchase_failed_count": 0,
        }
    )
    return {
        "running": True,
        "message": "运行中",
        "started_at": "2026-03-25T10:00:00",
        "stopped_at": None,
        "queue_size": 1,
        "active_account_count": 1,
        "total_account_count": len(accounts),
        "total_purchased_count": 9,
        "runtime_session_id": "purchase-run-1",
        "matched_product_count": 11,
        "purchase_success_count": 9,
        "purchase_failed_count": 2,
        "recent_events": recent_events,
        "accounts": accounts,
        "item_rows": [],
    }


class FakeQueryRuntimeService:
    def __init__(self, status: dict[str, object]) -> None:
        self._status = status

    def get_status(self) -> dict[str, object]:
        return self._status


class FakePurchaseRuntimeService:
    def __init__(self, status: dict[str, object]) -> None:
        self._status = status

    def get_status(self) -> dict[str, object]:
        return self._status


async def test_sidebar_diagnostics_defaults_to_idle_snapshot(client):
    response = await client.get("/diagnostics/sidebar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["backend_online"] is True
    assert payload["summary"]["query_running"] is False
    assert payload["summary"]["purchase_running"] is False
    assert payload["query"]["running"] is False
    assert payload["query"]["mode_rows"] == []
    assert payload["query"]["account_rows"] == []
    assert payload["purchase"]["running"] is False
    assert payload["purchase"]["account_rows"] == []
    assert payload["login_tasks"]["recent_tasks"] == []
    assert payload["updated_at"] is not None


async def test_sidebar_diagnostics_returns_query_purchase_and_login_sections(client, app):
    app.state.query_runtime_service = FakeQueryRuntimeService(_build_query_status())
    app.state.purchase_runtime_service = FakePurchaseRuntimeService(_build_purchase_status())
    task = app.state.task_manager.create_task(task_type="login", message="创建任务")
    app.state.task_manager.set_state(task.task_id, "waiting_for_scan", message="等待扫码")

    response = await client.get("/diagnostics/sidebar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["query_running"] is True
    assert payload["summary"]["purchase_running"] is True
    assert payload["summary"]["active_query_config_name"] == "查询配置A"
    assert payload["summary"]["last_error"] == "token invalid"
    assert payload["query"]["mode_rows"][0]["mode_type"] == "new_api"
    assert payload["query"]["mode_rows"][1]["mode_type"] == "token"
    assert payload["query"]["account_rows"][0]["account_id"] == "query-bad-1"
    assert payload["purchase"]["account_rows"][0]["account_id"] == "purchase-bad-1"
    assert payload["purchase"]["recent_events"][1]["status"] == "failed"
    assert payload["login_tasks"]["running_count"] == 1
    assert payload["login_tasks"]["recent_tasks"][0]["state"] == "waiting_for_scan"
    assert payload["login_tasks"]["recent_tasks"][0]["last_message"] == "等待扫码"


async def test_sidebar_diagnostics_prioritizes_abnormal_rows_and_caps_recent_history(client, app):
    app.state.query_runtime_service = FakeQueryRuntimeService(
        _build_query_status(recent_event_count=520, abnormal_row_count=10)
    )
    app.state.purchase_runtime_service = FakePurchaseRuntimeService(
        _build_purchase_status(recent_event_count=520, abnormal_account_count=10)
    )

    for index in range(15):
        task = app.state.task_manager.create_task(task_type="login", message=f"创建-{index}")
        app.state.task_manager.set_state(task.task_id, "waiting_for_scan", message=f"扫码-{index}")
        app.state.task_manager.set_state(
            task.task_id,
            "failed" if index % 2 else "succeeded",
            message=f"结束-{index}",
        )

    response = await client.get("/diagnostics/sidebar")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["query"]["recent_events"]) == 500
    assert len(payload["purchase"]["recent_events"]) == 500
    assert len(payload["query"]["account_rows"]) == 8
    assert len(payload["purchase"]["account_rows"]) == 8
    assert all(row["last_error"] or row["disabled_reason"] for row in payload["query"]["account_rows"])
    assert all(row["last_error"] or row["purchase_disabled"] for row in payload["purchase"]["account_rows"])
    assert len(payload["login_tasks"]["recent_tasks"]) == 12
    assert all(len(task["events"]) == 3 for task in payload["login_tasks"]["recent_tasks"])
    assert payload["login_tasks"]["failed_count"] >= 1


async def test_sidebar_diagnostics_exposes_raw_debug_fields_for_query_purchase_and_login(client, app):
    query_status = _build_query_status(recent_event_count=1, abnormal_row_count=1)
    query_status["recent_events"][0]["status_code"] = 401
    query_status["recent_events"][0]["request_method"] = "GET"
    query_status["recent_events"][0]["request_path"] = "/openapi/query"
    query_status["recent_events"][0]["request_body"] = {"page": 1, "pageSize": 50}
    query_status["recent_events"][0]["response_text"] = "not login"

    purchase_status = _build_purchase_status(recent_event_count=1, abnormal_account_count=1)
    purchase_status["recent_events"][0]["status_code"] = 409
    purchase_status["recent_events"][0]["request_method"] = "POST"
    purchase_status["recent_events"][0]["request_path"] = "/purchase/orders"
    purchase_status["recent_events"][0]["request_body"] = {"bizOrderId": "order-1"}
    purchase_status["recent_events"][0]["response_text"] = "{\"error\":\"sold out\"}"

    app.state.query_runtime_service = FakeQueryRuntimeService(query_status)
    app.state.purchase_runtime_service = FakePurchaseRuntimeService(purchase_status)

    task = app.state.task_manager.create_task(task_type="login", message="创建任务")
    app.state.task_manager.set_state(
        task.task_id,
        "failed",
        message="浏览器关闭",
        payload={
            "status_code": 500,
            "request_method": "POST",
            "request_path": "/accounts/a-1/login",
            "response_text": "browser crashed",
        },
    )

    response = await client.get("/diagnostics/sidebar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"]["recent_events"][0]["status_code"] == 401
    assert payload["query"]["recent_events"][0]["request_method"] == "GET"
    assert payload["query"]["recent_events"][0]["request_path"] == "/openapi/query"
    assert payload["query"]["recent_events"][0]["request_body"] == {"page": 1, "pageSize": 50}
    assert payload["query"]["recent_events"][0]["response_text"] == "not login"
    assert payload["purchase"]["recent_events"][0]["status_code"] == 409
    assert payload["purchase"]["recent_events"][0]["request_method"] == "POST"
    assert payload["purchase"]["recent_events"][0]["request_path"] == "/purchase/orders"
    assert payload["purchase"]["recent_events"][0]["request_body"] == {"bizOrderId": "order-1"}
    assert payload["purchase"]["recent_events"][0]["response_text"] == "{\"error\":\"sold out\"}"
    assert payload["login_tasks"]["recent_tasks"][0]["events"][-1]["payload"]["status_code"] == 500
    assert payload["login_tasks"]["recent_tasks"][0]["events"][-1]["payload"]["request_path"] == "/accounts/a-1/login"


async def test_sidebar_diagnostics_summary_only_reports_auth_invalid_errors(client, app):
    query_status = _build_query_status(recent_event_count=0, abnormal_row_count=0)
    for raw_mode in query_status["modes"].values():
        raw_mode["last_error"] = None
    purchase_status = _build_purchase_status(recent_event_count=0, abnormal_account_count=1)
    purchase_status["accounts"][0]["purchase_pool_state"] = "paused_no_inventory"
    purchase_status["accounts"][0]["last_error"] = "库存刷新失败"

    app.state.query_runtime_service = FakeQueryRuntimeService(query_status)
    app.state.purchase_runtime_service = FakePurchaseRuntimeService(purchase_status)
    task = app.state.task_manager.create_task(task_type="login", message="创建任务")
    app.state.task_manager.set_state(task.task_id, "failed", message="浏览器关闭")

    response = await client.get("/diagnostics/sidebar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["purchase"]["last_error"] == "库存刷新失败"
    assert payload["summary"]["last_error"] is None


async def test_sidebar_diagnostics_ignores_duplicate_and_item_unavailable_purchase_events_as_last_error(client, app):
    query_status = _build_query_status(recent_event_count=0, abnormal_row_count=0)
    for raw_mode in query_status["modes"].values():
        raw_mode["last_error"] = None
    purchase_status = _build_purchase_status(recent_event_count=0, abnormal_account_count=0)
    purchase_status["recent_events"] = [
        {
            "occurred_at": "2026-03-25T10:01:00",
            "status": "duplicate_filtered",
            "message": "重复命中已忽略",
            "query_item_name": "AK-47 | Redline",
            "product_list": [],
            "total_price": 123.45,
            "total_wear_sum": 0.12,
            "source_mode_type": "token",
        },
        {
            "occurred_at": "2026-03-25T10:01:01",
            "status": "payment_success_no_items",
            "message": "购买了但是没有买到物品：订单数据发生变化,请刷新页面重试",
            "query_item_name": "AK-47 | Redline",
            "product_list": [],
            "total_price": 123.45,
            "total_wear_sum": 0.12,
            "source_mode_type": "token",
            "status_code": 409,
        },
    ]

    app.state.query_runtime_service = FakeQueryRuntimeService(query_status)
    app.state.purchase_runtime_service = FakePurchaseRuntimeService(purchase_status)

    response = await client.get("/diagnostics/sidebar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["purchase"]["recent_events"][0]["status"] == "duplicate_filtered"
    assert payload["purchase"]["recent_events"][1]["status"] == "payment_success_no_items"
    assert payload["purchase"]["last_error"] is None
    assert payload["summary"]["last_error"] is None
