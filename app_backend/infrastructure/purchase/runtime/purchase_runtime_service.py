from __future__ import annotations

import asyncio
import random
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from inspect import Parameter, signature

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.domain.models.purchase_runtime_settings import PurchaseRuntimeSettings
from app_backend.infrastructure.purchase.runtime.account_purchase_worker import AccountPurchaseWorker
from app_backend.infrastructure.purchase.runtime.inventory_state import InventoryState
from app_backend.infrastructure.purchase.runtime.legacy_purchase_gateway import LegacyPurchaseGateway
from app_backend.infrastructure.purchase.runtime.purchase_hit_inbox import PurchaseHitInbox
from app_backend.infrastructure.purchase.runtime.purchase_scheduler import PurchaseScheduler
from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

RuntimeFactory = Callable[..., object]
ExecutionGatewayFactory = Callable[[], object]
InventoryRefreshGatewayFactory = Callable[[], object]
RecoveryDelaySecondsProvider = Callable[[], float]


class PurchaseRuntimeService:
    def __init__(
        self,
        *,
        account_repository,
        settings_repository,
        inventory_snapshot_repository=None,
        inventory_refresh_gateway_factory: InventoryRefreshGatewayFactory | None = None,
        recovery_delay_seconds_provider: RecoveryDelaySecondsProvider | None = None,
        execution_gateway_factory: ExecutionGatewayFactory | None = None,
        runtime_factory: RuntimeFactory | None = None,
    ) -> None:
        self._account_repository = account_repository
        self._settings_repository = settings_repository
        self._inventory_snapshot_repository = inventory_snapshot_repository
        self._inventory_refresh_gateway_factory = inventory_refresh_gateway_factory
        self._recovery_delay_seconds_provider = recovery_delay_seconds_provider
        self._execution_gateway_factory = execution_gateway_factory or LegacyPurchaseGateway
        self._runtime_factory = runtime_factory or self._build_default_runtime
        self._runtime = None

    def start(self) -> tuple[bool, str]:
        if self._has_running_runtime():
            return False, "已有购买运行时在运行"

        settings = self._settings_repository.get()
        accounts = list(self._account_repository.list_accounts())
        runtime = self._create_runtime(accounts, settings)
        runtime.start()
        self._runtime = runtime
        return True, "购买运行时已启动"

    def stop(self) -> tuple[bool, str]:
        if not self._has_running_runtime():
            self._runtime = None
            return False, "当前没有运行中的购买运行时"

        self._runtime.stop()
        self._runtime = None
        return True, "购买运行时已停止"

    def get_status(self) -> dict[str, object]:
        settings = self._settings_repository.get()
        if not self._has_running_runtime():
            self._runtime = None
            return self._build_idle_snapshot(settings)
        snapshot = self._runtime.snapshot()
        return self._normalize_snapshot(snapshot, settings)

    def get_account_inventory_detail(self, account_id: str) -> dict[str, object] | None:
        account = self._find_account(account_id)
        if account is None:
            return None

        runtime_detail = self._get_runtime_inventory_detail(account_id)
        if runtime_detail is not None:
            return runtime_detail

        snapshot = (
            self._inventory_snapshot_repository.get(account_id)
            if self._inventory_snapshot_repository is not None
            else None
        )
        return self._build_inventory_detail_from_snapshot(account, snapshot)

    def update_settings(self, *, query_only: bool, whitelist_account_ids: list[str]) -> dict[str, object]:
        updated_settings = self._settings_repository.save(
            query_only=bool(query_only),
            whitelist_account_ids=list(whitelist_account_ids),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
        if self._runtime is not None:
            apply_settings = getattr(self._runtime, "apply_settings", None)
            if callable(apply_settings):
                apply_settings(updated_settings)
        return self.get_status()

    def accept_query_hit(self, hit: dict[str, object]) -> dict[str, object]:
        return _run_coroutine_sync(self.accept_query_hit_async(hit))

    async def accept_query_hit_async(self, hit: dict[str, object]) -> dict[str, object]:
        if not self._has_running_runtime():
            self._runtime = None
            return {"accepted": False, "status": "ignored_not_running"}

        accept_query_hit = getattr(self._runtime, "accept_query_hit_async", None)
        if callable(accept_query_hit):
            return dict(await accept_query_hit(hit))

        accept_query_hit = getattr(self._runtime, "accept_query_hit", None)
        if not callable(accept_query_hit):
            return {"accepted": False, "status": "ignored_not_supported"}
        return dict(accept_query_hit(hit))

    def _has_running_runtime(self) -> bool:
        if self._runtime is None:
            return False
        snapshot = self._runtime.snapshot()
        return bool(snapshot.get("running"))

    def _create_runtime(self, accounts: list[object], settings: PurchaseRuntimeSettings):
        if self._runtime_factory_accepts_extended_kwargs():
            return self._runtime_factory(
                accounts,
                settings,
                account_repository=self._account_repository,
                inventory_snapshot_repository=self._inventory_snapshot_repository,
                inventory_refresh_gateway_factory=self._inventory_refresh_gateway_factory,
                recovery_delay_seconds_provider=self._recovery_delay_seconds_provider,
                execution_gateway_factory=self._execution_gateway_factory,
            )
        return self._runtime_factory(accounts, settings)

    def _runtime_factory_accepts_extended_kwargs(self) -> bool:
        try:
            parameters = signature(self._runtime_factory).parameters.values()
        except (TypeError, ValueError):
            return False

        for parameter in parameters:
            if parameter.kind == Parameter.VAR_KEYWORD:
                return True
            if parameter.name in {
                "account_repository",
                "inventory_snapshot_repository",
                "inventory_refresh_gateway_factory",
                "recovery_delay_seconds_provider",
                "execution_gateway_factory",
            }:
                return True
        return False

    @staticmethod
    def _build_idle_snapshot(settings: PurchaseRuntimeSettings) -> dict[str, object]:
        return {
            "running": False,
            "message": "未运行",
            "started_at": None,
            "stopped_at": None,
            "queue_size": 0,
            "active_account_count": 0,
            "total_account_count": 0,
            "total_purchased_count": 0,
            "recent_events": [],
            "accounts": [],
            "settings": {
                "query_only": settings.query_only,
                "whitelist_account_ids": list(settings.whitelist_account_ids),
                "updated_at": settings.updated_at,
            },
        }

    @staticmethod
    def _normalize_snapshot(snapshot: dict[str, object], settings: PurchaseRuntimeSettings) -> dict[str, object]:
        return {
            "running": bool(snapshot.get("running")),
            "message": str(snapshot.get("message") or ("运行中" if snapshot.get("running") else "未运行")),
            "started_at": snapshot.get("started_at"),
            "stopped_at": snapshot.get("stopped_at"),
            "queue_size": int(snapshot.get("queue_size", 0)),
            "active_account_count": int(snapshot.get("active_account_count", 0)),
            "total_account_count": int(snapshot.get("total_account_count", 0)),
            "total_purchased_count": int(snapshot.get("total_purchased_count", 0)),
            "recent_events": list(snapshot.get("recent_events") or []),
            "accounts": PurchaseRuntimeService._normalize_accounts(snapshot.get("accounts")),
            "settings": {
                "query_only": settings.query_only,
                "whitelist_account_ids": list(settings.whitelist_account_ids),
                "updated_at": settings.updated_at,
            },
        }

    @staticmethod
    def _normalize_accounts(raw_accounts: object) -> list[dict[str, object]]:
        if not isinstance(raw_accounts, list):
            return []

        normalized: list[dict[str, object]] = []
        for raw_account in raw_accounts:
            if not isinstance(raw_account, dict):
                continue
            normalized.append(
                {
                    "account_id": str(raw_account.get("account_id") or ""),
                    "display_name": raw_account.get("display_name"),
                    "purchase_capability_state": raw_account.get("purchase_capability_state"),
                    "purchase_pool_state": raw_account.get("purchase_pool_state"),
                    "selected_steam_id": raw_account.get("selected_steam_id"),
                    "selected_inventory_remaining_capacity": (
                        int(raw_account["selected_inventory_remaining_capacity"])
                        if raw_account.get("selected_inventory_remaining_capacity") is not None
                        else None
                    ),
                    "selected_inventory_max": (
                        int(raw_account["selected_inventory_max"])
                        if raw_account.get("selected_inventory_max") is not None
                        else None
                    ),
                    "last_error": raw_account.get("last_error"),
                    "total_purchased_count": (
                        int(raw_account["total_purchased_count"])
                        if raw_account.get("total_purchased_count") is not None
                        else None
                    ),
                }
            )
        return normalized

    def _find_account(self, account_id: str):
        get_account = getattr(self._account_repository, "get_account", None)
        if callable(get_account):
            account = get_account(account_id)
            if account is not None:
                return account
        for account in self._account_repository.list_accounts():
            if str(getattr(account, "account_id", "")) == str(account_id):
                return account
        return None

    def _get_runtime_inventory_detail(self, account_id: str) -> dict[str, object] | None:
        if not self._has_running_runtime():
            return None
        get_detail = getattr(self._runtime, "get_account_inventory_detail", None)
        if not callable(get_detail):
            return None
        detail = get_detail(account_id)
        if detail is None:
            return None
        return self._normalize_inventory_detail(detail)

    def _build_inventory_detail_from_snapshot(self, account, snapshot) -> dict[str, object]:
        inventories = list(getattr(snapshot, "inventories", []) or []) if snapshot is not None else []
        selected_steam_id = getattr(snapshot, "selected_steam_id", None) if snapshot is not None else None
        return self._normalize_inventory_detail(
            {
                "account_id": str(getattr(account, "account_id", "") or ""),
                "display_name": str(getattr(account, "display_name", "") or ""),
                "selected_steam_id": selected_steam_id,
                "refreshed_at": getattr(snapshot, "refreshed_at", None) if snapshot is not None else None,
                "last_error": getattr(snapshot, "last_error", None) if snapshot is not None else None,
                "inventories": self._build_inventory_rows(inventories, selected_steam_id=selected_steam_id),
            }
        )

    @staticmethod
    def _normalize_inventory_detail(detail: dict[str, object]) -> dict[str, object]:
        return {
            "account_id": str(detail.get("account_id") or ""),
            "display_name": str(detail.get("display_name") or detail.get("account_id") or ""),
            "selected_steam_id": detail.get("selected_steam_id"),
            "refreshed_at": detail.get("refreshed_at"),
            "last_error": detail.get("last_error"),
            "inventories": [
                {
                    "steamId": str(row.get("steamId") or ""),
                    "inventory_num": int(row.get("inventory_num", 0)),
                    "inventory_max": int(row.get("inventory_max", 0)),
                    "remaining_capacity": int(row.get("remaining_capacity", 0)),
                    "is_selected": bool(row.get("is_selected")),
                    "is_available": bool(row.get("is_available")),
                }
                for row in detail.get("inventories") or []
                if isinstance(row, dict)
            ],
        }

    @staticmethod
    def _build_inventory_rows(
        inventories: list[dict[str, object]],
        *,
        selected_steam_id: str | None,
        min_capacity_threshold: int = 50,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for inventory in inventories:
            current_num = int(inventory.get("inventory_num", 0))
            max_num = int(inventory.get("inventory_max", 1000))
            remaining = int(inventory.get("remaining_capacity", max_num - current_num))
            steam_id = str(inventory.get("steamId") or "")
            rows.append(
                {
                    "steamId": steam_id,
                    "inventory_num": current_num,
                    "inventory_max": max_num,
                    "remaining_capacity": remaining,
                    "is_selected": bool(selected_steam_id and steam_id == selected_steam_id),
                    "is_available": current_num > 0 and remaining >= int(min_capacity_threshold),
                }
            )
        return rows

    @staticmethod
    def _build_default_runtime(
        accounts: list[object],
        settings: PurchaseRuntimeSettings,
        *,
        account_repository=None,
        inventory_snapshot_repository=None,
        inventory_refresh_gateway_factory: InventoryRefreshGatewayFactory | None = None,
        recovery_delay_seconds_provider: RecoveryDelaySecondsProvider | None = None,
        execution_gateway_factory: ExecutionGatewayFactory | None = None,
    ):
        return _DefaultPurchaseRuntime(
            accounts,
            settings,
            account_repository=account_repository,
            inventory_snapshot_repository=inventory_snapshot_repository,
            inventory_refresh_gateway_factory=inventory_refresh_gateway_factory,
            recovery_delay_seconds_provider=recovery_delay_seconds_provider,
            execution_gateway_factory=execution_gateway_factory or LegacyPurchaseGateway,
        )


@dataclass(slots=True)
class _RuntimeAccountState:
    account: object
    inventory_state: InventoryState
    worker: AccountPurchaseWorker
    capability_state: str
    pool_state: str
    last_error: str | None = None
    total_purchased_count: int = 0
    inventory_refreshed_at: str | None = None

    @property
    def account_id(self) -> str:
        return str(getattr(self.account, "account_id"))

    @property
    def display_name(self) -> str:
        return str(getattr(self.account, "display_name", None) or getattr(self.account, "default_name", "") or "")


class _DefaultPurchaseRuntime:
    _RECENT_EVENT_LIMIT = 20

    def __init__(
        self,
        accounts: list[object],
        settings: PurchaseRuntimeSettings,
        *,
        account_repository=None,
        inventory_snapshot_repository=None,
        inventory_refresh_gateway_factory: InventoryRefreshGatewayFactory | None,
        recovery_delay_seconds_provider: RecoveryDelaySecondsProvider | None,
        execution_gateway_factory: ExecutionGatewayFactory,
    ) -> None:
        self._accounts = list(accounts)
        self._settings = settings
        self._account_repository = account_repository
        self._inventory_snapshot_repository = inventory_snapshot_repository
        self._inventory_refresh_gateway_factory = inventory_refresh_gateway_factory
        self._recovery_delay_seconds_provider = (
            recovery_delay_seconds_provider or self._default_recovery_delay_seconds
        )
        self._execution_gateway_factory = execution_gateway_factory
        self._running = False
        self._started_at: str | None = None
        self._stopped_at: str | None = None
        self._recent_events: list[dict[str, object]] = []
        self._scheduler = PurchaseScheduler()
        self._hit_inbox = PurchaseHitInbox()
        self._account_states: dict[str, _RuntimeAccountState] = {}
        self._total_purchased_count = 0
        self._recovery_timers: dict[str, threading.Timer] = {}

    def start(self) -> None:
        self._cancel_all_recovery_checks()
        self._running = True
        self._started_at = datetime.now().isoformat(timespec="seconds")
        self._stopped_at = None
        self._recent_events = []
        self._scheduler = PurchaseScheduler()
        self._hit_inbox = PurchaseHitInbox()
        self._account_states = {}
        self._total_purchased_count = 0
        self._recovery_timers = {}
        self._initialize_accounts()

    def stop(self) -> None:
        self._running = False
        self._cancel_all_recovery_checks()
        self._stopped_at = datetime.now().isoformat(timespec="seconds")

    def apply_settings(self, settings: PurchaseRuntimeSettings) -> None:
        self._settings = settings
        if self._running:
            self._cancel_all_recovery_checks()
            self._scheduler = PurchaseScheduler()
            self._account_states = {}
            self._recovery_timers = {}
            self._initialize_accounts()

    async def accept_query_hit_async(self, hit: dict[str, object]) -> dict[str, object]:
        if self._settings.query_only:
            self._push_event(hit, status="blocked_query_only", message="仅查询模式已拦截")
            return {"accepted": False, "status": "blocked_query_only"}

        batch = self._hit_inbox.accept(hit)
        if batch is None:
            self._push_event(hit, status="duplicate_filtered", message="重复命中已忽略")
            return {"accepted": False, "status": "duplicate_filtered"}

        self._scheduler.submit(batch)
        self._push_event(hit, status="queued", message="已转入购买")
        await self._drain_scheduler()
        return {"accepted": True, "status": "queued"}

    def snapshot(self) -> dict[str, object]:
        return {
            "running": self._running,
            "message": "运行中" if self._running else "未运行",
            "started_at": self._started_at if self._running else None,
            "stopped_at": self._stopped_at if not self._running else None,
            "queue_size": self._scheduler.queue_size(),
            "active_account_count": self._scheduler.active_account_count() if self._running else 0,
            "total_account_count": self._scheduler.total_account_count() if self._running else 0,
            "total_purchased_count": self._total_purchased_count,
            "recent_events": list(self._recent_events),
            "accounts": [
                {
                    "account_id": state.account_id,
                    "display_name": state.display_name,
                    "purchase_capability_state": state.capability_state,
                    "purchase_pool_state": state.pool_state,
                    "selected_steam_id": state.inventory_state.selected_steam_id,
                    "selected_inventory_remaining_capacity": self._selected_inventory_remaining_capacity(state),
                    "selected_inventory_max": self._selected_inventory_max(state),
                    "last_error": state.last_error,
                    "total_purchased_count": state.total_purchased_count,
                }
                for state in self._account_states.values()
            ],
        }

    def get_account_inventory_detail(self, account_id: str) -> dict[str, object] | None:
        state = self._account_states.get(account_id)
        if state is None:
            return None
        return {
            "account_id": state.account_id,
            "display_name": state.display_name,
            "selected_steam_id": state.inventory_state.selected_steam_id,
            "refreshed_at": state.inventory_refreshed_at,
            "last_error": state.last_error,
            "inventories": PurchaseRuntimeService._build_inventory_rows(
                state.inventory_state.inventories,
                selected_steam_id=state.inventory_state.selected_steam_id,
            ),
        }

    def _initialize_accounts(self) -> None:
        for account in self._accounts:
            if not self._is_eligible_account(account):
                continue
            account_id = str(getattr(account, "account_id", "") or "")
            if not account_id:
                continue

            inventory_state = InventoryState()
            snapshot = self._inventory_snapshot_repository.get(account_id) if self._inventory_snapshot_repository is not None else None
            if snapshot is not None and list(getattr(snapshot, "inventories", []) or []):
                inventory_state.load_snapshot(list(snapshot.inventories))
                selected_steam_id = getattr(snapshot, "selected_steam_id", None)
                if selected_steam_id and any(
                    inventory.get("steamId") == selected_steam_id
                    for inventory in inventory_state.available_inventories
                ):
                    inventory_state.selected_steam_id = selected_steam_id

            capability_state = str(
                getattr(account, "purchase_capability_state", PurchaseCapabilityState.UNBOUND)
            )
            last_error = getattr(snapshot, "last_error", None)
            inventory_refreshed_at = getattr(snapshot, "refreshed_at", None)
            refresh_result = self._refresh_inventory_from_remote(account, inventory_state)
            should_persist_snapshot = False
            if refresh_result is None:
                pass
            elif refresh_result.status == "success":
                inventory_state.refresh_from_remote(list(refresh_result.inventories))
                last_error = None
                should_persist_snapshot = True
            elif refresh_result.status == "auth_invalid":
                inventory_state.load_snapshot([])
                capability_state = PurchaseCapabilityState.EXPIRED
                last_error = refresh_result.error
                should_persist_snapshot = True
            elif refresh_result.error:
                last_error = refresh_result.error

            available = (
                capability_state == PurchaseCapabilityState.BOUND
                and inventory_state.selected_steam_id is not None
            )
            pool_state = (
                PurchasePoolState.PAUSED_AUTH_INVALID
                if capability_state == PurchaseCapabilityState.EXPIRED
                else (
                    PurchasePoolState.ACTIVE
                    if available
                    else PurchasePoolState.PAUSED_NO_INVENTORY
                )
            )
            state = _RuntimeAccountState(
                account=account,
                inventory_state=inventory_state,
                worker=AccountPurchaseWorker(
                    account=account,
                    inventory_state=inventory_state,
                    execution_gateway=self._execution_gateway_factory(),
                ),
                capability_state=capability_state,
                pool_state=pool_state,
                last_error=last_error,
                inventory_refreshed_at=inventory_refreshed_at,
            )
            self._account_states[account_id] = state
            self._scheduler.register_account(account_id, available=available)
            if state.pool_state == PurchasePoolState.PAUSED_NO_INVENTORY:
                self._schedule_recovery_check(state.account_id)
            if should_persist_snapshot:
                self._persist_inventory_snapshot(state, last_error=state.last_error)
            self._sync_account_repository_state(state)

    def _refresh_inventory_from_remote(
        self,
        account: object,
        inventory_state: InventoryState,
    ) -> InventoryRefreshResult | None:
        if self._inventory_refresh_gateway_factory is None:
            return None

        gateway = self._inventory_refresh_gateway_factory()
        refresh = getattr(gateway, "refresh", None)
        if not callable(refresh):
            return InventoryRefreshResult(status="error", inventories=[], error="refresh not supported")

        try:
            result = _run_coroutine_sync(refresh(account=account))
        except Exception as exc:
            return InventoryRefreshResult(status="error", inventories=[], error=str(exc))

        if isinstance(result, InventoryRefreshResult):
            return result
        return InventoryRefreshResult(status="error", inventories=[], error="invalid refresh result")

    def _is_eligible_account(self, account: object) -> bool:
        if bool(getattr(account, "disabled", False)):
            return False
        if str(getattr(account, "purchase_capability_state", "")) != PurchaseCapabilityState.BOUND:
            return False
        whitelist = {str(account_id) for account_id in self._settings.whitelist_account_ids}
        if whitelist and str(getattr(account, "account_id", "")) not in whitelist:
            return False
        return True

    @staticmethod
    def _selected_inventory_remaining_capacity(state: _RuntimeAccountState) -> int | None:
        selected_inventory = state.inventory_state.selected_inventory
        if selected_inventory is None:
            return None
        current_num = int(selected_inventory.get("inventory_num", 0))
        max_num = int(selected_inventory.get("inventory_max", 1000))
        return int(selected_inventory.get("remaining_capacity", max_num - current_num))

    @staticmethod
    def _selected_inventory_max(state: _RuntimeAccountState) -> int | None:
        selected_inventory = state.inventory_state.selected_inventory
        if selected_inventory is None:
            return None
        return int(selected_inventory.get("inventory_max", 1000))

    async def _drain_scheduler(self) -> None:
        while self._scheduler.queue_size() > 0:
            account_id = self._scheduler.select_next_account_id()
            if not account_id:
                return
            state = self._account_states.get(account_id)
            if state is None:
                self._scheduler.mark_unavailable(account_id, reason="missing_account_state")
                continue

            batch = self._scheduler.pop_next_batch()
            outcome = await state.worker.process(batch)
            self._apply_worker_outcome(state, batch, outcome)

    def _apply_worker_outcome(self, state: _RuntimeAccountState, batch, outcome) -> None:
        state.capability_state = outcome.capability_state
        state.pool_state = outcome.pool_state
        state.last_error = outcome.error
        if outcome.status == "success":
            state.total_purchased_count += int(outcome.purchased_count)
            self._total_purchased_count += int(outcome.purchased_count)
            event_status = "success"
            event_message = f"购买成功 {outcome.purchased_count} 件"
            if outcome.requires_remote_refresh:
                event_status, event_message = self._reconcile_inventory_after_success(
                    state,
                    purchased_count=int(outcome.purchased_count),
                )
            self._sync_scheduler_state(state)
            self._persist_inventory_snapshot(state, last_error=state.last_error)
            self._push_event_from_batch(
                batch,
                status=event_status,
                message=event_message,
            )
        elif outcome.status == "auth_invalid":
            self._sync_scheduler_state(state)
            self._persist_inventory_snapshot(state, last_error=outcome.error)
            self._push_event_from_batch(
                batch,
                status="auth_invalid",
                message=outcome.error or "登录已失效",
            )
        elif outcome.status == "no_inventory":
            self._sync_scheduler_state(state)
            self._persist_inventory_snapshot(state, last_error=outcome.error)
            self._push_event_from_batch(
                batch,
                status="paused_no_inventory",
                message=outcome.error or "没有可用仓库",
            )
        else:
            self._push_event_from_batch(
                batch,
                status=str(outcome.status),
                message=outcome.error or "购买失败",
            )

        self._sync_account_repository_state(state)

    def _reconcile_inventory_after_success(
        self,
        state: _RuntimeAccountState,
        *,
        purchased_count: int,
    ) -> tuple[str, str]:
        refresh_result = self._refresh_inventory_from_remote(state.account, state.inventory_state)
        if refresh_result is None:
            return self._success_event_for_state(state, purchased_count=purchased_count)

        if refresh_result.status == "success":
            state.inventory_state.refresh_from_remote(list(refresh_result.inventories))
            state.last_error = None
            state.pool_state = (
                PurchasePoolState.ACTIVE
                if state.inventory_state.selected_steam_id is not None
                else PurchasePoolState.PAUSED_NO_INVENTORY
            )
            return self._success_event_for_state(state, purchased_count=purchased_count)

        if refresh_result.status == "auth_invalid":
            state.capability_state = PurchaseCapabilityState.EXPIRED
            state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
            state.last_error = refresh_result.error
            return "auth_invalid", refresh_result.error or "登录已失效"

        state.pool_state = PurchasePoolState.PAUSED_NO_INVENTORY
        state.last_error = refresh_result.error
        return "paused_no_inventory", refresh_result.error or "没有可用仓库"

    def _success_event_for_state(
        self,
        state: _RuntimeAccountState,
        *,
        purchased_count: int,
    ) -> tuple[str, str]:
        if state.pool_state == PurchasePoolState.ACTIVE:
            return "success", f"购买成功 {purchased_count} 件"
        return "paused_no_inventory", f"购买成功 {purchased_count} 件，当前没有可用仓库"

    def _sync_scheduler_state(self, state: _RuntimeAccountState) -> None:
        if state.pool_state == PurchasePoolState.ACTIVE:
            self._scheduler.mark_available(state.account_id)
            self._cancel_recovery_check(state.account_id)
            return
        if state.pool_state == PurchasePoolState.PAUSED_AUTH_INVALID:
            self._scheduler.mark_unavailable(state.account_id, reason="auth_invalid")
            self._cancel_recovery_check(state.account_id)
            return
        self._scheduler.mark_no_inventory(state.account_id)
        self._schedule_recovery_check(state.account_id)

    def _schedule_recovery_check(self, account_id: str) -> None:
        if not self._running:
            return
        state = self._account_states.get(account_id)
        if state is None:
            return
        if state.pool_state != PurchasePoolState.PAUSED_NO_INVENTORY:
            return
        if state.capability_state != PurchaseCapabilityState.BOUND:
            return

        self._cancel_recovery_check(account_id)
        delay_seconds = max(float(self._recovery_delay_seconds_provider()), 0.0)
        timer = threading.Timer(delay_seconds, self._run_recovery_check, args=(account_id,))
        timer.daemon = True
        self._recovery_timers[account_id] = timer
        timer.start()

    def _cancel_recovery_check(self, account_id: str) -> None:
        timer = self._recovery_timers.pop(account_id, None)
        if timer is not None:
            timer.cancel()

    def _cancel_all_recovery_checks(self) -> None:
        for account_id in list(self._recovery_timers.keys()):
            self._cancel_recovery_check(account_id)

    def _run_recovery_check(self, account_id: str) -> None:
        self._recovery_timers.pop(account_id, None)
        if not self._running:
            return

        state = self._account_states.get(account_id)
        if state is None or state.pool_state != PurchasePoolState.PAUSED_NO_INVENTORY:
            return

        refresh_result = self._refresh_inventory_from_remote(state.account, state.inventory_state)
        if refresh_result is None:
            self._schedule_recovery_check(account_id)
            return

        if refresh_result.status == "success":
            state.inventory_state.refresh_from_remote(list(refresh_result.inventories))
            state.last_error = None
            state.pool_state = (
                PurchasePoolState.ACTIVE
                if state.inventory_state.selected_steam_id is not None
                else PurchasePoolState.PAUSED_NO_INVENTORY
            )
            self._sync_scheduler_state(state)
            self._persist_inventory_snapshot(state, last_error=state.last_error)
            self._sync_account_repository_state(state)
            if state.pool_state == PurchasePoolState.ACTIVE:
                self._push_runtime_event(
                    state,
                    status="inventory_recovered",
                    message="库存恢复，账号已重新入池",
                )
            else:
                self._push_runtime_event(
                    state,
                    status="recovery_waiting",
                    message="恢复检查完成，仍无可用仓库",
                )
            return

        if refresh_result.status == "auth_invalid":
            state.capability_state = PurchaseCapabilityState.EXPIRED
            state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
            state.last_error = refresh_result.error
            self._sync_scheduler_state(state)
            self._persist_inventory_snapshot(state, last_error=state.last_error)
            self._sync_account_repository_state(state)
            self._push_runtime_event(
                state,
                status="auth_invalid",
                message=refresh_result.error or "登录已失效",
            )
            return

        state.last_error = refresh_result.error
        self._sync_scheduler_state(state)
        self._persist_inventory_snapshot(state, last_error=state.last_error)
        self._sync_account_repository_state(state)
        self._push_runtime_event(
            state,
            status="recovery_waiting",
            message=refresh_result.error or "恢复检查失败，等待下次重试",
        )

    @staticmethod
    def _default_recovery_delay_seconds() -> float:
        return random.uniform(30 * 60, 40 * 60)

    def _persist_inventory_snapshot(self, state: _RuntimeAccountState, *, last_error: str | None = None) -> None:
        refreshed_at = datetime.now().isoformat(timespec="seconds")
        state.inventory_refreshed_at = refreshed_at
        if self._inventory_snapshot_repository is None:
            return
        self._inventory_snapshot_repository.save(
            account_id=state.account_id,
            selected_steam_id=state.inventory_state.selected_steam_id,
            inventories=state.inventory_state.inventories,
            refreshed_at=refreshed_at,
            last_error=last_error,
        )

    def _sync_account_repository_state(self, state: _RuntimeAccountState) -> None:
        if self._account_repository is None or not hasattr(self._account_repository, "update_account"):
            return
        try:
            self._account_repository.update_account(
                state.account_id,
                purchase_capability_state=state.capability_state,
                purchase_pool_state=state.pool_state,
                last_error=state.last_error,
                updated_at=datetime.now().isoformat(timespec="seconds"),
            )
        except Exception:
            return

    def _push_runtime_event(self, state: _RuntimeAccountState, *, status: str, message: str) -> None:
        self._recent_events.insert(
            0,
            {
                "occurred_at": datetime.now().isoformat(timespec="seconds"),
                "status": status,
                "message": message,
                "account_id": state.account_id,
                "account_display_name": state.display_name,
                "selected_steam_id": state.inventory_state.selected_steam_id,
                "query_item_name": "",
                "external_item_id": None,
                "product_url": None,
                "product_list": [],
                "total_price": 0.0,
                "total_wear_sum": None,
                "source_mode_type": "",
            },
        )
        del self._recent_events[self._RECENT_EVENT_LIMIT :]

    def _push_event_from_batch(self, batch, *, status: str, message: str) -> None:
        self._recent_events.insert(
            0,
            {
                "occurred_at": datetime.now().isoformat(timespec="seconds"),
                "status": status,
                "message": message,
                "query_item_name": str(getattr(batch, "query_item_name", "") or ""),
                "external_item_id": getattr(batch, "external_item_id", None),
                "product_url": getattr(batch, "product_url", None),
                "product_list": list(getattr(batch, "product_list", []) or []),
                "total_price": float(getattr(batch, "total_price", 0.0) or 0.0),
                "total_wear_sum": getattr(batch, "total_wear_sum", None),
                "source_mode_type": str(getattr(batch, "source_mode_type", "") or ""),
            },
        )
        del self._recent_events[self._RECENT_EVENT_LIMIT :]

    def _push_event(self, hit: dict[str, object], *, status: str, message: str) -> None:
        self._recent_events.insert(
            0,
            {
                "occurred_at": datetime.now().isoformat(timespec="seconds"),
                "status": status,
                "message": message,
                "query_item_name": str(hit.get("query_item_name") or ""),
                "external_item_id": hit.get("external_item_id"),
                "product_url": hit.get("product_url"),
                "product_list": list(hit.get("product_list") or []),
                "total_price": float(hit["total_price"]) if hit.get("total_price") is not None else None,
                "total_wear_sum": (
                    float(hit["total_wear_sum"])
                    if hit.get("total_wear_sum") is not None
                    else None
                ),
                "source_mode_type": str(hit.get("mode_type") or ""),
            },
        )
        del self._recent_events[self._RECENT_EVENT_LIMIT :]


def _run_coroutine_sync(coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result_holder: dict[str, object] = {}
    error_holder: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result_holder["value"] = asyncio.run(coroutine)
        except BaseException as exc:  # pragma: no cover - defensive thread bridge
            error_holder["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder.get("value")
