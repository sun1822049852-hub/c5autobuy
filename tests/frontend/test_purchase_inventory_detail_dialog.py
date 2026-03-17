from __future__ import annotations


def build_detail(*, inventories=None) -> dict:
    return {
        "account_id": "a1",
        "display_name": "主号",
        "selected_steam_id": "steam-1",
        "refreshed_at": "2026-03-16T12:15:00",
        "last_error": None,
        "inventories": inventories
        if inventories is not None
        else [
            {
                "steamId": "steam-1",
                "inventory_num": 910,
                "inventory_max": 1000,
                "remaining_capacity": 90,
                "is_selected": True,
                "is_available": True,
            },
            {
                "steamId": "steam-2",
                "inventory_num": 990,
                "inventory_max": 1000,
                "remaining_capacity": 10,
                "is_selected": False,
                "is_available": False,
            },
        ],
    }


def test_purchase_inventory_detail_dialog_renders_detail(qtbot):
    from app_frontend.app.dialogs.purchase_inventory_detail_dialog import PurchaseInventoryDetailDialog

    dialog = PurchaseInventoryDetailDialog()
    qtbot.addWidget(dialog)

    dialog.load_detail(build_detail())

    assert dialog.account_name_input.text() == "主号"
    assert dialog.selected_steam_id_input.text() == "steam-1"
    assert dialog.refreshed_at_input.text() == "2026-03-16T12:15:00"
    assert dialog.inventory_table.rowCount() == 2
    assert dialog.inventory_table.item(0, 0).text() == "steam-1"
    assert dialog.inventory_table.item(0, 4).text() == "是"
    assert dialog.inventory_table.item(1, 5).text() == "否"


def test_purchase_inventory_detail_dialog_shows_empty_state(qtbot):
    from app_frontend.app.dialogs.purchase_inventory_detail_dialog import PurchaseInventoryDetailDialog

    dialog = PurchaseInventoryDetailDialog()
    qtbot.addWidget(dialog)

    dialog.load_detail(build_detail(inventories=[]))

    assert dialog.inventory_table.rowCount() == 0
    assert dialog.empty_state_label.text() == "暂无库存快照"


def test_purchase_inventory_detail_dialog_shows_error_state(qtbot):
    from app_frontend.app.dialogs.purchase_inventory_detail_dialog import PurchaseInventoryDetailDialog

    dialog = PurchaseInventoryDetailDialog()
    qtbot.addWidget(dialog)

    dialog.show_error("请求失败")

    assert dialog.error_label.text() == "加载失败: 请求失败"
    assert dialog.inventory_table.rowCount() == 0
