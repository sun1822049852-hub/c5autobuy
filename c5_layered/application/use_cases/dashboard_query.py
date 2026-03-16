from __future__ import annotations

from c5_layered.application.dto import DashboardSummary
from c5_layered.application.ports import AccountRepository, ConfigRepository, ItemRepository
from c5_layered.domain.models import AccountProfile, ItemSnapshot, ProductConfig


class DashboardQueryUseCase:
    """Read-only dashboard query use case."""

    def __init__(
        self,
        account_repo: AccountRepository,
        config_repo: ConfigRepository,
        item_repo: ItemRepository,
    ) -> None:
        self._account_repo = account_repo
        self._config_repo = config_repo
        self._item_repo = item_repo

    def list_accounts(self) -> list[AccountProfile]:
        return self._account_repo.list_accounts()

    def list_configs(self) -> list[ProductConfig]:
        return self._config_repo.list_configs()

    def get_item_snapshot(self, item_id: str) -> ItemSnapshot | None:
        return self._item_repo.get_item_snapshot(item_id)

    def get_summary(self) -> DashboardSummary:
        accounts = self.list_accounts()
        configs = self.list_configs()
        total_products = sum(len(cfg.products) for cfg in configs)
        return DashboardSummary(
            total_accounts=len(accounts),
            logged_in_accounts=sum(1 for x in accounts if x.login),
            api_key_accounts=sum(1 for x in accounts if x.has_api_key),
            total_configs=len(configs),
            total_products=total_products,
        )

