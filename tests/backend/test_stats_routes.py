from __future__ import annotations

from types import SimpleNamespace


def _find_row(rows: list[dict[str, object]], *, key: str, value: str) -> dict[str, object]:
    for row in rows:
        if row.get(key) == value:
            return row
    raise AssertionError(f"Missing row where {key}={value!r}: {rows!r}")


def _seed_stats(app) -> None:
    repository = app.state.stats_repository
    repository.apply_query_execution_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:00",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            rule_fingerprint="0.12|0.3|123.45",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="new_api",
            account_id="a1",
            account_display_name="账号-A",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            latency_ms=120.0,
            success=True,
            error=None,
        )
    )
    repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:01",
            runtime_session_id="run-1",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            rule_fingerprint="0.12|0.3|123.45",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="new_api",
            account_id="a1",
            account_display_name="账号-A",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            matched_count=2,
        )
    )
    repository.apply_purchase_create_order_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:02",
            runtime_session_id="run-1",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            rule_fingerprint="0.12|0.3|123.45",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            account_id="a1",
            account_display_name="账号-A",
            create_order_latency_ms=210.0,
            submitted_count=2,
            status="success",
            error=None,
        )
    )
    repository.apply_purchase_submit_order_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:03",
            runtime_session_id="run-1",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            rule_fingerprint="0.12|0.3|123.45",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            account_id="a1",
            account_display_name="账号-A",
            submit_order_latency_ms=450.0,
            submitted_count=2,
            success_count=1,
            failed_count=1,
            status="success",
            error=None,
        )
    )
    repository.apply_query_execution_event(
        SimpleNamespace(
            timestamp="2026-03-22T18:00:00",
            query_config_id="cfg-2",
            query_item_id="item-1",
            external_item_id="ext-1",
            rule_fingerprint="0.12|0.3|123.45",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="fast_api",
            account_id="a1",
            account_display_name="账号-A",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            latency_ms=80.0,
            success=False,
            error="timeout",
        )
    )
    repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp="2026-03-22T18:00:01",
            runtime_session_id="run-2",
            query_config_id="cfg-2",
            query_item_id="item-1",
            external_item_id="ext-1",
            rule_fingerprint="0.12|0.3|123.45",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="fast_api",
            account_id="a1",
            account_display_name="账号-A",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            matched_count=1,
        )
    )


async def test_stats_query_items_route_supports_total_day_and_range_modes(client, app):
    _seed_stats(app)

    total_response = await client.get("/stats/query-items", params={"range_mode": "total"})
    day_response = await client.get(
        "/stats/query-items",
        params={"range_mode": "day", "date": "2026-03-21"},
    )
    range_response = await client.get(
        "/stats/query-items",
        params={
            "range_mode": "range",
            "start_date": "2026-03-21",
            "end_date": "2026-03-22",
        },
    )

    assert total_response.status_code == 200
    assert day_response.status_code == 200
    assert range_response.status_code == 200

    total_item = _find_row(total_response.json()["items"], key="external_item_id", value="ext-1")
    day_item = _find_row(day_response.json()["items"], key="external_item_id", value="ext-1")
    range_item = _find_row(range_response.json()["items"], key="external_item_id", value="ext-1")

    assert total_item["query_execution_count"] == 2
    assert total_item["matched_product_count"] == 3
    assert total_item["purchase_success_count"] == 1
    assert total_item["purchase_failed_count"] == 1
    assert total_item["source_mode_stats"] == [
        {"mode_type": "new_api", "hit_count": 2},
        {"mode_type": "fast_api", "hit_count": 1},
    ]

    assert day_item["query_execution_count"] == 1
    assert day_item["matched_product_count"] == 2
    assert day_item["purchase_success_count"] == 1
    assert day_item["purchase_failed_count"] == 1

    assert range_item["query_execution_count"] == 2
    assert range_item["matched_product_count"] == 3
    assert range_item["purchase_success_count"] == 1
    assert range_item["purchase_failed_count"] == 1


async def test_stats_account_capability_route_supports_total_day_and_range_modes(client, app):
    _seed_stats(app)

    total_response = await client.get("/stats/account-capability", params={"range_mode": "total"})
    day_response = await client.get(
        "/stats/account-capability",
        params={"range_mode": "day", "date": "2026-03-21"},
    )
    range_response = await client.get(
        "/stats/account-capability",
        params={
            "range_mode": "range",
            "start_date": "2026-03-21",
            "end_date": "2026-03-22",
        },
    )

    assert total_response.status_code == 200
    assert day_response.status_code == 200
    assert range_response.status_code == 200

    total_row = _find_row(total_response.json()["items"], key="account_id", value="a1")
    day_row = _find_row(day_response.json()["items"], key="account_id", value="a1")
    range_row = _find_row(range_response.json()["items"], key="account_id", value="a1")

    assert total_row["account_display_name"] == "账号-A"
    assert total_row["new_api"]["avg_latency_ms"] == 120.0
    assert total_row["new_api"]["sample_count"] == 1
    assert total_row["fast_api"]["avg_latency_ms"] == 80.0
    assert total_row["fast_api"]["sample_count"] == 1
    assert total_row["browser"]["avg_latency_ms"] is None
    assert total_row["browser"]["sample_count"] == 0
    assert total_row["create_order"]["avg_latency_ms"] == 210.0
    assert total_row["create_order"]["sample_count"] == 1
    assert total_row["submit_order"]["avg_latency_ms"] == 450.0
    assert total_row["submit_order"]["sample_count"] == 1

    assert day_row["new_api"]["avg_latency_ms"] == 120.0
    assert day_row["fast_api"]["sample_count"] == 0
    assert day_row["submit_order"]["avg_latency_ms"] == 450.0

    assert range_row["new_api"]["avg_latency_ms"] == 120.0
    assert range_row["fast_api"]["avg_latency_ms"] == 80.0
    assert range_row["create_order"]["sample_count"] == 1
    assert range_row["submit_order"]["sample_count"] == 1


async def test_stats_routes_validate_range_params(client):
    query_response = await client.get("/stats/query-items", params={"range_mode": "day"})
    account_response = await client.get(
        "/stats/account-capability",
        params={"range_mode": "range", "start_date": "2026-03-21"},
    )

    assert query_response.status_code == 400
    assert query_response.json()["detail"] == "range_mode=day requires date"
    assert account_response.status_code == 400
    assert account_response.json()["detail"] == "range_mode=range requires start_date and end_date"
