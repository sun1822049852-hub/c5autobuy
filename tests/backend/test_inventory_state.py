from app_backend.infrastructure.purchase.runtime.inventory_state import InventoryState


def test_inventory_state_prefers_smaller_remaining_capacity_above_threshold():
    state = InventoryState(min_capacity_threshold=50)

    state.load_snapshot(
        [
            {"steamId": "s1", "inventory_num": 910, "inventory_max": 1000},
            {"steamId": "s2", "inventory_num": 850, "inventory_max": 1000},
            {"steamId": "s3", "inventory_num": 970, "inventory_max": 1000},
        ]
    )

    assert state.selected_steam_id == "s1"
    assert [item["steamId"] for item in state.available_inventories] == ["s1", "s2"]


def test_inventory_state_updates_local_capacity_after_purchase_without_refresh():
    state = InventoryState(min_capacity_threshold=50)
    state.load_snapshot(
        [
            {"steamId": "s1", "inventory_num": 910, "inventory_max": 1000},
            {"steamId": "s2", "inventory_num": 850, "inventory_max": 1000},
        ]
    )

    transition = state.apply_purchase_success(purchased_count=10)

    assert transition.requires_remote_refresh is False
    assert transition.became_unavailable is False
    assert state.selected_steam_id == "s1"
    assert state.selected_inventory["inventory_num"] == 920


def test_inventory_state_switches_selected_steam_id_when_target_changes():
    state = InventoryState(min_capacity_threshold=50)
    state.load_snapshot(
        [
            {"steamId": "s1", "inventory_num": 945, "inventory_max": 1000},
            {"steamId": "s2", "inventory_num": 910, "inventory_max": 1000},
        ]
    )

    transition = state.apply_purchase_success(purchased_count=10)

    assert transition.requires_remote_refresh is False
    assert transition.switched_inventory is True
    assert state.selected_steam_id == "s2"


def test_inventory_state_requests_remote_refresh_when_no_local_inventory_left():
    state = InventoryState(min_capacity_threshold=50)
    state.load_snapshot(
        [
            {"steamId": "s1", "inventory_num": 945, "inventory_max": 1000},
        ]
    )

    transition = state.apply_purchase_success(purchased_count=10)

    assert transition.requires_remote_refresh is True
    assert transition.became_unavailable is True
    assert state.selected_steam_id is None
