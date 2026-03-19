from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType

from c5_layered.infrastructure.query.coordinator_adapter import (
    LegacyQueryCoordinatorAdapter,
)


@dataclass(slots=True)
class LegacyQueryGroupStats:
    query_count: int
    found_count: int


class LegacyQueryBridge:
    """
    Thin adapter over legacy query runtime classes in `autobuy.py`.
    """

    def __init__(self, legacy_module: ModuleType) -> None:
        self._legacy = legacy_module

    def setup_scheduler(
        self,
        product_ids: list[str],
        *,
        min_cooldown: float = 0.1,
    ) -> None:
        scheduler = self._legacy.QueryScheduler(product_ids, min_cooldown=min_cooldown)
        self._legacy.QueryCoordinator.set_global_scheduler(scheduler)

    def build_coordinator(self, *, query_only: bool) -> LegacyQueryCoordinatorAdapter:
        coordinator = self._legacy.MultiAccountCoordinator()
        return LegacyQueryCoordinatorAdapter(
            self._legacy,
            coordinator,
            query_only=query_only,
        )

    async def start_scheduler(self) -> None:
        await self._legacy.QueryCoordinator.start_global_scheduler()

    async def stop_scheduler(self) -> None:
        await self._legacy.QueryCoordinator.stop_global_scheduler()

    def collect_group_metrics(self) -> LegacyQueryGroupStats:
        query_count = 0
        found_count = 0

        try:
            groups = self._legacy.QueryCoordinator.get_all_groups()
            if isinstance(groups, dict):
                query_count = sum(
                    g.get_stats().get("query_count", 0)
                    for g in groups.values()
                    if hasattr(g, "get_stats")
                )
                found_count = sum(
                    g.get_stats().get("found_count", 0)
                    for g in groups.values()
                    if hasattr(g, "get_stats")
                )
        except Exception:  # noqa: BLE001
            pass

        return LegacyQueryGroupStats(
            query_count=query_count,
            found_count=found_count,
        )
