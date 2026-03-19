from __future__ import annotations

from types import ModuleType
from typing import Any, Awaitable, Callable

from c5_layered.infrastructure.query.query_group_policy import LegacyQueryGroupPolicy
from c5_layered.infrastructure.query.scanner_factory import LegacyScannerFactory


ResultCallback = Callable[[dict[str, Any]], Awaitable[None]]


class LegacyQueryGroupRunner:
    """
    Builds and runs legacy QueryGroup instances without using
    legacy QueryCoordinator construction.
    """

    def __init__(
        self,
        legacy_module: ModuleType,
        *,
        config_name: str,
        product_items: list[Any],
        account_manager: Any,
        result_callback: ResultCallback,
    ) -> None:
        self._legacy = legacy_module
        self._scanner_factory = LegacyScannerFactory(legacy_module)
        self._group_policy = LegacyQueryGroupPolicy()
        self._config_name = config_name
        self._product_items = product_items
        self._account_manager = account_manager
        self._result_callback = result_callback
        self._account_id = str(getattr(account_manager, "current_user_id", "") or "")
        self._running = False
        self._new_group: Any | None = None
        self._fast_group: Any | None = None
        self._old_group: Any | None = None

    async def start(self) -> bool:
        if self._running:
            return True

        if not self._initialize_groups():
            return False

        scheduler = self._legacy.QueryCoordinator.get_global_scheduler()
        if scheduler is None:
            return False

        self._running = True
        for group_id, group_type, group in self._iter_groups():
            scheduler.register_group(
                group_id=group_id,
                group_type=group_type,
                on_ready_callback=group.on_ready_for_query,
            )
            await group.start()
        return True

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        all_groups = self._legacy.QueryCoordinator.get_all_groups()
        for group_id, _, group in self._iter_groups():
            try:
                await group.stop()
            except Exception:  # noqa: BLE001
                pass
            if group_id in all_groups:
                del all_groups[group_id]

    def _initialize_groups(self) -> bool:
        if not self._account_id:
            return False

        plan = self._group_policy.decide(
            account_manager=self._account_manager,
            product_items=self._product_items,
        )

        new_scanner_cls = self._scanner_factory.get_scanner_class("new")
        fast_scanner_cls = self._scanner_factory.get_scanner_class("fast")
        old_scanner_cls = self._scanner_factory.get_scanner_class("old")

        if plan.enable_new and plan.enable_fast and new_scanner_cls and fast_scanner_cls:
            self._new_group = self._legacy.QueryGroup(
                group_id=f"N_{self._account_id}",
                group_type="new",
                account_manager=self._account_manager,
                product_items=self._product_items,
                query_scanner_class=new_scanner_cls,
                result_callback=self._on_group_query_result,
            )
            self._fast_group = self._legacy.QueryGroup(
                group_id=f"F_{self._account_id}",
                group_type="fast",
                account_manager=self._account_manager,
                product_items=self._product_items,
                query_scanner_class=fast_scanner_cls,
                result_callback=self._on_group_query_result,
            )

        if plan.enable_old and old_scanner_cls:
            self._old_group = self._legacy.QueryGroup(
                group_id=f"O_{self._account_id}",
                group_type="old",
                account_manager=self._account_manager,
                product_items=self._product_items,
                query_scanner_class=old_scanner_cls,
                result_callback=self._on_group_query_result,
            )

        all_groups = self._legacy.QueryCoordinator.get_all_groups()
        created_any = False
        for group_id, _, group in self._iter_groups():
            all_groups[group_id] = group
            created_any = True
        return created_any

    async def _on_group_query_result(self, result_data: dict[str, Any]) -> None:
        await self._result_callback(result_data)

    def get_stats(self) -> dict[str, Any]:
        stats = {
            "config_name": self._config_name,
            "account_id": self._account_id,
            "running": self._running,
            "group_count": len(self._iter_groups()),
            "query_count": 0,
            "found_count": 0,
        }
        for _, _, group in self._iter_groups():
            if hasattr(group, "get_stats"):
                group_stats = group.get_stats()
                stats["query_count"] += int(group_stats.get("query_count", 0))
                stats["found_count"] += int(group_stats.get("found_count", 0))
        return stats

    def _iter_groups(self) -> list[tuple[str, str, Any]]:
        items: list[tuple[str, str, Any]] = []
        if self._new_group is not None:
            items.append((self._new_group.group_id, "new", self._new_group))
        if self._fast_group is not None:
            items.append((self._fast_group.group_id, "fast", self._fast_group))
        if self._old_group is not None:
            items.append((self._old_group.group_id, "old", self._old_group))
        return items
