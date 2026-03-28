from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class InventoryTransition:
    requires_remote_refresh: bool
    became_unavailable: bool
    switched_inventory: bool


class InventoryState:
    def __init__(self, *, min_capacity_threshold: int = 50) -> None:
        self._min_capacity_threshold = int(min_capacity_threshold)
        self._inventories: list[dict[str, Any]] = []
        self.available_inventories: list[dict[str, Any]] = []
        self.selected_steam_id: str | None = None

    @property
    def selected_inventory(self) -> dict[str, Any] | None:
        if self.selected_steam_id is None:
            return None
        for inventory in self._inventories:
            if inventory.get("steamId") == self.selected_steam_id:
                return inventory
        return None

    @property
    def inventories(self) -> list[dict[str, Any]]:
        return [dict(inventory) for inventory in self._inventories]

    def load_snapshot(self, inventories: list[dict[str, Any]]) -> None:
        self._inventories = [dict(inventory) for inventory in inventories]
        self._refresh_available_inventories()
        self.selected_steam_id = self.available_inventories[0]["steamId"] if self.available_inventories else None

    def apply_purchase_success(self, *, purchased_count: int) -> InventoryTransition:
        selected_inventory = self.selected_inventory
        if selected_inventory is None:
            return InventoryTransition(
                requires_remote_refresh=True,
                became_unavailable=True,
                switched_inventory=False,
            )

        selected_inventory["inventory_num"] = int(selected_inventory.get("inventory_num", 0)) + int(purchased_count)
        previous_selected_steam_id = self.selected_steam_id
        self._refresh_available_inventories()

        if previous_selected_steam_id in {item["steamId"] for item in self.available_inventories}:
            self.selected_steam_id = previous_selected_steam_id
            return InventoryTransition(
                requires_remote_refresh=False,
                became_unavailable=False,
                switched_inventory=False,
            )

        if self.available_inventories:
            self.selected_steam_id = self.available_inventories[0]["steamId"]
            return InventoryTransition(
                requires_remote_refresh=False,
                became_unavailable=False,
                switched_inventory=True,
            )

        self.selected_steam_id = None
        return InventoryTransition(
            requires_remote_refresh=True,
            became_unavailable=True,
            switched_inventory=False,
        )

    def refresh_from_remote(self, inventories: list[dict[str, Any]]) -> InventoryTransition:
        previous_selected_steam_id = self.selected_steam_id
        self.load_snapshot(inventories)
        return InventoryTransition(
            requires_remote_refresh=False,
            became_unavailable=self.selected_steam_id is None,
            switched_inventory=previous_selected_steam_id != self.selected_steam_id,
        )

    def _refresh_available_inventories(self) -> None:
        self.available_inventories = []
        for inventory in self._inventories:
            current_num = int(inventory.get("inventory_num", 0))
            max_num = int(inventory.get("inventory_max", 1000))
            remaining = max_num - current_num
            inventory["remaining_capacity"] = remaining
            if remaining >= self._min_capacity_threshold:
                self.available_inventories.append(inventory)
        self.available_inventories.sort(key=lambda item: (item.get("remaining_capacity", 0), item.get("steamId", "")))
