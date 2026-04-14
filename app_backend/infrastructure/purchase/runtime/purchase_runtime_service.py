from __future__ import annotations

import asyncio
import inspect
import random
import threading
import time
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from inspect import Parameter, signature
from queue import Empty, Queue

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter
from app_backend.infrastructure.query.runtime.api_key_status import (
    build_api_query_status,
    build_browser_query_status,
)
from app_backend.infrastructure.purchase.runtime.account_purchase_worker import AccountPurchaseWorker
from app_backend.infrastructure.purchase.runtime.inventory_state import InventoryState
from app_backend.infrastructure.purchase.runtime.purchase_hit_inbox import PurchaseHitInbox
from app_backend.infrastructure.purchase.runtime.proxy_bucket import normalize_proxy_bucket_key
from app_backend.infrastructure.purchase.runtime.purchase_scheduler import PurchaseScheduler
from app_backend.infrastructure.purchase.runtime.purchase_execution_gateway import PurchaseExecutionGateway
from app_backend.infrastructure.purchase.runtime.purchase_stats_aggregator import PurchaseStatsAggregator
from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult, PurchaseWorkerOutcome
from app_backend.infrastructure.stats.runtime.stats_events import (
    PurchaseCreateOrderStatsEvent,
    PurchaseSubmitOrderStatsEvent,
)
from app_backend.application.use_cases.get_purchase_runtime_status import GetPurchaseRuntimeStatusUseCase
from app_backend.api.schemas.purchase_runtime import PurchaseRuntimeStatusResponse

RuntimeFactory = Callable[..., object]
ExecutionGatewayFactory = Callable[[], object]
InventoryRefreshGatewayFactory = Callable[[], object]
RecoveryDelaySecondsProvider = Callable[[], float]

_DISPATCH_STOP = object()
_DISPATCH_SKIPPED = object()
_REMOTE_REFRESH_UNSET = object()
_POST_PROCESS_STOP = object()
_HIT_INTAKE_STOP = object()


@dataclass(slots=True)
class _DispatchJob:
    batch: object
    generation: int
    dispatch_key: tuple[int, int] | None = None


@dataclass(slots=True)
class _PostProcessOutcomeJob:
    account_id: str
    batch: object
    outcome: PurchaseWorkerOutcome
    generation: int
    postprocess_epoch: int


class _AccountDispatchRunner:
    def __init__(
        self,
        *,
        account_id: str,
        worker: AccountPurchaseWorker,
        on_complete,
        should_process=None,
        max_concurrent: int = 1,
    ) -> None:
        self._account_id = str(account_id)
        self._worker = worker
        self._on_complete = on_complete
        self._should_process = should_process
        self._max_concurrent = max(int(max_concurrent), 1)
        self._queue: Queue[object] = Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wakeup_event: asyncio.Event | None = None
        self._active_tasks: dict[asyncio.Task, str] = {}
        self._state_lock = threading.Lock()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"purchase-account-dispatch-{self._account_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, timeout: float = 0.2) -> None:
        self._stop_event.set()
        self._queue.put(_DISPATCH_STOP)
        self._notify_loop()
        self.cancel_current_task()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None

    def submit(self, *, batch, generation: int) -> None:
        dispatch_key = (int(generation), id(batch))
        self._queue.put(_DispatchJob(batch=batch, generation=int(generation), dispatch_key=dispatch_key))
        self._notify_loop()

    def cancel_current_task(self) -> None:
        with self._state_lock:
            loop = self._loop
            cancellable_tasks = [
                task
                for task, phase in self._active_tasks.items()
                if phase != "gateway"
            ]
        if loop is None or not cancellable_tasks:
            return
        for task in cancellable_tasks:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                return

    def update_max_concurrent(self, max_concurrent: int) -> None:
        with self._state_lock:
            self._max_concurrent = max(int(max_concurrent), 1)
        self._notify_loop()

    def discard_pending_jobs(self) -> list[_DispatchJob]:
        dropped_jobs: list[_DispatchJob] = []
        stop_markers = 0
        while True:
            try:
                queued_item = self._queue.get_nowait()
            except Empty:
                break
            if queued_item is _DISPATCH_STOP:
                stop_markers += 1
                continue
            if isinstance(queued_item, _DispatchJob):
                dropped_jobs.append(queued_item)
        for _ in range(stop_markers):
            self._queue.put(_DISPATCH_STOP)
        return dropped_jobs

    def mark_gateway_execute_start(self, task: asyncio.Task | None) -> None:
        if task is None:
            return
        with self._state_lock:
            if task in self._active_tasks:
                self._active_tasks[task] = "gateway"

    def _notify_loop(self) -> None:
        with self._state_lock:
            loop = self._loop
            wakeup_event = self._wakeup_event
        if loop is None or wakeup_event is None:
            return
        try:
            loop.call_soon_threadsafe(wakeup_event.set)
        except RuntimeError:
            return

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._state_lock:
            self._loop = loop
        try:
            loop.run_until_complete(self._run_async())
        finally:
            try:
                loop.run_until_complete(self._worker.cleanup())
            except Exception:
                pass
            with self._state_lock:
                self._loop = None
                self._active_tasks = {}
            loop.close()

    async def _run_async(self) -> None:
        running_tasks: set[asyncio.Task] = set()
        wakeup_event = asyncio.Event()
        with self._state_lock:
            self._wakeup_event = wakeup_event

        def track_job(job: _DispatchJob) -> bool:
            if job is _DISPATCH_STOP:
                self._stop_event.set()
                return False
            task = asyncio.create_task(self._run_job(job))
            running_tasks.add(task)
            with self._state_lock:
                self._active_tasks[task] = "processing"
            task.add_done_callback(lambda done_task, current_job=job: self._handle_job_result(done_task, current_job))
            return True

        try:
            while True:
                if not self._stop_event.is_set():
                    while len(running_tasks) < self._max_concurrent:
                        try:
                            job = self._queue.get_nowait()
                        except Empty:
                            break
                        if not track_job(job):
                            break

                if self._stop_event.is_set() and not running_tasks:
                    return

                waiters: set[asyncio.Task] = set(running_tasks)
                wakeup_waiter: asyncio.Task | None = None
                should_wait_for_wakeup = (
                    not self._stop_event.is_set()
                    and len(running_tasks) < self._max_concurrent
                    and self._queue.empty()
                )
                if should_wait_for_wakeup:
                    if wakeup_event.is_set():
                        wakeup_event.clear()
                        continue
                    wakeup_waiter = asyncio.create_task(wakeup_event.wait())
                    waiters.add(wakeup_waiter)

                if not waiters:
                    await wakeup_event.wait()
                    wakeup_event.clear()
                    continue

                done, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
                running_tasks.difference_update(done)

                if wakeup_waiter is not None:
                    if wakeup_waiter in done:
                        wakeup_event.clear()
                    else:
                        wakeup_waiter.cancel()
                        try:
                            await wakeup_waiter
                        except asyncio.CancelledError:
                            pass
        finally:
            with self._state_lock:
                if self._wakeup_event is wakeup_event:
                    self._wakeup_event = None

    async def _run_job(self, job: _DispatchJob):
        should_process = self._should_process
        if callable(should_process) and not should_process(int(job.generation)):
            return _DISPATCH_SKIPPED
        current_task = asyncio.current_task()
        return await self._worker.process(
            job.batch,
            generation=int(job.generation),
            on_gateway_execute_start=lambda: self.mark_gateway_execute_start(current_task),
        )

    def _handle_job_result(self, task: asyncio.Task, job: _DispatchJob) -> None:
        with self._state_lock:
            phase = self._active_tasks.pop(task, None)
        try:
            outcome = task.result()
        except BaseException as exc:  # pragma: no cover - defensive background worker guard
            cancelled_before_gateway = isinstance(exc, asyncio.CancelledError) and phase == "processing"
            outcome = _DISPATCH_SKIPPED if cancelled_before_gateway else exc
        self._on_complete(
            account_id=self._account_id,
            batch=job.batch,
            outcome=outcome,
            generation=job.generation,
            dispatch_key=job.dispatch_key,
        )


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
        max_inflight_per_account: int | None = None,
        queued_hit_timeout_seconds: float = 2.0,
        stats_sink=None,
        runtime_update_hub=None,
        query_runtime_service=None,
    ) -> None:
        self._account_repository = account_repository
        self._settings_repository = settings_repository
        self._inventory_snapshot_repository = inventory_snapshot_repository
        self._inventory_refresh_gateway_factory = inventory_refresh_gateway_factory
        self._recovery_delay_seconds_provider = recovery_delay_seconds_provider
        self._execution_gateway_factory = execution_gateway_factory or PurchaseExecutionGateway
        self._runtime_factory = runtime_factory or self._build_default_runtime
        self._max_inflight_per_account = (
            max(int(max_inflight_per_account), 1)
            if max_inflight_per_account is not None
            else None
        )
        self._queued_hit_timeout_seconds = max(float(queued_hit_timeout_seconds), 0.0)
        self._stats_sink = stats_sink
        self._runtime_update_hub = runtime_update_hub
        self._query_runtime_service = query_runtime_service
        self._runtime = None
        self._on_no_available_accounts = None
        self._on_accounts_available = None
        self._runtime_update_pending = False
        self._runtime_update_thread: threading.Thread | None = None
        self._runtime_update_thread_lock = threading.Lock()
        self._runtime_lifecycle_lock = threading.RLock()

    def start(self) -> tuple[bool, str]:
        with self._runtime_lifecycle_lock:
            if self._has_running_runtime():
                return False, "已有购买运行时在运行"

            accounts = list(self._account_repository.list_accounts())
            runtime = self._create_runtime(accounts)
            self._bind_runtime_callbacks(runtime)
            runtime.start()
            self._runtime = runtime
            self._publish_runtime_update()
        return True, "购买运行时已启动"

    def stop(self) -> tuple[bool, str]:
        with self._runtime_lifecycle_lock:
            if not self._has_running_runtime():
                self._runtime = None
                return False, "当前没有运行中的购买运行时"

            runtime = self._runtime
            if runtime is None:
                self._runtime = None
                return False, "当前没有运行中的购买运行时"
            runtime.stop()
            self._runtime = None
            self._publish_runtime_update()
        return True, "购买运行时已停止"

    def get_status(self) -> dict[str, object]:
        runtime = self._runtime
        if runtime is None:
            self._runtime = None
            return self._build_idle_snapshot()
        snapshot = self._snapshot_runtime_state(runtime)
        if not bool(snapshot.get("running")):
            if self._runtime is runtime:
                self._runtime = None
            return self._build_idle_snapshot()
        return self._normalize_snapshot(snapshot)

    def has_available_accounts(self) -> bool:
        runtime = self._runtime
        if runtime is None:
            return False
        snapshot = self._snapshot_runtime_state(runtime)
        if not bool(snapshot.get("running")):
            return False
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

    def set_query_runtime_service(self, query_runtime_service) -> None:
        self._query_runtime_service = query_runtime_service

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
            detail = self._normalize_inventory_detail(detail_payload, account=account)
            self._publish_runtime_update()
            return detail

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
        detail = self._normalize_inventory_detail(detail_payload, account=account)
        self._publish_runtime_update()
        return detail

    def list_account_center_accounts(self) -> list[dict[str, object]]:
        runtime_accounts = self._runtime_account_map()
        rows: list[dict[str, object]] = []
        for account in self._account_repository.list_accounts():
            runtime_account = runtime_accounts.get(str(getattr(account, "account_id", "") or ""))
            rows.append(self._build_account_center_row(account, runtime_account=runtime_account))
        return rows

    def get_account_center_account(self, account_id: str) -> dict[str, object] | None:
        account = self._find_account(account_id)
        if account is None:
            return None
        runtime_account = self._runtime_account_map().get(str(getattr(account, "account_id", "") or ""))
        return self._build_account_center_row(account, runtime_account=runtime_account)

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

        row = self._build_account_center_row(updated_account)
        self._publish_runtime_update()
        return row

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
        self._publish_runtime_update()

    def accept_query_hit(self, hit: dict[str, object]) -> dict[str, object]:
        return _run_coroutine_sync(self.accept_query_hit_async(hit))

    def enqueue_query_hit(self, hit: dict[str, object]) -> dict[str, object]:
        with self._runtime_lifecycle_lock:
            if not self._has_running_runtime():
                self._runtime = None
                return {"accepted": False, "status": "ignored_not_running"}

            runtime = self._runtime
            enqueue_query_hit = getattr(runtime, "enqueue_query_hit", None)
            if callable(enqueue_query_hit):
                return dict(enqueue_query_hit(hit))

            accept_query_hit = getattr(runtime, "accept_query_hit", None)
            if not callable(accept_query_hit):
                return {"accepted": False, "status": "ignored_not_supported"}
            return dict(accept_query_hit(hit))

    async def accept_query_hit_async(self, hit: dict[str, object]) -> dict[str, object]:
        with self._runtime_lifecycle_lock:
            if not self._has_running_runtime():
                self._runtime = None
                return {"accepted": False, "status": "ignored_not_running"}

            runtime = self._runtime
            accept_query_hit = getattr(runtime, "accept_query_hit_async", None)
            if callable(accept_query_hit):
                return dict(await accept_query_hit(hit))

            accept_query_hit = getattr(runtime, "accept_query_hit", None)
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
        self._publish_runtime_update()

    def _publish_runtime_update(self) -> None:
        if self._runtime_update_hub is None:
            return
        try:
            with self._runtime_lifecycle_lock:
                payload = self._build_runtime_update_payload()
                self._runtime_update_hub.publish(
                    event="purchase_runtime.updated",
                    payload=payload,
                )
        except Exception:
            return

    def _build_runtime_update_payload(self) -> dict[str, object]:
        snapshot = GetPurchaseRuntimeStatusUseCase(
            self,
            self._query_runtime_service,
        ).execute()
        return PurchaseRuntimeStatusResponse.model_validate(snapshot).model_dump(mode="json")

    def _has_running_runtime(self) -> bool:
        runtime = self._runtime
        if runtime is None:
            return False
        snapshot = self._snapshot_runtime_state(runtime)
        return bool(snapshot.get("running"))

    def _create_runtime(self, accounts: list[object]):
        current_settings = self._get_purchase_runtime_settings()
        if self._runtime_factory_accepts_extended_kwargs():
            return self._runtime_factory(
                accounts,
                None,
                account_repository=self._account_repository,
                settings_repository=self._settings_repository,
                inventory_snapshot_repository=self._inventory_snapshot_repository,
                inventory_refresh_gateway_factory=self._inventory_refresh_gateway_factory,
                recovery_delay_seconds_provider=self._recovery_delay_seconds_provider,
                execution_gateway_factory=self._execution_gateway_factory,
                per_batch_ip_fanout_limit=int(current_settings["per_batch_ip_fanout_limit"]),
                max_inflight_per_account=int(current_settings["max_inflight_per_account"]),
                queued_hit_timeout_seconds=self._queued_hit_timeout_seconds,
                stats_sink=self._stats_sink,
            )
        return self._runtime_factory(accounts, None)

    def apply_purchase_runtime_settings(
        self,
        *,
        per_batch_ip_fanout_limit: int,
        max_inflight_per_account: int,
    ) -> str:
        runtime = self._runtime
        if runtime is None or not self._has_running_runtime():
            return "skipped"
        apply_settings = getattr(runtime, "apply_purchase_runtime_settings", None)
        if not callable(apply_settings):
            return "skipped"
        return str(
            apply_settings(
                per_batch_ip_fanout_limit=per_batch_ip_fanout_limit,
                max_inflight_per_account=max_inflight_per_account,
            )
            or "skipped"
        )

    def _bind_runtime_callbacks(self, runtime) -> None:
        set_callbacks = getattr(runtime, "set_availability_callbacks", None)
        if callable(set_callbacks):
            set_callbacks(
                on_no_available_accounts=self._notify_no_available_accounts,
                on_accounts_available=self._notify_accounts_available,
            )
        set_state_change_callback = getattr(runtime, "set_state_change_callback", None)
        if callable(set_state_change_callback):
            set_state_change_callback(self._schedule_runtime_update_publish)

    def _schedule_runtime_update_publish(self) -> None:
        if self._runtime_update_hub is None:
            return
        worker_to_start: threading.Thread | None = None
        with self._runtime_update_thread_lock:
            self._runtime_update_pending = True
            worker = self._runtime_update_thread
            if worker is None or not worker.is_alive():
                worker = threading.Thread(
                    target=self._drain_runtime_update_publishes,
                    name="purchase-runtime-update-publisher",
                    daemon=True,
                )
                self._runtime_update_thread = worker
                worker_to_start = worker
        if worker_to_start is not None:
            worker_to_start.start()

    def _drain_runtime_update_publishes(self) -> None:
        while True:
            with self._runtime_update_thread_lock:
                if not self._runtime_update_pending:
                    self._runtime_update_thread = None
                    return
                self._runtime_update_pending = False
            try:
                self._publish_runtime_update()
            except Exception:
                continue

    @staticmethod
    def _runtime_state_guard(runtime):
        state_lock = getattr(runtime, "_state_lock", None)
        if state_lock is None:
            return nullcontext()
        return state_lock

    @classmethod
    def _snapshot_runtime_state(cls, runtime) -> dict[str, object]:
        with cls._runtime_state_guard(runtime):
            snapshot = runtime.snapshot()
        if not isinstance(snapshot, dict):
            return {}
        return snapshot

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
                "per_batch_ip_fanout_limit",
                "max_inflight_per_account",
                "queued_hit_timeout_seconds",
                "stats_sink",
            }:
                return True
        return False

    def _get_purchase_runtime_settings(self) -> dict[str, int]:
        repository = self._settings_repository
        settings_payload = {
            "per_batch_ip_fanout_limit": 1,
            "max_inflight_per_account": 3,
        }
        if repository is not None:
            get_settings = getattr(repository, "get", None)
            if callable(get_settings):
                try:
                    runtime_settings = get_settings()
                except Exception:
                    runtime_settings = None
                purchase_settings = dict(getattr(runtime_settings, "purchase_settings_json", {}) or {})
                try:
                    settings_payload["per_batch_ip_fanout_limit"] = max(
                        int(purchase_settings.get("per_batch_ip_fanout_limit", 1) or 1),
                        1,
                    )
                except (TypeError, ValueError):
                    settings_payload["per_batch_ip_fanout_limit"] = 1
                try:
                    settings_payload["max_inflight_per_account"] = max(
                        int(purchase_settings.get("max_inflight_per_account", 3) or 3),
                        1,
                    )
                except (TypeError, ValueError):
                    settings_payload["max_inflight_per_account"] = 3
        if self._max_inflight_per_account is not None:
            settings_payload["max_inflight_per_account"] = max(int(self._max_inflight_per_account), 1)
        return settings_payload

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
                    "source_mode_stats": PurchaseRuntimeService._normalize_item_hit_sources(
                        raw_row.get("source_mode_stats")
                    ),
                    "recent_hit_sources": PurchaseRuntimeService._normalize_item_hit_sources(
                        raw_row.get("recent_hit_sources")
                    ),
                }
            )
        return normalized

    @staticmethod
    def _normalize_item_hit_sources(raw_rows: object) -> list[dict[str, object]]:
        if not isinstance(raw_rows, list):
            return []

        normalized: list[dict[str, object]] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            normalized.append(
                {
                    "mode_type": str(raw_row.get("mode_type") or ""),
                    "hit_count": int(raw_row.get("hit_count", 0)),
                    "last_hit_at": raw_row.get("last_hit_at"),
                    "account_id": raw_row.get("account_id"),
                    "account_display_name": raw_row.get("account_display_name"),
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
        browser_proxy_url = getattr(account, "browser_proxy_url", None) or None
        api_proxy_url = getattr(account, "api_proxy_url", None) or None
        browser_public_ip = getattr(account, "browser_public_ip", None)
        api_public_ip = getattr(account, "api_public_ip", None)
        api_key = getattr(account, "api_key", None) or None
        (
            api_query_enabled,
            api_query_status_code,
            api_query_status_text,
            api_query_disable_reason_code,
            api_query_disable_reason_text,
        ) = build_api_query_status(
            api_key=api_key,
            new_api_enabled=bool(getattr(account, "new_api_enabled", False)),
            fast_api_enabled=bool(getattr(account, "fast_api_enabled", False)),
            api_query_disabled_reason=getattr(account, "api_query_disabled_reason", None),
            proxy_public_ip=getattr(account, "api_public_ip", None),
        )
        (
            browser_query_enabled,
            browser_query_status_code,
            browser_query_status_text,
            browser_query_disable_reason_code,
            browser_query_disable_reason_text,
        ) = build_browser_query_status(
            token_enabled=bool(getattr(account, "token_enabled", False)),
            browser_query_disabled_reason=getattr(account, "browser_query_disabled_reason", None),
            cookie_raw=getattr(account, "cookie_raw", None),
            last_error=getattr(account, "last_error", None),
            purchase_capability_state=purchase_capability_state,
            purchase_pool_state=purchase_pool_state,
        )
        purchase_disabled = bool(getattr(account, "purchase_disabled", False))
        return {
            "account_id": account_id,
            "display_name": str(getattr(account, "display_name", "") or account_id),
            "remark_name": getattr(account, "remark_name", None),
            "c5_nick_name": getattr(account, "c5_nick_name", None),
            "default_name": str(getattr(account, "default_name", "") or ""),
            "api_key_present": bool(api_key),
            "api_query_enabled": api_query_enabled,
            "api_query_status_code": api_query_status_code,
            "api_query_status_text": api_query_status_text,
            "api_query_disable_reason_code": api_query_disable_reason_code,
            "api_query_disable_reason_text": api_query_disable_reason_text,
            "browser_query_enabled": browser_query_enabled,
            "browser_query_status_code": browser_query_status_code,
            "browser_query_status_text": browser_query_status_text,
            "browser_query_disable_reason_code": browser_query_disable_reason_code,
            "browser_query_disable_reason_text": browser_query_disable_reason_text,
            "api_key": api_key,
            "browser_proxy_mode": str(getattr(account, "browser_proxy_mode", "") or "direct"),
            "browser_proxy_url": browser_proxy_url,
            "browser_proxy_display": browser_proxy_url or browser_public_ip or "未获取IP",
            "api_proxy_mode": str(getattr(account, "api_proxy_mode", "") or "direct"),
            "api_proxy_url": api_proxy_url,
            "api_proxy_display": api_proxy_url or api_public_ip or "未获取IP",
            "proxy_mode": str(getattr(account, "api_proxy_mode", "") or "direct"),
            "proxy_url": api_proxy_url,
            "proxy_display": api_proxy_url or api_public_ip or "未获取IP",
            "api_ip_allow_list": getattr(account, "api_ip_allow_list", None),
            "browser_public_ip": browser_public_ip,
            "api_public_ip": api_public_ip,
            "balance_amount": getattr(account, "balance_amount", None),
            "balance_source": getattr(account, "balance_source", None),
            "balance_updated_at": getattr(account, "balance_updated_at", None),
            "balance_refresh_after_at": getattr(account, "balance_refresh_after_at", None),
            "balance_last_error": getattr(account, "balance_last_error", None),
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
        runtime = self._runtime
        account_states = getattr(self._runtime, "_account_states", None)
        if not isinstance(account_states, dict):
            return False
        state_lock = getattr(self._runtime, "_state_lock", None)
        if state_lock is None:
            return False
        effects: _DispatchCompletionEffects | None = None
        with state_lock:
            state = account_states.get(account_id)
            if state is None:
                return False

            state.purchase_disabled = bool(purchase_disabled)
            setattr(state.account, "purchase_disabled", state.purchase_disabled)
            available_inventory_ids = {
                str(inventory.get("steamId") or "")
                for inventory in state.inventory_state.available_inventories
                if str(inventory.get("steamId") or "")
            }
            previous_selected_steam_id = state.inventory_state.selected_steam_id
            if selected_steam_id is not None:
                candidate_selected_steam_id = str(selected_steam_id or "").strip() or None
                if candidate_selected_steam_id in available_inventory_ids:
                    state.inventory_state.selected_steam_id = candidate_selected_steam_id
                elif previous_selected_steam_id in available_inventory_ids:
                    state.inventory_state.selected_steam_id = previous_selected_steam_id
                else:
                    state.inventory_state.selected_steam_id = None

            selected_inventory = state.inventory_state.selected_inventory
            selected_inventory_is_available = (
                selected_inventory is not None
                and str(selected_inventory.get("steamId") or "") in available_inventory_ids
            )
            if state.capability_state == PurchaseCapabilityState.BOUND and selected_inventory_is_available:
                state.pool_state = PurchasePoolState.ACTIVE
                state.last_error = None
            elif state.capability_state == PurchaseCapabilityState.EXPIRED:
                state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
            else:
                state.pool_state = PurchasePoolState.PAUSED_NO_INVENTORY

            scheduler_effects = runtime._sync_scheduler_state(state)
            effects = _DispatchCompletionEffects(
                account_id=state.account_id,
                expected_state_version=state.state_version,
                expected_generation=getattr(runtime, "_dispatch_generation", None),
                scheduler_effects=scheduler_effects,
                snapshot_payload=runtime._build_inventory_snapshot_payload(state, last_error=state.last_error),
                account_repository_payload=runtime._build_account_repository_payload(state),
                notify_state_change=True,
            )

        if effects is not None:
            runtime._run_dispatch_completion_effects(effects)
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
                purchase_recovery_due_at=None,
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
                    "is_available": remaining >= int(min_capacity_threshold),
                }
            )
        return rows

    @staticmethod
    def _build_default_runtime(
        accounts: list[object],
        _legacy_settings=None,
        *,
        account_repository=None,
        settings_repository=None,
        inventory_snapshot_repository=None,
        inventory_refresh_gateway_factory: InventoryRefreshGatewayFactory | None = None,
        recovery_delay_seconds_provider: RecoveryDelaySecondsProvider | None = None,
        execution_gateway_factory: ExecutionGatewayFactory | None = None,
        per_batch_ip_fanout_limit: int = 1,
        max_inflight_per_account: int = 3,
        queued_hit_timeout_seconds: float = 2.0,
        stats_sink=None,
    ):
        return _DefaultPurchaseRuntime(
            accounts,
            _legacy_settings,
            account_repository=account_repository,
            settings_repository=settings_repository,
            inventory_snapshot_repository=inventory_snapshot_repository,
            inventory_refresh_gateway_factory=inventory_refresh_gateway_factory,
            recovery_delay_seconds_provider=recovery_delay_seconds_provider,
            execution_gateway_factory=execution_gateway_factory or PurchaseExecutionGateway,
            per_batch_ip_fanout_limit=per_batch_ip_fanout_limit,
            max_inflight_per_account=max_inflight_per_account,
            queued_hit_timeout_seconds=queued_hit_timeout_seconds,
            stats_sink=stats_sink,
        )


@dataclass(slots=True)
class _RuntimeAccountState:
    account: object
    inventory_state: InventoryState
    worker: AccountPurchaseWorker
    capability_state: str
    pool_state: str
    purchase_disabled: bool = False
    busy: bool = False
    last_error: str | None = None
    total_purchased_count: int = 0
    inventory_refreshed_at: str | None = None
    recovery_due_at: datetime | None = None
    state_version: int = 0
    postprocess_epoch: int = 0

    @property
    def account_id(self) -> str:
        return str(getattr(self.account, "account_id"))

    @property
    def display_name(self) -> str:
        return str(getattr(self.account, "display_name", None) or getattr(self.account, "default_name", "") or "")


@dataclass(slots=True)
class _SchedulerStateEffects:
    should_signal_drain: bool = False
    scheduler_event: dict[str, str] | None = None
    notify_no_available_accounts: bool = False
    notify_accounts_available: bool = False
    cancel_recovery_account_ids: list[str] = field(default_factory=list)
    schedule_recovery_account_ids: list[str] = field(default_factory=list)
    clear_backlog_when_no_accounts: bool = False


@dataclass(slots=True)
class _DispatchCompletionEffects:
    account_id: str | None = None
    expected_state_version: int | None = None
    expected_generation: int | None = None
    scheduler_effects: _SchedulerStateEffects | None = None
    snapshot_payload: dict[str, object] | None = None
    account_repository_payload: dict[str, object] | None = None
    stats_outcome_payload: dict[str, object] | None = None
    stats_forward_payload: dict[str, object] | None = None
    notify_state_change: bool = False


@dataclass(slots=True)
class _TrackedDispatchBatch:
    batch: object | None = None
    remaining_jobs: int = 0
    had_non_skipped_outcome: bool = False


class _DefaultPurchaseRuntime:
    _RECENT_EVENT_LIMIT = 500

    def __init__(
        self,
        accounts: list[object],
        _legacy_settings=None,
        *,
        account_repository=None,
        settings_repository=None,
        inventory_snapshot_repository=None,
        inventory_refresh_gateway_factory: InventoryRefreshGatewayFactory | None,
        recovery_delay_seconds_provider: RecoveryDelaySecondsProvider | None,
        execution_gateway_factory: ExecutionGatewayFactory,
        per_batch_ip_fanout_limit: int = 1,
        max_inflight_per_account: int = 3,
        queued_hit_timeout_seconds: float = 2.0,
        stats_sink=None,
    ) -> None:
        self._accounts = list(accounts)
        self._account_repository = account_repository
        self._settings_repository = settings_repository
        self._inventory_snapshot_repository = inventory_snapshot_repository
        self._inventory_refresh_gateway_factory = inventory_refresh_gateway_factory
        self._recovery_delay_seconds_provider = (
            recovery_delay_seconds_provider or self._default_recovery_delay_seconds
        )
        self._execution_gateway_factory = execution_gateway_factory
        self._per_batch_ip_fanout_limit = max(int(per_batch_ip_fanout_limit), 1)
        self._max_inflight_per_account = max(int(max_inflight_per_account), 1)
        self._queued_hit_timeout_seconds = max(float(queued_hit_timeout_seconds), 0.0)
        self._stats_sink = stats_sink
        self._running = False
        self._started_at: str | None = None
        self._stopped_at: str | None = None
        self._recent_events: list[dict[str, object]] = []
        self._scheduler = PurchaseScheduler()
        self._hit_inbox = PurchaseHitInbox(now_provider=self._queue_now)
        self._account_states: dict[str, _RuntimeAccountState] = {}
        self._total_purchased_count = 0
        self._recovery_timers: dict[str, threading.Timer] = {}
        self._recovery_lock = threading.RLock()
        self._on_no_available_accounts = None
        self._on_accounts_available = None
        self._state_change_callback = None
        self._active_account_count = 0
        self._drain_signal = threading.Event()
        self._drain_stop_signal = threading.Event()
        self._drain_thread: threading.Thread | None = None
        self._dispatch_runners: dict[str, _AccountDispatchRunner] = {}
        self._state_lock = threading.RLock()
        self._dispatch_generation = 0
        self._tracked_dispatch_batches: dict[tuple[int, int], _TrackedDispatchBatch] = {}
        self._stats_aggregator = PurchaseStatsAggregator()
        self._pending_purchase_settings: dict[str, int] | None = None
        self._hit_intake_queue: Queue[object] = Queue()
        self._hit_intake_stop_signal = threading.Event()
        self._hit_intake_thread: threading.Thread | None = None
        self._post_process_queue: Queue[object] = Queue()
        self._post_process_stop_signal = threading.Event()
        self._post_process_thread: threading.Thread | None = None

    def set_availability_callbacks(
        self,
        *,
        on_no_available_accounts=None,
        on_accounts_available=None,
    ) -> None:
        self._on_no_available_accounts = on_no_available_accounts
        self._on_accounts_available = on_accounts_available

    def set_state_change_callback(self, callback) -> None:
        self._state_change_callback = callback

    def start(self) -> None:
        self._cancel_all_recovery_checks()
        self._running = True
        self._dispatch_generation += 1
        self._started_at = datetime.now().isoformat(timespec="seconds")
        self._stopped_at = None
        self._recent_events = []
        self._scheduler = PurchaseScheduler()
        self._hit_inbox = PurchaseHitInbox(now_provider=self._queue_now)
        self._account_states = {}
        self._total_purchased_count = 0
        self._recovery_timers = {}
        self._dispatch_runners = {}
        self._tracked_dispatch_batches = {}
        self._stats_aggregator = PurchaseStatsAggregator()
        self._pending_purchase_settings = None
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
        self._hit_intake_queue = Queue()
        self._hit_intake_stop_signal = threading.Event()
        self._post_process_queue = Queue()
        self._post_process_stop_signal = threading.Event()
        self._start_drain_worker()
        self._start_hit_intake_worker()
        self._start_post_process_worker()

    def stop(self) -> None:
        with self._state_lock:
            self._dispatch_generation += 1
            for state in self._account_states.values():
                state.state_version += 1
                state.postprocess_epoch += 1
            self._running = False
            self._cancel_all_recovery_checks()
            self._drain_stop_signal.set()
            self._drain_signal.set()
            self._hit_intake_stop_signal.set()
            self._post_process_stop_signal.set()
        drain_thread = self._drain_thread
        if drain_thread is not None and drain_thread.is_alive():
            drain_thread.join(timeout=0.2)
        self._drain_thread = None
        self._stop_hit_intake_worker()
        self._stop_post_process_worker()
        for dispatch_runner in list(self._dispatch_runners.values()):
            dispatch_runner.stop(timeout=0.2)
        self._dispatch_runners = {}
        self._tracked_dispatch_batches = {}
        self._stats_aggregator.stop()
        self._stopped_at = datetime.now().isoformat(timespec="seconds")

    def bind_query_runtime_session(
        self,
        *,
        query_config_id: str | None,
        query_config_name: str | None,
        runtime_session_id: str | None,
    ) -> None:
        with self._state_lock:
            current_stats = self._stats_aggregator.snapshot()
            if (
                current_stats.get("runtime_session_id") == runtime_session_id
                and current_stats.get("query_config_id") == query_config_id
            ):
                return
            self._dispatch_generation += 1
            for state in self._account_states.values():
                state.postprocess_epoch += 1
            for dispatch_runner in self._dispatch_runners.values():
                dispatch_runner.cancel_current_task()
            self._hit_inbox = PurchaseHitInbox(now_provider=self._queue_now)
            self._drop_expired_backlog()
            self._forget_batches(self._scheduler.clear_queue_batches())
            self._recent_events = []
            self._stats_aggregator.reset(
                runtime_session_id=runtime_session_id,
                query_config_id=query_config_id,
                query_config_name=query_config_name,
            )

    def enqueue_query_hit(self, hit: dict[str, object]) -> dict[str, object]:
        payload = self._clone_hit_payload(hit)
        with self._state_lock:
            if not self._running:
                self._push_event(
                    payload,
                    status="ignored_not_running",
                    message="购买运行时未启动，命中已忽略",
                )
                return {"accepted": False, "status": "ignored_not_running"}
            self._hit_intake_queue.put(payload)
        return {"accepted": True, "status": "queued"}

    async def accept_query_hit_async(self, hit: dict[str, object]) -> dict[str, object]:
        payload = self._clone_hit_payload(hit)
        return self._accept_query_hit_now(payload)

    def _accept_query_hit_now(self, hit: dict[str, object]) -> dict[str, object]:
        with self._state_lock:
            if not self._running:
                self._push_event(
                    hit,
                    status="ignored_not_running",
                    message="购买运行时未启动，命中已忽略",
                )
                return {"accepted": False, "status": "ignored_not_running"}
            if self._scheduler.active_account_count() <= 0:
                self._push_event(
                    hit,
                    status="ignored_no_available_accounts",
                    message="当前没有可用购买账号，命中已忽略",
                )
                return {"accepted": False, "status": "ignored_no_available_accounts"}

            self._stats_aggregator.enqueue_hit(hit)
            self._drop_expired_backlog()
            batch = self._hit_inbox.accept(hit)
            if batch is None:
                self._push_event(hit, status="duplicate_filtered", message="重复命中已忽略")
                return {"accepted": False, "status": "duplicate_filtered"}
            claimed_account_ids = self._scheduler.claim_idle_accounts_by_bucket(
                limit_per_bucket=self._get_per_batch_ip_fanout_limit(),
            )
            if not claimed_account_ids:
                if self._scheduler.active_account_count() <= 0:
                    self._forget_batches([batch])
                    self._push_event(
                        hit,
                        status="ignored_no_available_accounts",
                        message="当前没有可用购买账号，命中已忽略",
                    )
                    return {"accepted": False, "status": "ignored_no_available_accounts"}
                self._scheduler.submit(batch)
                self._signal_drain_worker()
                self._push_event(hit, status="queued", message="当前购买账号忙碌，命中已进入等待队列")
                return {"accepted": True, "status": "queued"}

            started_account_ids = [
                account_id
                for account_id in claimed_account_ids
                if self._start_account_dispatch(account_id, batch)
            ]
            if not started_account_ids:
                if self._scheduler.active_account_count() <= 0:
                    self._forget_batches([batch])
                    self._push_event(
                        hit,
                        status="ignored_no_available_accounts",
                        message="当前没有可用购买账号，命中已忽略",
                    )
                    return {"accepted": False, "status": "ignored_no_available_accounts"}
                self._scheduler.submit(batch)
                self._signal_drain_worker()
                self._push_event(hit, status="queued", message="当前购买账号忙碌，命中已进入等待队列")
                return {"accepted": True, "status": "queued"}
            self._push_event(
                hit,
                status="queued",
                message=f"已派发 {len(started_account_ids)} 个购买账号",
            )
            return {"accepted": True, "status": "queued"}

    def snapshot(self) -> dict[str, object]:
        self._drop_expired_backlog()
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
        with self._state_lock:
            state = self._account_states.get(account_id)
            if state is None:
                return None
            return self._build_account_inventory_detail(state)

    def refresh_account_inventory_detail(self, account_id: str) -> dict[str, object] | None:
        effects: _DispatchCompletionEffects | None = None
        with self._state_lock:
            state = self._account_states.get(account_id)
            if state is None:
                return None
            expected_state_version = state.state_version
            state.recovery_due_at = None
            account = state.account
            inventory_state = state.inventory_state

        refresh_result = self._refresh_inventory_from_remote(account, inventory_state)

        with self._state_lock:
            state = self._account_states.get(account_id)
            if state is None:
                return None
            if state.state_version != expected_state_version:
                return self._build_account_inventory_detail(state)
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
                self._invalidate_post_process_locked(state)
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

            scheduler_effects = self._sync_scheduler_state(state)
            effects = _DispatchCompletionEffects(
                account_id=state.account_id,
                expected_state_version=state.state_version,
                expected_generation=self._dispatch_generation,
                scheduler_effects=scheduler_effects,
                snapshot_payload=self._build_inventory_snapshot_payload(state, last_error=state.last_error),
                account_repository_payload=self._build_account_repository_payload(state),
                notify_state_change=True,
            )
            detail = self._build_account_inventory_detail(state)

        if effects is not None:
            self._run_dispatch_completion_effects(effects)
        return detail

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
        effects: _DispatchCompletionEffects | None = None
        dispatch_runner = None
        normalized_error = str(error or "Not login")
        with self._state_lock:
            state = self._account_states.get(account_id)
            if state is None:
                return
            self._invalidate_post_process_locked(state)
            state.capability_state = PurchaseCapabilityState.EXPIRED
            state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
            state.last_error = normalized_error
            setattr(state.account, "purchase_capability_state", state.capability_state)
            setattr(state.account, "purchase_pool_state", state.pool_state)
            setattr(state.account, "last_error", state.last_error)
            dispatch_runner = self._dispatch_runners.get(account_id)
            scheduler_effects = self._sync_scheduler_state(state)
            effects = _DispatchCompletionEffects(
                account_id=state.account_id,
                expected_state_version=state.state_version,
                expected_generation=self._dispatch_generation,
                scheduler_effects=scheduler_effects,
                snapshot_payload=self._build_inventory_snapshot_payload(state, last_error=state.last_error),
                account_repository_payload=self._build_account_repository_payload(state),
                notify_state_change=True,
            )
            self._push_runtime_event(
                state,
                status="auth_invalid",
                message=normalized_error or "登录已失效",
                notify=False,
            )

        dropped_jobs: list[_DispatchJob] = []
        if dispatch_runner is not None:
            dispatch_runner.cancel_current_task()
            dropped_jobs = dispatch_runner.discard_pending_jobs()
        for _ in dropped_jobs:
            self._scheduler.release_account(account_id)
        batches_to_forget: list[object] = []
        with self._state_lock:
            for job in dropped_jobs:
                batches_to_forget.extend(
                    self._forget_tracked_dispatch_locked(
                        getattr(job, "dispatch_key", None),
                        batch=getattr(job, "batch", None),
                    )
                )
        self._forget_batches(batches_to_forget)
        if effects is not None:
            self._run_dispatch_completion_effects(effects)

    def apply_purchase_runtime_settings(
        self,
        *,
        per_batch_ip_fanout_limit: int,
        max_inflight_per_account: int,
    ) -> str:
        normalized_settings = {
            "per_batch_ip_fanout_limit": max(int(per_batch_ip_fanout_limit), 1),
            "max_inflight_per_account": max(int(max_inflight_per_account), 1),
        }
        should_signal_drain = False
        with self._state_lock:
            if self._scheduler.total_inflight_count() > 0:
                self._pending_purchase_settings = normalized_settings
                return "pending"
            self._pending_purchase_settings = None
            should_signal_drain = self._apply_purchase_settings_locked(normalized_settings)
        if should_signal_drain:
            self._signal_drain_worker()
        return "applied"

    def _initialize_accounts(self) -> None:
        self._max_inflight_per_account = max(int(self._max_inflight_per_account), 1)
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
            worker = AccountPurchaseWorker(
                account=account,
                inventory_state=inventory_state,
                execution_gateway=self._execution_gateway_factory(),
                runtime_account=RuntimeAccountAdapter(account),
                should_process_generation=lambda generation, current_account_id=account_id: self._should_process_account_dispatch(
                    current_account_id,
                    generation,
                ),
            )
            state = _RuntimeAccountState(
                account=account,
                inventory_state=inventory_state,
                worker=worker,
                capability_state=capability_state,
                pool_state=pool_state,
                purchase_disabled=purchase_disabled,
                last_error=last_error,
                inventory_refreshed_at=inventory_refreshed_at,
                recovery_due_at=recovery_due_at,
            )
            self._account_states[account_id] = state
            dispatch_runner = _AccountDispatchRunner(
                account_id=account_id,
                worker=state.worker,
                on_complete=self._finish_account_dispatch,
                should_process=lambda generation, current_account_id=account_id: self._should_process_account_dispatch(
                    current_account_id,
                    generation,
                ),
                max_concurrent=self._max_inflight_per_account,
            )
            dispatch_runner.start()
            self._dispatch_runners[account_id] = dispatch_runner
            self._scheduler.register_account(
                account_id,
                available=available,
                bucket_key=self._account_bucket_key(account),
                max_inflight=self._max_inflight_per_account,
            )
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

    @staticmethod
    def _success_requires_remote_reconcile(
        state: _RuntimeAccountState,
        outcome: PurchaseWorkerOutcome,
    ) -> bool:
        inventory_preview = state.inventory_state.clone()
        transition = inventory_preview.apply_purchase_success(
            purchased_count=int(outcome.purchased_count),
            selected_steam_id=outcome.selected_steam_id,
        )
        return transition.requires_remote_refresh

    def _apply_worker_outcome(
        self,
        state: _RuntimeAccountState,
        batch,
        outcome,
        *,
        reconcile_refresh_result: InventoryRefreshResult | None | object = _REMOTE_REFRESH_UNSET,
    ) -> _DispatchCompletionEffects:
        effects = _DispatchCompletionEffects()
        effects.account_id = state.account_id
        state.capability_state = outcome.capability_state
        state.pool_state = outcome.pool_state
        state.busy = False
        state.last_error = None if self._should_clear_account_error_for_outcome(outcome) else outcome.error
        stats_status = str(outcome.status)
        if outcome.status == "success":
            transition = state.inventory_state.apply_purchase_success(
                purchased_count=int(outcome.purchased_count),
                selected_steam_id=outcome.selected_steam_id,
            )
            state.total_purchased_count += int(outcome.purchased_count)
            self._total_purchased_count += int(outcome.purchased_count)
            state.pool_state = (
                PurchasePoolState.PAUSED_NO_INVENTORY
                if transition.became_unavailable
                else PurchasePoolState.ACTIVE
            )
            event_status = "success"
            event_message = f"购买成功 {outcome.purchased_count} 件"
            if transition.requires_remote_refresh:
                event_status, event_message = self._reconcile_inventory_after_success(
                    state,
                    purchased_count=int(outcome.purchased_count),
                    refresh_result=reconcile_refresh_result,
                )
            effects.scheduler_effects = self._sync_scheduler_state(state)
            effects.snapshot_payload = self._build_inventory_snapshot_payload(state, last_error=state.last_error)
            self._push_event_from_batch(
                batch,
                status=event_status,
                message=event_message,
                notify=False,
            )
        elif outcome.status == "auth_invalid":
            self._invalidate_post_process_locked(state)
            effects.scheduler_effects = self._sync_scheduler_state(state)
            effects.snapshot_payload = self._build_inventory_snapshot_payload(state, last_error=outcome.error)
            self._push_event_from_batch(
                batch,
                status="auth_invalid",
                message=outcome.error or "登录已失效",
                debug_details=self._build_purchase_debug_details(outcome),
                notify=False,
            )
        elif outcome.status == "payment_success_no_items":
            effects.scheduler_effects = self._sync_scheduler_state(state)
            effects.snapshot_payload = self._build_inventory_snapshot_payload(state, last_error=state.last_error)
            self._push_event_from_batch(
                batch,
                status="payment_success_no_items",
                message=self._build_payment_success_no_items_message(outcome.error),
                debug_details=self._build_purchase_debug_details(outcome),
                notify=False,
            )
        elif outcome.status == "no_inventory":
            stats_status = "paused_no_inventory"
            effects.scheduler_effects = self._sync_scheduler_state(state)
            effects.snapshot_payload = self._build_inventory_snapshot_payload(state, last_error=outcome.error)
            self._push_event_from_batch(
                batch,
                status="paused_no_inventory",
                message=outcome.error or "没有可用仓库",
                debug_details=self._build_purchase_debug_details(outcome),
                notify=False,
            )
        else:
            self._push_event_from_batch(
                batch,
                status=str(outcome.status),
                message=outcome.error or "购买失败",
                debug_details=self._build_purchase_debug_details(outcome),
                notify=False,
            )

        effects.account_repository_payload = self._build_account_repository_payload(state)
        effects.stats_outcome_payload = {
            "account_id": state.account_id,
            "batch": batch,
            "status": stats_status,
            "purchased_count": int(outcome.purchased_count),
        }
        effects.stats_forward_payload = {
            "account_id": state.account_id,
            "account_display_name": state.display_name,
            "batch": batch,
            "outcome": outcome,
        }
        effects.expected_generation = self._dispatch_generation
        effects.expected_state_version = state.state_version
        effects.notify_state_change = True
        return effects

    @staticmethod
    def _should_clear_account_error_for_outcome(outcome) -> bool:
        return str(getattr(outcome, "status", "") or "") in {"item_unavailable", "payment_success_no_items"}

    def _forward_stats_events(self, *, account_id: str, account_display_name: str, batch, outcome) -> None:
        if self._stats_sink is None:
            return

        create_order_latency_ms = getattr(outcome, "create_order_latency_ms", None)
        submit_order_latency_ms = getattr(outcome, "submit_order_latency_ms", None)
        submitted_count = max(int(getattr(outcome, "submitted_count", 0) or 0), 0)

        if create_order_latency_ms is not None:
            create_status = "success" if submit_order_latency_ms is not None else str(outcome.status)
            self._emit_stats_event(
                PurchaseCreateOrderStatsEvent(
                    timestamp=datetime.now().isoformat(timespec="seconds"),
                    runtime_session_id=getattr(batch, "runtime_session_id", None),
                    query_config_id=getattr(batch, "query_config_id", None),
                    query_item_id=getattr(batch, "query_item_id", None),
                    external_item_id=str(getattr(batch, "external_item_id", "") or ""),
                    rule_fingerprint=self._build_rule_fingerprint(batch),
                    detail_min_wear=getattr(batch, "detail_min_wear", None),
                    detail_max_wear=getattr(batch, "detail_max_wear", None),
                    max_price=getattr(batch, "max_price", None),
                    item_name=str(getattr(batch, "query_item_name", "") or "") or None,
                    product_url=getattr(batch, "product_url", None),
                    account_id=account_id,
                    account_display_name=account_display_name,
                    create_order_latency_ms=float(create_order_latency_ms),
                    submitted_count=submitted_count,
                    status=create_status,
                    error=None if create_status == "success" else outcome.error,
                )
            )

        if submit_order_latency_ms is None:
            return

        success_count = min(max(int(outcome.purchased_count), 0), submitted_count)
        failed_count = max(submitted_count - success_count, 0)
        self._emit_stats_event(
            PurchaseSubmitOrderStatsEvent(
                timestamp=datetime.now().isoformat(timespec="seconds"),
                runtime_session_id=getattr(batch, "runtime_session_id", None),
                query_config_id=getattr(batch, "query_config_id", None),
                query_item_id=getattr(batch, "query_item_id", None),
                external_item_id=str(getattr(batch, "external_item_id", "") or ""),
                rule_fingerprint=self._build_rule_fingerprint(batch),
                detail_min_wear=getattr(batch, "detail_min_wear", None),
                detail_max_wear=getattr(batch, "detail_max_wear", None),
                max_price=getattr(batch, "max_price", None),
                item_name=str(getattr(batch, "query_item_name", "") or "") or None,
                product_url=getattr(batch, "product_url", None),
                account_id=account_id,
                account_display_name=account_display_name,
                submit_order_latency_ms=float(submit_order_latency_ms),
                submitted_count=submitted_count,
                success_count=success_count,
                failed_count=failed_count,
                status=str(outcome.status),
                error=outcome.error,
            )
        )

    def _emit_stats_event(self, event: object) -> None:
        if self._stats_sink is None:
            return
        try:
            result = self._stats_sink(event)
            if inspect.isawaitable(result):
                _run_coroutine_sync(result)
        except Exception:
            return

    @staticmethod
    def _build_rule_fingerprint(batch) -> str:
        return "|".join(
            [
                "" if getattr(batch, "detail_min_wear", None) is None else str(getattr(batch, "detail_min_wear", None)),
                "" if getattr(batch, "detail_max_wear", None) is None else str(getattr(batch, "detail_max_wear", None)),
                "" if getattr(batch, "max_price", None) is None else str(getattr(batch, "max_price", None)),
            ]
        )

    def _reconcile_inventory_after_success(
        self,
        state: _RuntimeAccountState,
        *,
        purchased_count: int,
        refresh_result: InventoryRefreshResult | None | object = _REMOTE_REFRESH_UNSET,
    ) -> tuple[str, str]:
        if refresh_result is _REMOTE_REFRESH_UNSET:
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
            self._invalidate_post_process_locked(state)
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

    def _sync_scheduler_state(self, state: _RuntimeAccountState) -> _SchedulerStateEffects:
        previous_active_account_count = self._scheduler.active_account_count()
        effects = _SchedulerStateEffects()
        if state.purchase_disabled:
            if state.pool_state == PurchasePoolState.PAUSED_NO_INVENTORY and state.capability_state == PurchaseCapabilityState.BOUND:
                if state.recovery_due_at is None:
                    state.recovery_due_at = self._build_next_recovery_due_at()
            else:
                state.recovery_due_at = None
            self._scheduler.mark_unavailable(state.account_id, reason="purchase_disabled")
            effects.cancel_recovery_account_ids.append(state.account_id)
        elif state.capability_state != PurchaseCapabilityState.BOUND:
            state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
            self._scheduler.mark_unavailable(state.account_id, reason="auth_invalid")
            effects.cancel_recovery_account_ids.append(state.account_id)
            state.recovery_due_at = None
        elif state.pool_state == PurchasePoolState.ACTIVE:
            self._scheduler.mark_available(state.account_id)
            effects.cancel_recovery_account_ids.append(state.account_id)
            state.recovery_due_at = None
        elif state.pool_state == PurchasePoolState.PAUSED_AUTH_INVALID:
            self._scheduler.mark_unavailable(state.account_id, reason="auth_invalid")
            effects.cancel_recovery_account_ids.append(state.account_id)
            state.recovery_due_at = None
        else:
            if state.recovery_due_at is None:
                state.recovery_due_at = self._build_next_recovery_due_at()
            self._scheduler.mark_no_inventory(state.account_id)
            effects.schedule_recovery_account_ids.append(state.account_id)
        state.state_version += 1
        active_effects = self._handle_active_account_count_change(previous_active_account_count)
        effects.should_signal_drain = effects.should_signal_drain or active_effects.should_signal_drain
        effects.notify_no_available_accounts = (
            effects.notify_no_available_accounts or active_effects.notify_no_available_accounts
        )
        effects.notify_accounts_available = (
            effects.notify_accounts_available or active_effects.notify_accounts_available
        )
        effects.clear_backlog_when_no_accounts = (
            effects.clear_backlog_when_no_accounts or active_effects.clear_backlog_when_no_accounts
        )
        if active_effects.scheduler_event is not None:
            effects.scheduler_event = active_effects.scheduler_event
        effects.cancel_recovery_account_ids.extend(active_effects.cancel_recovery_account_ids)
        effects.schedule_recovery_account_ids.extend(active_effects.schedule_recovery_account_ids)
        return effects

    def _get_per_batch_ip_fanout_limit(self) -> int:
        return max(int(self._per_batch_ip_fanout_limit), 1)

    def _apply_purchase_settings_locked(self, purchase_settings: dict[str, int]) -> bool:
        self._per_batch_ip_fanout_limit = max(int(purchase_settings["per_batch_ip_fanout_limit"]), 1)
        self._max_inflight_per_account = max(int(purchase_settings["max_inflight_per_account"]), 1)
        for account_id, dispatch_runner in self._dispatch_runners.items():
            self._scheduler.update_account_max_inflight(
                account_id,
                max_inflight=self._max_inflight_per_account,
            )
            dispatch_runner.update_max_concurrent(self._max_inflight_per_account)
        return self._scheduler.queue_size() > 0

    def _apply_pending_purchase_settings_if_idle_locked(self) -> bool:
        pending_settings = self._pending_purchase_settings
        if pending_settings is None:
            return False
        if self._scheduler.total_inflight_count() > 0:
            return False
        self._pending_purchase_settings = None
        return self._apply_purchase_settings_locked(pending_settings)

    @staticmethod
    def _account_bucket_key(account: object) -> str:
        return normalize_proxy_bucket_key(
            proxy_mode=str(getattr(account, "browser_proxy_mode", "") or "direct"),
            proxy_url=getattr(account, "browser_proxy_url", None),
        )

    def _can_start_account_dispatch_locked(self, state: _RuntimeAccountState, generation: int) -> bool:
        if not self._running or int(generation) != self._dispatch_generation:
            return False
        if state.purchase_disabled:
            return False
        if state.capability_state != PurchaseCapabilityState.BOUND:
            return False
        return state.pool_state == PurchasePoolState.ACTIVE

    def _finish_tracked_dispatch_locked(self, dispatch_key: tuple[int, int] | None, outcome) -> bool:
        if dispatch_key is None:
            return outcome is _DISPATCH_SKIPPED
        tracked = self._tracked_dispatch_batches.get(dispatch_key)
        if tracked is None:
            return outcome is _DISPATCH_SKIPPED
        if outcome is not _DISPATCH_SKIPPED:
            tracked.had_non_skipped_outcome = True
        tracked.remaining_jobs = max(int(tracked.remaining_jobs) - 1, 0)
        if tracked.remaining_jobs > 0:
            return False
        self._tracked_dispatch_batches.pop(dispatch_key, None)
        return outcome is _DISPATCH_SKIPPED and not tracked.had_non_skipped_outcome

    def _forget_tracked_dispatch_locked(self, dispatch_key: tuple[int, int] | None, *, batch=None) -> list[object]:
        if dispatch_key is None:
            return [batch] if batch is not None else []
        tracked = self._tracked_dispatch_batches.get(dispatch_key)
        if tracked is None:
            return [batch] if batch is not None else []
        tracked.remaining_jobs = max(int(tracked.remaining_jobs) - 1, 0)
        if tracked.remaining_jobs > 0:
            return []
        self._tracked_dispatch_batches.pop(dispatch_key, None)
        if tracked.had_non_skipped_outcome:
            return []
        tracked_batch = tracked.batch if tracked.batch is not None else batch
        return [tracked_batch] if tracked_batch is not None else []

    def _prepare_backlog_clear_locked(self, leading_batches: list[object] | None = None) -> list[object] | None:
        if self._scheduler.active_account_count() > 0:
            return None
        cleared_batches = list(leading_batches or [])
        cleared_batches.extend(
            self._scheduler.drop_expired_batches(
                now=self._queue_now(),
                max_wait_seconds=self._queued_hit_timeout_seconds,
            )
        )
        cleared_batches.extend(self._scheduler.clear_queue_batches())
        return cleared_batches

    def _restore_or_drop_undispatched_batch(self, batch, *, generation: int) -> str:
        cleared_batches: list[object] | None = None
        with self._state_lock:
            if not self._running or int(generation) != int(self._dispatch_generation):
                action = "forgotten"
            elif self._scheduler.active_account_count() > 0:
                self._scheduler.requeue_batch_front(batch)
                action = "requeued"
            else:
                cleared_batches = self._prepare_backlog_clear_locked([batch])
                if cleared_batches is None:
                    self._scheduler.requeue_batch_front(batch)
                    action = "requeued"
                else:
                    self._forget_batches(cleared_batches)
                    action = "cleared"
        if action == "forgotten":
            self._forget_batches([batch])
            return "forgotten"
        if action == "requeued":
            self._signal_drain_worker()
            return "requeued"
        cleared = len(cleared_batches or [])
        if cleared > 0:
            with self._state_lock:
                current_generation = self._running and int(generation) == int(self._dispatch_generation)
            if current_generation:
                self._push_scheduler_event(
                    status="backlog_cleared_no_purchase_accounts",
                    message=f"没有可用购买账号，已清空 {cleared} 条积压任务",
                )
        return "cleared"

    def _start_account_dispatch(self, account_id: str, batch, *, generation: int | None = None) -> bool:
        with self._state_lock:
            state = self._account_states.get(account_id)
            dispatch_generation = self._dispatch_generation if generation is None else int(generation)
            if state is None:
                self._scheduler.release_account(account_id)
                self._scheduler.mark_unavailable(account_id, reason="missing_account_state")
                return False
            if not self._can_start_account_dispatch_locked(state, dispatch_generation):
                self._scheduler.release_account(account_id)
                return False
            dispatch_runner = self._dispatch_runners.get(account_id)
            if dispatch_runner is None:
                self._scheduler.release_account(account_id)
                self._scheduler.mark_unavailable(account_id, reason="missing_dispatch_runner")
                return False
            state.busy = True
            dispatch_key = (dispatch_generation, id(batch))
            tracked = self._tracked_dispatch_batches.setdefault(dispatch_key, _TrackedDispatchBatch())
            if tracked.batch is None:
                tracked.batch = batch
            tracked.remaining_jobs += 1
            dispatch_runner.submit(batch=batch, generation=dispatch_generation)
            return True

    def _finish_account_dispatch(self, *, account_id: str, batch, outcome, generation: int, dispatch_key=None) -> None:
        should_signal_drain = False
        post_process_job: _PostProcessOutcomeJob | None = None
        completion_effects: _DispatchCompletionEffects | None = None
        should_restore_skipped_batch = False
        with self._state_lock:
            state = self._account_states.get(account_id)
            if state is not None:
                state.busy = False
            should_restore_skipped_batch = self._finish_tracked_dispatch_locked(dispatch_key, outcome)

            normalized_outcome = outcome
            if outcome is _DISPATCH_SKIPPED:
                normalized_outcome = None
            if isinstance(outcome, BaseException):
                normalized_outcome = self._build_dispatch_exception_outcome(state, batch=batch, error=outcome)

            if (
                state is not None
                and isinstance(normalized_outcome, PurchaseWorkerOutcome)
                and normalized_outcome.status == "auth_invalid"
                and int(generation) != self._dispatch_generation
                and self._running
            ):
                completion_effects = self._apply_stale_auth_invalid_outcome(state, normalized_outcome)
                normalized_outcome = None

            if (
                state is not None
                and isinstance(normalized_outcome, PurchaseWorkerOutcome)
                and int(generation) == self._dispatch_generation
            ):
                if (
                    state.capability_state != PurchaseCapabilityState.BOUND
                    and normalized_outcome.status != "auth_invalid"
                ):
                    normalized_outcome = None

            if (
                state is not None
                and isinstance(normalized_outcome, PurchaseWorkerOutcome)
                and int(generation) == self._dispatch_generation
            ):
                if normalized_outcome.status == "auth_invalid":
                    completion_effects = self._apply_worker_outcome(state, batch, normalized_outcome)
                else:
                    post_process_job = _PostProcessOutcomeJob(
                        account_id=account_id,
                        batch=batch,
                        outcome=normalized_outcome,
                        generation=int(generation),
                        postprocess_epoch=state.postprocess_epoch,
                    )

            self._scheduler.release_account(account_id)
            if self._apply_pending_purchase_settings_if_idle_locked():
                should_signal_drain = True
            should_signal_drain = should_signal_drain or self._scheduler.queue_size() > 0

        if completion_effects is not None:
            self._run_dispatch_completion_effects(completion_effects)

        if post_process_job is not None:
            self._enqueue_post_process_job(post_process_job)

        if should_restore_skipped_batch:
            restore_result = self._restore_or_drop_undispatched_batch(batch, generation=int(generation))
            if restore_result == "requeued":
                should_signal_drain = False

        if should_signal_drain:
            self._signal_drain_worker()

    def _apply_stale_auth_invalid_outcome(
        self,
        state: _RuntimeAccountState,
        outcome: PurchaseWorkerOutcome,
    ) -> _DispatchCompletionEffects:
        effects = _DispatchCompletionEffects()
        effects.account_id = state.account_id
        self._invalidate_post_process_locked(state)
        state.capability_state = PurchaseCapabilityState.EXPIRED
        state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
        state.last_error = outcome.error or state.last_error or "Not login"
        setattr(state.account, "purchase_capability_state", state.capability_state)
        setattr(state.account, "purchase_pool_state", state.pool_state)
        setattr(state.account, "last_error", state.last_error)
        effects.scheduler_effects = self._sync_scheduler_state(state)
        effects.snapshot_payload = self._build_inventory_snapshot_payload(state, last_error=state.last_error)
        effects.account_repository_payload = self._build_account_repository_payload(state)
        self._push_runtime_event(
            state,
            status="auth_invalid",
            message=state.last_error or "登录已失效",
            notify=False,
        )
        effects.expected_generation = self._dispatch_generation
        effects.expected_state_version = state.state_version
        effects.notify_state_change = True
        return effects

    @staticmethod
    def _build_dispatch_exception_outcome(state: _RuntimeAccountState | None, *, batch, error: BaseException):
        return PurchaseWorkerOutcome(
            status="exception",
            purchased_count=0,
            submitted_count=len(list(getattr(batch, "product_list", []) or [])),
            selected_steam_id=(state.inventory_state.selected_steam_id if state is not None else None),
            pool_state=(state.pool_state if state is not None else PurchasePoolState.NOT_CONNECTED),
            capability_state=(
                state.capability_state if state is not None else PurchaseCapabilityState.UNBOUND
            ),
            requires_remote_refresh=False,
            error=str(error),
        )

    def _handle_active_account_count_change(self, previous_active_account_count: int) -> _SchedulerStateEffects:
        effects = _SchedulerStateEffects()
        current_active_account_count = self._scheduler.active_account_count()
        self._active_account_count = current_active_account_count
        if previous_active_account_count > 0 and current_active_account_count == 0:
            effects.clear_backlog_when_no_accounts = True
            effects.notify_no_available_accounts = True
            return effects
        if previous_active_account_count == 0 and current_active_account_count > 0:
            effects.should_signal_drain = self._scheduler.queue_size() > 0
            effects.notify_accounts_available = True
        return effects

    def _run_scheduler_state_effects(
        self,
        effects: _SchedulerStateEffects | None,
        *,
        is_current=None,
    ) -> None:
        if effects is None:
            return
        current = is_current or (lambda: True)
        if not current():
            return
        for account_id in list(dict.fromkeys(effects.cancel_recovery_account_ids)):
            if not current():
                return
            self._cancel_recovery_check(account_id)
        for account_id in list(dict.fromkeys(effects.schedule_recovery_account_ids)):
            if not current():
                return
            self._schedule_recovery_check(account_id)
        if effects.clear_backlog_when_no_accounts:
            with self._state_lock:
                if not current():
                    return
                cleared_batches = self._prepare_backlog_clear_locked()
                if cleared_batches is not None:
                    self._forget_batches(cleared_batches)
            if cleared_batches is None:
                return
            cleared = len(cleared_batches)
            if cleared > 0 and current():
                self._push_scheduler_event(
                    status="backlog_cleared_no_purchase_accounts",
                    message=f"没有可用购买账号，已清空 {cleared} 条积压任务",
                )
        elif effects.scheduler_event is not None:
            if not current():
                return
            self._push_scheduler_event(**effects.scheduler_event)
        if effects.should_signal_drain:
            if not current():
                return
            if self._scheduler.active_account_count() > 0:
                self._signal_drain_worker()
        if effects.notify_no_available_accounts:
            if not current():
                return
            if self._scheduler.active_account_count() <= 0:
                self._notify_no_available_accounts()
        if effects.notify_accounts_available:
            if not current():
                return
            if self._scheduler.active_account_count() > 0:
                self._notify_accounts_available()

    def _dispatch_completion_effects_are_current(self, effects: _DispatchCompletionEffects) -> bool:
        account_id = effects.account_id
        if not account_id:
            return True
        with self._state_lock:
            state = self._account_states.get(account_id)
            if state is None:
                return False
            if effects.expected_generation is not None and int(effects.expected_generation) != self._dispatch_generation:
                return False
            if (
                effects.expected_state_version is not None
                and int(effects.expected_state_version) != state.state_version
            ):
                return False
            return True

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
        with self._state_lock:
            if not self._running:
                return
            state = self._account_states.get(account_id)
            if state is None:
                return
            if state.pool_state != PurchasePoolState.PAUSED_NO_INVENTORY:
                return
            if state.capability_state != PurchaseCapabilityState.BOUND:
                return
            if state.recovery_due_at is None:
                state.recovery_due_at = self._build_next_recovery_due_at()
            if state.purchase_disabled:
                return
            delay_seconds = max((state.recovery_due_at - datetime.now()).total_seconds(), 0.0)

        self._cancel_recovery_check(account_id)
        timer = threading.Timer(delay_seconds, self._run_recovery_check, args=(account_id,))
        timer.daemon = True
        with self._recovery_lock:
            self._recovery_timers[account_id] = timer
        timer.start()

    def _cancel_recovery_check(self, account_id: str) -> None:
        with self._recovery_lock:
            timer = self._recovery_timers.pop(account_id, None)
        if timer is not None:
            timer.cancel()

    def _cancel_all_recovery_checks(self) -> None:
        with self._recovery_lock:
            account_ids = list(self._recovery_timers.keys())
        for account_id in account_ids:
            self._cancel_recovery_check(account_id)

    def _run_recovery_check(self, account_id: str) -> None:
        with self._recovery_lock:
            self._recovery_timers.pop(account_id, None)
        effects: _DispatchCompletionEffects | None = None
        with self._state_lock:
            if not self._running:
                return

            state = self._account_states.get(account_id)
            if state is None or state.pool_state != PurchasePoolState.PAUSED_NO_INVENTORY:
                return
            if state.purchase_disabled:
                return

            expected_state_version = state.state_version
            state.recovery_due_at = None
            account = state.account
            inventory_state = state.inventory_state

        refresh_result = self._refresh_inventory_from_remote(account, inventory_state)

        with self._state_lock:
            state = self._account_states.get(account_id)
            if state is None:
                return
            if state.state_version != expected_state_version:
                return
            if refresh_result is None:
                effects = _DispatchCompletionEffects(
                    account_id=state.account_id,
                    expected_state_version=state.state_version,
                    expected_generation=self._dispatch_generation,
                    scheduler_effects=_SchedulerStateEffects(
                        schedule_recovery_account_ids=[account_id],
                    ),
                )
            elif refresh_result.status == "success":
                state.inventory_state.refresh_from_remote(list(refresh_result.inventories))
                state.last_error = None
                state.pool_state = (
                    PurchasePoolState.ACTIVE
                    if state.inventory_state.selected_steam_id is not None
                    else PurchasePoolState.PAUSED_NO_INVENTORY
                )
                scheduler_effects = self._sync_scheduler_state(state)
                effects = _DispatchCompletionEffects(
                    account_id=state.account_id,
                    expected_state_version=state.state_version,
                    expected_generation=self._dispatch_generation,
                    scheduler_effects=scheduler_effects,
                    snapshot_payload=self._build_inventory_snapshot_payload(state, last_error=state.last_error),
                    account_repository_payload=self._build_account_repository_payload(state),
                    notify_state_change=True,
                )
                if state.pool_state == PurchasePoolState.ACTIVE:
                    self._push_runtime_event(
                        state,
                        status="inventory_recovered",
                        message="库存恢复，账号已重新入池",
                        notify=False,
                    )
                else:
                    self._push_runtime_event(
                        state,
                        status="recovery_waiting",
                        message="恢复检查完成，仍无可用仓库",
                        notify=False,
                    )
            elif refresh_result.status == "auth_invalid":
                self._invalidate_post_process_locked(state)
                state.capability_state = PurchaseCapabilityState.EXPIRED
                state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
                state.last_error = refresh_result.error
                scheduler_effects = self._sync_scheduler_state(state)
                effects = _DispatchCompletionEffects(
                    account_id=state.account_id,
                    expected_state_version=state.state_version,
                    expected_generation=self._dispatch_generation,
                    scheduler_effects=scheduler_effects,
                    snapshot_payload=self._build_inventory_snapshot_payload(state, last_error=state.last_error),
                    account_repository_payload=self._build_account_repository_payload(state),
                    notify_state_change=True,
                )
                self._push_runtime_event(
                    state,
                    status="auth_invalid",
                    message=refresh_result.error or "登录已失效",
                    notify=False,
                )
            else:
                state.last_error = refresh_result.error
                scheduler_effects = self._sync_scheduler_state(state)
                effects = _DispatchCompletionEffects(
                    account_id=state.account_id,
                    expected_state_version=state.state_version,
                    expected_generation=self._dispatch_generation,
                    scheduler_effects=scheduler_effects,
                    snapshot_payload=self._build_inventory_snapshot_payload(state, last_error=state.last_error),
                    account_repository_payload=self._build_account_repository_payload(state),
                    notify_state_change=True,
                )
                self._push_runtime_event(
                    state,
                    status="recovery_waiting",
                    message=refresh_result.error or "恢复检查失败，等待下次重试",
                    notify=False,
                )

        if effects is not None:
            self._run_dispatch_completion_effects(effects)

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
        payload = self._build_inventory_snapshot_payload(state, last_error=last_error)
        self._persist_inventory_snapshot_payload(payload)

    def _sync_account_repository_state(self, state: _RuntimeAccountState) -> None:
        payload = self._build_account_repository_payload(state)
        self._sync_account_repository_payload(payload)

    def _build_inventory_snapshot_payload(
        self,
        state: _RuntimeAccountState,
        *,
        last_error: str | None = None,
    ) -> dict[str, object]:
        refreshed_at = datetime.now().isoformat(timespec="seconds")
        state.inventory_refreshed_at = refreshed_at
        return {
            "account_id": state.account_id,
            "selected_steam_id": state.inventory_state.selected_steam_id,
            "inventories": state.inventory_state.inventories,
            "refreshed_at": refreshed_at,
            "last_error": last_error,
        }

    def _persist_inventory_snapshot_payload(self, payload: dict[str, object]) -> None:
        if self._inventory_snapshot_repository is None:
            return
        self._inventory_snapshot_repository.save(**payload)

    def _build_account_repository_payload(self, state: _RuntimeAccountState) -> dict[str, object]:
        recovery_due_at = self._format_recovery_due_at(state.recovery_due_at)
        updated_at = datetime.now().isoformat(timespec="seconds")
        changes = {
            "purchase_capability_state": state.capability_state,
            "purchase_pool_state": state.pool_state,
            "last_error": state.last_error,
            "purchase_disabled": state.purchase_disabled,
            "purchase_recovery_due_at": recovery_due_at,
            "updated_at": updated_at,
        }
        setattr(state.account, "purchase_capability_state", state.capability_state)
        setattr(state.account, "purchase_pool_state", state.pool_state)
        setattr(state.account, "last_error", state.last_error)
        setattr(state.account, "purchase_disabled", state.purchase_disabled)
        setattr(state.account, "purchase_recovery_due_at", recovery_due_at)
        return {"account_id": state.account_id, "changes": changes}

    def _sync_account_repository_payload(self, payload: dict[str, object]) -> None:
        if self._account_repository is None or not hasattr(self._account_repository, "update_account"):
            return
        try:
            self._account_repository.update_account(payload["account_id"], **dict(payload["changes"]))
        except Exception:
            return

    def _run_dispatch_completion_effects(self, effects: _DispatchCompletionEffects) -> None:
        if not self._dispatch_completion_effects_are_current(effects):
            return
        self._run_scheduler_state_effects(
            effects.scheduler_effects,
            is_current=lambda: self._dispatch_completion_effects_are_current(effects),
        )
        if effects.snapshot_payload is not None and self._dispatch_completion_effects_are_current(effects):
            self._persist_inventory_snapshot_payload(effects.snapshot_payload)
        if effects.account_repository_payload is not None and self._dispatch_completion_effects_are_current(effects):
            self._sync_account_repository_payload(effects.account_repository_payload)
        if effects.stats_outcome_payload is not None and self._dispatch_completion_effects_are_current(effects):
            self._stats_aggregator.enqueue_outcome(**effects.stats_outcome_payload)
        if effects.stats_forward_payload is not None and self._dispatch_completion_effects_are_current(effects):
            self._forward_stats_events(**effects.stats_forward_payload)
        if effects.notify_state_change and self._dispatch_completion_effects_are_current(effects):
            self._notify_state_change()

    def _push_runtime_event(self, state: _RuntimeAccountState, *, status: str, message: str, notify: bool = True) -> None:
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
        if notify:
            self._notify_state_change()

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
        self._notify_state_change()

    @staticmethod
    def _build_purchase_debug_details(outcome) -> dict[str, object]:
        return {
            "status_code": getattr(outcome, "status_code", None),
            "request_method": getattr(outcome, "request_method", None),
            "request_path": getattr(outcome, "request_path", None),
            "request_body": getattr(outcome, "request_body", None),
            "response_text": getattr(outcome, "response_text", None),
        }

    def _push_event_from_batch(
        self,
        batch,
        *,
        status: str,
        message: str,
        debug_details: dict[str, object] | None = None,
        notify: bool = True,
    ) -> None:
        details = debug_details or {}
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
                "status_code": details.get("status_code"),
                "request_method": details.get("request_method"),
                "request_path": details.get("request_path"),
                "request_body": details.get("request_body"),
                "response_text": details.get("response_text"),
            },
        )
        del self._recent_events[self._RECENT_EVENT_LIMIT :]
        if notify:
            self._notify_state_change()

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
        self._notify_state_change()

    def _notify_state_change(self) -> None:
        callback = self._state_change_callback
        if not callable(callback):
            return
        try:
            callback()
        except Exception:
            return

    @staticmethod
    def _invalidate_post_process_locked(state: _RuntimeAccountState) -> None:
        state.postprocess_epoch += 1

    def _enqueue_post_process_job(self, job: _PostProcessOutcomeJob) -> None:
        self._post_process_queue.put(job)

    def _post_process_job_is_current_locked(
        self,
        job: _PostProcessOutcomeJob,
        *,
        state: _RuntimeAccountState | None = None,
    ) -> bool:
        if not self._running or int(job.generation) != self._dispatch_generation:
            return False
        current_state = state if state is not None else self._account_states.get(job.account_id)
        if current_state is None:
            return False
        return int(job.postprocess_epoch) == current_state.postprocess_epoch

    def _process_post_process_job(self, job: _PostProcessOutcomeJob) -> None:
        completion_effects: _DispatchCompletionEffects | None = None
        refresh_account = None
        refresh_inventory_state = None

        with self._state_lock:
            state = self._account_states.get(job.account_id)
            if not self._post_process_job_is_current_locked(job, state=state):
                return
            if state is None:
                return
            if job.outcome.status == "success" and self._success_requires_remote_reconcile(state, job.outcome):
                refresh_account = state.account
                refresh_inventory_state = state.inventory_state
            else:
                completion_effects = self._apply_worker_outcome(state, job.batch, job.outcome)

        if refresh_account is not None:
            refresh_result = self._refresh_inventory_from_remote(refresh_account, refresh_inventory_state)
            with self._state_lock:
                state = self._account_states.get(job.account_id)
                if not self._post_process_job_is_current_locked(job, state=state):
                    completion_effects = None
                elif state is not None:
                    completion_effects = self._apply_worker_outcome(
                        state,
                        job.batch,
                        job.outcome,
                        reconcile_refresh_result=refresh_result,
                    )

        if completion_effects is not None:
            self._run_dispatch_completion_effects(completion_effects)

    @staticmethod
    def _clone_hit_payload(hit: dict[str, object]) -> dict[str, object]:
        payload = dict(hit)
        payload["product_list"] = list(hit.get("product_list") or [])
        return payload

    @staticmethod
    def _build_payment_success_no_items_message(error: str | None) -> str:
        text = str(error or "").strip()
        if text.startswith("支付失败:"):
            text = text.split(":", 1)[1].strip()
        elif text.startswith("支付失败："):
            text = text.split("：", 1)[1].strip()
        return f"购买了但是没有买到物品：{text}" if text else "购买了但是没有买到物品"

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

    def _start_hit_intake_worker(self) -> None:
        if self._hit_intake_thread is not None and self._hit_intake_thread.is_alive():
            return
        queue = self._hit_intake_queue
        stop_signal = self._hit_intake_stop_signal

        def runner() -> None:
            self._hit_intake_worker_loop(queue, stop_signal)

        self._hit_intake_thread = threading.Thread(
            target=runner,
            name="purchase-runtime-hit-intake",
            daemon=True,
        )
        self._hit_intake_thread.start()

    def _stop_hit_intake_worker(self) -> None:
        self._hit_intake_stop_signal.set()
        self._hit_intake_queue.put(_HIT_INTAKE_STOP)
        thread = self._hit_intake_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.2)
        self._hit_intake_thread = None

    def _start_post_process_worker(self) -> None:
        if self._post_process_thread is not None and self._post_process_thread.is_alive():
            return
        queue = self._post_process_queue
        stop_signal = self._post_process_stop_signal

        def runner() -> None:
            self._post_process_worker_loop(queue, stop_signal)

        self._post_process_thread = threading.Thread(
            target=runner,
            name="purchase-runtime-post-process",
            daemon=True,
        )
        self._post_process_thread.start()

    def _stop_post_process_worker(self) -> None:
        self._post_process_stop_signal.set()
        self._post_process_queue.put(_POST_PROCESS_STOP)
        thread = self._post_process_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.2)
        self._post_process_thread = None

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
                    self._drop_expired_backlog()
                    drain_result = asyncio.run(self._drain_scheduler())
                    if drain_result == "dispatched":
                        continue
                    if drain_result == "retry":
                        continue
                    wait_seconds = self._scheduler.next_expiration_delay(
                        now=self._queue_now(),
                        max_wait_seconds=self._queued_hit_timeout_seconds,
                    )
                    if wait_seconds is None:
                        break
                    self._drain_signal.wait(timeout=wait_seconds)
                    self._drain_signal.clear()
                    if self._drain_stop_signal.is_set():
                        return
                except Exception as exc:  # pragma: no cover - defensive background worker guard
                    self._push_scheduler_event(
                        status="drain_worker_error",
                        message=f"后台购买线程异常: {exc}",
                    )
                    break

    def _hit_intake_worker_loop(self, queue: Queue[object], stop_signal: threading.Event) -> None:
        while not stop_signal.is_set():
            try:
                queued_item = queue.get(timeout=0.1)
            except Empty:
                continue
            if queued_item is _HIT_INTAKE_STOP:
                return
            if not isinstance(queued_item, dict):
                continue
            try:
                self._accept_query_hit_now(queued_item)
            except Exception as exc:  # pragma: no cover - defensive background worker guard
                self._push_scheduler_event(
                    status="hit_intake_worker_error",
                    message=f"后台命中投递线程异常: {exc}",
                )

    def _post_process_worker_loop(self, queue: Queue[object], stop_signal: threading.Event) -> None:
        while not stop_signal.is_set():
            try:
                queued_item = queue.get(timeout=0.1)
            except Empty:
                continue
            if queued_item is _POST_PROCESS_STOP:
                return
            if not isinstance(queued_item, _PostProcessOutcomeJob):
                continue
            try:
                self._process_post_process_job(queued_item)
            except Exception as exc:  # pragma: no cover - defensive background worker guard
                self._push_scheduler_event(
                    status="post_process_worker_error",
                    message=f"后台购买后处理线程异常: {exc}",
                )

    async def _drain_scheduler(self) -> str:
        self._drop_expired_backlog()
        claimed_account_ids = self._scheduler.claim_idle_accounts_by_bucket(
            limit_per_bucket=self._get_per_batch_ip_fanout_limit(),
        )
        if not claimed_account_ids:
            return "idle"

        batch = self._scheduler.pop_next_batch()
        if batch is None:
            for account_id in claimed_account_ids:
                self._scheduler.release_account(account_id)
            return "idle"
        if self._batch_expired(batch):
            self._forget_batches([batch])
            for account_id in claimed_account_ids:
                self._scheduler.release_account(account_id)
            return "retry"

        with self._state_lock:
            dispatch_generation = self._dispatch_generation
            batch_matches_current_session = self._batch_matches_current_session_locked(batch)
        if not batch_matches_current_session:
            self._forget_batches([batch])
            for account_id in claimed_account_ids:
                self._scheduler.release_account(account_id)
            return "retry"
        started_dispatch_count = 0
        for account_id in claimed_account_ids:
            if self._start_account_dispatch(account_id, batch, generation=dispatch_generation):
                started_dispatch_count += 1
        if started_dispatch_count > 0:
            return "dispatched"
        restore_result = self._restore_or_drop_undispatched_batch(batch, generation=dispatch_generation)
        return "retry" if restore_result == "requeued" else "idle"

    def _should_process_account_dispatch(self, account_id: str, generation: int) -> bool:
        with self._state_lock:
            if not self._running or int(generation) != self._dispatch_generation:
                return False
            state = self._account_states.get(account_id)
            if state is None:
                return False
            if state.purchase_disabled:
                return False
            if state.capability_state != PurchaseCapabilityState.BOUND:
                return False
            return state.pool_state == PurchasePoolState.ACTIVE

    def _drop_expired_backlog(self) -> int:
        dropped_batches = self._scheduler.drop_expired_batches(
            now=self._queue_now(),
            max_wait_seconds=self._queued_hit_timeout_seconds,
        )
        self._forget_batches(dropped_batches)
        return len(dropped_batches)

    def _batch_expired(self, batch) -> bool:
        max_wait_seconds = self._queued_hit_timeout_seconds
        if max_wait_seconds <= 0:
            return False
        enqueued_at = getattr(batch, "enqueued_at", None)
        if enqueued_at is None:
            return False
        return (self._queue_now() - float(enqueued_at)) >= max_wait_seconds

    def _batch_matches_current_session_locked(self, batch) -> bool:
        current_stats = self._stats_aggregator.snapshot()
        current_runtime_session_id = str(current_stats.get("runtime_session_id") or "") or None
        current_query_config_id = str(current_stats.get("query_config_id") or "") or None
        batch_runtime_session_id = str(getattr(batch, "runtime_session_id", "") or "") or None
        batch_query_config_id = str(getattr(batch, "query_config_id", "") or "") or None
        return (
            current_runtime_session_id == batch_runtime_session_id
            and current_query_config_id == batch_query_config_id
        )

    def _forget_batches(self, batches: list[object]) -> None:
        forget_batches = getattr(self._hit_inbox, "forget_batches", None)
        if callable(forget_batches):
            try:
                forget_batches(list(batches))
            except Exception:
                return

    @staticmethod
    def _queue_now() -> float:
        return time.monotonic()


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
