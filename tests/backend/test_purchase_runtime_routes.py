from datetime import datetime, timedelta

import asyncio
from types import SimpleNamespace
from app_backend.domain.models.account import Account
from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseExecutionResult
from app_backend.infrastructure.stats.runtime.stats_pipeline import StatsPipeline
from app_backend.infrastructure.stats.runtime.stats_events import (
    PurchaseSubmitOrderStatsEvent,
    QueryExecutionStatsEvent,
    QueryHitStatsEvent,
)


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


async def _create_query_config(client, *, name: str = "查询配置A") -> str:
    response = await client.post(
        "/query-configs",
        json={
            "name": name,
            "description": "用于购买运行时",
        },
    )
    return response.json()["config_id"]


async def test_purchase_runtime_status_defaults_to_idle(client):
    response = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    assert response.json() == {
        "running": False,
        "message": "未运行",
        "started_at": None,
        "stopped_at": None,
        "queue_size": 0,
        "active_account_count": 0,
        "total_account_count": 0,
        "total_purchased_count": 0,
        "runtime_session_id": None,
        "active_query_config": None,
        "matched_product_count": 0,
        "purchase_success_count": 0,
        "purchase_failed_count": 0,
        "recent_events": [],
        "accounts": [],
        "item_rows": [],
    }


async def test_start_purchase_runtime_requires_config_id(client):
    response = await client.post("/purchase-runtime/start", json={})

    assert response.status_code == 422


async def test_start_purchase_runtime_returns_running_snapshot_with_selected_config(client, app):
    config_id = await _create_query_config(client)
    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:00:00",
        last_error=None,
    )
    response = await client.post("/purchase-runtime/start", json={"config_id": config_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["running"] is True
    assert payload["message"] == "运行中"
    assert payload["queue_size"] == 0
    assert payload["active_account_count"] == 1
    assert payload["total_account_count"] == 1
    assert payload["total_purchased_count"] == 0
    assert payload["recent_events"] == []
    assert payload["accounts"][0]["account_id"] == "a1"
    assert payload["started_at"] is not None
    assert payload["stopped_at"] is None
    assert payload["active_query_config"] == {
        "config_id": config_id,
        "config_name": "查询配置A",
        "state": "running",
        "message": "运行中",
    }


async def test_stop_purchase_runtime_returns_idle_snapshot(client):
    config_id = await _create_query_config(client)
    await client.post("/purchase-runtime/start", json={"config_id": config_id})

    response = await client.post("/purchase-runtime/stop")

    assert response.status_code == 200
    assert response.json() == {
        "running": False,
        "message": "未运行",
        "started_at": None,
        "stopped_at": None,
        "queue_size": 0,
        "active_account_count": 0,
        "total_account_count": 0,
        "total_purchased_count": 0,
        "runtime_session_id": None,
        "active_query_config": None,
        "matched_product_count": 0,
        "purchase_success_count": 0,
        "purchase_failed_count": 0,
        "recent_events": [],
        "accounts": [],
        "item_rows": [],
    }


async def test_purchase_runtime_status_keeps_selected_config_daily_item_stats_when_stopped(client, app):
    today = datetime.now().date().isoformat()
    config_id = await _create_query_config(client)
    query_item = app.state.query_config_repository.add_item(
        config_id=config_id,
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
        external_item_id="1380979899390261111",
        item_name="AK-47 | Redline",
        market_hash_name="AK-47 | Redline (Field-Tested)",
        min_wear=0.1,
        max_wear=0.7,
        detail_min_wear=0.12,
        detail_max_wear=0.3,
        max_price=123.45,
        last_market_price=118.88,
        last_detail_sync_at=f"{today}T10:00:00",
    )
    await client.put(
        "/purchase-runtime/ui-preferences",
        json={"selected_config_id": config_id},
    )

    app.state.stats_repository.apply_query_execution_event(
        SimpleNamespace(
            timestamp=f"{today}T10:00:00",
            query_item_id=query_item.query_item_id,
            external_item_id=query_item.external_item_id,
            item_name=query_item.item_name,
            product_url=query_item.product_url,
            rule_fingerprint="rule-1",
            detail_min_wear=query_item.detail_min_wear,
            detail_max_wear=query_item.detail_max_wear,
            max_price=query_item.max_price,
            mode_type="new_api",
            account_id="query-a",
            account_display_name="查询账号A",
            latency_ms=120.0,
            success=True,
            error=None,
        )
    )
    app.state.stats_repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp=f"{today}T10:00:01",
            runtime_session_id="run-day-1",
            query_config_id=config_id,
            query_item_id=query_item.query_item_id,
            external_item_id=query_item.external_item_id,
            item_name=query_item.item_name,
            product_url=query_item.product_url,
            rule_fingerprint="rule-1",
            detail_min_wear=query_item.detail_min_wear,
            detail_max_wear=query_item.detail_max_wear,
            max_price=query_item.max_price,
            mode_type="new_api",
            account_id="query-a",
            account_display_name="查询账号A",
            matched_count=2,
            product_ids=["p-1", "p-2"],
        )
    )
    app.state.stats_repository.apply_purchase_submit_order_event(
        SimpleNamespace(
            timestamp=f"{today}T10:00:02",
            runtime_session_id="run-day-1",
            query_config_id=config_id,
            query_item_id=query_item.query_item_id,
            external_item_id=query_item.external_item_id,
            item_name=query_item.item_name,
            product_url=query_item.product_url,
            rule_fingerprint="rule-1",
            detail_min_wear=query_item.detail_min_wear,
            detail_max_wear=query_item.detail_max_wear,
            max_price=query_item.max_price,
            account_id="purchase-a",
            account_display_name="购买账号A",
            submit_order_latency_ms=450.0,
            submitted_count=2,
            success_count=1,
            failed_count=1,
            status="success",
            error=None,
        )
    )

    response = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    assert response.json()["running"] is False
    assert response.json()["active_query_config"] is None
    assert response.json()["item_rows"] == [
        {
            "query_item_id": query_item.query_item_id,
            "item_name": "AK-47 | Redline",
            "max_price": 123.45,
            "min_wear": 0.1,
            "max_wear": 0.7,
            "detail_min_wear": 0.12,
            "detail_max_wear": 0.3,
            "manual_paused": False,
            "query_execution_count": 1,
            "matched_product_count": 2,
            "purchase_success_count": 1,
            "purchase_failed_count": 1,
            "modes": {},
            "source_mode_stats": [
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": None,
                    "account_id": None,
                    "account_display_name": None,
                }
            ],
            "recent_hit_sources": [
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": None,
                    "account_id": None,
                    "account_display_name": None,
                }
            ],
        }
    ]


async def test_stop_purchase_runtime_keeps_daily_item_stats_without_pre_saved_ui_preferences(client, app):
    today = datetime.now().date().isoformat()
    config_id = await _create_query_config(client)
    query_item = app.state.query_config_repository.add_item(
        config_id=config_id,
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
        external_item_id="1380979899390261111",
        item_name="AK-47 | Redline",
        market_hash_name="AK-47 | Redline (Field-Tested)",
        min_wear=0.1,
        max_wear=0.7,
        detail_min_wear=0.12,
        detail_max_wear=0.3,
        max_price=123.45,
        last_market_price=118.88,
        last_detail_sync_at=f"{today}T10:00:00",
    )
    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at=f"{today}T10:00:00",
        last_error=None,
    )
    start_response = await client.post("/purchase-runtime/start", json={"config_id": config_id})
    assert start_response.status_code == 200

    app.state.stats_repository.apply_query_execution_event(
        SimpleNamespace(
            timestamp=f"{today}T10:00:00",
            query_item_id=query_item.query_item_id,
            external_item_id=query_item.external_item_id,
            item_name=query_item.item_name,
            product_url=query_item.product_url,
            rule_fingerprint="rule-1",
            detail_min_wear=query_item.detail_min_wear,
            detail_max_wear=query_item.detail_max_wear,
            max_price=query_item.max_price,
            mode_type="new_api",
            account_id="query-a",
            account_display_name="查询账号A",
            latency_ms=120.0,
            success=True,
            error=None,
        )
    )
    app.state.stats_repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp=f"{today}T10:00:01",
            runtime_session_id="run-day-1",
            query_config_id=config_id,
            query_item_id=query_item.query_item_id,
            external_item_id=query_item.external_item_id,
            item_name=query_item.item_name,
            product_url=query_item.product_url,
            rule_fingerprint="rule-1",
            detail_min_wear=query_item.detail_min_wear,
            detail_max_wear=query_item.detail_max_wear,
            max_price=query_item.max_price,
            mode_type="new_api",
            account_id="query-a",
            account_display_name="查询账号A",
            matched_count=2,
            product_ids=["p-1", "p-2"],
        )
    )
    app.state.stats_repository.apply_purchase_submit_order_event(
        SimpleNamespace(
            timestamp=f"{today}T10:00:02",
            runtime_session_id="run-day-1",
            query_config_id=config_id,
            query_item_id=query_item.query_item_id,
            external_item_id=query_item.external_item_id,
            item_name=query_item.item_name,
            product_url=query_item.product_url,
            rule_fingerprint="rule-1",
            detail_min_wear=query_item.detail_min_wear,
            detail_max_wear=query_item.detail_max_wear,
            max_price=query_item.max_price,
            account_id="purchase-a",
            account_display_name="购买账号A",
            submit_order_latency_ms=450.0,
            submitted_count=2,
            success_count=1,
            failed_count=1,
            status="success",
            error=None,
        )
    )

    stop_response = await client.post("/purchase-runtime/stop")

    assert stop_response.status_code == 200
    assert stop_response.json()["item_rows"] == [
        {
            "query_item_id": query_item.query_item_id,
            "item_name": "AK-47 | Redline",
            "max_price": 123.45,
            "min_wear": 0.1,
            "max_wear": 0.7,
            "detail_min_wear": 0.12,
            "detail_max_wear": 0.3,
            "manual_paused": False,
            "query_execution_count": 1,
            "matched_product_count": 2,
            "purchase_success_count": 1,
            "purchase_failed_count": 1,
            "modes": {},
            "source_mode_stats": [
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": None,
                    "account_id": None,
                    "account_display_name": None,
                }
            ],
            "recent_hit_sources": [
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": None,
                    "account_id": None,
                    "account_display_name": None,
                }
            ],
        }
    ]


async def test_purchase_runtime_status_keeps_daily_item_stats_while_running(client, app):
    today = datetime.now().date().isoformat()
    config_id = await _create_query_config(client)
    query_item = app.state.query_config_repository.add_item(
        config_id=config_id,
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
        external_item_id="1380979899390261111",
        item_name="AK-47 | Redline",
        market_hash_name="AK-47 | Redline (Field-Tested)",
        min_wear=0.1,
        max_wear=0.7,
        detail_min_wear=0.12,
        detail_max_wear=0.3,
        max_price=123.45,
        last_market_price=118.88,
        last_detail_sync_at=f"{today}T10:00:00",
    )
    for _ in range(3):
        app.state.stats_repository.apply_query_execution_event(
            SimpleNamespace(
                timestamp=f"{today}T09:59:00",
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                item_name=query_item.item_name,
                product_url=query_item.product_url,
                rule_fingerprint="rule-1",
                detail_min_wear=query_item.detail_min_wear,
                detail_max_wear=query_item.detail_max_wear,
                max_price=query_item.max_price,
                mode_type="new_api",
                account_id="query-history",
                account_display_name="历史查询账号",
                latency_ms=90.0,
                success=True,
                error=None,
            )
        )
    app.state.stats_repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp=f"{today}T09:59:01",
            runtime_session_id="history-run-1",
            query_config_id=config_id,
            query_item_id=query_item.query_item_id,
            external_item_id=query_item.external_item_id,
            item_name=query_item.item_name,
            product_url=query_item.product_url,
            rule_fingerprint="rule-1",
            detail_min_wear=query_item.detail_min_wear,
            detail_max_wear=query_item.detail_max_wear,
            max_price=query_item.max_price,
            mode_type="new_api",
            account_id="query-history",
            account_display_name="历史查询账号",
            matched_count=2,
            product_ids=["history-p-1", "history-p-2"],
        )
    )
    app.state.stats_repository.apply_purchase_submit_order_event(
        SimpleNamespace(
            timestamp=f"{today}T09:59:02",
            runtime_session_id="history-run-1",
            query_config_id=config_id,
            query_item_id=query_item.query_item_id,
            external_item_id=query_item.external_item_id,
            item_name=query_item.item_name,
            product_url=query_item.product_url,
            rule_fingerprint="rule-1",
            detail_min_wear=query_item.detail_min_wear,
            detail_max_wear=query_item.detail_max_wear,
            max_price=query_item.max_price,
            account_id="purchase-history",
            account_display_name="历史购买账号",
            submit_order_latency_ms=320.0,
            submitted_count=2,
            success_count=1,
            failed_count=1,
            status="success",
            error=None,
        )
    )
    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at=f"{today}T10:00:00",
        last_error=None,
    )
    start_response = await client.post("/purchase-runtime/start", json={"config_id": config_id})
    assert start_response.status_code == 200
    original_stats_pipeline = app.state.stats_pipeline
    app.state.stats_pipeline.stop()
    app.state.stats_pipeline = StatsPipeline(repository=app.state.stats_repository, flush_batch_size=1)
    try:
        app.state.stats_repository.apply_query_execution_event(
            SimpleNamespace(
                timestamp=f"{today}T10:00:00",
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                item_name=query_item.item_name,
                product_url=query_item.product_url,
                rule_fingerprint="rule-1",
                detail_min_wear=query_item.detail_min_wear,
                detail_max_wear=query_item.detail_max_wear,
                max_price=query_item.max_price,
                mode_type="new_api",
                account_id="query-a",
                account_display_name="查询账号A",
                latency_ms=120.0,
                success=True,
                error=None,
            )
        )
        app.state.stats_repository.apply_query_hit_event(
            SimpleNamespace(
                timestamp=f"{today}T10:00:01",
                runtime_session_id="run-day-1",
                query_config_id=config_id,
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                item_name=query_item.item_name,
                product_url=query_item.product_url,
                rule_fingerprint="rule-1",
                detail_min_wear=query_item.detail_min_wear,
                detail_max_wear=query_item.detail_max_wear,
                max_price=query_item.max_price,
                mode_type="new_api",
                account_id="query-a",
                account_display_name="查询账号A",
                matched_count=2,
                product_ids=["p-1", "p-2"],
            )
        )
        app.state.stats_repository.apply_purchase_submit_order_event(
            SimpleNamespace(
                timestamp=f"{today}T10:00:02",
                runtime_session_id="run-day-1",
                query_config_id=config_id,
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                item_name=query_item.item_name,
                product_url=query_item.product_url,
                rule_fingerprint="rule-1",
                detail_min_wear=query_item.detail_min_wear,
                detail_max_wear=query_item.detail_max_wear,
                max_price=query_item.max_price,
                account_id="purchase-a",
                account_display_name="购买账号A",
                submit_order_latency_ms=450.0,
                submitted_count=2,
                success_count=1,
                failed_count=1,
                status="success",
                error=None,
            )
        )

        response = await client.get("/purchase-runtime/status")
    finally:
        app.state.stats_pipeline = original_stats_pipeline

    assert response.status_code == 200
    assert response.json()["running"] is True
    assert response.json()["active_query_config"] == {
        "config_id": config_id,
        "config_name": "查询配置A",
        "state": "running",
        "message": "运行中",
    }
    assert len(response.json()["item_rows"]) == 1
    assert response.json()["item_rows"][0]["query_item_id"] == query_item.query_item_id
    assert response.json()["item_rows"][0]["item_name"] == "AK-47 | Redline"
    assert response.json()["item_rows"][0]["query_execution_count"] >= 3
    assert response.json()["item_rows"][0]["matched_product_count"] >= 2
    assert response.json()["item_rows"][0]["purchase_success_count"] >= 1
    assert response.json()["item_rows"][0]["purchase_failed_count"] >= 1


async def test_purchase_runtime_status_flushes_pending_stats_pipeline_before_stopped_daily_snapshot(client, app):
    today = datetime.now().date().isoformat()
    config_id = await _create_query_config(client)
    query_item = app.state.query_config_repository.add_item(
        config_id=config_id,
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
        external_item_id="1380979899390261111",
        item_name="AK-47 | Redline",
        market_hash_name="AK-47 | Redline (Field-Tested)",
        min_wear=0.1,
        max_wear=0.7,
        detail_min_wear=0.12,
        detail_max_wear=0.3,
        max_price=123.45,
        last_market_price=118.88,
        last_detail_sync_at=f"{today}T10:00:00",
    )
    await client.put(
        "/purchase-runtime/ui-preferences",
        json={"selected_config_id": config_id},
    )

    original_stats_pipeline = app.state.stats_pipeline
    stats_pipeline = StatsPipeline(repository=app.state.stats_repository, flush_batch_size=1)
    app.state.stats_pipeline = stats_pipeline
    try:
        assert stats_pipeline.enqueue(
            QueryExecutionStatsEvent(
                timestamp=f"{today}T10:00:00",
                query_config_id=config_id,
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                rule_fingerprint="rule-1",
                detail_min_wear=query_item.detail_min_wear,
                detail_max_wear=query_item.detail_max_wear,
                max_price=query_item.max_price,
                mode_type="new_api",
                account_id="query-a",
                account_display_name="查询账号A",
                item_name=query_item.item_name,
                product_url=query_item.product_url,
                latency_ms=120.0,
                success=True,
                error=None,
            )
        )
        assert stats_pipeline.enqueue(
            QueryHitStatsEvent(
                timestamp=f"{today}T10:00:01",
                runtime_session_id="run-day-1",
                query_config_id=config_id,
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                rule_fingerprint="rule-1",
                detail_min_wear=query_item.detail_min_wear,
                detail_max_wear=query_item.detail_max_wear,
                max_price=query_item.max_price,
                mode_type="new_api",
                account_id="query-a",
                account_display_name="查询账号A",
                item_name=query_item.item_name,
                product_url=query_item.product_url,
                matched_count=2,
                product_ids=["p-1", "p-2"],
            )
        )
        assert stats_pipeline.enqueue(
            PurchaseSubmitOrderStatsEvent(
                timestamp=f"{today}T10:00:02",
                runtime_session_id="run-day-1",
                query_config_id=config_id,
                query_item_id=query_item.query_item_id,
                external_item_id=query_item.external_item_id,
                rule_fingerprint="rule-1",
                detail_min_wear=query_item.detail_min_wear,
                detail_max_wear=query_item.detail_max_wear,
                max_price=query_item.max_price,
                item_name=query_item.item_name,
                product_url=query_item.product_url,
                account_id="purchase-a",
                account_display_name="购买账号A",
                submit_order_latency_ms=450.0,
                submitted_count=2,
                success_count=1,
                failed_count=1,
                status="success",
                error=None,
            )
        )

        response = await client.get("/purchase-runtime/status")
    finally:
        app.state.stats_pipeline = original_stats_pipeline

    assert response.status_code == 200
    assert response.json()["item_rows"] == [
        {
            "query_item_id": query_item.query_item_id,
            "item_name": "AK-47 | Redline",
            "max_price": 123.45,
            "min_wear": 0.1,
            "max_wear": 0.7,
            "detail_min_wear": 0.12,
            "detail_max_wear": 0.3,
            "manual_paused": False,
            "query_execution_count": 1,
            "matched_product_count": 2,
            "purchase_success_count": 1,
            "purchase_failed_count": 1,
            "modes": {},
            "source_mode_stats": [
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": None,
                    "account_id": None,
                    "account_display_name": None,
                }
            ],
            "recent_hit_sources": [
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": None,
                    "account_id": None,
                    "account_display_name": None,
                }
            ],
        }
    ]


async def test_purchase_runtime_settings_routes_are_removed(client):
    get_response = await client.get("/purchase-runtime/settings")
    put_response = await client.put(
        "/purchase-runtime/settings",
        json={"whitelist_account_ids": ["a1"]},
    )

    assert get_response.status_code == 404
    assert put_response.status_code == 404


async def test_purchase_runtime_ui_preferences_defaults_to_empty_selection(client):
    response = await client.get("/purchase-runtime/ui-preferences")

    assert response.status_code == 200
    assert response.json() == {
        "selected_config_id": None,
        "updated_at": None,
    }


async def test_purchase_runtime_ui_preferences_can_persist_selected_config(client):
    config_id = await _create_query_config(client)

    put_response = await client.put(
        "/purchase-runtime/ui-preferences",
        json={"selected_config_id": config_id},
    )
    get_response = await client.get("/purchase-runtime/ui-preferences")

    assert put_response.status_code == 200
    assert put_response.json()["selected_config_id"] == config_id
    assert put_response.json()["updated_at"] is not None
    assert get_response.status_code == 200
    assert get_response.json()["selected_config_id"] == config_id
    assert get_response.json()["updated_at"] is not None


async def test_purchase_runtime_ui_preferences_rejects_missing_config(client):
    response = await client.put(
        "/purchase-runtime/ui-preferences",
        json={"selected_config_id": "missing-config"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "查询配置不存在"


async def test_purchase_runtime_ui_preferences_clears_deleted_config(client):
    config_id = await _create_query_config(client)
    await client.put(
        "/purchase-runtime/ui-preferences",
        json={"selected_config_id": config_id},
    )

    delete_response = await client.delete(f"/query-configs/{config_id}")
    get_response = await client.get("/purchase-runtime/ui-preferences")

    assert delete_response.status_code == 204
    assert get_response.status_code == 200
    assert get_response.json() == {
        "selected_config_id": None,
        "updated_at": None,
    }


async def test_delete_selected_query_config_bumps_runtime_update_version(client, app):
    config_id = await _create_query_config(client)
    await client.put(
        "/purchase-runtime/ui-preferences",
        json={"selected_config_id": config_id},
    )
    version_before_delete = app.state.runtime_update_hub.current_version()

    delete_response = await client.delete(f"/query-configs/{config_id}")

    assert delete_response.status_code == 204
    assert app.state.runtime_update_hub.current_version() == version_before_delete + 2


async def _wait_until_status(client, predicate, *, timeout: float = 1.0, interval: float = 0.01):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get("/purchase-runtime/status")
        if predicate(response.json()):
            return response
        if asyncio.get_running_loop().time() >= deadline:
            return response
        await asyncio.sleep(interval)
async def test_purchase_runtime_end_to_end_handles_hit(client, app):
    class StubExecutionGateway:
        async def execute(self, *, account, batch, selected_steam_id: str, on_execute_started=None, **_kwargs):
            if callable(on_execute_started):
                on_execute_started()
            return PurchaseExecutionResult.success(purchased_count=1)

    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._execution_gateway_factory = lambda: StubExecutionGateway()
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:00:00",
        last_error=None,
    )
    config_id = await _create_query_config(client)
    await client.post("/purchase-runtime/start", json={"config_id": config_id})

    result = app.state.purchase_runtime_service.accept_query_hit(
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
    response = await _wait_until_status(
        client,
        lambda payload: payload["total_purchased_count"] == 1,
    )

    assert result == {"accepted": True, "status": "queued"}
    assert response.status_code == 200
    assert response.json()["queue_size"] == 0
    assert response.json()["total_purchased_count"] == 1
    assert response.json()["recent_events"] == []


async def test_purchase_runtime_status_returns_selected_inventory_summary(client, app):
    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = None
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[{"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:00:00",
        last_error=None,
    )
    config_id = await _create_query_config(client)
    await client.post("/purchase-runtime/start", json={"config_id": config_id})

    response = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["accounts"][0]["selected_steam_id"] == "steam-1"
    assert payload["accounts"][0]["selected_inventory_name"] == "主仓"
    assert payload["accounts"][0]["selected_inventory_remaining_capacity"] == 90
    assert payload["accounts"][0]["selected_inventory_max"] == 1000


async def test_purchase_runtime_status_includes_stats_and_keeps_accounts_shape(client, app):
    class FakePurchaseRuntimeService:
        def get_status(self, *, include_recent_events: bool = True) -> dict[str, object]:
            return {
                "running": True,
                "message": "运行中",
                "started_at": "2026-03-19T13:00:00",
                "stopped_at": None,
                "queue_size": 0,
                "active_account_count": 1,
                "total_account_count": 1,
                "total_purchased_count": 1,
                "runtime_session_id": "run-1",
                "matched_product_count": 3,
                "purchase_success_count": 1,
                "purchase_failed_count": 2,
                "recent_events": [
                    {
                        "occurred_at": "2026-03-19T13:00:02",
                        "status": "payment_success_no_items",
                        "message": "购买了但是没有买到物品：订单数据发生变化,请刷新页面重试",
                        "query_item_name": "AK-47 | Redline",
                        "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0.0}],
                        "total_price": 88.0,
                        "total_wear_sum": 0.12,
                        "source_mode_type": "new_api",
                        "status_code": 409,
                        "request_method": "POST",
                        "request_path": "/pay/order/v1/pay",
                        "request_body": {"bizOrderId": "order-1", "receiveSteamId": "steam-1"},
                        "response_text": "{\"errorMsg\":\"订单数据发生变化,请刷新页面重试\"}",
                    }
                ],
                "accounts": [
                    {
                        "account_id": "a1",
                        "display_name": "购买账号",
                        "purchase_capability_state": "bound",
                        "purchase_pool_state": "active",
                        "selected_steam_id": "steam-1",
                        "selected_inventory_name": "主仓",
                        "selected_inventory_remaining_capacity": 90,
                        "selected_inventory_max": 1000,
                        "last_error": None,
                        "total_purchased_count": 1,
                        "submitted_product_count": 3,
                        "purchase_success_count": 1,
                        "purchase_failed_count": 2,
                    }
                ],
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "matched_product_count": 3,
                        "purchase_success_count": 1,
                        "purchase_failed_count": 2,
                        "source_mode_stats": [
                            {
                                "mode_type": "new_api",
                                "hit_count": 2,
                                "last_hit_at": "2026-03-20T12:00:00",
                                "account_id": "query-a",
                                "account_display_name": "查询账号A",
                            },
                            {
                                "mode_type": "fast_api",
                                "hit_count": 1,
                                "last_hit_at": "2026-03-20T12:00:03",
                                "account_id": "query-b",
                                "account_display_name": "查询账号B",
                            },
                        ],
                        "recent_hit_sources": [
                            {
                                "mode_type": "fast_api",
                                "hit_count": 1,
                                "last_hit_at": "2026-03-20T12:00:03",
                                "account_id": "query-b",
                                "account_display_name": "查询账号B",
                            },
                            {
                                "mode_type": "new_api",
                                "hit_count": 2,
                                "last_hit_at": "2026-03-20T12:00:00",
                                "account_id": "query-a",
                                "account_display_name": "查询账号A",
                            },
                        ],
                    }
                ],
            }

    class FakeQueryRuntimeService:
        def get_status(self) -> dict[str, object]:
            return {
                "running": False,
                "config_id": "cfg-1",
                "config_name": "查询配置A",
                "message": "等待购买账号恢复",
                "account_count": 0,
                "started_at": None,
                "stopped_at": "2026-03-19T13:00:01",
                "total_query_count": 7,
                "total_found_count": 3,
                "modes": {},
                "group_rows": [],
                "recent_events": [],
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "item_name": "AK-47 | Redline",
                        "max_price": 123.45,
                        "min_wear": 0.1,
                        "max_wear": 0.7,
                        "detail_min_wear": 0.12,
                        "detail_max_wear": 0.3,
                        "manual_paused": False,
                        "query_count": 7,
                        "modes": {
                            "new_api": {
                                "mode_type": "new_api",
                                "target_dedicated_count": 1,
                                "actual_dedicated_count": 1,
                                "status": "dedicated",
                                "status_message": "专属中 1/1",
                                "shared_available_count": 2,
                            }
                        },
                    }
                ],
            }

    app.state.purchase_runtime_service = FakePurchaseRuntimeService()
    app.state.query_runtime_service = FakeQueryRuntimeService()

    response = await client.get("/purchase-runtime/status")

    assert response.status_code == 200
    assert response.json()["runtime_session_id"] == "run-1"
    assert response.json()["active_query_config"] == {
        "config_id": "cfg-1",
        "config_name": "查询配置A",
        "state": "waiting",
        "message": "等待购买账号恢复",
    }
    assert response.json()["matched_product_count"] == 3
    assert response.json()["purchase_success_count"] == 1
    assert response.json()["purchase_failed_count"] == 2
    assert response.json()["recent_events"] == []
    assert response.json()["accounts"][0]["submitted_product_count"] == 3
    assert response.json()["accounts"][0]["purchase_success_count"] == 1
    assert response.json()["accounts"][0]["purchase_failed_count"] == 2
    assert response.json()["item_rows"] == [
        {
            "query_item_id": "item-1",
            "item_name": "AK-47 | Redline",
            "max_price": 123.45,
            "min_wear": 0.1,
            "max_wear": 0.7,
            "detail_min_wear": 0.12,
            "detail_max_wear": 0.3,
            "manual_paused": False,
            "query_execution_count": 7,
            "matched_product_count": 3,
            "purchase_success_count": 1,
            "purchase_failed_count": 2,
            "modes": {
                "new_api": {
                    "mode_type": "new_api",
                    "target_dedicated_count": 1,
                    "actual_dedicated_count": 1,
                    "status": "dedicated",
                    "status_message": "专属中 1/1",
                    "shared_available_count": 2,
                }
            },
            "source_mode_stats": [
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": "2026-03-20T12:00:00",
                    "account_id": "query-a",
                    "account_display_name": "查询账号A",
                },
                {
                    "mode_type": "fast_api",
                    "hit_count": 1,
                    "last_hit_at": "2026-03-20T12:00:03",
                    "account_id": "query-b",
                    "account_display_name": "查询账号B",
                },
            ],
            "recent_hit_sources": [
                {
                    "mode_type": "fast_api",
                    "hit_count": 1,
                    "last_hit_at": "2026-03-20T12:00:03",
                    "account_id": "query-b",
                    "account_display_name": "查询账号B",
                },
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": "2026-03-20T12:00:00",
                    "account_id": "query-a",
                    "account_display_name": "查询账号A",
                },
            ],
        }
    ]


async def test_purchase_runtime_inventory_detail_route_returns_snapshot(client, app):
    account = _build_account("a1")
    account.purchase_recovery_due_at = (datetime.now() + timedelta(seconds=180)).isoformat()
    app.state.account_repository.create_account(account)
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-2",
        inventories=[
            {"steamId": "steam-1", "nickname": "备用仓", "inventory_num": 990, "inventory_max": 1000},
            {"steamId": "steam-2", "nickname": "主仓", "inventory_num": 920, "inventory_max": 1000},
        ],
        refreshed_at="2026-03-16T21:00:00",
        last_error="等待恢复检查",
    )

    response = await client.get("/purchase-runtime/accounts/a1/inventory")

    assert response.status_code == 200
    assert response.json() == {
        "account_id": "a1",
        "display_name": "购买账号",
        "selected_steam_id": "steam-2",
        "refreshed_at": "2026-03-16T21:00:00",
        "last_error": "等待恢复检查",
        "auto_refresh_due_at": account.purchase_recovery_due_at,
        "auto_refresh_remaining_seconds": response.json()["auto_refresh_remaining_seconds"],
        "inventories": [
            {
                "steamId": "steam-1",
                "nickname": "备用仓",
                "inventory_num": 990,
                "inventory_max": 1000,
                "remaining_capacity": 10,
                "is_selected": False,
                "is_available": False,
            },
            {
                "steamId": "steam-2",
                "nickname": "主仓",
                "inventory_num": 920,
                "inventory_max": 1000,
                "remaining_capacity": 80,
                "is_selected": True,
                "is_available": True,
            },
        ],
    }
    assert 0 < response.json()["auto_refresh_remaining_seconds"] <= 180


async def test_purchase_runtime_inventory_refresh_route_returns_latest_detail(client, app):
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    app.state.account_repository.create_account(_build_account("a1"))
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="a1",
        selected_steam_id="steam-1",
        inventories=[
            {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 900, "inventory_max": 1000},
        ],
        refreshed_at="2026-03-16T21:00:00",
        last_error=None,
    )

    class RefreshGateway:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def refresh(self, *, account):
            self.calls.append({"account_id": account.account_id})
            return InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 800, "inventory_max": 1000},
                ]
            )

    refresh_gateway = RefreshGateway()
    app.state.purchase_runtime_service._inventory_refresh_gateway_factory = lambda: refresh_gateway

    response = await client.post("/purchase-runtime/accounts/a1/inventory/refresh")

    assert response.status_code == 200
    assert refresh_gateway.calls == [{"account_id": "a1"}]
    assert response.json()["selected_steam_id"] == "steam-1"
    assert response.json()["inventories"][0]["nickname"] == "主仓"
    assert response.json()["inventories"][0]["inventory_num"] == 800


async def test_purchase_runtime_ui_preferences_triggers_runtime_full_ensure_when_dependencies_missing(client, app):
    ensure_calls: list[str] = []

    class FakePreferences:
        selected_config_id = None
        updated_at = None

    class FakePurchaseUiPreferencesRepository:
        def get(self):
            return FakePreferences()

        def clear_selected_config(self) -> None:
            return None

    class FakeQueryConfigRepository:
        def get_config(self, _config_id: str):
            return None

    def fake_ensure() -> None:
        ensure_calls.append("called")
        app.state.purchase_ui_preferences_repository = FakePurchaseUiPreferencesRepository()
        app.state.query_config_repository = FakeQueryConfigRepository()

    delattr(app.state, "purchase_ui_preferences_repository")
    app.state.ensure_runtime_full_ready = fake_ensure

    response = await client.get("/purchase-runtime/ui-preferences")

    assert response.status_code == 200
    assert response.json() == {
        "selected_config_id": None,
        "updated_at": None,
    }
    assert ensure_calls == ["called"]
