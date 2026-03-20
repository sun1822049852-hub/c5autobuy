from __future__ import annotations

import asyncio
import random
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from inspect import Parameter, signature

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.infrastructure.purchase.runtime.account_purchase_worker import AccountPurchaseWorker
from app_backend.infrastructure.purchase.runtime.inventory_state import InventoryState
from app_backend.infrastructure.purchase.runtime.purchase_hit_inbox import PurchaseHitInbox
from app_backend.infrastructure.purchase.runtime.purchase_scheduler import PurchaseScheduler
from app_backend.infrastructure.purchase.runtime.purchase_execution_gateway import PurchaseExecutionGateway
from app_backend.infrastructure.purchase.runtime.purchase_stats_aggregator import PurchaseStatsAggregator
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
        settings_repository=None,
        inventory_snapshot_repository=None,
        inventory_refresh_gateway_factory: InventoryRefreshGatewayFactory | None = None,
        recovery_delay_seconds_provider: RecoveryDelaySecondsProvider | None = None,
        execution_gateway_factory: ExecutionGatewayFactory | None = None,
        runtime_factory: RuntimeFactory | None = None,
    ) -> None:
        self._account_repository = account_repository
        self._inventory_snapshot_repository = inventory_snapshot_repository
        self._inventory_refresh_gateway_factory = inventory_refresh_gateway_factory
        self._recovery_delay_seconds_provider = recovery_delay_seconds_provider
        self._execution_gateway_factory = execution_gateway_factory or PurchaseExecutionGateway
        self._runtime_factory = runtime_factory or self._build_default_runtime
        self._runtime = None
        self._on_no_available_accounts = None
        self._on_accounts_available = None

    def start(self) -> tuple[bool, str]:
        if self._has_running_runtime():
            return False, "已有购买运行时在运行"

        accounts = list(self._account_repository.list_accounts())
        runtime = self._create_runtime(accounts)
        self._bind_runtime_callbacks(runtime)
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
        if not self._has_running_runtime():
            self._runtime = None
            return self._build_idle_snapshot()
        snapshot = self._runtime.snapshot()
        return self._normalize_snapshot(snapshot)

    def has_available_accounts(self) -> bool:
        if not self._has_running_runtime():
            return False
        snapshot = self._runtime.snapshot()
        return int(snapshot.get("active_account_count", 0)) > 0

    def register_availability_callbacks(
        self,
        *,
        on_no_available_accounts=None,
        on_accounts_available=None,
    ) -> None:
        self._on_no_available_accounts = on_no_available_accounts
        self._on_accounts_available = on_accounts_available
        if self._runtime is not None:
            self._bind_runtime_callbacks(self._runtime)

    def get_account_inventory_detail(self, account_id: str) -> dict[str, object] | None:
        account = self._find_account(account_id)
        if account is None:
            return None

        runtime_detail = self._get_runtime_inventory_detail(account_id, account=account)
        if runtime_detail is not None:
            return runtime_detail

        snapshot = (
            self._inventory_snapshot_repository.get(account_id)
            if self._inventory_snapshot_repository is not None
            else None
        )
        return self._build_inventory_detail_from_snapshot(account, snapshot)

    def refresh_account_inventory_detail(self, account_id: str) -> dict[str, object] | None:
        account = self._find_account(account_id)
        if account is None:
            return None

        runtime_detail = self._refresh_runtime_inventory_detail(account_id, account=account)
        if runtime_detail is not None:
            return runtime_detail

        snapshot = (
            self._inventory_snapshot_repository.get(account_id)
            if self._inventory_snapshot_repository is not None
            else None
        )
        inventory_state = InventoryState()
        if snapshot is not None and list(getattr(snapshot, "inventories", []) or []):
            inventory_state.load_snapshot(list(snapshot.inventories))
            selected_steam_id = getattr(snapshot, "selected_steam_id", None)
            if selected_steam_id and any(
                inventory.get("steamId") == selected_steam_id
                for inventory in inventory_state.available_inventories
            ):
                inventory_state.selected_steam_id = selected_steam_id

        refresh_result = self._refresh_inventory_from_remote(account, inventory_state)
        if refresh_result is None:
            return self._build_inventory_detail_from_snapshot(account, snapshot)

        detail_payload = {
            "account_id": str(getattr(account, "account_id", "") or ""),
            "display_name": str(getattr(account, "display_name", "") or ""),
            "selected_steam_id": getattr(snapshot, "selected_steam_id", None) if snapshot is not None else None,
            "refreshed_at": getattr(snapshot, "refreshed_at", None) if snapshot is not None else None,
            "last_error": getattr(snapshot, "last_error", None) if snapshot is not None else None,
            "inventories": self._build_inventory_rows(
                list(getattr(snapshot, "inventories", []) or []) if snapshot is not None else [],
                selected_steam_id=getattr(snapshot, "selected_steam_id", None) if snapshot is not None else None,
            ),
        }

        if refresh_result.status == "success":
            inventory_state.refresh_from_remote(list(refresh_result.inventories))
            refreshed_at = datetime.now().isoformat(timespec="seconds")
            detail_payload = {
                "account_id": str(getattr(account, "account_id", "") or ""),
                "display_name": str(getattr(account, "display_name", "") or ""),
                "selected_steam_id": inventory_state.selected_steam_id,
                "refreshed_at": refreshed_at,
                "last_error": None,
                "inventories": self._build_inventory_rows(
                    inventory_state.inventories,
                    selected_steam_id=inventory_state.selected_steam_id,
                ),
            }
            if self._inventory_snapshot_repository is not None:
                self._inventory_snapshot_repository.save(
                    account_id=str(getattr(account, "account_id", "") or ""),
                    selected_steam_id=inventory_state.selected_steam_id,
                    inventories=inventory_state.inventories,
                    refreshed_at=refreshed_at,
                    last_error=None,
                )
            return self._normalize_inventory_detail(detail_payload, account=account)

        error = refresh_result.error
        if refresh_result.status == "auth_invalid" and error:
            self._mark_account_auth_invalid_in_repository(
                account_id=str(getattr(account, "account_id", "") or ""),
                error=error,
            )
            setattr(account, "purchase_capability_state", PurchaseCapabilityState.EXPIRED)
            setattr(account, "purchase_pool_state", PurchasePoolState.PAUSED_AUTH_INVALID)
        if error is not None:
            detail_payload["last_error"] = error
        return self._normalize_inventory_detail(detail_payload, account=account)

    def list_account_center_accounts(self) -> list[dict[str, object]]:
        runtime_accounts = self._runtime_account_map()
        rows: list[dict[str, object]] = []
        for account in self._account_repository.list_accounts():
            runtime_account = runtime_accounts.get(str(getattr(account, "account_id", "") or ""))
            rows.append(self._build_account_center_row(account, runtime_account=runtime_account))
        return rows

    def update_account_purchase_config(
        self,
        *,
        account_id: str,
        purchase_disabled: bool,
        selected_steam_id: str | None,
    ) -> dict[str, object]:
        account = self._find_account(account_id)
        if account is None:
            raise KeyError(account_id)

        inventory_detail = self.get_account_inventory_detail(account_id)
        next_selected_steam_id = self._resolve_selected_steam_id(
            account=account,
            inventory_detail=inventory_detail,
            selected_steam_id=selected_steam_id,
        )
        updated_account = self._account_repository.update_account(
            account_id,
            purchase_disabled=bool(purchase_disabled),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )

        if self._sync_runtime_purchase_config(
            account_id=account_id,
            purchase_disabled=bool(purchase_disabled),
            selected_steam_id=next_selected_steam_id,
        ):
            refreshed_account = self._find_account(account_id)
            if refreshed_account is not None:
                updated_account = refreshed_account
        else:
            self._persist_selected_inventory(
                account_id=account_id,
                inventory_detail=inventory_detail,
                selected_steam_id=next_selected_steam_id,
            )

        return self._build_account_center_row(updated_account)

    def bind_query_runtime_session(
        self,
        *,
        query_config_id: str | None,
        query_config_name: str | None,
        runtime_session_id: str | None,
    ) -> None:
        if not self._has_running_runtime():
            return
        bind_runtime_session = getattr(self._runtime, "bind_query_runtime_session", None)
        if not callable(bind_runtime_session):
            return
        bind_runtime_session(
            query_config_id=query_config_id,
            query_config_name=query_config_name,
            runtime_session_id=runtime_session_id,
        )

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

    def mark_account_auth_invalid(self, *, account_id: str, error: str | None = None) -> None:
        normalized_error = str(error or "Not login")
        if self._has_running_runtime():
            mark_account_auth_invalid = getattr(self._runtime, "mark_account_auth_invalid", None)
            if callable(mark_account_auth_invalid):
                mark_account_auth_invalid(account_id=account_id, error=normalized_error)
                return
        self._mark_account_auth_invalid_in_repository(account_id=account_id, error=normalized_error)

    def _has_running_runtime(self) -> bool:
        if self._runtime is None:
            return False
        snapshot = self._runtime.snapshot()
        return bool(snapshot.get("running"))

    def _create_runtime(self, accounts: list[object]):
        if self._runtime_factory_accepts_extended_kwargs():
            return self._runtime_factory(
                accounts,
                None,
                account_repository=self._account_repository,
                inventory_snapshot_repository=self._inventory_snapshot_repository,
                inventory_refresh_gateway_factory=self._inventory_refresh_gateway_factory,
                recovery_delay_seconds_provider=self._recovery_delay_seconds_provider,
                execution_gateway_factory=self._execution_gateway_factory,
            )
        return self._runtime_factory(accounts, None)

    def _bind_runtime_callbacks(self, runtime) -> None:
        set_callbacks = getattr(runtime, "set_availability_callbacks", None)
        if callable(set_callbacks):
            set_callbacks(
                on_no_available_accounts=self._notify_no_available_accounts,
                on_accounts_available=self._notify_accounts_available,
            )

    def _notify_no_available_accounts(self) -> None:
        callback = self._on_no_available_accounts
        if not callable(callback):
            return
        try:
            callback()
        except Exception:
            return

    def _notify_accounts_available(self) -> None:
        callback = self._on_accounts_available
        if not callable(callback):
            return
        try:
            callback()
        except Exception:
            return

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
    def _build_idle_snapshot() -> dict[str, object]:
        return {
            "running": False,
            "message": "未运行",
            "started_at": None,
            "stopped_at": None,
            "queue_size": 0,
            "active_account_count": 0,
            "total_account_count": 0,
            "total_purchased_count": 0,
            "runtime_session_id": None,
            "matched_product_count": 0,
            "purchase_success_count": 0,
            "purchase_failed_count": 0,
            "recent_events": [],
            "accounts": [],
            "item_rows": [],
            "active_query_config": None,
        }

    @staticmethod
    def _normalize_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
        return {
            "running": bool(snapshot.get("running")),
            "message": str(snapshot.get("message") or ("运行中" if snapshot.get("running") else "未运行")),
            "started_at": snapshot.get("started_at"),
            "stopped_at": snapshot.get("stopped_at"),
            "queue_size": int(snapshot.get("queue_size", 0)),
            "active_account_count": int(snapshot.get("active_account_count", 0)),
            "total_account_count": int(snapshot.get("total_account_count", 0)),
            "total_purchased_count": int(snapshot.get("total_purchased_count", 0)),
            "runtime_session_id": snapshot.get("runtime_session_id"),
            "matched_product_count": int(snapshot.get("matched_product_count", 0)),
            "purchase_success_count": int(snapshot.get("purchase_success_count", 0)),
            "purchase_failed_count": int(snapshot.get("purchase_failed_count", 0)),
            "recent_events": list(snapshot.get("recent_events") or []),
            "accounts": PurchaseRuntimeService._normalize_accounts(snapshot.get("accounts")),
            "item_rows": PurchaseRuntimeService._normalize_item_rows(snapshot.get("item_rows")),
            "active_query_config": snapshot.get("active_query_config"),
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
                    "purchase_disabled": bool(raw_account.get("purchase_disabled", False)),
                    "selected_steam_id": raw_account.get("selected_steam_id"),
                    "selected_inventory_name": raw_account.get("selected_inventory_name"),
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
                    "submitted_product_count": int(raw_account.get("submitted_product_count", 0)),
                    "purchase_success_count": int(raw_account.get("purchase_success_count", 0)),
                    "purchase_failed_count": int(raw_account.get("purchase_failed_count", 0)),
                }
            )
        return normalized

    @staticmethod
    def _normalize_item_rows(raw_rows: object) -> list[dict[str, object]]:
        if not isinstance(raw_rows, list):
            return []

        normalized: list[dict[str, object]] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            normalized.append(
                {
                    "query_item_id": str(raw_row.get("query_item_id") or ""),
                    "matched_product_count": int(raw_row.get("matched_product_count", 0)),
                    "purchase_success_count": int(raw_row.get("purchase_success_count", 0)),
                    "purchase_failed_count": int(raw_row.get("purchase_failed_count", 0)),
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

    def _runtime_account_map(self) -> dict[str, dict[str, object]]:
        if not self._has_running_runtime():
            return {}
        return {
            str(account.get("account_id") or ""): dict(account)
            for account in self.get_status().get("accounts") or []
            if isinstance(account, dict)
        }

    def _build_account_center_row(
        self,
        account,
        *,
        runtime_account: dict[str, object] | None = None,
    ) -> dict[str, object]:
        account_id = str(getattr(account, "account_id", "") or "")
        inventory_detail = self.get_account_inventory_detail(account_id)
        selected_row = self._selected_inventory_row(inventory_detail)
        selected_steam_id = str(selected_row.get("steamId") or "") if selected_row is not None else ""
        selected_warehouse_text = self._selected_inventory_display_text(selected_row)
        purchase_capability_state = (
            str(runtime_account.get("purchase_capability_state") or "")
            if runtime_account is not None
            else str(getattr(account, "purchase_capability_state", "") or "")
        )
        purchase_pool_state = (
            str(runtime_account.get("purchase_pool_state") or "")
            if runtime_account is not None
            else str(getattr(account, "purchase_pool_state", "") or "")
        )
        purchase_status_code, purchase_status_text = self._build_purchase_status(
            purchase_capability_state=purchase_capability_state,
            purchase_pool_state=purchase_pool_state,
            purchase_disabled=bool(getattr(account, "purchase_disabled", False)),
            selected_row=selected_row,
        )
        proxy_url = getattr(account, "proxy_url", None) or None
        api_key = getattr(account, "api_key", None) or None
        purchase_disabled = bool(getattr(account, "purchase_disabled", False))
        return {
            "account_id": account_id,
            "display_name": str(getattr(account, "display_name", "") or account_id),
            "remark_name": getattr(account, "remark_name", None),
            "c5_nick_name": getattr(account, "c5_nick_name", None),
            "default_name": str(getattr(account, "default_name", "") or ""),
            "api_key_present": bool(api_key),
            "api_key": api_key,
            "proxy_mode": str(getattr(account, "proxy_mode", "") or "direct"),
            "proxy_url": proxy_url,
            "proxy_display": proxy_url or "直连",
            "purchase_capability_state": purchase_capability_state,
            "purchase_pool_state": purchase_pool_state,
            "purchase_disabled": purchase_disabled,
            "selected_steam_id": selected_steam_id or None,
            "selected_warehouse_text": selected_warehouse_text,
            "purchase_status_code": purchase_status_code,
            "purchase_status_text": purchase_status_text,
        }

    @staticmethod
    def _selected_inventory_row(inventory_detail: dict[str, object] | None) -> dict[str, object] | None:
        if inventory_detail is None:
            return None
        for row in inventory_detail.get("inventories") or []:
            if isinstance(row, dict) and row.get("is_selected"):
                return row
        return None

    @staticmethod
    def _build_purchase_status(
        *,
        purchase_capability_state: str,
        purchase_pool_state: str,
        purchase_disabled: bool,
        selected_row: dict[str, object] | None,
    ) -> tuple[str, str]:
        if purchase_capability_state != PurchaseCapabilityState.BOUND or purchase_pool_state == PurchasePoolState.PAUSED_AUTH_INVALID:
            return "not_logged_in", "未登录"
        if purchase_disabled:
            return "disabled", "禁用"
        if selected_row is None or not bool(selected_row.get("is_available")) or purchase_pool_state == PurchasePoolState.PAUSED_NO_INVENTORY:
            return "inventory_full", "库存已满"
        selected_text = PurchaseRuntimeService._selected_inventory_display_text(selected_row)
        return "selected_warehouse", selected_text or str(selected_row.get("steamId") or "")

    @staticmethod
    def _selected_inventory_display_text(selected_row: dict[str, object] | None) -> str | None:
        if selected_row is None:
            return None
        nickname = str(selected_row.get("nickname") or "").strip()
        if nickname:
            return nickname
        steam_id = str(selected_row.get("steamId") or "").strip()
        return steam_id or None

    def _resolve_selected_steam_id(
        self,
        *,
        account,
        inventory_detail: dict[str, object] | None,
        selected_steam_id: str | None,
    ) -> str | None:
        if selected_steam_id is None:
            return (
                str(inventory_detail.get("selected_steam_id") or "")
                if inventory_detail is not None and inventory_detail.get("selected_steam_id") is not None
                else None
            )

        capability_state = str(getattr(account, "purchase_capability_state", "") or "")
        pool_state = str(getattr(account, "purchase_pool_state", "") or "")
        if capability_state != PurchaseCapabilityState.BOUND or pool_state == PurchasePoolState.PAUSED_AUTH_INVALID:
            raise ValueError("当前账号未登录，无法设置购买仓库")

        if inventory_detail is None:
            raise ValueError("当前账号未登录，无法设置购买仓库")

        for row in inventory_detail.get("inventories") or []:
            if str(row.get("steamId") or "") != str(selected_steam_id):
                continue
            if not bool(row.get("is_available")):
                raise ValueError("目标仓库不可用，无法选中")
            return str(selected_steam_id)

        raise ValueError("目标仓库不可用，无法选中")

    def _persist_selected_inventory(
        self,
        *,
        account_id: str,
        inventory_detail: dict[str, object] | None,
        selected_steam_id: str | None,
    ) -> None:
        if self._inventory_snapshot_repository is None or selected_steam_id is None:
            return
        inventories = self._snapshot_rows_from_detail(inventory_detail)
        if inventories:
            self._inventory_snapshot_repository.save(
                account_id=account_id,
                selected_steam_id=selected_steam_id,
                inventories=inventories,
                refreshed_at=inventory_detail.get("refreshed_at") if inventory_detail is not None else None,
                last_error=inventory_detail.get("last_error") if inventory_detail is not None else None,
            )
            return
        self._inventory_snapshot_repository.update_selected_steam_id(
            account_id=account_id,
            selected_steam_id=selected_steam_id,
        )

    def _sync_runtime_purchase_config(
        self,
        *,
        account_id: str,
        purchase_disabled: bool,
        selected_steam_id: str | None,
    ) -> bool:
        if not self._has_running_runtime() or self._runtime is None:
            return False
        account_states = getattr(self._runtime, "_account_states", None)
        if not isinstance(account_states, dict):
            return False
        state = account_states.get(account_id)
        if state is None:
            return False

        state.purchase_disabled = bool(purchase_disabled)
        setattr(state.account, "purchase_disabled", state.purchase_disabled)
        if selected_steam_id is not None:
            state.inventory_state.selected_steam_id = selected_steam_id

        if state.capability_state == PurchaseCapabilityState.BOUND and state.inventory_state.selected_steam_id is not None:
            state.pool_state = PurchasePoolState.ACTIVE
            state.last_error = None
        elif state.capability_state == PurchaseCapabilityState.EXPIRED:
            state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
        else:
            state.pool_state = PurchasePoolState.PAUSED_NO_INVENTORY

        self._runtime._sync_scheduler_state(state)
        self._runtime._persist_inventory_snapshot(state, last_error=state.last_error)
        self._runtime._sync_account_repository_state(state)
        return True

    @staticmethod
    def _snapshot_rows_from_detail(inventory_detail: dict[str, object] | None) -> list[dict[str, object]]:
        if inventory_detail is None:
            return []
        return [
            {
                "steamId": str(row.get("steamId") or ""),
                "nickname": (str(row.get("nickname") or "").strip() or None),
                "inventory_num": int(row.get("inventory_num", 0)),
                "inventory_max": int(row.get("inventory_max", 0)),
                "remaining_capacity": int(row.get("remaining_capacity", 0)),
            }
            for row in inventory_detail.get("inventories") or []
            if isinstance(row, dict)
        ]

    def _mark_account_auth_invalid_in_repository(self, *, account_id: str, error: str) -> None:
        update_account = getattr(self._account_repository, "update_account", None)
        if not callable(update_account):
            return
        try:
            update_account(
                account_id,
                purchase_capability_state=PurchaseCapabilityState.EXPIRED,
                purchase_pool_state=PurchasePoolState.PAUSED_AUTH_INVALID,
                last_error=error,
                updated_at=datetime.now().isoformat(timespec="seconds"),
            )
        except Exception:
            return

    def _get_runtime_inventory_detail(self, account_id: str, *, account) -> dict[str, object] | None:
        if not self._has_running_runtime():
            return None
        get_detail = getattr(self._runtime, "get_account_inventory_detail", None)
        if not callable(get_detail):
            return None
        detail = get_detail(account_id)
        if detail is None:
            return None
        return self._normalize_inventory_detail(detail, account=account)

    def _refresh_runtime_inventory_detail(self, account_id: str, *, account) -> dict[str, object] | None:
        if not self._has_running_runtime():
            return None
        refresh_detail = getattr(self._runtime, "refresh_account_inventory_detail", None)
        if not callable(refresh_detail):
            return None
        detail = refresh_detail(account_id)
        if detail is None:
            return None
        return self._normalize_inventory_detail(detail, account=account)

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
            },
            account=account,
        )

    @staticmethod
    def _normalize_inventory_detail(detail: dict[str, object], *, account=None) -> dict[str, object]:
        auto_refresh_due_at = detail.get("auto_refresh_due_at")
        if auto_refresh_due_at is None and account is not None:
            auto_refresh_due_at = getattr(account, "purchase_recovery_due_at", None)
        auto_refresh_remaining_seconds = detail.get("auto_refresh_remaining_seconds")
        if auto_refresh_remaining_seconds is None:
            auto_refresh_remaining_seconds = PurchaseRuntimeService._remaining_seconds_until(auto_refresh_due_at)
        return {
            "account_id": str(detail.get("account_id") or ""),
            "display_name": str(detail.get("display_name") or detail.get("account_id") or ""),
            "selected_steam_id": detail.get("selected_steam_id"),
            "refreshed_at": detail.get("refreshed_at"),
            "last_error": detail.get("last_error"),
            "auto_refresh_due_at": auto_refresh_due_at,
            "auto_refresh_remaining_seconds": (
                max(int(auto_refresh_remaining_seconds), 0)
                if auto_refresh_remaining_seconds is not None
                else None
            ),
            "inventories": [
                {
                    "steamId": str(row.get("steamId") or ""),
                    "nickname": (str(row.get("nickname") or "").strip() or None),
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
    def _remaining_seconds_until(value: str | datetime | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            due_at = value
        else:
            try:
                due_at = datetime.fromisoformat(str(value))
            except ValueError:
                return None
        return max(int((due_at - datetime.now()).total_seconds()), 0)

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
                    "nickname": (str(inventory.get("nickname") or "").strip() or None),
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
        _legacy_settings=None,
        *,
        account_repository=None,
        inventory_snapshot_repository=None,
        inventory_refresh_gateway_factory: InventoryRefreshGatewayFactory | None = None,
        recovery_delay_seconds_provider: RecoveryDelaySecondsProvider | None = None,
        execution_gateway_factory: ExecutionGatewayFactory | None = None,
    ):
        return _DefaultPurchaseRuntime(
            accounts,
            _legacy_settings,
            account_repository=account_repository,
            inventory_snapshot_repository=inventory_snapshot_repository,
            inventory_refresh_gateway_factory=inventory_refresh_gateway_factory,
            recovery_delay_seconds_provider=recovery_delay_seconds_provider,
            execution_gateway_factory=execution_gateway_factory or PurchaseExecutionGateway,
        )


@dataclass(slots=True)
class _RuntimeAccountState:
    account: object
    inventory_state: InventoryState
    worker: AccountPurchaseWorker
    capability_state: str
    pool_state: str
    purchase_disabled: bool = False
    last_error: str | None = None
    total_purchased_count: int = 0
    inventory_refreshed_at: str | None = None
    recovery_due_at: datetime | None = None

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
        _legacy_settings=None,
        *,
        account_repository=None,
        inventory_snapshot_repository=None,
        inventory_refresh_gateway_factory: InventoryRefreshGatewayFactory | None,
        recovery_delay_seconds_provider: RecoveryDelaySecondsProvider | None,
        execution_gateway_factory: ExecutionGatewayFactory,
    ) -> None:
        self._accounts = list(accounts)
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
        self._on_no_available_accounts = None
        self._on_accounts_available = None
        self._active_account_count = 0
        self._drain_signal = threading.Event()
        self._drain_stop_signal = threading.Event()
        self._drain_thread: threading.Thread | None = None
        self._stats_aggregator = PurchaseStatsAggregator()

    def set_availability_callbacks(
        self,
        *,
        on_no_available_accounts=None,
        on_accounts_available=None,
    ) -> None:
        self._on_no_available_accounts = on_no_available_accounts
        self._on_accounts_available = on_accounts_available

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
        self._stats_aggregator = PurchaseStatsAggregator()
        self._stats_aggregator.start()
        self._stats_aggregator.reset(
            runtime_session_id=None,
            query_config_id=None,
            query_config_name=None,
        )
        self._initialize_accounts()
        self._active_account_count = self._scheduler.active_account_count()
        self._drain_stop_signal = threading.Event()
        self._drain_signal = threading.Event()
        self._start_drain_worker()

    def stop(self) -> None:
        self._running = False
        self._cancel_all_recovery_checks()
        self._drain_stop_signal.set()
        self._drain_signal.set()
        drain_thread = self._drain_thread
        if drain_thread is not None and drain_thread.is_alive():
            drain_thread.join(timeout=0.2)
        self._drain_thread = None
        self._stats_aggregator.stop()
        self._stopped_at = datetime.now().isoformat(timespec="seconds")

    def bind_query_runtime_session(
        self,
        *,
        query_config_id: str | None,
        query_config_name: str | None,
        runtime_session_id: str | None,
    ) -> None:
        current_stats = self._stats_aggregator.snapshot()
        if (
            current_stats.get("runtime_session_id") == runtime_session_id
            and current_stats.get("query_config_id") == query_config_id
        ):
            return
        self._hit_inbox = PurchaseHitInbox()
        self._scheduler.clear_queue()
        self._stats_aggregator.reset(
            runtime_session_id=runtime_session_id,
            query_config_id=query_config_id,
            query_config_name=query_config_name,
        )

    async def accept_query_hit_async(self, hit: dict[str, object]) -> dict[str, object]:
        if self._scheduler.active_account_count() <= 0:
            self._push_event(
                hit,
                status="ignored_no_available_accounts",
                message="当前没有可用购买账号，命中已忽略",
            )
            return {"accepted": False, "status": "ignored_no_available_accounts"}

        self._stats_aggregator.enqueue_hit(hit)
        batch = self._hit_inbox.accept(hit)
        if batch is None:
            self._push_event(hit, status="duplicate_filtered", message="重复命中已忽略")
            return {"accepted": False, "status": "duplicate_filtered"}

        self._scheduler.submit(batch)
        self._push_event(hit, status="queued", message="已转入购买")
        self._signal_drain_worker()
        return {"accepted": True, "status": "queued"}

    def snapshot(self) -> dict[str, object]:
        stats_snapshot = self._stats_aggregator.snapshot()
        account_stats = {
            str(row.get("account_id") or ""): row
            for row in stats_snapshot.get("accounts", [])
            if isinstance(row, dict)
        }
        return {
            "running": self._running,
            "message": "运行中" if self._running else "未运行",
            "started_at": self._started_at if self._running else None,
            "stopped_at": self._stopped_at if not self._running else None,
            "queue_size": self._scheduler.queue_size(),
            "active_account_count": self._scheduler.active_account_count() if self._running else 0,
            "total_account_count": self._scheduler.total_account_count() if self._running else 0,
            "total_purchased_count": self._total_purchased_count,
            "runtime_session_id": stats_snapshot.get("runtime_session_id"),
            "matched_product_count": int(stats_snapshot.get("matched_product_count", 0)),
            "purchase_success_count": int(stats_snapshot.get("purchase_success_count", 0)),
            "purchase_failed_count": int(stats_snapshot.get("purchase_failed_count", 0)),
            "recent_events": list(self._recent_events),
            "accounts": [
                {
                    "account_id": state.account_id,
                    "display_name": state.display_name,
                    "purchase_capability_state": state.capability_state,
                    "purchase_pool_state": state.pool_state,
                    "purchase_disabled": state.purchase_disabled,
                    "purchase_recovery_due_at": self._format_recovery_due_at(state.recovery_due_at),
                    "selected_steam_id": state.inventory_state.selected_steam_id,
                    "selected_inventory_name": PurchaseRuntimeService._selected_inventory_display_text(
                        state.inventory_state.selected_inventory
                    ),
                    "selected_inventory_remaining_capacity": self._selected_inventory_remaining_capacity(state),
                    "selected_inventory_max": self._selected_inventory_max(state),
                    "last_error": state.last_error,
                    "total_purchased_count": state.total_purchased_count,
                    "submitted_product_count": int(
                        account_stats.get(state.account_id, {}).get("submitted_product_count", 0)
                    ),
                    "purchase_success_count": int(
                        account_stats.get(state.account_id, {}).get("purchase_success_count", 0)
                    ),
                    "purchase_failed_count": int(
                        account_stats.get(state.account_id, {}).get("purchase_failed_count", 0)
                    ),
                }
                for state in self._account_states.values()
            ],
            "item_rows": list(stats_snapshot.get("item_rows", [])),
        }

    def get_account_inventory_detail(self, account_id: str) -> dict[str, object] | None:
        state = self._account_states.get(account_id)
        if state is None:
            return None
        return self._build_account_inventory_detail(state)

    def refresh_account_inventory_detail(self, account_id: str) -> dict[str, object] | None:
        state = self._account_states.get(account_id)
        if state is None:
            return None

        state.recovery_due_at = None
        refresh_result = self._refresh_inventory_from_remote(state.account, state.inventory_state)
        if refresh_result is None:
            return self._build_account_inventory_detail(state)

        if refresh_result.status == "success":
            state.capability_state = PurchaseCapabilityState.BOUND
            state.inventory_state.refresh_from_remote(list(refresh_result.inventories))
            state.last_error = None
            state.pool_state = (
                PurchasePoolState.ACTIVE
                if state.inventory_state.selected_steam_id is not None
                else PurchasePoolState.PAUSED_NO_INVENTORY
            )
        elif refresh_result.status == "auth_invalid":
            state.capability_state = PurchaseCapabilityState.EXPIRED
            state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
            state.last_error = refresh_result.error
        else:
            if state.capability_state != PurchaseCapabilityState.EXPIRED:
                state.capability_state = PurchaseCapabilityState.BOUND
                state.pool_state = PurchasePoolState.PAUSED_NO_INVENTORY
            else:
                state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
            state.last_error = refresh_result.error

        self._sync_scheduler_state(state)
        self._persist_inventory_snapshot(state, last_error=state.last_error)
        self._sync_account_repository_state(state)
        return self._build_account_inventory_detail(state)

    def _build_account_inventory_detail(self, state: _RuntimeAccountState) -> dict[str, object]:
        auto_refresh_due_at = self._format_recovery_due_at(state.recovery_due_at)
        return {
            "account_id": state.account_id,
            "display_name": state.display_name,
            "selected_steam_id": state.inventory_state.selected_steam_id,
            "refreshed_at": state.inventory_refreshed_at,
            "last_error": state.last_error,
            "auto_refresh_due_at": auto_refresh_due_at,
            "auto_refresh_remaining_seconds": PurchaseRuntimeService._remaining_seconds_until(state.recovery_due_at),
            "inventories": PurchaseRuntimeService._build_inventory_rows(
                state.inventory_state.inventories,
                selected_steam_id=state.inventory_state.selected_steam_id,
            ),
        }

    def mark_account_auth_invalid(self, *, account_id: str, error: str | None = None) -> None:
        state = self._account_states.get(account_id)
        if state is None:
            return
        normalized_error = str(error or "Not login")
        state.capability_state = PurchaseCapabilityState.EXPIRED
        state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
        state.last_error = normalized_error
        setattr(state.account, "purchase_capability_state", state.capability_state)
        setattr(state.account, "purchase_pool_state", state.pool_state)
        setattr(state.account, "last_error", state.last_error)
        self._sync_scheduler_state(state)
        self._persist_inventory_snapshot(state, last_error=state.last_error)
        self._sync_account_repository_state(state)
        self._push_runtime_event(
            state,
            status="auth_invalid",
            message=normalized_error or "登录已失效",
        )

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
            purchase_disabled = bool(getattr(account, "purchase_disabled", False))
            recovery_due_at = self._parse_recovery_due_at(
                getattr(account, "purchase_recovery_due_at", None)
            )
            refresh_result = None if purchase_disabled else self._refresh_inventory_from_remote(account, inventory_state)
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
                and not purchase_disabled
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
                purchase_disabled=purchase_disabled,
                last_error=last_error,
                inventory_refreshed_at=inventory_refreshed_at,
                recovery_due_at=recovery_due_at,
            )
            self._account_states[account_id] = state
            self._scheduler.register_account(account_id, available=available)
            if state.pool_state == PurchasePoolState.PAUSED_NO_INVENTORY and not state.purchase_disabled:
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
        if str(getattr(account, "purchase_capability_state", "")) != PurchaseCapabilityState.BOUND:
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

            try:
                batch = self._scheduler.pop_next_batch()
            except IndexError:
                return
            outcome = await state.worker.process(batch)
            self._apply_worker_outcome(state, batch, outcome)

    def _apply_worker_outcome(self, state: _RuntimeAccountState, batch, outcome) -> None:
        state.capability_state = outcome.capability_state
        state.pool_state = outcome.pool_state
        state.last_error = outcome.error
        stats_status = str(outcome.status)
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
            stats_status = "paused_no_inventory"
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

        self._stats_aggregator.enqueue_outcome(
            account_id=state.account_id,
            batch=batch,
            status=stats_status,
            purchased_count=int(outcome.purchased_count),
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
        previous_active_account_count = self._scheduler.active_account_count()
        if state.purchase_disabled:
            if state.pool_state == PurchasePoolState.PAUSED_NO_INVENTORY and state.capability_state == PurchaseCapabilityState.BOUND:
                if state.recovery_due_at is None:
                    state.recovery_due_at = self._build_next_recovery_due_at()
            else:
                state.recovery_due_at = None
            self._scheduler.mark_unavailable(state.account_id, reason="purchase_disabled")
            self._cancel_recovery_check(state.account_id)
        elif state.pool_state == PurchasePoolState.ACTIVE:
            self._scheduler.mark_available(state.account_id)
            self._cancel_recovery_check(state.account_id)
            state.recovery_due_at = None
        elif state.pool_state == PurchasePoolState.PAUSED_AUTH_INVALID:
            self._scheduler.mark_unavailable(state.account_id, reason="auth_invalid")
            self._cancel_recovery_check(state.account_id)
            state.recovery_due_at = None
        else:
            self._scheduler.mark_no_inventory(state.account_id)
            self._schedule_recovery_check(state.account_id)
        self._handle_active_account_count_change(previous_active_account_count)

    def _handle_active_account_count_change(self, previous_active_account_count: int) -> None:
        current_active_account_count = self._scheduler.active_account_count()
        self._active_account_count = current_active_account_count
        if previous_active_account_count > 0 and current_active_account_count == 0:
            cleared = self._scheduler.clear_queue()
            if cleared > 0:
                self._push_scheduler_event(
                    status="backlog_cleared_no_purchase_accounts",
                    message=f"没有可用购买账号，已清空 {cleared} 条积压任务",
                )
            self._notify_no_available_accounts()
            return
        if previous_active_account_count == 0 and current_active_account_count > 0:
            if self._scheduler.queue_size() > 0:
                self._signal_drain_worker()
            self._notify_accounts_available()

    def _notify_no_available_accounts(self) -> None:
        callback = self._on_no_available_accounts
        if not callable(callback):
            return
        try:
            callback()
        except Exception:
            return

    def _notify_accounts_available(self) -> None:
        callback = self._on_accounts_available
        if not callable(callback):
            return
        try:
            callback()
        except Exception:
            return

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
        if state.recovery_due_at is None:
            state.recovery_due_at = self._build_next_recovery_due_at()
        if state.purchase_disabled:
            return
        delay_seconds = max((state.recovery_due_at - datetime.now()).total_seconds(), 0.0)
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
        if state.purchase_disabled:
            return

        state.recovery_due_at = None
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

    def _build_next_recovery_due_at(self) -> datetime:
        delay_seconds = max(float(self._recovery_delay_seconds_provider()), 0.0)
        return datetime.now() + timedelta(seconds=delay_seconds)

    @staticmethod
    def _parse_recovery_due_at(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    @staticmethod
    def _format_recovery_due_at(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

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
        setattr(state.account, "purchase_capability_state", state.capability_state)
        setattr(state.account, "purchase_pool_state", state.pool_state)
        setattr(state.account, "last_error", state.last_error)
        setattr(state.account, "purchase_disabled", state.purchase_disabled)
        recovery_due_at = self._format_recovery_due_at(state.recovery_due_at)
        setattr(state.account, "purchase_recovery_due_at", recovery_due_at)
        try:
            self._account_repository.update_account(
                state.account_id,
                purchase_capability_state=state.capability_state,
                purchase_pool_state=state.pool_state,
                last_error=state.last_error,
                purchase_disabled=state.purchase_disabled,
                purchase_recovery_due_at=recovery_due_at,
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
                "query_config_id": None,
                "query_item_id": None,
                "runtime_session_id": None,
                "external_item_id": None,
                "product_url": None,
                "product_list": [],
                "total_price": 0.0,
                "total_wear_sum": None,
                "source_mode_type": "",
            },
        )
        del self._recent_events[self._RECENT_EVENT_LIMIT :]

    def _push_scheduler_event(self, *, status: str, message: str) -> None:
        self._recent_events.insert(
            0,
            {
                "occurred_at": datetime.now().isoformat(timespec="seconds"),
                "status": status,
                "message": message,
                "account_id": "",
                "account_display_name": "",
                "selected_steam_id": None,
                "query_item_name": "",
                "query_config_id": None,
                "query_item_id": None,
                "runtime_session_id": None,
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
                "query_config_id": getattr(batch, "query_config_id", None),
                "query_item_id": getattr(batch, "query_item_id", None),
                "runtime_session_id": getattr(batch, "runtime_session_id", None),
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
                "query_config_id": str(hit.get("query_config_id") or "") or None,
                "query_item_id": str(hit.get("query_item_id") or "") or None,
                "runtime_session_id": str(hit.get("runtime_session_id") or "") or None,
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

    def _start_drain_worker(self) -> None:
        if self._drain_thread is not None and self._drain_thread.is_alive():
            return

        def runner() -> None:
            self._drain_worker_loop()

        self._drain_thread = threading.Thread(
            target=runner,
            name="purchase-runtime-drain",
            daemon=True,
        )
        self._drain_thread.start()

    def _signal_drain_worker(self) -> None:
        if not self._running or self._scheduler.active_account_count() <= 0:
            return
        self._drain_signal.set()

    def _drain_worker_loop(self) -> None:
        while not self._drain_stop_signal.is_set():
            self._drain_signal.wait()
            self._drain_signal.clear()
            if self._drain_stop_signal.is_set():
                return

            while (
                self._running
                and self._scheduler.active_account_count() > 0
                and self._scheduler.queue_size() > 0
            ):
                try:
                    asyncio.run(self._drain_scheduler())
                except Exception as exc:  # pragma: no cover - defensive background worker guard
                    self._push_scheduler_event(
                        status="drain_worker_error",
                        message=f"后台购买线程异常: {exc}",
                    )
                    break


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
