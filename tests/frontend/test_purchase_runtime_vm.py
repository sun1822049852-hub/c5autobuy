from __future__ import annotations


def build_snapshot(*, running: bool = False, active_account_count: int = 0) -> dict:
    return {
        "running": running,
        "message": "运行中" if running else "未运行",
        "started_at": "2026-03-16T12:00:00" if running else None,
        "stopped_at": None if running else "2026-03-16T12:30:00",
        "queue_size": 1 if running else 0,
        "active_account_count": active_account_count,
        "total_account_count": 3,
        "total_purchased_count": 5,
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
    }


def test_purchase_runtime_vm_formats_summary_and_account_rows():
    from app_frontend.app.viewmodels.purchase_runtime_vm import PurchaseRuntimeViewModel

    vm = PurchaseRuntimeViewModel()
    vm.load_status(build_snapshot(running=True, active_account_count=2))

    assert vm.summary["running"] == "是"
    assert vm.summary["active_account_count"] == "2"
    assert vm.summary["total_account_count"] == "3"
    assert vm.summary["queue_size"] == "1"
    assert vm.summary["recovery_waiting_count"] == "1"
    assert vm.summary["message"] == "运行中"
    assert vm.account_rows == [
        {
            "account_id": "a1",
            "display_name": "主号",
            "purchase_capability_state": "bound",
            "purchase_pool_state": "active",
            "recovery_status": "可参与购买",
            "selected_steam_id": "steam-1",
            "capacity_text": "90/1000",
            "last_error": "",
            "total_purchased_count": "2",
        },
        {
            "account_id": "a2",
            "display_name": "备号",
            "purchase_capability_state": "bound",
            "purchase_pool_state": "paused_no_inventory",
            "recovery_status": "等待恢复检查",
            "selected_steam_id": "",
            "capacity_text": "-",
            "last_error": "等待恢复检查",
            "total_purchased_count": "0",
        },
    ]
    assert vm.recent_event_rows[0]["status"] == "queued"
    assert vm.recent_event_rows[0]["account_display_name"] == "主号"
    assert vm.recent_event_rows[1]["status"] == "inventory_recovered"
    assert vm.recent_event_rows[1]["account_display_name"] == "备号"
