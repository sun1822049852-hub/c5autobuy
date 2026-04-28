from __future__ import annotations

import asyncio
import json
from pathlib import Path
from httpx import ASGITransport, AsyncClient

from app_backend.domain.models.account import Account
from app_backend.infrastructure.stats.runtime.stats_pipeline import StatsPipeline
from app_backend.infrastructure.stats.runtime.stats_events import (
    PurchaseSubmitOrderStatsEvent,
    QueryExecutionStatsEvent,
    QueryHitStatsEvent,
)
from app_backend.main import create_app


def _build_account(account_id: str, *, api_key: str | None = None) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"默认-{account_id}",
        remark_name=f"备注-{account_id}",
        browser_proxy_mode="custom",
        browser_proxy_url="http://127.0.0.1:9001",
        api_proxy_mode="custom",
        api_proxy_url="http://127.0.0.1:9001",
        api_key=api_key,
        c5_user_id="10001",
        c5_nick_name=f"昵称-{account_id}",
        cookie_raw="NC5_accessToken=token",
        purchase_capability_state="bound",
        purchase_pool_state="not_connected",
        last_login_at="2026-03-16T20:00:00",
        last_error=None,
        created_at="2026-03-16T20:00:00",
        updated_at="2026-03-16T20:00:00",
        purchase_disabled=False,
        purchase_recovery_due_at=None,
    )


async def test_request_diagnostics_logs_slow_requests(tmp_path: Path):
    log_path = tmp_path / "runtime" / "request_diagnostics.runtime.jsonl"
    app = create_app(
        db_path=tmp_path / "slow.db",
        request_diagnostics_log_path=log_path,
        request_diagnostics_slow_ms=0,
    )

    @app.get("/_slow-request")
    async def slow_request() -> dict[str, bool]:
        await asyncio.sleep(0.01)
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_slow-request")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert log_path.exists()

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records
    assert records[-1]["event"] == "slow_request"
    assert records[-1]["method"] == "GET"
    assert records[-1]["path"] == "/_slow-request"
    assert records[-1]["status_code"] == 200
    assert records[-1]["duration_ms"] >= 0


async def test_request_diagnostics_logs_account_center_accounts_trace_breakdown(tmp_path: Path):
    log_path = tmp_path / "runtime" / "request_diagnostics.runtime.jsonl"
    app = create_app(
        db_path=tmp_path / "account-center.db",
        request_diagnostics_log_path=log_path,
        request_diagnostics_slow_ms=60_000,
    )
    app.state.account_repository.create_account(_build_account("trace-a", api_key="api-trace-a"))
    app.state.account_repository.create_account(_build_account("trace-b"))
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="trace-a",
        selected_steam_id="steam-trace-a",
        inventories=[{"steamId": "steam-trace-a", "nickname": "主仓A", "inventory_num": 900, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:05:00",
        last_error=None,
    )
    app.state.purchase_runtime_service._inventory_snapshot_repository.save(
        account_id="trace-b",
        selected_steam_id="steam-trace-b",
        inventories=[{"steamId": "steam-trace-b", "nickname": "主仓B", "inventory_num": 880, "inventory_max": 1000}],
        refreshed_at="2026-03-16T20:05:00",
        last_error=None,
    )

    class _NoopBalanceService:
        def maybe_schedule_refresh(self, account_id: str) -> bool:
            return account_id == "trace-a"

    app.state.account_balance_service = _NoopBalanceService()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/account-center/accounts")

    assert response.status_code == 200
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    trace_record = next(record for record in reversed(records) if record["path"] == "/account-center/accounts")

    assert trace_record["event"] == "request_trace"
    assert trace_record["trace"]["name"] == "account_center.accounts"
    assert trace_record["trace"]["details"]["source"] == "runtime"
    assert trace_record["trace"]["details"]["account_count"] == 2
    assert trace_record["trace"]["details"]["row_count"] == 2

    phase_names = {phase["name"] for phase in trace_record["trace"]["phases"]}
    assert {
        "route.use_case.execute",
        "runtime.runtime_account_map",
        "runtime.account_repository.list_accounts",
        "runtime.account_center_row.build",
        "runtime.account_inventory_detail.total",
        "route.model_validate.row",
        "route.balance_refresh.schedule.row",
    }.issubset(phase_names)


async def test_request_diagnostics_logs_purchase_runtime_status_trace_breakdown(tmp_path: Path):
    log_path = tmp_path / "runtime" / "request_diagnostics.runtime.jsonl"
    app = create_app(
        db_path=tmp_path / "purchase-status.db",
        request_diagnostics_log_path=log_path,
        request_diagnostics_slow_ms=60_000,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_config_response = await client.post(
            "/query-configs",
            json={
                "name": "查询配置A",
                "description": "用于状态 trace",
            },
        )
        assert create_config_response.status_code == 201
        config_id = create_config_response.json()["config_id"]

        today = "2026-04-28"
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
        set_preferences_response = await client.put(
            "/purchase-runtime/ui-preferences",
            json={"selected_config_id": config_id},
        )
        assert set_preferences_response.status_code == 200

        original_stats_pipeline = app.state.stats_pipeline
        original_stats_pipeline.stop()
        app.state.stats_pipeline = StatsPipeline(repository=app.state.stats_repository, flush_batch_size=1)
        try:
            assert app.state.stats_pipeline.enqueue(
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
            assert app.state.stats_pipeline.enqueue(
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
            assert app.state.stats_pipeline.enqueue(
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
            "source_mode_stats": [],
            "recent_hit_sources": [],
        }
    ]

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    trace_record = next(record for record in reversed(records) if record["path"] == "/purchase-runtime/status")

    assert trace_record["event"] == "request_trace"
    assert trace_record["trace"]["name"] == "purchase_runtime.status"
    assert trace_record["trace"]["details"]["stats_flush_drained_count"] == 3
    assert trace_record["trace"]["details"]["stats_flush_budget_exhausted"] is False

    phase_names = {phase["name"] for phase in trace_record["trace"]["phases"]}
    assert {
        "route.use_case.execute",
        "runtime_status",
        "query_status",
        "stats_flush",
        "list_query_item_stats",
        "build_item_rows",
    }.issubset(phase_names)


async def test_request_diagnostics_logs_exceptions(tmp_path: Path):
    log_path = tmp_path / "runtime" / "request_diagnostics.runtime.jsonl"
    app = create_app(
        db_path=tmp_path / "boom.db",
        request_diagnostics_log_path=log_path,
        request_diagnostics_slow_ms=60_000,
    )

    @app.get("/_boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_boom")

    assert response.status_code == 500
    assert log_path.exists()

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records
    assert records[-1]["event"] == "request_exception"
    assert records[-1]["method"] == "GET"
    assert records[-1]["path"] == "/_boom"
    assert records[-1]["error_type"] == "RuntimeError"
    assert records[-1]["error_message"] == "boom"


async def test_request_diagnostics_logs_inflight_timeouts_before_request_completes(tmp_path: Path):
    log_path = tmp_path / "runtime" / "request_diagnostics.runtime.jsonl"
    app = create_app(
        db_path=tmp_path / "stuck.db",
        request_diagnostics_log_path=log_path,
        request_diagnostics_slow_ms=20,
    )
    release_request = asyncio.Event()
    request_started = asyncio.Event()

    @app.get("/_stuck")
    async def stuck_request() -> dict[str, bool]:
        request_started.set()
        await release_request.wait()
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        pending = asyncio.create_task(client.get("/_stuck"))
        await asyncio.wait_for(request_started.wait(), timeout=1)
        deadline = asyncio.get_running_loop().time() + 1
        saw_timeout_record = False
        while asyncio.get_running_loop().time() < deadline:
            if log_path.exists():
                records = [
                    json.loads(line)
                    for line in log_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                saw_timeout_record = any(
                    record["event"] == "request_inflight_timeout"
                    and record["method"] == "GET"
                    and record["path"] == "/_stuck"
                    and record["status_code"] is None
                    for record in records
                )
                if saw_timeout_record:
                    break
            await asyncio.sleep(0.01)

        assert saw_timeout_record is True

        release_request.set()
        response = await pending

    assert response.status_code == 200
    assert response.json() == {"ok": True}
