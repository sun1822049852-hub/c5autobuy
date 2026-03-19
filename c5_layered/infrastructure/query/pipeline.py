from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable

from c5_layered.infrastructure.query.coordinator_adapter import (
    LegacyQueryCoordinatorAdapter,
)
from c5_layered.infrastructure.query.legacy_bridge import LegacyQueryBridge


@dataclass(slots=True)
class QueryMetrics:
    query_count: int
    found_count: int
    purchased_count: int


@dataclass(slots=True)
class AccountAttachResult:
    can_query: bool
    purchase_registered: bool


class LegacyQueryPipeline:
    """
    Query lifecycle orchestration with legacy adapters.
    """

    def __init__(
        self,
        legacy_module: ModuleType,
        *,
        query_only: bool,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self._query_only = query_only
        self._logger = logger
        self._bridge = LegacyQueryBridge(legacy_module)
        self._coordinator: LegacyQueryCoordinatorAdapter | None = None
        self._scheduler_started = False

    def initialize(self, product_ids: list[str]) -> None:
        self._bridge.setup_scheduler(product_ids, min_cooldown=0.1)
        self._coordinator = self._bridge.build_coordinator(query_only=self._query_only)
        if self._query_only:
            self._log("仅查询模式已启用：查询结果不会进入购买队列。")

    async def attach_account(
        self,
        account_manager: Any,
        product_items: list[Any],
        config_name: str,
        *,
        allow_purchase: bool,
    ) -> AccountAttachResult:
        coordinator = self._require_coordinator()

        has_api_key = bool(account_manager.has_api_key())
        is_logged_in = bool(getattr(account_manager, "login_status", False))

        can_query = False
        if has_api_key or is_logged_in:
            can_query = await coordinator.attach_products(
                account_manager,
                product_items,
                config_name,
            )

        if not can_query:
            return AccountAttachResult(can_query=False, purchase_registered=False)

        purchase_registered = False
        if allow_purchase:
            purchase_registered = coordinator.register_purchase_account(account_manager)

        return AccountAttachResult(
            can_query=True,
            purchase_registered=purchase_registered,
        )

    async def start(self) -> tuple[bool, str]:
        coordinator = self._require_coordinator()
        start_ok = await coordinator.start(query_only=self._query_only)
        if not start_ok:
            return False, "failed to start multi-account coordinator"

        await self._bridge.start_scheduler()
        self._scheduler_started = True
        return True, "started"

    async def stop(self) -> None:
        coordinator = self._coordinator
        if coordinator is not None:
            try:
                await coordinator.stop()
            except Exception:  # noqa: BLE001
                pass

        if self._scheduler_started:
            try:
                await self._bridge.stop_scheduler()
            except Exception:  # noqa: BLE001
                pass
            self._scheduler_started = False

    def collect_metrics(self) -> QueryMetrics:
        group_stats = self._bridge.collect_group_metrics()
        purchased_count = 0
        if self._coordinator is not None:
            purchased_count = self._coordinator.get_purchased_count()
        return QueryMetrics(
            query_count=group_stats.query_count,
            found_count=group_stats.found_count,
            purchased_count=purchased_count,
        )

    def _require_coordinator(self) -> LegacyQueryCoordinatorAdapter:
        if self._coordinator is None:
            raise RuntimeError("LegacyQueryPipeline is not initialized.")
        return self._coordinator

    def _log(self, text: str) -> None:
        if self._logger:
            self._logger(text)
