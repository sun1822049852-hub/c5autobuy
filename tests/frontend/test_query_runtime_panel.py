from __future__ import annotations


def test_query_runtime_panel_renders_idle_state(qtbot):
    from app_frontend.app.widgets.query_runtime_panel import QueryRuntimePanel

    panel = QueryRuntimePanel()
    qtbot.addWidget(panel)

    panel.load_status(
        {
            "running": False,
            "config_id": None,
            "config_name": None,
            "message": "未运行",
            "account_count": 0,
            "modes": {},
        }
    )

    assert panel.summary_label.text() == "未运行"
    assert panel.config_name_input.text() == ""
    assert panel.account_count_input.text() == "0"
    assert panel.mode_table.rowCount() == 0
    assert panel.group_table.rowCount() == 0
    assert panel.event_table.rowCount() == 0
    assert panel.event_detail_status_label.text() == "选择一条命中事件查看详情"
    assert panel.event_detail_product_table.rowCount() == 0


def test_query_runtime_panel_renders_mode_account_counts(qtbot):
    from app_frontend.app.widgets.query_runtime_panel import QueryRuntimePanel

    panel = QueryRuntimePanel()
    qtbot.addWidget(panel)

    panel.load_status(
        {
            "running": True,
            "config_id": "cfg-1",
            "config_name": "白天配置",
            "message": "运行中",
            "account_count": 3,
            "total_query_count": 12,
            "total_found_count": 4,
            "recent_events": [
                {
                    "timestamp": "2026-03-16T10:00:02",
                    "level": "error",
                    "mode_type": "fast_api",
                    "account_id": "a2",
                    "account_display_name": "夜间副号",
                    "query_item_id": "item-2",
                    "query_item_name": "商品-2",
                    "message": "HTTP 429 Too Many Requests",
                    "match_count": 0,
                    "latency_ms": 22.3,
                    "error": "HTTP 429 Too Many Requests",
                },
                {
                    "timestamp": "2026-03-16T10:00:01",
                    "level": "info",
                    "mode_type": "new_api",
                    "account_id": "a1",
                    "account_display_name": "白天主号",
                    "query_item_id": "item-1",
                    "query_item_name": "商品-1",
                    "message": "查询完成",
                    "match_count": 2,
                    "product_list": [
                        {"productId": "p-1", "price": 88.5, "actRebateAmount": 0},
                        {"productId": "p-2", "price": 89.5, "actRebateAmount": 0},
                    ],
                    "total_price": 178.0,
                    "total_wear_sum": 0.1234,
                    "latency_ms": 11.2,
                    "error": None,
                },
            ],
            "group_rows": [
                {
                    "account_id": "a1",
                    "account_display_name": "白天主号",
                    "mode_type": "new_api",
                    "active": True,
                    "in_window": True,
                    "cooldown_until": None,
                    "last_query_at": "2026-03-16T10:00:01",
                    "last_success_at": "2026-03-16T10:00:01",
                    "query_count": 7,
                    "found_count": 2,
                    "disabled_reason": None,
                    "last_error": None,
                    "rate_limit_increment": 0.0,
                },
                {
                    "account_id": "a2",
                    "account_display_name": "夜间副号",
                    "mode_type": "fast_api",
                    "active": False,
                    "in_window": True,
                    "cooldown_until": "2026-03-16T10:05:00",
                    "last_query_at": "2026-03-16T10:00:02",
                    "last_success_at": None,
                    "query_count": 5,
                    "found_count": 0,
                    "disabled_reason": None,
                    "last_error": "HTTP 429 Too Many Requests",
                    "rate_limit_increment": 0.05,
                },
                {
                    "account_id": "a3",
                    "account_display_name": "待机号",
                    "mode_type": "token",
                    "active": True,
                    "in_window": False,
                    "cooldown_until": None,
                    "last_query_at": None,
                    "last_success_at": None,
                    "query_count": 0,
                    "found_count": 0,
                    "disabled_reason": None,
                    "last_error": None,
                    "rate_limit_increment": 0.0,
                },
            ],
            "modes": {
                "new_api": {
                    "mode_type": "new_api",
                    "enabled": True,
                    "eligible_account_count": 1,
                    "active_account_count": 1,
                    "in_window": True,
                    "query_count": 7,
                    "found_count": 2,
                    "next_window_start": None,
                    "next_window_end": None,
                    "last_error": None,
                },
                "fast_api": {
                    "mode_type": "fast_api",
                    "enabled": True,
                    "eligible_account_count": 2,
                    "active_account_count": 0,
                    "in_window": False,
                    "query_count": 5,
                    "found_count": 2,
                    "next_window_start": "2026-03-16T20:00:00",
                    "next_window_end": "2026-03-16T23:00:00",
                    "last_error": "HTTP 429 Too Many Requests",
                },
                "token": {
                    "mode_type": "token",
                    "enabled": False,
                    "eligible_account_count": 0,
                    "active_account_count": 0,
                    "in_window": False,
                    "query_count": 0,
                    "found_count": 0,
                    "next_window_start": None,
                    "next_window_end": None,
                    "last_error": None,
                },
            },
        }
    )

    assert panel.summary_label.text() == "运行中: 白天配置 (账号 3, 查询 12, 命中 4)"
    assert panel.config_name_input.text() == "白天配置"
    assert panel.account_count_input.text() == "3"
    assert panel.mode_table.rowCount() == 3
    assert panel.mode_table.columnCount() == 6
    assert panel.group_table.rowCount() == 3
    assert panel.group_table.columnCount() == 8
    assert panel.group_table.item(0, 0).text() == "白天主号"
    assert panel.group_table.item(0, 1).text() == "new_api"
    assert panel.group_table.item(0, 2).text() == "运行中"
    assert panel.group_table.item(0, 3).text() == "窗口内"
    assert panel.group_table.item(0, 4).text() == "-"
    assert panel.group_table.item(0, 5).text() == "7/2"
    assert panel.group_table.item(1, 2).text() == "限流退避"
    assert panel.group_table.item(1, 4).text() == "10:05:00"
    assert panel.group_table.item(2, 2).text() == "窗口外等待"
    assert panel.mode_table.item(0, 0).text() == "new_api"
    assert panel.mode_table.item(0, 1).text() == "启用 / 窗口内"
    assert panel.mode_table.item(0, 2).text() == "1/1"
    assert panel.mode_table.item(0, 3).text() == "7/2"
    assert panel.mode_table.item(0, 4).text() == "始终运行"
    assert panel.mode_table.item(0, 5).text() == "-"
    assert panel.mode_table.item(1, 1).text() == "启用 / 窗口外"
    assert panel.mode_table.item(1, 2).text() == "0/2"
    assert panel.mode_table.item(1, 3).text() == "5/2"
    assert panel.mode_table.item(1, 4).text() == "20:00 - 23:00"
    assert panel.mode_table.item(1, 5).text() == "HTTP 429 Too Many Requests"
    assert panel.mode_table.item(2, 0).text() == "token"
    assert panel.mode_table.item(2, 1).text() == "关闭"
    assert panel.event_table.rowCount() == 2
    assert panel.event_table.item(0, 0).text() == "10:00:02"
    assert panel.event_table.item(0, 1).text() == "fast_api"
    assert panel.event_table.item(0, 2).text() == "夜间副号"
    assert panel.event_table.item(0, 4).text() == "错误"
    assert panel.event_table.item(0, 5).text() == "HTTP 429 Too Many Requests"
    assert panel.event_table.item(1, 3).text() == "商品-1"
    assert panel.event_table.item(1, 4).text() == "命中 2"
    assert panel.event_detail_status_label.text() == "白天主号 / new_api / 商品-1"
    assert panel.event_detail_match_count_input.text() == "2"
    assert panel.event_detail_total_price_input.text() == "178.00"
    assert panel.event_detail_total_wear_input.text() == "0.123400"
    assert panel.event_detail_product_table.rowCount() == 2
    assert panel.event_detail_product_table.item(0, 0).text() == "p-1"
    assert panel.event_detail_product_table.item(0, 1).text() == "88.50"
    assert panel.event_detail_product_table.item(1, 0).text() == "p-2"


def test_query_runtime_panel_clears_detail_for_error_event(qtbot):
    from app_frontend.app.widgets.query_runtime_panel import QueryRuntimePanel

    panel = QueryRuntimePanel()
    qtbot.addWidget(panel)

    panel.load_status(
        {
            "running": True,
            "config_id": "cfg-1",
            "config_name": "白天配置",
            "message": "运行中",
            "account_count": 1,
            "total_query_count": 2,
            "total_found_count": 1,
            "recent_events": [
                {
                    "timestamp": "2026-03-16T10:00:02",
                    "level": "error",
                    "mode_type": "fast_api",
                    "account_id": "a2",
                    "account_display_name": "夜间副号",
                    "query_item_id": "item-2",
                    "query_item_name": "商品-2",
                    "message": "HTTP 429 Too Many Requests",
                    "match_count": 0,
                    "product_list": [],
                    "total_price": None,
                    "total_wear_sum": None,
                    "latency_ms": 22.3,
                    "error": "HTTP 429 Too Many Requests",
                },
                {
                    "timestamp": "2026-03-16T10:00:01",
                    "level": "info",
                    "mode_type": "new_api",
                    "account_id": "a1",
                    "account_display_name": "白天主号",
                    "query_item_id": "item-1",
                    "query_item_name": "商品-1",
                    "message": "查询完成",
                    "match_count": 1,
                    "product_list": [
                        {"productId": "p-1", "price": 88.5, "actRebateAmount": 0},
                    ],
                    "total_price": 88.5,
                    "total_wear_sum": 0.1,
                    "latency_ms": 11.2,
                    "error": None,
                },
            ],
            "modes": {},
        }
    )

    panel.event_table.selectRow(0)
    qtbot.wait(20)

    assert panel.event_detail_status_label.text() == "当前事件没有命中商品明细"
    assert panel.event_detail_match_count_input.text() == ""
    assert panel.event_detail_total_price_input.text() == ""
    assert panel.event_detail_total_wear_input.text() == ""
    assert panel.event_detail_product_table.rowCount() == 0
