from __future__ import annotations

import asyncio
import threading
import time
from queue import Empty

import pytest
from app_backend.domain.models.account import Account
from fastapi.testclient import TestClient


def _create_query_config(client: TestClient, *, name: str = "运行时配置A") -> str:
    response = client.post(
        "/query-configs",
        json={
            "name": name,
            "description": "用于 runtime update websocket",
        },
    )
    assert response.status_code == 201
    return response.json()["config_id"]


def _build_account(account_id: str) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=None,
        browser_proxy_mode="direct",
        browser_proxy_url=None,
        api_proxy_mode="direct",
        api_proxy_url=None,
        api_key=None,
        c5_user_id="10001",
        c5_nick_name="购买账号",
        cookie_raw="NC5_accessToken=token",
        purchase_capability_state="bound",
        purchase_pool_state="not_connected",
        last_login_at="2026-03-16T20:00:00",
        last_error=None,
        created_at="2026-03-16T20:00:00",
        updated_at="2026-03-16T20:00:00",
    )


def _wait_until(predicate, *, timeout: float = 1.0, interval: float = 0.01):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_runtime_update_websocket_streams_published_events(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/runtime") as websocket:
            expected_version = app.state.runtime_update_hub.current_version() + 1
            app.state.runtime_update_hub.publish(
                event="query_runtime.updated",
                payload={"running": True, "message": "运行中"},
            )

            payload = websocket.receive_json()

    assert payload["version"] == expected_version
    assert payload["event"] == "query_runtime.updated"
    assert payload["payload"] == {"running": True, "message": "运行中"}
    assert payload["updated_at"]


def test_runtime_update_websocket_replays_events_since_bootstrap_version(app):
    with TestClient(app) as client:
        bootstrap_response = client.get("/app/bootstrap")
        assert bootstrap_response.status_code == 200
        since_version = bootstrap_response.json()["version"]
        expected_version = since_version + 1

        app.state.runtime_update_hub.publish(
            event="query_runtime.updated",
            payload={"source": "missed-after-bootstrap"},
        )

        with client.websocket_connect(f"/ws/runtime?since_version={since_version}") as websocket:
            app.state.runtime_update_hub.publish(
                event="query_runtime.updated",
                payload={"source": "live-after-connect"},
            )
            payload = websocket.receive_json()

    assert payload["version"] == expected_version
    assert payload["event"] == "query_runtime.updated"
    assert payload["payload"] == {"source": "missed-after-bootstrap"}


def test_runtime_update_websocket_requests_resync_when_since_version_falls_outside_history(app):
    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub

    original_hub = app.state.runtime_update_hub
    app.state.runtime_update_hub = RuntimeUpdateHub(history_limit=2)
    try:
        with TestClient(app) as client:
            app.state.runtime_update_hub.publish(
                event="query_runtime.updated",
                payload={"step": 1},
            )
            app.state.runtime_update_hub.publish(
                event="query_runtime.updated",
                payload={"step": 2},
            )
            app.state.runtime_update_hub.publish(
                event="query_runtime.updated",
                payload={"step": 3},
            )

            with client.websocket_connect("/ws/runtime?since_version=0") as websocket:
                payload = websocket.receive_json()
                app.state.runtime_update_hub.publish(
                    event="query_runtime.updated",
                    payload={"step": "live"},
                )
                with pytest.raises(Exception):
                    websocket.receive_json()
    finally:
        app.state.runtime_update_hub = original_hub

    assert payload["event"] == "runtime.resync_required"
    assert payload["version"] == 3
    assert payload["payload"]["reason"] == "history_overflow"
    assert payload["payload"]["requested_version"] == 0
    assert payload["payload"]["oldest_available_version"] == 2
    assert payload["payload"]["current_version"] == 3


def test_runtime_update_websocket_receives_background_thread_publish(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/runtime") as websocket:
            expected_version = app.state.runtime_update_hub.current_version() + 1
            publisher = threading.Thread(
                target=lambda: app.state.runtime_update_hub.publish(
                    event="query_runtime.updated",
                    payload={"source": "background-thread"},
                ),
                daemon=True,
            )
            publisher.start()
            payload = websocket.receive_json()
            publisher.join(timeout=1.0)

    assert payload["version"] == expected_version
    assert payload["event"] == "query_runtime.updated"
    assert payload["payload"] == {"source": "background-thread"}


def test_runtime_update_hub_preserves_version_order_across_concurrent_publishers():
    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub

    hub = RuntimeUpdateHub()
    queue = hub.subscribe("*")
    barrier = threading.Barrier(3)

    def publish(payload: dict[str, object]) -> None:
        barrier.wait()
        hub.publish(event="query_runtime.updated", payload=payload)

    large_payload = {"blob": ["x" * 20000 for _ in range(32)]}
    small_payload = {"blob": ["small"]}
    first_publisher = threading.Thread(target=publish, args=(large_payload,), daemon=True)
    second_publisher = threading.Thread(target=publish, args=(small_payload,), daemon=True)
    first_publisher.start()
    second_publisher.start()
    barrier.wait()
    first_publisher.join(timeout=1.0)
    second_publisher.join(timeout=1.0)

    first_event = queue.get_nowait()
    second_event = queue.get_nowait()

    assert [first_event.version, second_event.version] == [1, 2]


def test_runtime_update_websocket_preserves_version_order_for_event_loop_subscribers(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/runtime") as websocket:
            barrier = threading.Barrier(3)

            def publish(payload: dict[str, object]) -> None:
                barrier.wait()
                app.state.runtime_update_hub.publish(
                    event="query_runtime.updated",
                    payload=payload,
                )

            first_publisher = threading.Thread(
                target=publish,
                args=({"blob": ["x" * 20000 for _ in range(32)]},),
                daemon=True,
            )
            second_publisher = threading.Thread(
                target=publish,
                args=({"blob": ["small"]},),
                daemon=True,
            )
            first_publisher.start()
            second_publisher.start()
            barrier.wait()

            first_payload = websocket.receive_json()
            second_payload = websocket.receive_json()

            first_publisher.join(timeout=1.0)
            second_publisher.join(timeout=1.0)

    assert [first_payload["version"], second_payload["version"]] == sorted(
        [first_payload["version"], second_payload["version"]]
    )
    assert first_payload["version"] + 1 == second_payload["version"]


def test_runtime_update_websocket_receives_query_config_updates(app):
    with TestClient(app) as client:
        expected_version = app.state.runtime_update_hub.current_version() + 1

        with client.websocket_connect("/ws/runtime") as websocket:
            response = client.post(
                "/query-configs",
                json={
                    "name": "配置-1",
                    "description": "用于 query config websocket update",
                },
            )
            payload = websocket.receive_json()

    assert response.status_code == 201
    assert payload["version"] == expected_version
    assert payload["event"] == "query_configs.updated"
    assert any(config["config_id"] == response.json()["config_id"] for config in payload["payload"]["configs"])


def test_runtime_update_websocket_receives_purchase_ui_preferences_updates(app):
    with TestClient(app) as client:
        config_id = _create_query_config(client)
        expected_version = app.state.runtime_update_hub.current_version() + 1

        with client.websocket_connect("/ws/runtime") as websocket:
            response = client.put(
                "/purchase-runtime/ui-preferences",
                json={"selected_config_id": config_id},
            )
            payload = websocket.receive_json()

    assert response.status_code == 200
    assert payload["version"] == expected_version
    assert payload["event"] == "purchase_ui_preferences.updated"
    assert payload["payload"] == response.json()
    assert payload["updated_at"]


def test_runtime_update_websocket_receives_runtime_settings_updates(app):
    with TestClient(app) as client:
        expected_version = app.state.runtime_update_hub.current_version() + 1

        with client.websocket_connect("/ws/runtime") as websocket:
            response = client.put(
                "/runtime-settings/purchase",
                json={
                    "per_batch_ip_fanout_limit": 4,
                    "max_inflight_per_account": 2,
                },
            )
            payload = websocket.receive_json()

    assert response.status_code == 200
    assert payload["version"] == expected_version
    assert payload["event"] == "runtime_settings.updated"
    assert payload["payload"] == response.json()
    assert payload["payload"]["max_inflight_per_account"] == 2
    assert payload["updated_at"]


def test_runtime_update_websocket_streams_real_query_and_purchase_runtime_updates(app):
    release_gateway = threading.Event()

    class BlockingExecutionGateway:
        async def execute(self, *, account, batch, selected_steam_id: str, on_execute_started=None, **_kwargs):
            if callable(on_execute_started):
                on_execute_started()
            release_gateway.wait(timeout=1.0)
            from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseExecutionResult

            return PurchaseExecutionResult.success(purchased_count=1)

    with TestClient(app) as client:
        config_id = _create_query_config(client)
        app.state.account_repository.create_account(_build_account("a1"))
        app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
        app.state.purchase_runtime_service._execution_gateway_factory = lambda: BlockingExecutionGateway()
        app.state.purchase_runtime_service._inventory_snapshot_repository.save(
            account_id="a1",
            selected_steam_id="steam-1",
            inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
            refreshed_at="2026-03-16T20:00:00",
            last_error=None,
        )

        with client.websocket_connect("/ws/runtime") as websocket:
            start_response = client.post("/query-runtime/start", json={"config_id": config_id})
            assert start_response.status_code == 200

            seen_events: list[dict[str, object]] = []
            while True:
                event = websocket.receive_json()
                seen_events.append(event)
                if event["event"] == "query_runtime.updated":
                    query_event = event
                    break

            query_status_response = client.get("/query-runtime/status")
            assert query_status_response.status_code == 200
            assert query_event["payload"] == query_status_response.json()

            hit_result = app.state.purchase_runtime_service.accept_query_hit(
                {
                    "external_item_id": "1380979899390261111",
                    "query_item_name": "AK",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                    "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                    "total_price": 88.0,
                    "total_wear_sum": 0.1234,
                    "mode_type": "new_api",
                }
            )
            assert hit_result == {"accepted": True, "status": "queued"}

            while True:
                event = websocket.receive_json()
                seen_events.append(event)
                if event["event"] == "purchase_runtime.updated":
                    purchase_event = event
                    break

            status_response = client.get("/purchase-runtime/status")
            assert status_response.status_code == 200
            assert purchase_event["payload"] == status_response.json()
            versions = [int(event["version"]) for event in seen_events]
            assert versions == sorted(versions)
            assert len(set(versions)) == len(versions)
            assert any(event["event"] == "query_runtime.updated" for event in seen_events)
        release_gateway.set()


def test_runtime_update_hub_streams_forced_stop_reason_updates(app):
    class FakeProgramRuntimeControlService:
        def __init__(self) -> None:
            self.start_calls = 0
            self.stop_calls = 0
            self._on_force_stop = None

        def set_on_force_stop(self, callback) -> None:
            self._on_force_stop = callback

        def start(self) -> None:
            self.start_calls += 1

        def stop(self, *, timeout: float = 1.0) -> None:
            _ = timeout
            self.stop_calls += 1

        def emit_force_stop(self, reason: str) -> None:
            if callable(self._on_force_stop):
                self._on_force_stop(reason)

    with TestClient(app) as client:
        config_id = _create_query_config(client)
        app.state.account_repository.create_account(_build_account("a1"))
        fake_runtime_control_service = FakeProgramRuntimeControlService()
        app.state.query_runtime_service._program_runtime_control_service = fake_runtime_control_service
        app.state.query_runtime_service._register_program_runtime_control_callback()
        queue = app.state.runtime_update_hub.subscribe("*")

        start_response = client.post("/query-runtime/start", json={"config_id": config_id})
        assert start_response.status_code == 200
        assert fake_runtime_control_service.start_calls == 1
        drain_deadline = time.time() + 0.2
        while time.time() < drain_deadline:
            try:
                queue.get_nowait()
            except (Empty, asyncio.QueueEmpty):
                time.sleep(0.01)
                continue

        fake_runtime_control_service.emit_force_stop("program_runtime_revoked")

        forced_events = []
        deadline = time.time() + 1.0
        while time.time() < deadline and len(forced_events) < 2:
            try:
                candidate = queue.get_nowait()
            except (Empty, asyncio.QueueEmpty):
                time.sleep(0.01)
                continue
            if candidate.event in {"purchase_runtime.updated", "query_runtime.updated"}:
                forced_events.append(candidate)

        query_status_response = client.get("/query-runtime/status")
        purchase_status_response = client.get("/purchase-runtime/status")

    assert query_status_response.status_code == 200
    assert purchase_status_response.status_code == 200
    assert len(forced_events) == 2
    assert [event.event for event in forced_events] == [
        "purchase_runtime.updated",
        "query_runtime.updated",
    ]
    assert forced_events[0].payload["last_error"] == "program_runtime_revoked"
    assert forced_events[1].payload["last_error"] == "program_runtime_revoked"
    assert forced_events[0].payload == purchase_status_response.json()
    assert forced_events[1].payload == query_status_response.json()


def test_runtime_update_websocket_receives_selected_config_clear_on_delete(app):
    with TestClient(app) as client:
        config_id = _create_query_config(client)
        put_response = client.put(
            "/purchase-runtime/ui-preferences",
            json={"selected_config_id": config_id},
        )
        assert put_response.status_code == 200
        expected_version = app.state.runtime_update_hub.current_version() + 2

        with client.websocket_connect("/ws/runtime") as websocket:
            delete_response = client.delete(f"/query-configs/{config_id}")
            while True:
                payload = websocket.receive_json()
                if payload["event"] == "purchase_ui_preferences.updated":
                    break

    assert delete_response.status_code == 204
    assert payload["version"] == expected_version
    assert payload["event"] == "purchase_ui_preferences.updated"
    assert payload["payload"] == {
        "selected_config_id": None,
        "updated_at": None,
    }


def test_delete_active_query_config_publishes_runtime_snapshot_updates(app):
    with TestClient(app) as client:
        config_id = _create_query_config(client)
        start_response = client.post("/query-runtime/start", json={"config_id": config_id})
        assert start_response.status_code == 200

        with client.websocket_connect("/ws/runtime") as websocket:
            delete_response = client.delete(f"/query-configs/{config_id}")
            app.state.runtime_update_hub.publish(event="sentinel", payload={"done": True})
            events: list[dict[str, object]] = []
            while True:
                payload = websocket.receive_json()
                events.append(payload)
                if payload["event"] == "sentinel":
                    break
        query_status_response = client.get("/query-runtime/status")
        purchase_status_response = client.get("/purchase-runtime/status")

    assert delete_response.status_code == 204
    assert query_status_response.status_code == 200
    assert purchase_status_response.status_code == 200
    assert [event["event"] for event in events[:-1]] == [
        "query_configs.updated",
        "query_runtime.updated",
        "purchase_runtime.updated",
    ]
    assert events[1]["payload"] == query_status_response.json()
    assert events[2]["payload"] == purchase_status_response.json()


def test_runtime_update_websocket_receives_purchase_inventory_refresh_updates(app):
    class InventoryRefreshGateway:
        async def refresh(self, *, account):
            from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

            return InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-2", "nickname": "刷新仓", "inventory_num": 920, "inventory_max": 1000},
                ]
            )

    with TestClient(app) as client:
        config_id = _create_query_config(client)
        app.state.account_repository.create_account(_build_account("a1"))
        app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: InventoryRefreshGateway()
        app.state.purchase_runtime_service._inventory_snapshot_repository.save(
            account_id="a1",
            selected_steam_id="steam-1",
            inventories=[{"steamId": "steam-1", "nickname": "旧仓", "inventory_num": 910, "inventory_max": 1000}],
            refreshed_at="2026-03-16T20:00:00",
            last_error=None,
        )
        start_response = client.post("/query-runtime/start", json={"config_id": config_id})
        assert start_response.status_code == 200
        expected_version = app.state.runtime_update_hub.current_version() + 1

        with client.websocket_connect("/ws/runtime") as websocket:
            response = client.post("/purchase-runtime/accounts/a1/inventory/refresh")
            payload = websocket.receive_json()
        status_response = client.get("/purchase-runtime/status")

    assert response.status_code == 200
    assert status_response.status_code == 200
    assert payload["version"] == expected_version
    assert payload["event"] == "purchase_runtime.updated"
    assert payload["payload"] == status_response.json()


def test_purchase_inventory_refresh_without_running_runtime_publishes_runtime_update(app):
    class InventoryRefreshGateway:
        async def refresh(self, *, account):
            from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

            return InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-2", "nickname": "刷新仓", "inventory_num": 920, "inventory_max": 1000},
                ]
            )

    with TestClient(app) as client:
        app.state.account_repository.create_account(_build_account("a1"))
        app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: InventoryRefreshGateway()

        queue = app.state.runtime_update_hub.subscribe("*")
        response = client.post("/purchase-runtime/accounts/a1/inventory/refresh")
        status_response = client.get("/purchase-runtime/status")

    event = queue.get_nowait()

    assert response.status_code == 200
    assert status_response.status_code == 200
    assert event.event == "purchase_runtime.updated"
    assert event.payload == status_response.json()
