from __future__ import annotations

from typing import Protocol

from c5_layered.domain.models import AccountProfile, ItemSnapshot, ProductConfig


class AccountRepository(Protocol):
    def list_accounts(self) -> list[AccountProfile]:
        ...


class ConfigRepository(Protocol):
    def list_configs(self) -> list[ProductConfig]:
        ...

    def get_by_name(self, name: str) -> ProductConfig | None:
        ...

    def save_all(self, configs: list[ProductConfig]) -> None:
        ...


class ItemRepository(Protocol):
    def get_item_snapshot(self, item_id: str) -> ItemSnapshot | None:
        ...

