from __future__ import annotations

from types import ModuleType
from typing import Any

from c5_layered.infrastructure.query.group_runner import LegacyQueryGroupRunner


class LegacyQueryCoordinatorAdapter:
    """
    Wraps legacy MultiAccountCoordinator with a stable adapter interface.

    Key point:
    - Query group construction no longer depends on
      `MultiAccountCoordinator.add_products_to_account`.
    """

    def __init__(
        self,
        legacy_module: ModuleType,
        coordinator: Any,
        *,
        query_only: bool,
    ) -> None:
        self._legacy = legacy_module
        self._coordinator = coordinator
        self._query_only = query_only
        self._query_groups: list[LegacyQueryGroupRunner] = []

    async def attach_products(
        self,
        account_manager: Any,
        product_items: list[Any],
        config_name: str,
    ) -> bool:
        account_id = getattr(account_manager, "current_user_id", None)
        if not account_id:
            return False

        try:
            if self._query_only:

                async def _noop(_result_data: dict[str, Any]) -> None:
                    return

                result_callback = _noop
            else:
                result_callback = self._coordinator._on_query_result

            query_runner = LegacyQueryGroupRunner(
                legacy_module=self._legacy,
                config_name=config_name,
                product_items=product_items,
                account_manager=account_manager,
                result_callback=result_callback,
            )

            if account_id not in self._coordinator.query_coordinators:
                self._coordinator.query_coordinators[account_id] = []
            self._coordinator.query_coordinators[account_id].append(query_runner)
            self._query_groups.append(query_runner)
            return True
        except Exception:  # noqa: BLE001
            return False

    def register_purchase_account(self, account_manager: Any) -> bool:
        return bool(self._coordinator.register_account(account_manager))

    async def start(self, *, query_only: bool) -> bool:
        if query_only:
            return await self._start_query_only_groups()
        return bool(await self._coordinator.start_all())

    async def stop(self) -> None:
        await self._coordinator.stop_all()

    def get_purchased_count(self) -> int:
        try:
            if hasattr(self._coordinator, "scheduler"):
                return int(
                    self._coordinator.scheduler.get_stats().get("total_purchased", 0)
                )
        except Exception:  # noqa: BLE001
            pass
        return 0

    async def _start_query_only_groups(self) -> bool:
        ok = True
        for query_runner in self._query_groups:
            try:
                started = await query_runner.start()
                if not started:
                    ok = False
            except Exception:  # noqa: BLE001
                ok = False
        return ok
