from __future__ import annotations

from app_backend.infrastructure.stats.runtime.stats_events import (
    PurchaseSubmitOrderStatsEvent,
    QueryExecutionStatsEvent,
)
from app_backend.infrastructure.stats.runtime.stats_pipeline import StatsPipeline


class FakeStatsRepository:
    def __init__(self) -> None:
        self.query_execution_events: list[object] = []
        self.purchase_submit_events: list[object] = []

    def apply_query_execution_event(self, event: object) -> None:
        self.query_execution_events.append(event)

    def apply_purchase_submit_order_event(self, event: object) -> None:
        self.purchase_submit_events.append(event)


def test_stats_pipeline_drops_events_when_queue_is_full():
    repository = FakeStatsRepository()
    pipeline = StatsPipeline(
        repository=repository,
        max_queue_size=1,
        flush_batch_size=10,
        flush_interval_seconds=60,
    )

    first_accepted = pipeline.enqueue(
        QueryExecutionStatsEvent(
            timestamp="2026-03-22T10:00:00",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            rule_fingerprint="fp-1",
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
    second_accepted = pipeline.enqueue(
        QueryExecutionStatsEvent(
            timestamp="2026-03-22T10:00:01",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            rule_fingerprint="fp-1",
            detail_min_wear=0.12,
            detail_max_wear=0.3,
            max_price=123.45,
            mode_type="fast_api",
            account_id="a1",
            account_display_name="账号-A",
            item_name="AK-47 | Redline",
            product_url="https://example.com/items/ext-1",
            latency_ms=80.0,
            success=True,
            error=None,
        )
    )

    assert first_accepted is True
    assert second_accepted is False
    assert pipeline.dropped_event_count == 1


def test_stats_pipeline_flushes_queued_events_to_repository():
    repository = FakeStatsRepository()
    pipeline = StatsPipeline(
        repository=repository,
        max_queue_size=4,
        flush_batch_size=10,
        flush_interval_seconds=60,
    )
    query_event = QueryExecutionStatsEvent(
        timestamp="2026-03-22T10:00:00",
        query_config_id="cfg-1",
        query_item_id="item-1",
        external_item_id="ext-1",
        rule_fingerprint="fp-1",
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
    submit_event = PurchaseSubmitOrderStatsEvent(
        timestamp="2026-03-22T10:00:01",
        runtime_session_id="run-1",
        query_config_id="cfg-1",
        query_item_id="item-1",
        external_item_id="ext-1",
        rule_fingerprint="fp-1",
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

    pipeline.enqueue(query_event)
    pipeline.enqueue(submit_event)

    flushed_count = pipeline.flush_pending()

    assert flushed_count == 2
    assert repository.query_execution_events == [query_event]
    assert repository.purchase_submit_events == [submit_event]


def test_stats_pipeline_stop_allows_pending_events_without_raising():
    repository = FakeStatsRepository()
    pipeline = StatsPipeline(
        repository=repository,
        max_queue_size=2,
        flush_batch_size=10,
        flush_interval_seconds=60,
    )
    pipeline.enqueue(
        QueryExecutionStatsEvent(
            timestamp="2026-03-22T10:00:00",
            query_config_id="cfg-1",
            query_item_id="item-1",
            external_item_id="ext-1",
            rule_fingerprint="fp-1",
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

    pipeline.stop()

    assert pipeline.dropped_event_count == 0
