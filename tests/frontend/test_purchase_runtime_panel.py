from __future__ import annotations


def build_snapshot(*, running: bool = False) -> dict:
    return {
        "running": running,
        "message": "运行中" if running else "未运行",
        "started_at": "2026-03-16T12:00:00" if running else None,
        "stopped_at": None if running else "2026-03-16T12:30:00",
        "queue_size": 1 if running else 0,
        "active_account_count": 1 if running else 0,
        "total_account_count": 2,
        "total_purchased_count": 3,
        "recent_events": [
            {
                "occurred_at": "2026-03-16T12:10:00",
                "status": "queued",
                "message": "已转入购买",
                "account_id": "a1",
                "account_display_name": "主号",
                "query_item_name": "AK",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "source_mode_type": "new_api",
            },
            {
                "occurred_at": "2026-03-16T12:12:00",
                "status": "inventory_recovered",
                "message": "库存恢复，账号已重新入池",
                "account_id": "a2",
                "account_display_name": "备号",
                "query_item_name": "",
                "product_list": [],
                "total_price": 0.0,
                "total_wear_sum": None,
                "source_mode_type": "",
            },
        ],
        "accounts": [
            {
                "account_id": "a1",
                "display_name": "主号",
                "purchase_capability_state": "bound",
                "purchase_pool_state": "active",
                "selected_steam_id": "steam-1",
                "selected_inventory_remaining_capacity": 90,
                "selected_inventory_max": 1000,
                "last_error": None,
                "total_purchased_count": 2,
            },
            {
                "account_id": "a2",
                "display_name": "备号",
                "purchase_capability_state": "bound",
                "purchase_pool_state": "paused_no_inventory",
                "selected_steam_id": "",
                "selected_inventory_remaining_capacity": None,
                "selected_inventory_max": None,
                "last_error": "等待恢复检查",
                "total_purchased_count": 0,
            },
        ],
        "settings": {
            "whitelist_account_ids": ["a1", "a2"],
            "updated_at": "2026-03-16T12:05:00",
        },
    }


def test_purchase_runtime_panel_renders_summary_accounts_and_events(qtbot):
    from app_frontend.app.widgets.purchase_runtime_panel import PurchaseRuntimePanel

    panel = PurchaseRuntimePanel()
    qtbot.addWidget(panel)

    panel.load_status(build_snapshot(running=True))

    assert panel.summary_label.text() == "运行中"
    assert panel.queue_size_input.text() == "1"
    assert panel.active_account_count_input.text() == "1"
    assert panel.total_account_count_input.text() == "2"
    assert panel.recovery_waiting_count_input.text() == "1"
    assert panel.whitelist_input.text() == "a1, a2"
    assert panel.account_table.columnCount() == 7
    assert panel.account_table.item(0, 0).text() == "主号"
    assert panel.account_table.item(0, 3).text() == "steam-1"
    assert panel.account_table.item(0, 4).text() == "90/1000"
    assert panel.account_table.item(1, 3).text() == "-"
    assert panel.account_table.item(1, 4).text() == "-"
    assert panel.account_table.item(1, 5).text() == "等待恢复检查"
    assert panel.event_table.item(0, 1).text() == "queued"
    assert panel.event_table.item(1, 2).text() == "备号"
    assert panel.event_table.item(1, 3).text() == "库存恢复"
