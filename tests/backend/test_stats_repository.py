from __future__ import annotations

from types import SimpleNamespace

from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
from app_backend.infrastructure.repositories.stats_repository import SqliteStatsRepository


def _find_row(rows: list[dict[str, object]], **expected) -> dict[str, object]:
    for row in rows:
        if all(row.get(key) == value for key, value in expected.items()):
            return row
    raise AssertionError(f"Missing row for {expected!r}: {rows!r}")


def _to_source_counts(row: dict[str, object]) -> dict[str, int]:
    return {
        str(source.get("mode_type")): int(source.get("hit_count", 0))
        for source in row.get("source_mode_stats", [])
    }


def test_stats_repository_accumulates_query_item_total_daily_and_range_views(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteStatsRepository(build_session_factory(engine))

    repository.apply_query_execution_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:00",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="new_api",
            account_id="a1",
            account_display_name="账号-A",
            latency_ms=120.0,
            success=True,
            error=None,
        )
    )
    repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:01",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="new_api",
            account_id="a1",
            account_display_name="账号-A",
            matched_count=2,
        )
    )
    repository.apply_purchase_submit_order_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:02",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
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
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="fast_api",
            account_id="a1",
            account_display_name="账号-A",
            latency_ms=80.0,
            success=True,
            error=None,
        )
    )
    repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp="2026-03-22T18:00:01",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="fast_api",
            account_id="a1",
            account_display_name="账号-A",
            matched_count=1,
        )
    )

    total_row = _find_row(repository.list_query_item_stats(range_mode="total"), external_item_id="ext-1")
    day_row = _find_row(
        repository.list_query_item_stats(range_mode="day", date="2026-03-21"),
        external_item_id="ext-1",
    )
    range_row = _find_row(
        repository.list_query_item_stats(
            range_mode="range",
            start_date="2026-03-21",
            end_date="2026-03-22",
        ),
        external_item_id="ext-1",
    )

    assert total_row["query_execution_count"] == 2
    assert total_row["matched_product_count"] == 3
    assert total_row["purchase_success_count"] == 1
    assert total_row["purchase_failed_count"] == 1
    assert _to_source_counts(total_row) == {"new_api": 2, "fast_api": 1}

    assert day_row["query_execution_count"] == 1
    assert day_row["matched_product_count"] == 2
    assert day_row["purchase_success_count"] == 1
    assert day_row["purchase_failed_count"] == 1
    assert _to_source_counts(day_row) == {"new_api": 2}

    assert range_row["query_execution_count"] == 2
    assert range_row["matched_product_count"] == 3
    assert range_row["purchase_success_count"] == 1
    assert range_row["purchase_failed_count"] == 1
    assert _to_source_counts(range_row) == {"new_api": 2, "fast_api": 1}


def test_stats_repository_deduplicates_query_hits_by_runtime_session_query_item_and_product_id(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteStatsRepository(build_session_factory(engine))

    repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:01",
            runtime_session_id="run-1",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="new_api",
            account_id="a1",
            account_display_name="账号-A",
            matched_count=2,
            product_ids=["p-1", "p-2"],
        )
    )
    repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:02",
            runtime_session_id="run-1",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="fast_api",
            account_id="a2",
            account_display_name="账号-B",
            matched_count=1,
            product_ids=["p-1"],
        )
    )
    repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:03",
            runtime_session_id="run-1",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="fast_api",
            account_id="a2",
            account_display_name="账号-B",
            matched_count=1,
            product_ids=["p-3"],
        )
    )
    repository.apply_query_hit_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:04",
            runtime_session_id="run-2",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="fast_api",
            account_id="a2",
            account_display_name="账号-B",
            matched_count=1,
            product_ids=["p-1"],
        )
    )

    total_row = _find_row(repository.list_query_item_stats(range_mode="total"), external_item_id="ext-1")
    day_row = _find_row(
        repository.list_query_item_stats(range_mode="day", date="2026-03-21"),
        external_item_id="ext-1",
    )

    assert total_row["matched_product_count"] == 4
    assert _to_source_counts(total_row) == {"new_api": 2, "fast_api": 2}
    assert day_row["matched_product_count"] == 4
    assert _to_source_counts(day_row) == {"new_api": 2, "fast_api": 2}


def test_stats_repository_accumulates_account_capability_by_mode_phase_and_range(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteStatsRepository(build_session_factory(engine))

    repository.apply_query_execution_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:00",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="new_api",
            account_id="a1",
            account_display_name="账号-A",
            latency_ms=120.0,
            success=True,
            error=None,
        )
    )
    repository.apply_query_execution_event(
        SimpleNamespace(
            timestamp="2026-03-22T18:00:00",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="fast_api",
            account_id="a1",
            account_display_name="账号-A",
            latency_ms=80.0,
            success=False,
            error="timeout",
        )
    )
    repository.apply_purchase_create_order_event(
        SimpleNamespace(
            timestamp="2026-03-21T18:00:01",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
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
            timestamp="2026-03-21T18:00:02",
            external_item_id="ext-1",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
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

    total_rows = repository.list_account_capability_stats(range_mode="total")
    day_rows = repository.list_account_capability_stats(range_mode="day", date="2026-03-21")
    range_rows = repository.list_account_capability_stats(
        range_mode="range",
        start_date="2026-03-21",
        end_date="2026-03-22",
    )

    total_query_new_api = _find_row(total_rows, account_id="a1", mode_type="new_api", phase="query")
    total_query_fast_api = _find_row(total_rows, account_id="a1", mode_type="fast_api", phase="query")
    total_create_order = _find_row(total_rows, account_id="a1", mode_type="purchase", phase="create_order")
    total_submit_order = _find_row(total_rows, account_id="a1", mode_type="purchase", phase="submit_order")
    day_query = _find_row(day_rows, account_id="a1", mode_type="new_api", phase="query")
    range_submit = _find_row(range_rows, account_id="a1", mode_type="purchase", phase="submit_order")

    assert total_query_new_api["sample_count"] == 1
    assert total_query_new_api["success_count"] == 1
    assert total_query_new_api["failure_count"] == 0
    assert total_query_new_api["total_latency_ms"] == 120.0
    assert total_query_new_api["last_latency_ms"] == 120.0

    assert total_query_fast_api["sample_count"] == 1
    assert total_query_fast_api["success_count"] == 0
    assert total_query_fast_api["failure_count"] == 1
    assert total_query_fast_api["last_error"] == "timeout"

    assert total_create_order["sample_count"] == 1
    assert total_create_order["total_latency_ms"] == 210.0
    assert total_submit_order["sample_count"] == 1
    assert total_submit_order["success_count"] == 1
    assert total_submit_order["failure_count"] == 0
    assert total_submit_order["total_latency_ms"] == 450.0

    assert day_query["sample_count"] == 1
    assert day_query["total_latency_ms"] == 120.0
    assert range_submit["sample_count"] == 1
    assert range_submit["total_latency_ms"] == 450.0
