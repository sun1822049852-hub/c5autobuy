import asyncio
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

from app_backend.domain.models.account import Account
from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseExecutionResult


def build_account(
    account_id: str,
    *,
    bound: bool = True,
    browser_proxy_mode: str = "direct",
    browser_proxy_url: str | None = None,
    api_proxy_mode: str = "direct",
    api_proxy_url: str | None = None,
) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=None,
        browser_proxy_mode=browser_proxy_mode,
        browser_proxy_url=browser_proxy_url,
        api_proxy_mode=api_proxy_mode,
        api_proxy_url=api_proxy_url,
        api_key=None,
        c5_user_id="10001" if bound else None,
        c5_nick_name="购买账号" if bound else None,
        cookie_raw="NC5_accessToken=token" if bound else None,
        purchase_capability_state="bound" if bound else "unbound",
        purchase_pool_state="not_connected",
        last_login_at="2026-03-16T20:00:00" if bound else None,
        last_error=None,
        created_at="2026-03-16T20:00:00",
        updated_at="2026-03-16T20:00:00",
        purchase_disabled=False,
        purchase_recovery_due_at=None,
    )


class FakeAccountRepository:
    def __init__(self, accounts=None) -> None:
        self._accounts = list(accounts or [])

    def list_accounts(self):
        return list(self._accounts)

    def get_account(self, account_id: str):
        for account in self._accounts:
            if account.account_id == account_id:
                return account
        return None

    def update_account(self, account_id: str, **changes):
        account = self.get_account(account_id)
        if account is None:
            raise KeyError(account_id)
        for key, value in changes.items():
            if hasattr(account, key):
                setattr(account, key, value)
        return account


def _extract_account_id(account) -> str | None:
    account_id = getattr(account, "account_id", None)
    if account_id:
        return str(account_id)
    get_account_id = getattr(account, "get_account_id", None)
    if callable(get_account_id):
        return str(get_account_id())
    current_user_id = getattr(account, "current_user_id", None)
    if current_user_id:
        return str(current_user_id)
    return None


class FakeSettingsRepository:
    def __init__(self, purchase_settings=None) -> None:
        self._purchase_settings = {
            "per_batch_ip_fanout_limit": 1,
            "max_inflight_per_account": 3,
        }
        if isinstance(purchase_settings, dict):
            self._purchase_settings.update(purchase_settings)

    def get(self):
        return type(
            "RuntimeSettings",
            (),
            {
                "settings_id": "default",
                "query_settings_json": {},
                "purchase_settings_json": dict(self._purchase_settings),
                "updated_at": None,
            },
        )()


class FakeRuntime:
    def __init__(self, accounts, _legacy_settings=None) -> None:
        self.accounts = list(accounts)
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def snapshot(self) -> dict:
        return {
            "running": self.started and not self.stopped,
            "message": "运行中" if self.started and not self.stopped else "未运行",
            "started_at": "2026-03-16T21:00:00" if self.started and not self.stopped else None,
            "stopped_at": None,
            "queue_size": 0,
            "active_account_count": 1 if self.started and not self.stopped else 0,
            "total_account_count": len(self.accounts),
            "total_purchased_count": 0,
            "recent_events": [],
            "accounts": [
                {
                    "account_id": account.account_id,
                    "display_name": account.display_name,
                    "purchase_capability_state": account.purchase_capability_state,
                    "purchase_pool_state": "active" if self.started and not self.stopped else "not_connected",
                    "selected_steam_id": "steam-1" if self.started and not self.stopped else None,
                    "last_error": None,
                    "total_purchased_count": 0,
                }
                for account in self.accounts
            ],
        }


class FakeInventorySnapshotRepository:
    def __init__(self, snapshots=None) -> None:
        self._snapshots = dict(snapshots or {})
        self.saved_payloads: list[dict] = []

    def get(self, account_id: str):
        return self._snapshots.get(account_id)

    def save(
        self,
        *,
        account_id: str,
        selected_steam_id,
        inventories,
        refreshed_at=None,
        last_error=None,
    ):
        payload = {
            "account_id": account_id,
            "selected_steam_id": selected_steam_id,
            "inventories": list(inventories),
            "refreshed_at": refreshed_at,
            "last_error": last_error,
        }
        self.saved_payloads.append(payload)
        self._snapshots[account_id] = type(
            "Snapshot",
            (),
            payload,
        )()
        return self._snapshots[account_id]


class StubExecutionGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    async def execute(self, *, account, batch, selected_steam_id: str, **_kwargs):
        on_execute_started = _kwargs.get("on_execute_started")
        if callable(on_execute_started):
            on_execute_started()
        self.calls.append(
            {
                "account": account,
                "account_id": _extract_account_id(account),
                "selected_steam_id": selected_steam_id,
                "query_item_name": batch.query_item_name,
            }
        )
        return self._result


class StubStatsSink:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.events: list[object] = []
        self._error = error

    def __call__(self, event: object) -> bool:
        if self._error is not None:
            raise self._error
        self.events.append(event)
        return True


class BlockingExecutionGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []
        self.started = threading.Event()
        self.release = threading.Event()

    async def execute(self, *, account, batch, selected_steam_id: str, **_kwargs):
        on_execute_started = _kwargs.get("on_execute_started")
        if callable(on_execute_started):
            on_execute_started()
        self.calls.append(
            {
                "account": account,
                "account_id": _extract_account_id(account),
                "selected_steam_id": selected_steam_id,
                "query_item_name": batch.query_item_name,
            }
        )
        self.started.set()
        await asyncio.to_thread(self.release.wait, 1.0)
        return self._result


class MultiReleaseExecutionGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []
        self.release_events: list[threading.Event] = []
        self._lock = threading.Lock()

    async def execute(self, *, account, batch, selected_steam_id: str, **_kwargs):
        on_execute_started = _kwargs.get("on_execute_started")
        if callable(on_execute_started):
            on_execute_started()
        release_event = threading.Event()
        with self._lock:
            self.calls.append(
                {
                    "account": account,
                    "account_id": _extract_account_id(account),
                    "selected_steam_id": selected_steam_id,
                    "query_item_name": batch.query_item_name,
                }
            )
            self.release_events.append(release_event)
        await asyncio.to_thread(release_event.wait, 1.0)
        return self._result


class PreGatewayBlockingExecutionGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []
        self.entered = threading.Event()
        self.started = threading.Event()
        self.release = threading.Event()

    async def execute(self, *, account, batch, selected_steam_id: str, **_kwargs):
        self.entered.set()
        await asyncio.to_thread(self.release.wait, 1.0)
        on_execute_started = _kwargs.get("on_execute_started")
        if callable(on_execute_started):
            on_execute_started()
        self.calls.append(
            {
                "account": account,
                "account_id": _extract_account_id(account),
                "selected_steam_id": selected_steam_id,
                "query_item_name": batch.query_item_name,
            }
        )
        self.started.set()
        return self._result


class PostGatewayCancelledExecutionGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []
        self.started = threading.Event()
        self.replayed = threading.Event()
        self.release = threading.Event()

    async def execute(self, *, account, batch, selected_steam_id: str, **_kwargs):
        on_execute_started = _kwargs.get("on_execute_started")
        if callable(on_execute_started):
            on_execute_started()
        self.calls.append(
            {
                "account": account,
                "account_id": _extract_account_id(account),
                "selected_steam_id": selected_steam_id,
                "query_item_name": batch.query_item_name,
            }
        )
        self.started.set()
        if len(self.calls) == 1:
            raise asyncio.CancelledError()
        self.replayed.set()
        await asyncio.to_thread(self.release.wait, 1.0)
        return self._result


class RecordingAccountGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    async def execute(self, *, account, batch, selected_steam_id: str, **_kwargs):
        on_execute_started = _kwargs.get("on_execute_started")
        if callable(on_execute_started):
            on_execute_started()
        self.calls.append(
            {
                "account": account,
                "account_id": _extract_account_id(account),
                "selected_steam_id": selected_steam_id,
                "query_item_name": batch.query_item_name,
            }
        )
        return self._result


class SessionReuseGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    async def execute(self, *, account, batch, selected_steam_id: str, **_kwargs):
        on_execute_started = _kwargs.get("on_execute_started")
        if callable(on_execute_started):
            on_execute_started()
        session = await account.get_global_session()
        self.calls.append(
            {
                "account": account,
                "session": session,
                "selected_steam_id": selected_steam_id,
                "query_item_name": batch.query_item_name,
            }
        )
        return self._result


class BlockingSessionReuseGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []
        self.started = threading.Event()
        self.release = threading.Event()

    async def execute(self, *, account, batch, selected_steam_id: str, **_kwargs):
        on_execute_started = _kwargs.get("on_execute_started")
        if callable(on_execute_started):
            on_execute_started()
        session = await account.get_global_session()
        self.calls.append(
            {
                "account": account,
                "session": session,
                "selected_steam_id": selected_steam_id,
                "query_item_name": batch.query_item_name,
            }
        )
        self.started.set()
        await asyncio.to_thread(self.release.wait, 1.0)
        return self._result


class StubInventoryRefreshGateway:
    def __init__(self, result) -> None:
        self._results = list(result) if isinstance(result, list) else [result]
        self.calls: list[dict[str, object]] = []

    async def refresh(self, *, account):
        self.calls.append({"account_id": account.account_id})
        if len(self._results) > 1:
            return self._results.pop(0)
        return self._results[0]


class ImmediateDispatchWorker:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.calls: list[dict[str, object]] = []

    async def process(self, batch, *, generation: int | None = None, on_gateway_execute_start=None):
        if callable(on_gateway_execute_start):
            on_gateway_execute_start()
        self.calls.append(
            {
                "query_item_name": getattr(batch, "query_item_name", None),
                "generation": generation,
            }
        )
        self.started.set()
        return {"status": "ok"}

    async def cleanup(self) -> None:
        return None


def _build_hit_payload() -> dict[str, object]:
    return {
        "query_item_name": "AK-47",
        "query_config_id": "cfg-1",
        "query_item_id": "item-1",
        "runtime_session_id": "run-1",
        "external_item_id": "1380979899390261111",
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
        "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
        "total_price": 88.0,
        "total_wear_sum": 0.1234,
        "mode_type": "new_api",
    }


def wait_until(predicate, *, timeout: float = 1.0, interval: float = 0.01) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_account_dispatch_runner_wakes_immediately_when_idle():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import _AccountDispatchRunner

    worker = ImmediateDispatchWorker()
    completed: list[dict[str, object]] = []
    runner = _AccountDispatchRunner(
        account_id="a1",
        worker=worker,
        on_complete=lambda **payload: completed.append(payload),
    )
    runner.start()

    try:
        assert wait_until(
            lambda: (
                runner._thread is not None
                and runner._thread.is_alive()
                and runner._loop is not None
                and runner._wakeup_event is not None
                and runner._queue.empty()
                and len(runner._active_tasks) == 0
            ),
            timeout=0.5,
            interval=0.001,
        )

        runner.submit(
            batch=SimpleNamespace(query_item_name="AK-47"),
            generation=1,
        )

        assert wait_until(worker.started.is_set, timeout=0.1, interval=0.001)
        assert wait_until(lambda: len(completed) == 1, timeout=0.1, interval=0.001)
        assert completed[0]["account_id"] == "a1"
    finally:
        runner.stop()


class FakeReusableSession:
    def __init__(self, loop) -> None:
        self._loop = loop
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_purchase_runtime_service_returns_idle_snapshot_when_stopped():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        runtime_factory=lambda accounts, settings: FakeRuntime(accounts, settings),
    )

    snapshot = service.get_status()

    assert snapshot["running"] is False
    assert snapshot["message"] == "未运行"
    assert snapshot["queue_size"] == 0
    assert snapshot["active_account_count"] == 0
    assert snapshot["total_account_count"] == 0
    assert snapshot["recent_events"] == []
    assert snapshot["accounts"] == []


def test_purchase_runtime_service_starts_runtime_and_exposes_snapshot():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        runtime_factory=lambda accounts, settings: FakeRuntime(accounts, settings),
    )

    started, message = service.start()

    assert started is True
    assert message == "购买运行时已启动"
    snapshot = service.get_status()
    assert snapshot["running"] is True
    assert snapshot["active_account_count"] == 1
    assert snapshot["accounts"][0]["selected_steam_id"] == "steam-1"


def test_purchase_runtime_service_publishes_runtime_update_events_on_start_and_stop():
    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    hub = RuntimeUpdateHub()
    queue = hub.subscribe("*")
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        runtime_factory=lambda accounts, settings: FakeRuntime(accounts, settings),
        runtime_update_hub=hub,
    )

    started, start_message = service.start()
    start_event = queue.get_nowait()
    stopped, stop_message = service.stop()
    stop_event = queue.get_nowait()

    assert started is True
    assert start_message == "购买运行时已启动"
    assert start_event.version == 1
    assert start_event.event == "purchase_runtime.updated"
    assert start_event.payload["running"] is True
    assert start_event.payload["active_account_count"] == 1

    assert stopped is True
    assert stop_message == "购买运行时已停止"
    assert stop_event.version == 2
    assert stop_event.event == "purchase_runtime.updated"
    assert stop_event.payload["running"] is False
    assert stop_event.payload["active_account_count"] == 0


def test_purchase_runtime_service_serializes_start_and_stop_runtime_update_events():
    import threading

    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    class BlockingFirstPublishHub(RuntimeUpdateHub):
        def __init__(self) -> None:
            super().__init__()
            self.first_publish_entered = threading.Event()
            self.release_first_publish = threading.Event()
            self._publish_count = 0

        def publish(self, *, event: str, payload: dict[str, object] | None = None):
            self._publish_count += 1
            if self._publish_count == 1:
                self.first_publish_entered.set()
                self.release_first_publish.wait(timeout=1.0)
            return super().publish(event=event, payload=payload)

    hub = BlockingFirstPublishHub()
    queue = hub.subscribe("*")
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        runtime_factory=lambda accounts, settings: FakeRuntime(accounts, settings),
        runtime_update_hub=hub,
    )
    start_result: dict[str, object] = {}
    stop_result: dict[str, object] = {}
    start_thread = threading.Thread(
        target=lambda: start_result.setdefault("value", service.start()),
        daemon=True,
    )
    stop_thread = threading.Thread(
        target=lambda: stop_result.setdefault("value", service.stop()),
        daemon=True,
    )

    try:
        start_thread.start()
        assert wait_until(hub.first_publish_entered.is_set)

        stop_thread.start()
        assert wait_until(lambda: stop_thread.is_alive() and "value" not in stop_result, timeout=0.2, interval=0.001)

        hub.release_first_publish.set()
        start_thread.join(timeout=1.0)
        stop_thread.join(timeout=1.0)

        start_event = queue.get_nowait()
        stop_event = queue.get_nowait()

        assert start_result["value"] == (True, "购买运行时已启动")
        assert stop_result["value"] == (True, "购买运行时已停止")
        assert start_event.version == 1
        assert start_event.payload["running"] is True
        assert stop_event.version == 2
        assert stop_event.payload["running"] is False
    finally:
        hub.release_first_publish.set()
        start_thread.join(timeout=1.0)
        stop_thread.join(timeout=1.0)
        service.stop()


def test_purchase_runtime_service_stop_waits_for_background_runtime_update_publish():
    import threading

    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    class CallbackRuntime(FakeRuntime):
        def __init__(self, accounts, _legacy_settings=None) -> None:
            super().__init__(accounts, _legacy_settings)
            self._state_change_callback = None

        def set_state_change_callback(self, callback) -> None:
            self._state_change_callback = callback

        def trigger_state_change(self) -> None:
            callback = self._state_change_callback
            if callable(callback):
                callback()

    class BlockingBackgroundPublishHub(RuntimeUpdateHub):
        def __init__(self) -> None:
            super().__init__()
            self.background_publish_entered = threading.Event()
            self.release_background_publish = threading.Event()

        def publish(self, *, event: str, payload: dict[str, object] | None = None):
            if (
                threading.current_thread().name == "purchase-runtime-update-publisher"
                and not self.background_publish_entered.is_set()
            ):
                self.background_publish_entered.set()
                self.release_background_publish.wait(timeout=1.0)
            return super().publish(event=event, payload=payload)

    hub = BlockingBackgroundPublishHub()
    queue = hub.subscribe("*")
    runtime_holder: dict[str, CallbackRuntime] = {}

    def build_runtime(accounts, settings):
        runtime = CallbackRuntime(accounts, settings)
        runtime_holder["runtime"] = runtime
        return runtime

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        runtime_factory=build_runtime,
        runtime_update_hub=hub,
    )

    started, _ = service.start()
    queue.get_nowait()
    runtime = runtime_holder["runtime"]
    stop_result: dict[str, object] = {}
    stop_thread = threading.Thread(
        target=lambda: stop_result.setdefault("value", service.stop()),
        daemon=True,
    )

    try:
        runtime.trigger_state_change()
        assert wait_until(hub.background_publish_entered.is_set)

        stop_thread.start()
        assert wait_until(lambda: stop_thread.is_alive() and "value" not in stop_result, timeout=0.2, interval=0.001)

        hub.release_background_publish.set()
        stop_thread.join(timeout=1.0)

        background_event = queue.get_nowait()
        stop_event = queue.get_nowait()

        assert started is True
        assert stop_result["value"] == (True, "购买运行时已停止")
        assert background_event.version == 2
        assert background_event.payload["running"] is True
        assert stop_event.version == 3
        assert stop_event.payload["running"] is False
    finally:
        hub.release_background_publish.set()
        stop_thread.join(timeout=1.0)
        service.stop()


def test_purchase_runtime_service_ignores_runtime_update_publish_failures_during_start_and_stop():
    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    class ExplodingQueryRuntimeService:
        def get_status(self) -> dict[str, object]:
            raise RuntimeError("boom")

    hub = RuntimeUpdateHub()
    queue = hub.subscribe("*")
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        runtime_factory=lambda accounts, settings: FakeRuntime(accounts, settings),
        runtime_update_hub=hub,
        query_runtime_service=ExplodingQueryRuntimeService(),
    )

    started, start_message = service.start()
    running_snapshot = service.get_status()
    stopped, stop_message = service.stop()
    stopped_snapshot = service.get_status()

    assert started is True
    assert start_message == "购买运行时已启动"
    assert running_snapshot["running"] is True
    assert stopped is True
    assert stop_message == "购买运行时已停止"
    assert stopped_snapshot["running"] is False
    assert queue.empty()


def test_purchase_runtime_service_runtime_callback_publishes_route_shape_updates():
    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseExecutionResult

    class FakeQueryRuntimeService:
        def get_status(self) -> dict[str, object]:
            return {
                "running": True,
                "config_id": "cfg-1",
                "config_name": "测试配置",
                "message": "运行中",
                "item_rows": [
                    {
                        "query_item_id": "item-1",
                        "item_name": "商品-1",
                        "max_price": 100.0,
                        "min_wear": 0.0,
                        "max_wear": 0.7,
                        "detail_min_wear": 0.0,
                        "detail_max_wear": 0.25,
                        "manual_paused": False,
                        "query_count": 1,
                        "modes": {},
                    }
                ],
            }

    hub = RuntimeUpdateHub()
    queue = hub.subscribe("*")
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=FakeInventorySnapshotRepository(
            {
                "a1": type(
                    "Snapshot",
                    (),
                    {
                        "account_id": "a1",
                        "selected_steam_id": "steam-1",
                        "inventories": [{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
                        "refreshed_at": "2026-03-16T20:00:00",
                        "last_error": None,
                    },
                )()
            }
        ),
        execution_gateway_factory=lambda: RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1)),
        runtime_update_hub=hub,
        query_runtime_service=FakeQueryRuntimeService(),
    )

    started, _ = service.start()
    queue.get_nowait()
    hit_result = service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    assert started is True
    assert hit_result == {"accepted": True, "status": "queued"}
    assert wait_until(lambda: not queue.empty(), timeout=1.0)
    queued_event = queue.get_nowait()
    assert queued_event.event == "purchase_runtime.updated"
    assert queued_event.payload["active_query_config"] == {
        "config_id": "cfg-1",
        "config_name": "测试配置",
        "state": "running",
        "message": "运行中",
    }
    assert "item_rows" in queued_event.payload


def test_purchase_runtime_service_runtime_callback_does_not_read_query_status_under_runtime_lock():
    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    class LockAwareRuntime(FakeRuntime):
        def __init__(self, accounts, _legacy_settings=None) -> None:
            super().__init__(accounts, _legacy_settings)
            self._state_lock = threading.RLock()
            self._state_change_callback = None
            self.callback_invoked_under_runtime_lock = False

        def set_state_change_callback(self, callback) -> None:
            self._state_change_callback = callback

        def trigger_state_change(self) -> None:
            with self._state_lock:
                callback = self._state_change_callback
                if callable(callback):
                    self.callback_invoked_under_runtime_lock = True
                    try:
                        callback()
                    finally:
                        self.callback_invoked_under_runtime_lock = False

    class LockProbeQueryRuntimeService:
        def __init__(self, runtime) -> None:
            self._runtime = runtime
            self.called_under_runtime_lock = False

        def get_status(self) -> dict[str, object]:
            if self._runtime.callback_invoked_under_runtime_lock:
                self.called_under_runtime_lock = True
            return {
                "running": True,
                "config_id": "cfg-1",
                "config_name": "测试配置",
                "message": "运行中",
                "item_rows": [],
            }

    hub = RuntimeUpdateHub()
    queue = hub.subscribe("*")
    runtime_holder: dict[str, LockAwareRuntime] = {}

    def build_runtime(accounts, settings):
        runtime = LockAwareRuntime(accounts, settings)
        runtime_holder["runtime"] = runtime
        return runtime

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        runtime_factory=build_runtime,
        runtime_update_hub=hub,
    )

    started, _ = service.start()
    queue.get_nowait()

    runtime = runtime_holder["runtime"]
    query_service = LockProbeQueryRuntimeService(runtime)
    service.set_query_runtime_service(query_service)

    runtime.trigger_state_change()

    assert started is True
    assert wait_until(lambda: not queue.empty(), timeout=1.0)
    event = queue.get_nowait()
    assert event.event == "purchase_runtime.updated"
    assert query_service.called_under_runtime_lock is False


def test_default_purchase_runtime_manual_refresh_does_not_override_later_auth_invalid():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import _DefaultPurchaseRuntime
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    class BlockingRefreshRuntime(_DefaultPurchaseRuntime):
        def __init__(self, accounts, _legacy_settings=None, **kwargs) -> None:
            super().__init__(accounts, _legacy_settings, **kwargs)
            self.refresh_started = threading.Event()
            self.release_refresh = threading.Event()

        def _refresh_inventory_from_remote(self, account, inventory_state):
            self.refresh_started.set()
            self.release_refresh.wait(timeout=1.0)
            return InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-2", "nickname": "刷新仓", "inventory_num": 920, "inventory_max": 1000},
                ]
            )

    runtime = BlockingRefreshRuntime(
        [build_account("a1")],
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=FakeInventorySnapshotRepository(),
        inventory_refresh_gateway_factory=None,
        recovery_delay_seconds_provider=lambda: 0.0,
        execution_gateway_factory=lambda: RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1)),
        max_inflight_per_account=1,
        queued_hit_timeout_seconds=0.5,
    )
    runtime.start()

    refresh_thread = threading.Thread(
        target=lambda: runtime.refresh_account_inventory_detail("a1"),
        daemon=True,
    )
    refresh_thread.start()

    assert wait_until(runtime.refresh_started.is_set, timeout=1.0)
    auth_thread = threading.Thread(
        target=lambda: runtime.mark_account_auth_invalid(account_id="a1", error="Not login"),
        daemon=True,
    )
    auth_thread.start()
    assert wait_until(lambda: not auth_thread.is_alive(), timeout=1.0)

    runtime.release_refresh.set()
    refresh_thread.join(timeout=1.0)
    auth_thread.join(timeout=1.0)

    status = runtime.snapshot()

    assert refresh_thread.is_alive() is False
    assert auth_thread.is_alive() is False
    assert status["accounts"][0]["purchase_capability_state"] == "expired"
    assert status["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid"
    assert status["accounts"][0]["last_error"] == "Not login"


def test_default_purchase_runtime_manual_refresh_does_not_commit_after_stop():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import _DefaultPurchaseRuntime
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    class BlockingRefreshRuntime(_DefaultPurchaseRuntime):
        def __init__(self, accounts, _legacy_settings=None, **kwargs) -> None:
            super().__init__(accounts, _legacy_settings, **kwargs)
            self.refresh_started = threading.Event()
            self.release_refresh = threading.Event()

        def _refresh_inventory_from_remote(self, account, inventory_state):
            self.refresh_started.set()
            self.release_refresh.wait(timeout=1.0)
            return InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-2", "nickname": "刷新仓", "inventory_num": 920, "inventory_max": 1000},
                ]
            )

    snapshot_repository = FakeInventorySnapshotRepository()
    runtime = BlockingRefreshRuntime(
        [build_account("a1")],
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=None,
        recovery_delay_seconds_provider=lambda: 0.0,
        execution_gateway_factory=lambda: RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1)),
        max_inflight_per_account=1,
        queued_hit_timeout_seconds=0.5,
    )
    runtime.start()

    refresh_thread = threading.Thread(
        target=lambda: runtime.refresh_account_inventory_detail("a1"),
        daemon=True,
    )
    refresh_thread.start()

    assert wait_until(runtime.refresh_started.is_set, timeout=1.0)
    saved_before_stop = len(snapshot_repository.saved_payloads)

    runtime.stop()
    runtime.release_refresh.set()
    refresh_thread.join(timeout=1.0)

    assert refresh_thread.is_alive() is False
    assert len(snapshot_repository.saved_payloads) == saved_before_stop


def test_default_purchase_runtime_recovery_check_does_not_override_later_auth_invalid():
    from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import _DefaultPurchaseRuntime
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    class BlockingRecoveryRuntime(_DefaultPurchaseRuntime):
        def __init__(self, accounts, _legacy_settings=None, **kwargs) -> None:
            super().__init__(accounts, _legacy_settings, **kwargs)
            self.refresh_started = threading.Event()
            self.release_refresh = threading.Event()

        def _refresh_inventory_from_remote(self, account, inventory_state):
            self.refresh_started.set()
            self.release_refresh.wait(timeout=1.0)
            return InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-2", "nickname": "恢复仓", "inventory_num": 920, "inventory_max": 1000},
                ]
            )

    runtime = BlockingRecoveryRuntime(
        [build_account("a1")],
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=FakeInventorySnapshotRepository(),
        inventory_refresh_gateway_factory=None,
        recovery_delay_seconds_provider=lambda: 0.0,
        execution_gateway_factory=lambda: RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1)),
        max_inflight_per_account=1,
        queued_hit_timeout_seconds=0.5,
    )
    runtime.start()

    with runtime._state_lock:
        state = runtime._account_states["a1"]
        state.capability_state = PurchaseCapabilityState.BOUND
        state.pool_state = PurchasePoolState.PAUSED_NO_INVENTORY
        state.purchase_disabled = False

    recovery_thread = threading.Thread(
        target=lambda: runtime._run_recovery_check("a1"),
        daemon=True,
    )
    recovery_thread.start()

    assert wait_until(runtime.refresh_started.is_set, timeout=1.0)
    auth_thread = threading.Thread(
        target=lambda: runtime.mark_account_auth_invalid(account_id="a1", error="Not login"),
        daemon=True,
    )
    auth_thread.start()
    assert wait_until(lambda: not auth_thread.is_alive(), timeout=1.0)

    runtime.release_refresh.set()
    recovery_thread.join(timeout=1.0)
    auth_thread.join(timeout=1.0)

    status = runtime.snapshot()

    assert recovery_thread.is_alive() is False
    assert auth_thread.is_alive() is False
    assert status["accounts"][0]["purchase_capability_state"] == "expired"
    assert status["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid"
    assert status["accounts"][0]["last_error"] == "Not login"


def test_purchase_runtime_service_ignores_legacy_settings_repository_when_initializing_accounts():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository({"whitelist_account_ids": ["other-account"]}),
    )

    started, message = service.start()

    assert started is True
    assert message == "购买运行时已启动"
    snapshot = service.get_status()
    assert snapshot["total_account_count"] == 1
    assert snapshot["accounts"][0]["account_id"] == "a1"


def test_purchase_runtime_service_exposes_selected_inventory_summary_in_status():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {
                            "steamId": "steam-1",
                            "nickname": "主仓",
                            "inventory_num": 910,
                            "inventory_max": 1000,
                        },
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()

    snapshot = service.get_status()

    assert snapshot["accounts"][0]["selected_steam_id"] == "steam-1"
    assert snapshot["accounts"][0]["selected_inventory_name"] == "主仓"
    assert snapshot["accounts"][0]["selected_inventory_remaining_capacity"] == 90
    assert snapshot["accounts"][0]["selected_inventory_max"] == 1000


def test_purchase_runtime_service_refreshes_inventory_from_remote_on_start():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-local",
                    "inventories": [
                        {"steamId": "steam-local", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    refresh_gateway = StubInventoryRefreshGateway(
        InventoryRefreshResult.success(
            inventories=[
                {"steamId": "steam-remote-1", "inventory_num": 920, "inventory_max": 1000},
                {"steamId": "steam-remote-2", "inventory_num": 880, "inventory_max": 1000},
            ]
        )
    )

    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
    )

    started, _ = service.start()

    assert started is True
    snapshot = service.get_status()
    assert refresh_gateway.calls == [{"account_id": "a1"}]
    assert snapshot["active_account_count"] == 1
    assert snapshot["accounts"][0]["selected_steam_id"] == "steam-remote-1"
    assert snapshot_repository.saved_payloads[-1]["selected_steam_id"] == "steam-remote-1"
    assert [item["steamId"] for item in snapshot_repository.saved_payloads[-1]["inventories"]] == [
        "steam-remote-1",
        "steam-remote-2",
    ]


def test_purchase_runtime_service_marks_account_auth_invalid_when_startup_inventory_refresh_returns_not_login():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository()
    refresh_gateway = StubInventoryRefreshGateway(InventoryRefreshResult.auth_invalid("Not login"))

    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
    )

    started, _ = service.start()

    assert started is True
    snapshot = service.get_status()
    assert snapshot["active_account_count"] == 0
    assert snapshot["total_account_count"] == 1
    assert snapshot["accounts"][0]["purchase_capability_state"] == "expired"
    assert snapshot["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid"
    assert snapshot["accounts"][0]["selected_steam_id"] is None
    assert snapshot["accounts"][0]["last_error"] == "Not login"


def test_purchase_runtime_service_returns_inventory_detail_from_runtime_memory():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-2",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "备用仓", "inventory_num": 910, "inventory_max": 1000},
                        {"steamId": "steam-2", "nickname": "主仓", "inventory_num": 950, "inventory_max": 1200},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()

    detail = service.get_account_inventory_detail("a1")

    assert detail["account_id"] == "a1"
    assert detail["display_name"] == "购买账号"
    assert detail["selected_steam_id"] == "steam-2"
    assert detail["inventories"] == [
        {
            "steamId": "steam-1",
            "nickname": "备用仓",
            "inventory_num": 910,
            "inventory_max": 1000,
            "remaining_capacity": 90,
            "is_selected": False,
            "is_available": True,
        },
        {
            "steamId": "steam-2",
            "nickname": "主仓",
            "inventory_num": 950,
            "inventory_max": 1200,
            "remaining_capacity": 250,
            "is_selected": True,
            "is_available": True,
        },
    ]


def test_purchase_runtime_service_returns_inventory_detail_from_persisted_snapshot_when_runtime_missing():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-3",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 990, "inventory_max": 1000},
                        {"steamId": "steam-3", "inventory_num": 920, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T21:00:00",
                    "last_error": "等待恢复检查",
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )

    detail = service.get_account_inventory_detail("a1")

    assert detail["account_id"] == "a1"
    assert detail["display_name"] == "购买账号"
    assert detail["selected_steam_id"] == "steam-3"
    assert detail["refreshed_at"] == "2026-03-16T21:00:00"
    assert detail["last_error"] == "等待恢复检查"
    assert detail["inventories"] == [
        {
            "steamId": "steam-1",
            "nickname": None,
            "inventory_num": 990,
            "inventory_max": 1000,
            "remaining_capacity": 10,
            "is_selected": False,
            "is_available": False,
        },
        {
            "steamId": "steam-3",
            "nickname": None,
            "inventory_num": 920,
            "inventory_max": 1000,
            "remaining_capacity": 80,
            "is_selected": True,
            "is_available": True,
        },
    ]


def test_purchase_runtime_service_inventory_detail_exposes_auto_refresh_remaining_time():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account = build_account("a1")
    account.purchase_recovery_due_at = (datetime.now() + timedelta(seconds=180)).isoformat()
    account_repository = FakeAccountRepository([account])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-3",
                    "inventories": [
                        {"steamId": "steam-3", "inventory_num": 920, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T21:00:00",
                    "last_error": "等待恢复检查",
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )

    detail = service.get_account_inventory_detail("a1")

    assert detail["auto_refresh_due_at"] == account.purchase_recovery_due_at
    assert 0 < detail["auto_refresh_remaining_seconds"] <= 180


def test_purchase_runtime_service_manual_refresh_updates_inventory_detail():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 900, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    refresh_gateway = StubInventoryRefreshGateway(
        InventoryRefreshResult.success(
            inventories=[
                {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 800, "inventory_max": 1000},
                {"steamId": "steam-2", "nickname": "备用仓", "inventory_num": 760, "inventory_max": 1000},
            ]
        )
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
    )

    detail = service.refresh_account_inventory_detail("a1")

    assert refresh_gateway.calls == [{"account_id": "a1"}]
    assert detail["selected_steam_id"] == "steam-1"
    assert detail["inventories"][0]["nickname"] == "主仓"
    assert detail["inventories"][0]["inventory_num"] == 800
    assert snapshot_repository.saved_payloads[-1]["inventories"][0]["nickname"] == "主仓"
    assert snapshot_repository.saved_payloads[-1]["inventories"][0]["inventory_num"] == 800


def test_purchase_runtime_service_manual_refresh_persists_recovery_due_at_before_return():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 995, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    refresh_gateway = StubInventoryRefreshGateway(InventoryRefreshResult.success(inventories=[]))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        recovery_delay_seconds_provider=lambda: 120.0,
    )
    service.start()

    try:
        detail = service.refresh_account_inventory_detail("a1")
        stored_account = account_repository.get_account("a1")

        assert detail is not None
        assert detail["selected_steam_id"] is None
        assert detail["auto_refresh_due_at"] is not None
        assert stored_account is not None
        assert stored_account.purchase_recovery_due_at == detail["auto_refresh_due_at"]
        assert stored_account.purchase_pool_state == "paused_no_inventory"
    finally:
        service.stop()


def test_purchase_runtime_service_stops_running_runtime():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        runtime_factory=lambda accounts, settings: FakeRuntime(accounts, settings),
    )
    service.start()

    stopped, message = service.stop()

    assert stopped is True
    assert message == "购买运行时已停止"
    snapshot = service.get_status()
    assert snapshot["running"] is False


def test_purchase_runtime_service_accepts_query_hit_when_running_with_available_account():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = StubExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    result = service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    assert result == {"accepted": True, "status": "queued"}
    assert wait_until(lambda: service.get_status()["total_purchased_count"] == 1)
    snapshot = service.get_status()
    assert snapshot["queue_size"] == 0
    assert snapshot["total_purchased_count"] == 1
    assert snapshot["recent_events"][0]["status"] == "success"
    assert snapshot["recent_events"][0]["query_item_name"] == "AK"


def test_purchase_runtime_service_queues_hit_without_waiting_for_purchase_completion():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        started_at = time.perf_counter()
        result = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        elapsed = time.perf_counter() - started_at

        assert result == {"accepted": True, "status": "queued"}
        assert elapsed < 0.2
        assert wait_until(gateway.started.is_set)
        snapshot = service.get_status()
        assert snapshot["total_purchased_count"] == 0
        assert snapshot["recent_events"][0]["status"] == "queued"

        gateway.release.set()
        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 1)
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_queues_hit_while_account_busy_and_dispatches_after_release():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )

        snapshot = service.get_status()
        assert second == {"accepted": True, "status": "queued"}
        assert snapshot["queue_size"] == 1

        gateway.release.set()

        assert wait_until(lambda: len(gateway.calls) == 2)
        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 2)
        assert service.get_status()["queue_size"] == 0
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_fast_path_dispatches_hit_when_account_releases_within_grace_window():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        releaser = threading.Timer(0.02, gateway.release.set)
        releaser.daemon = True
        releaser.start()

        second = asyncio.run(
            service.accept_query_hit_fast_async(
                {
                    "external_item_id": "1380979899390262222",
                    "query_item_name": "AK-2",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                    "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                    "total_price": 89.0,
                    "total_wear_sum": 0.2234,
                    "mode_type": "new_api",
                }
            )
        )

        assert second == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(gateway.calls) == 2)
        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 2)
        assert service.get_status()["queue_size"] == 0
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_fast_path_does_not_require_runtime_snapshot_check():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    class SnapshotlessFastRuntime:
        def __init__(self, accounts, _legacy_settings=None) -> None:
            self.accounts = list(accounts)
            self._running = False

        def start(self) -> None:
            self._running = True

        async def accept_query_hit_fast_async(self, hit: dict[str, object]) -> dict[str, object]:
            return {"accepted": True, "status": str(hit.get("query_item_name") or "")}

        def snapshot(self) -> dict[str, object]:
            raise AssertionError("fast-path should not rely on runtime snapshot checks")

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        runtime_factory=lambda accounts, settings: SnapshotlessFastRuntime(accounts, settings),
    )
    started, _ = service.start()

    try:
        result = asyncio.run(
            service.accept_query_hit_fast_async(
                {
                    "query_item_name": "AK-SNAPSHOTLESS",
                    "product_list": [{"productId": "p-1"}],
                    "mode_type": "new_api",
                }
            )
        )

        assert started is True
        assert result == {"accepted": True, "status": "AK-SNAPSHOTLESS"}
    finally:
        service._runtime = None


def test_purchase_runtime_service_fast_path_does_not_publish_runtime_update_for_intermediate_hit():
    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    hub = RuntimeUpdateHub()
    queue = hub.subscribe("*")
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        runtime_update_hub=hub,
    )

    started, _ = service.start()
    queue.get_nowait()

    try:
        result = asyncio.run(
            service.accept_query_hit_fast_async(
                {
                    "external_item_id": "1380979899390263111",
                    "query_item_name": "AK-NO-PUBLISH",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390263111",
                    "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                    "total_price": 88.0,
                    "total_wear_sum": 0.3334,
                    "mode_type": "new_api",
                }
            )
        )

        assert started is True
        assert result == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(gateway.calls) == 1)
        time.sleep(0.05)
        assert queue.empty()
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_fast_path_does_not_clear_backlog_inline(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1)),
    )
    service.start()
    runtime = service._runtime
    assert runtime is not None
    original_drop_expired_backlog = runtime._drop_expired_backlog

    monkeypatch.setattr(
        runtime,
        "_drop_expired_backlog",
        lambda: (_ for _ in ()).throw(AssertionError("fast-path should not clear backlog inline")),
    )

    try:
        result = asyncio.run(
            service.accept_query_hit_fast_async(
                {
                    "external_item_id": "1380979899390264111",
                    "query_item_name": "AK-NO-BACKLOG-CLEANUP",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390264111",
                    "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                    "total_price": 88.0,
                    "total_wear_sum": 0.4334,
                    "mode_type": "new_api",
                }
            )
        )

        assert result == {"accepted": True, "status": "queued"}
    finally:
        monkeypatch.setattr(runtime, "_drop_expired_backlog", original_drop_expired_backlog)
        service.stop()


def test_purchase_runtime_service_fast_path_claims_ready_account_without_scanning_global_available_list():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    class GuardedAvailableList:
        def __init__(self, values: list[str]) -> None:
            self._values = list(values)

        def __len__(self) -> int:
            return len(self._values)

        def __contains__(self, item: object) -> bool:
            return item in self._values

        def append(self, value: str) -> None:
            self._values.append(value)

        def remove(self, value: str) -> None:
            self._values.remove(value)

        def index(self, value: str) -> int:
            return self._values.index(value)

        def __iter__(self):
            raise AssertionError("fast-path should not scan the global available-account list")

        def __getitem__(self, index):
            raise AssertionError("fast-path should not index into the global available-account list")

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    assert runtime is not None
    runtime._scheduler._available_account_ids = GuardedAvailableList(["a1"])

    try:
        result = asyncio.run(
            service.accept_query_hit_fast_async(
                {
                    "external_item_id": "1380979899390264555",
                    "query_item_name": "AK-BUCKET-READY",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390264555",
                    "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                    "total_price": 88.0,
                    "total_wear_sum": 0.4555,
                    "mode_type": "new_api",
                }
            )
        )

        assert result == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(gateway.calls) == 1)
        assert gateway.calls[0]["account_id"] == "a1"
    finally:
        service.stop()


def test_purchase_runtime_service_fast_path_does_not_block_on_stats_hit_normalization(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [{"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000}],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()
    runtime = service._runtime
    assert runtime is not None

    original_normalize = runtime._stats_aggregator._normalize_product_list

    def slow_normalize(value):
        time.sleep(0.1)
        return original_normalize(value)

    monkeypatch.setattr(runtime._stats_aggregator, "_normalize_product_list", slow_normalize)

    try:
        started_at = time.perf_counter()
        result = asyncio.run(
            service.accept_query_hit_fast_async(
                {
                    "external_item_id": "1380979899390265111",
                    "query_item_name": "AK-NO-STATS-BLOCK",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390265111",
                    "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                    "total_price": 88.0,
                    "total_wear_sum": 0.5334,
                    "mode_type": "new_api",
                }
            )
        )
        elapsed = time.perf_counter() - started_at

        assert result == {"accepted": True, "status": "queued"}
        assert elapsed < 0.05
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_fast_path_waits_on_idle_signal_without_poll_sleep(monkeypatch):
    from app_backend.infrastructure.purchase.runtime import purchase_runtime_service as runtime_module
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()

    async def forbidden_sleep(delay, result=None):
        raise AssertionError(f"fast-path should wait on idle signal, not poll sleep: {delay}")

    monkeypatch.setattr(runtime_module.asyncio, "sleep", forbidden_sleep)

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390266111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390266111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.6234,
                "mode_type": "new_api",
            }
        )
        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        releaser = threading.Timer(0.02, gateway.release.set)
        releaser.daemon = True
        releaser.start()

        second = asyncio.run(
            service.accept_query_hit_fast_async(
                {
                    "external_item_id": "1380979899390266222",
                    "query_item_name": "AK-2",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390266222",
                    "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                    "total_price": 89.0,
                    "total_wear_sum": 0.7234,
                    "mode_type": "new_api",
                }
            )
        )

        assert second == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(gateway.calls) == 2)
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_fast_path_drops_hit_when_all_accounts_stay_busy_past_grace_window():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        second = asyncio.run(
            service.accept_query_hit_fast_async(
                {
                    "external_item_id": "1380979899390262222",
                    "query_item_name": "AK-2",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                    "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                    "total_price": 89.0,
                    "total_wear_sum": 0.2234,
                    "mode_type": "new_api",
                }
            )
        )
        snapshot = service.get_status()

        assert second == {"accepted": False, "status": "dropped_busy_accounts_after_grace"}
        assert len(gateway.calls) == 1
        assert snapshot["queue_size"] == 0
        assert snapshot["recent_events"][0]["status"] == "dropped_busy_accounts_after_grace"
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_defaults_to_three_inflight_tasks_per_account_before_queueing():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        results = []
        for index in range(4):
            results.append(
                service.accept_query_hit(
                    {
                        "external_item_id": f"13809798993902611{index}",
                        "query_item_name": f"AK-{index + 1}",
                        "product_url": f"https://www.c5game.com/csgo/730/asset/13809798993902611{index}",
                        "product_list": [{"productId": f"p-{index + 1}", "price": 88.0 + index, "actRebateAmount": 0}],
                        "total_price": 88.0 + index,
                        "total_wear_sum": 0.1234 + index,
                        "mode_type": "new_api",
                    }
                )
            )

        assert results[:3] == [{"accepted": True, "status": "queued"}] * 3
        assert results[3] == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(gateway.calls) == 3)

        snapshot = service.get_status()
        assert snapshot["queue_size"] == 1
        assert snapshot["active_account_count"] == 1

        gateway.release.set()

        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 4)
        assert len(gateway.calls) == 4
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_reads_max_inflight_from_settings_repository():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository({"max_inflight_per_account": 2}),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261110",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261110",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )
        third = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261112",
                "query_item_name": "AK-3",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261112",
                "product_list": [{"productId": "p-3", "price": 90.0, "actRebateAmount": 0}],
                "total_price": 90.0,
                "total_wear_sum": 0.3234,
                "mode_type": "new_api",
            }
        )

        assert first == {"accepted": True, "status": "queued"}
        assert second == {"accepted": True, "status": "queued"}
        assert third == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(gateway.calls) == 2)
        assert service._runtime._scheduler.account_status("a1")["max_inflight"] == 2
        assert service.get_status()["queue_size"] == 1
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_waits_for_current_purchase_completion_before_applying_new_max_inflight():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = MultiReleaseExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository({"max_inflight_per_account": 1}),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()
    runtime = service._runtime

    try:
        for index in range(3):
            result = service.accept_query_hit(
                {
                    "external_item_id": f"13809798993902621{index}",
                    "query_item_name": f"AK-{index + 1}",
                    "product_url": f"https://www.c5game.com/csgo/730/asset/13809798993902621{index}",
                    "product_list": [{"productId": f"p-{index + 1}", "price": 88.0 + index, "actRebateAmount": 0}],
                    "total_price": 88.0 + index,
                    "total_wear_sum": 0.5234 + index,
                    "mode_type": "new_api",
                }
            )
            assert result == {"accepted": True, "status": "queued"}

        assert wait_until(lambda: len(gateway.release_events) == 1)
        assert runtime._scheduler.account_status("a1")["max_inflight"] == 1

        service.apply_purchase_runtime_settings(
            per_batch_ip_fanout_limit=1,
            max_inflight_per_account=2,
        )

        assert runtime._scheduler.account_status("a1")["max_inflight"] == 1
        assert getattr(runtime, "_pending_purchase_settings", None) == {
            "per_batch_ip_fanout_limit": 1,
            "max_inflight_per_account": 2,
        }
        assert wait_until(lambda: len(gateway.release_events) == 2, timeout=0.2) is False

        gateway.release_events[0].set()

        assert wait_until(lambda: len(gateway.release_events) == 3)
        assert runtime._scheduler.account_status("a1")["max_inflight"] == 2
        assert runtime._dispatch_runners["a1"]._max_concurrent == 2
        assert getattr(runtime, "_pending_purchase_settings", None) is None
    finally:
        for event in list(gateway.release_events):
            event.set()
        service.stop()


def test_purchase_runtime_service_drops_queued_hit_after_timeout():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
        queued_hit_timeout_seconds=0.05,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )
        assert second == {"accepted": True, "status": "queued"}

        time.sleep(0.1)
        gateway.release.set()

        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 1)
        time.sleep(0.1)

        snapshot = service.get_status()
        assert len(gateway.calls) == 1
        assert snapshot["queue_size"] == 0
        assert snapshot["total_purchased_count"] == 1

        retried = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )

        assert retried == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 2)
        assert len(gateway.calls) == 2
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_rejects_hit_when_no_available_accounts():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository()
    refresh_gateway = StubInventoryRefreshGateway(InventoryRefreshResult.success(inventories=[]))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
    )
    service.start()

    result = service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    snapshot = service.get_status()

    assert result == {"accepted": False, "status": "ignored_no_available_accounts"}
    assert snapshot["active_account_count"] == 0
    assert snapshot["queue_size"] == 0
    assert snapshot["purchase_failed_count"] == 0
    assert snapshot["recent_events"][0]["status"] == "ignored_no_available_accounts"


def test_purchase_runtime_service_counts_unique_products_before_fast_dedupe():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "query_config_id": "cfg-1",
                "query_item_id": "item-1",
                "runtime_session_id": "run-1",
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        second = service.accept_query_hit(
            {
                "query_config_id": "cfg-1",
                "query_item_id": "item-1",
                "runtime_session_id": "run-1",
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )

        snapshot = service.get_status()

        assert first == {"accepted": True, "status": "queued"}
        assert second == {"accepted": False, "status": "duplicate_filtered"}
        assert snapshot["matched_product_count"] == 1
        assert snapshot["purchase_failed_count"] == 0
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_partial_success_updates_piece_counts_only():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = StubExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    accepted = service.accept_query_hit(
        {
            "query_config_id": "cfg-1",
            "query_item_id": "item-1",
            "runtime_session_id": "run-1",
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [
                {"productId": "p-1", "price": 88.0, "actRebateAmount": 0},
                {"productId": "p-2", "price": 89.0, "actRebateAmount": 0},
                {"productId": "p-3", "price": 90.0, "actRebateAmount": 0},
            ],
            "total_price": 267.0,
            "total_wear_sum": 0.3333,
            "mode_type": "new_api",
        }
    )

    assert accepted == {"accepted": True, "status": "queued"}
    assert wait_until(lambda: service.get_status()["purchase_success_count"] == 1)
    snapshot = service.get_status()
    assert snapshot["matched_product_count"] == 3
    assert snapshot["purchase_success_count"] == 1
    assert snapshot["purchase_failed_count"] == 2
    assert snapshot["accounts"][0]["submitted_product_count"] == 3
    assert snapshot["accounts"][0]["purchase_success_count"] == 1
    assert snapshot["accounts"][0]["purchase_failed_count"] == 2


def test_purchase_runtime_service_exposes_item_hit_source_summary():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = StubExecutionGateway(PurchaseExecutionResult.success(purchased_count=2))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    first = service.accept_query_hit(
        {
            "query_config_id": "cfg-1",
            "query_item_id": "item-1",
            "runtime_session_id": "run-1",
            "timestamp": "2026-03-20T12:00:00",
            "account_id": "query-a",
            "account_display_name": "查询账号A",
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [
                {"productId": "p-1", "price": 88.0, "actRebateAmount": 0},
                {"productId": "p-2", "price": 89.0, "actRebateAmount": 0},
            ],
            "total_price": 177.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )
    assert first == {"accepted": True, "status": "queued"}
    assert wait_until(lambda: service.get_status()["purchase_success_count"] == 2)

    second = service.accept_query_hit(
        {
            "query_config_id": "cfg-1",
            "query_item_id": "item-1",
            "runtime_session_id": "run-1",
            "timestamp": "2026-03-20T12:00:03",
            "account_id": "query-b",
            "account_display_name": "查询账号B",
            "external_item_id": "1380979899390261112",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261112",
            "product_list": [
                {"productId": "p-3", "price": 90.0, "actRebateAmount": 0},
            ],
            "total_price": 90.0,
            "total_wear_sum": 0.5678,
            "mode_type": "fast_api",
        }
    )

    assert second == {"accepted": True, "status": "queued"}
    assert wait_until(lambda: service.get_status()["purchase_success_count"] == 3)
    snapshot = service.get_status()
    assert snapshot["item_rows"] == [
        {
            "query_item_id": "item-1",
            "matched_product_count": 3,
            "purchase_success_count": 3,
            "purchase_failed_count": 0,
            "source_mode_stats": [
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": "2026-03-20T12:00:00",
                    "account_id": "query-a",
                    "account_display_name": "查询账号A",
                },
                {
                    "mode_type": "fast_api",
                    "hit_count": 1,
                    "last_hit_at": "2026-03-20T12:00:03",
                    "account_id": "query-b",
                    "account_display_name": "查询账号B",
                },
            ],
            "recent_hit_sources": [
                {
                    "mode_type": "fast_api",
                    "hit_count": 1,
                    "last_hit_at": "2026-03-20T12:00:03",
                    "account_id": "query-b",
                    "account_display_name": "查询账号B",
                },
                {
                    "mode_type": "new_api",
                    "hit_count": 2,
                    "last_hit_at": "2026-03-20T12:00:00",
                    "account_id": "query-a",
                    "account_display_name": "查询账号A",
                },
            ],
        }
    ]


def test_purchase_runtime_service_old_runtime_session_results_are_ignored_after_reset():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {
                            "steamId": "steam-1",
                            "nickname": "主仓",
                            "inventory_num": 910,
                            "inventory_max": 1000,
                        },
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        accepted = service.accept_query_hit(
            {
                "query_config_id": "cfg-1",
                "query_item_id": "item-1",
                "runtime_session_id": "run-1",
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        service.bind_query_runtime_session(
            query_config_id="cfg-2",
            query_config_name="配置-B",
            runtime_session_id="run-2",
        )
        gateway.release.set()
        time.sleep(0.3)

        assert wait_until(lambda: service.get_status()["runtime_session_id"] == "run-2")
        snapshot = service.get_status()
        assert snapshot["runtime_session_id"] == "run-2"
        assert snapshot["matched_product_count"] == 0
        assert snapshot["purchase_success_count"] == 0
        assert snapshot["purchase_failed_count"] == 0
        assert snapshot["recent_events"] == []
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_old_runtime_session_auth_invalid_still_expires_account_after_reset():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {
                            "steamId": "steam-1",
                            "nickname": "主仓",
                            "inventory_num": 910,
                            "inventory_max": 1000,
                        },
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.auth_invalid("Not login"))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        accepted = service.accept_query_hit(
            {
                "query_config_id": "cfg-1",
                "query_item_id": "item-1",
                "runtime_session_id": "run-1",
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        service.bind_query_runtime_session(
            query_config_id="cfg-2",
            query_config_name="配置-B",
            runtime_session_id="run-2",
        )
        gateway.release.set()

        assert wait_until(lambda: service.get_status()["accounts"][0]["purchase_capability_state"] == "expired")
        snapshot = service.get_status()
        assert snapshot["runtime_session_id"] == "run-2"
        assert snapshot["active_account_count"] == 0
        assert snapshot["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid"
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_ignores_old_dispatch_results_after_stop():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {
                            "steamId": "steam-1",
                            "nickname": "主仓",
                            "inventory_num": 910,
                            "inventory_max": 1000,
                        },
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()
    runtime = service._runtime

    service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )
    assert wait_until(gateway.started.is_set)

    service.stop()
    gateway.release.set()
    time.sleep(0.3)

    assert runtime._total_purchased_count == 0
    assert all(event.get("status") != "success" for event in runtime._recent_events)


def test_purchase_runtime_service_stop_does_not_start_later_runner_jobs():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {
                            "steamId": "steam-1",
                            "nickname": "主仓",
                            "inventory_num": 910,
                            "inventory_max": 1000,
                        },
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime

    first_batch = PurchaseHitBatch(
        query_item_name="AK-1",
        external_item_id="1380979899390261111",
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
        product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
        total_price=88.0,
        total_wear_sum=0.1234,
        source_mode_type="new_api",
    )
    second_hit = {
        "external_item_id": "1380979899390262222",
        "query_item_name": "AK-2",
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
        "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
        "total_price": 89.0,
        "total_wear_sum": 0.2234,
        "mode_type": "new_api",
    }
    second_batch = runtime._hit_inbox.accept(second_hit)
    assert second_batch is not None

    runtime._start_account_dispatch("a1", first_batch)
    assert wait_until(gateway.started.is_set)
    runtime._start_account_dispatch("a1", second_batch)

    service.stop()
    gateway.release.set()
    time.sleep(0.3)

    assert len(gateway.calls) == 1
    assert gateway.calls[0]["query_item_name"] == "AK-1"
    assert runtime._total_purchased_count == 0
    assert all(event.get("query_item_name") != "AK-2" for event in runtime._recent_events)


def test_default_purchase_runtime_accept_query_hit_rejects_when_running_flag_cleared_mid_stop():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {
                            "steamId": "steam-1",
                            "nickname": "主仓",
                            "inventory_num": 910,
                            "inventory_max": 1000,
                        },
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()
    runtime = service._runtime
    assert runtime is not None

    try:
        with runtime._state_lock:
            runtime._running = False
            active_account_count = runtime._scheduler.active_account_count()

        assert active_account_count == 1
        accepted = asyncio.run(
            runtime.accept_query_hit_async(
                {
                    "external_item_id": "1380979899390264444",
                    "query_item_name": "AK-STOP-RACE",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390264444",
                    "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                    "total_price": 88.0,
                    "total_wear_sum": 0.4234,
                    "mode_type": "new_api",
                }
            )
        )

        assert accepted == {"accepted": False, "status": "ignored_not_running"}
        assert runtime._recent_events[0]["status"] == "ignored_not_running"
        assert runtime._recent_events[0]["query_item_name"] == "AK-STOP-RACE"
    finally:
        runtime.stop()
        service._runtime = None


def test_purchase_runtime_service_stop_blocks_concurrent_accept_from_public_api(monkeypatch):
    import threading

    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {
                            "steamId": "steam-1",
                            "nickname": "主仓",
                            "inventory_num": 910,
                            "inventory_max": 1000,
                        },
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()
    runtime = service._runtime
    assert runtime is not None

    entered_stop = threading.Event()
    release_stop = threading.Event()
    original_stop = runtime.stop

    def blocked_stop():
        entered_stop.set()
        release_stop.wait(timeout=1.0)
        return original_stop()

    monkeypatch.setattr(runtime, "stop", blocked_stop)
    stop_result: dict[str, object] = {}
    accept_result: dict[str, object] = {}

    stop_thread = threading.Thread(
        target=lambda: stop_result.setdefault("value", service.stop()),
        daemon=True,
    )
    accept_thread = threading.Thread(
        target=lambda: accept_result.setdefault(
            "value",
            service.accept_query_hit(
                {
                    "external_item_id": "1380979899390265555",
                    "query_item_name": "AK-STOP-SERVICE",
                    "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390265555",
                    "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                    "total_price": 88.0,
                    "total_wear_sum": 0.5234,
                    "mode_type": "new_api",
                }
            ),
        ),
        daemon=True,
    )

    try:
        stop_thread.start()
        assert wait_until(entered_stop.is_set)

        accept_thread.start()
        time.sleep(0.05)
        assert accept_thread.is_alive()

        release_stop.set()
        stop_thread.join(timeout=1.0)
        accept_thread.join(timeout=1.0)

        assert stop_result["value"] == (True, "购买运行时已停止")
        assert accept_result["value"] == {"accepted": False, "status": "ignored_not_running"}
        assert gateway.calls == []
    finally:
        release_stop.set()
        stop_thread.join(timeout=1.0)
        accept_thread.join(timeout=1.0)
        service.stop()


def test_purchase_runtime_service_stop_ignores_stale_auth_invalid_from_old_runtime():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {
                            "steamId": "steam-1",
                            "nickname": "主仓",
                            "inventory_num": 910,
                            "inventory_max": 1000,
                        },
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    old_gateway = BlockingExecutionGateway(PurchaseExecutionResult.auth_invalid("Not login"))
    new_gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    gateways = [old_gateway, new_gateway]
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateways.pop(0),
        max_inflight_per_account=1,
    )
    service.start()

    try:
        accepted = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-OLD",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(old_gateway.started.is_set)

        service.stop()
        restarted, _ = service.start()
        assert restarted is True
        assert wait_until(lambda: service.get_status()["active_account_count"] == 1)

        old_gateway.release.set()
        time.sleep(0.2)

        next_hit = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-NEW",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )
        assert next_hit == {"accepted": True, "status": "queued"}
        assert wait_until(new_gateway.started.is_set)

        new_gateway.release.set()

        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 1)
        snapshot = service.get_status()
        assert snapshot["accounts"][0]["purchase_capability_state"] == "bound"
        assert snapshot["accounts"][0]["purchase_pool_state"] == "active"
        assert snapshot["active_account_count"] == 1
        assert account_repository.get_account("a1").purchase_capability_state == "bound"
    finally:
        old_gateway.release.set()
        new_gateway.release.set()
        service.stop()


def test_purchase_runtime_service_consumes_queued_hit_and_updates_runtime_snapshot():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
                        {"steamId": "steam-2", "inventory_num": 850, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = StubExecutionGateway(PurchaseExecutionResult.success(purchased_count=2))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    accepted = service.accept_query_hit(
        {
            "query_config_id": "cfg-1",
            "query_item_id": "item-1",
            "runtime_session_id": "run-1",
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    assert accepted == {"accepted": True, "status": "queued"}
    assert wait_until(lambda: service.get_status()["total_purchased_count"] == 2)
    snapshot = service.get_status()
    assert snapshot["queue_size"] == 0
    assert snapshot["total_purchased_count"] == 2
    assert snapshot["active_account_count"] == 1
    assert snapshot["accounts"][0]["purchase_pool_state"] == "active"
    assert snapshot["accounts"][0]["selected_steam_id"] == "steam-1"
    assert snapshot["accounts"][0]["total_purchased_count"] == 2
    assert snapshot["recent_events"][0]["status"] == "success"
    assert snapshot["recent_events"][0]["query_config_id"] == "cfg-1"
    assert snapshot["recent_events"][0]["query_item_id"] == "item-1"
    assert snapshot["recent_events"][0]["runtime_session_id"] == "run-1"
    assert gateway.calls[0]["selected_steam_id"] == "steam-1"
    assert snapshot_repository.saved_payloads[-1]["inventories"][0]["inventory_num"] == 912


def test_purchase_runtime_service_reuses_runtime_account_adapter_across_batches():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )

        assert first == {"accepted": True, "status": "queued"}
        assert second == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(gateway.calls) == 2)
        assert gateway.calls[0]["account"] is gateway.calls[1]["account"]
        assert isinstance(gateway.calls[0]["account"], RuntimeAccountAdapter)
    finally:
        service.stop()


def test_purchase_runtime_service_inflight_purchase_updates_original_inventory_after_runtime_switch():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                        {"steamId": "steam-2", "nickname": "备用仓", "inventory_num": 850, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()

    try:
        accepted = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        updated = service.update_account_purchase_config(
            account_id="a1",
            purchase_disabled=False,
            selected_steam_id="steam-2",
        )
        assert updated["selected_steam_id"] == "steam-2"

        gateway.release.set()
        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 1)

        detail = service.get_account_inventory_detail("a1")
        assert detail["selected_steam_id"] == "steam-2"
        assert detail["inventories"] == [
            {
                "steamId": "steam-1",
                "nickname": "主仓",
                "inventory_num": 911,
                "inventory_max": 1000,
                "remaining_capacity": 89,
                "is_selected": False,
                "is_available": True,
            },
            {
                "steamId": "steam-2",
                "nickname": "备用仓",
                "inventory_num": 850,
                "inventory_max": 1000,
                "remaining_capacity": 150,
                "is_selected": True,
                "is_available": True,
            },
        ]
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_sync_runtime_purchase_config_revalidates_selected_inventory_inside_lock():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1)),
    )
    service.start()

    try:
        applied = service._sync_runtime_purchase_config(
            account_id="a1",
            purchase_disabled=False,
            selected_steam_id="steam-missing",
        )

        snapshot = service.get_status()
        assert applied is True
        assert snapshot["accounts"][0]["selected_steam_id"] == "steam-1"
        assert snapshot["accounts"][0]["purchase_pool_state"] == "active"
    finally:
        service.stop()


def test_purchase_runtime_service_reuses_same_global_session_across_batches(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    created_sessions: list[FakeReusableSession] = []

    def fake_create_session(self, **_kwargs):
        session = FakeReusableSession(asyncio.get_running_loop())
        created_sessions.append(session)
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "_create_session", fake_create_session)

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingSessionReuseGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )
        assert second == {"accepted": True, "status": "queued"}

        gateway.release.set()

        assert wait_until(lambda: len(gateway.calls) == 2)
        assert gateway.calls[0]["session"] is gateway.calls[1]["session"]
        assert len(created_sessions) == 1
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_bind_query_runtime_session_does_not_carry_old_hit_into_new_session(monkeypatch):
    import threading

    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    service.bind_query_runtime_session(
        query_config_id="cfg-old",
        query_config_name="旧配置",
        runtime_session_id="run-old",
    )
    original_claim = runtime._scheduler.claim_idle_accounts_by_bucket

    def wrapped_claim(*, limit_per_bucket: int):
        binder = threading.Thread(
            target=lambda: runtime.bind_query_runtime_session(
                query_config_id="cfg-new",
                query_config_name="新配置",
                runtime_session_id="run-new",
            ),
            daemon=True,
        )
        binder.start()
        time.sleep(0.02)
        claimed = original_claim(limit_per_bucket=limit_per_bucket)
        binder.join(timeout=1.0)
        return claimed

    monkeypatch.setattr(runtime._scheduler, "claim_idle_accounts_by_bucket", wrapped_claim)

    try:
        accepted = service.accept_query_hit(
            {
                "query_config_id": "cfg-old",
                "runtime_session_id": "run-old",
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        gateway.release.set()

        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: service.get_status()["runtime_session_id"] == "run-new")
        snapshot = service.get_status()
        assert snapshot["runtime_session_id"] == "run-new"
        assert snapshot["matched_product_count"] == 0
        assert snapshot["purchase_success_count"] == 0
        assert all(event.get("runtime_session_id") != "run-old" for event in snapshot["recent_events"])
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_bind_query_runtime_session_blocks_old_batch_between_pop_and_generation_capture(monkeypatch):
    import asyncio

    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    runtime.bind_query_runtime_session(
        query_config_id="cfg-old",
        query_config_name="旧配置",
        runtime_session_id="run-old",
    )
    runtime._scheduler.submit(
        PurchaseHitBatch(
            query_item_name="AK-OLD",
            query_config_id="cfg-old",
            runtime_session_id="run-old",
            external_item_id="1380979899390261111",
            product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
            product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            total_price=88.0,
            total_wear_sum=0.1234,
            source_mode_type="new_api",
            enqueued_at=runtime._queue_now(),
        )
    )
    original_pop = runtime._scheduler.pop_next_batch

    def wrapped_pop():
        batch = original_pop()
        runtime.bind_query_runtime_session(
            query_config_id="cfg-new",
            query_config_name="新配置",
            runtime_session_id="run-new",
        )
        return batch

    monkeypatch.setattr(runtime._scheduler, "pop_next_batch", wrapped_pop)

    try:
        drained = asyncio.run(runtime._drain_scheduler())
        gateway.release.set()

        assert drained == "retry"
        snapshot = service.get_status()
        assert gateway.calls == []
        assert snapshot["runtime_session_id"] == "run-new"
        assert snapshot["queue_size"] == 0
        assert snapshot["recent_events"] == []
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_drain_worker_dispatches_without_asyncio_run(monkeypatch):
    from app_backend.infrastructure.purchase.runtime import purchase_runtime_service as purchase_runtime_module
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = StubExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime

    try:
        runtime._scheduler.submit(
            PurchaseHitBatch(
                query_item_name="AK-1",
                external_item_id="1380979899390261111",
                product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
                product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                total_price=88.0,
                total_wear_sum=0.1234,
                source_mode_type="new_api",
                enqueued_at=runtime._queue_now(),
            )
        )

        def fail_asyncio_run(_coroutine):
            raise AssertionError("drain worker should not depend on asyncio.run")

        monkeypatch.setattr(purchase_runtime_module.asyncio, "run", fail_asyncio_run)
        runtime._signal_drain_worker()

        assert wait_until(lambda: len(gateway.calls) == 1)
    finally:
        service.stop()


def test_purchase_runtime_service_bind_query_runtime_session_blocks_old_batch_between_pop_and_dispatch(monkeypatch):
    import asyncio
    import threading

    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    runtime.bind_query_runtime_session(
        query_config_id="cfg-old",
        query_config_name="旧配置",
        runtime_session_id="run-old",
    )
    runtime._scheduler.submit(
        PurchaseHitBatch(
            query_item_name="AK-OLD",
            query_config_id="cfg-old",
            runtime_session_id="run-old",
            external_item_id="1380979899390261111",
            product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
            product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            total_price=88.0,
            total_wear_sum=0.1234,
            source_mode_type="new_api",
            enqueued_at=runtime._queue_now(),
        )
    )
    original_start_dispatch = runtime._start_account_dispatch
    bind_done = threading.Event()

    def wrapped_start_dispatch(account_id: str, batch, **kwargs) -> None:
        binder = threading.Thread(
            target=lambda: (
                runtime.bind_query_runtime_session(
                    query_config_id="cfg-new",
                    query_config_name="新配置",
                    runtime_session_id="run-new",
                ),
                bind_done.set(),
            ),
            daemon=True,
        )
        binder.start()
        time.sleep(0.02)
        original_start_dispatch(account_id, batch, **kwargs)
        binder.join(timeout=1.0)

    monkeypatch.setattr(runtime, "_start_account_dispatch", wrapped_start_dispatch)

    try:
        dispatched = asyncio.run(runtime._drain_scheduler())
        assert dispatched == "idle"
        gateway.release.set()

        assert wait_until(bind_done.is_set)
        assert wait_until(lambda: service.get_status()["runtime_session_id"] == "run-new")
        snapshot = service.get_status()
        assert gateway.calls == []
        assert snapshot["runtime_session_id"] == "run-new"
        assert snapshot["matched_product_count"] == 0
        assert snapshot["purchase_success_count"] == 0
        assert snapshot["recent_events"] == []

        next_hit = service.accept_query_hit(
            {
                "query_config_id": "cfg-new",
                "runtime_session_id": "run-new",
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-NEW",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )
        gateway.release.set()

        assert next_hit == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: service.get_status()["purchase_success_count"] == 1)
        assert len(gateway.calls) == 1
        assert gateway.calls[0]["query_item_name"] == "AK-NEW"
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_session_match_does_not_depend_on_stats_snapshot(monkeypatch):
    import asyncio

    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    runtime.bind_query_runtime_session(
        query_config_id="cfg-1",
        query_config_name="配置一",
        runtime_session_id="run-1",
    )
    runtime._scheduler.submit(
        PurchaseHitBatch(
            query_item_name="AK-1",
            query_config_id="cfg-1",
            runtime_session_id="run-1",
            external_item_id="1380979899390261111",
            product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
            product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            total_price=88.0,
            total_wear_sum=0.1234,
            source_mode_type="new_api",
            enqueued_at=runtime._queue_now(),
        )
    )
    monkeypatch.setattr(
        runtime._stats_aggregator,
        "snapshot",
        lambda: (_ for _ in ()).throw(AssertionError("session match should not query stats snapshot")),
    )

    try:
        drained = asyncio.run(runtime._drain_scheduler())
        gateway.release.set()

        assert drained == "dispatched"
        assert wait_until(lambda: len(gateway.calls) == 1)
        assert gateway.calls[0]["query_item_name"] == "AK-1"
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_drain_worker_does_not_spin_while_all_accounts_busy(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        queued_hit_timeout_seconds=0.2,
    )
    service.start()
    runtime = service._runtime
    call_count = 0
    original = runtime._drain_scheduler

    async def wrapped():
        nonlocal call_count
        call_count += 1
        return await original()

    monkeypatch.setattr(runtime, "_drain_scheduler", wrapped)

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )
        assert second == {"accepted": True, "status": "queued"}

        time.sleep(0.05)

        assert call_count <= 2
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_stop_closes_reused_global_session(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    created_sessions: list[FakeReusableSession] = []

    def fake_create_session(self, **_kwargs):
        session = FakeReusableSession(asyncio.get_running_loop())
        created_sessions.append(session)
        return session

    monkeypatch.setattr(RuntimeAccountAdapter, "_create_session", fake_create_session)

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingSessionReuseGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()

    try:
        accepted = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        service.stop()

        assert wait_until(lambda: bool(created_sessions) and created_sessions[0].closed, timeout=1.0)
    finally:
        gateway.release.set()


def test_purchase_runtime_service_final_expiry_check_blocks_boundary_dispatch(monkeypatch):
    import asyncio

    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        queued_hit_timeout_seconds=0.05,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime

    try:
        runtime._scheduler.submit(
            type(
                "Batch",
                (),
                {
                    "query_item_name": "AK-EDGE",
                    "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                    "total_price": 88.0,
                    "total_wear_sum": 0.1234,
                    "selected_steam_id": "steam-1",
                    "enqueued_at": 100.0,
                },
            )()
        )
        clock_values = iter([100.049, 100.051, 100.051, 100.051, 100.051])
        monkeypatch.setattr(runtime, "_queue_now", lambda: next(clock_values))

        dispatched = asyncio.run(runtime._drain_scheduler())

        assert dispatched == "retry"
        assert gateway.calls == []
        assert service.get_status()["queue_size"] == 0
    finally:
        service.stop()


def test_purchase_runtime_service_drain_retries_after_expired_head_and_dispatches_fresh_tail(monkeypatch):
    import asyncio

    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        queued_hit_timeout_seconds=0.05,
    )
    service.start()
    runtime = service._runtime

    try:
        runtime._scheduler.submit(
            PurchaseHitBatch(
                query_item_name="AK-OLD",
                product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                total_price=88.0,
                total_wear_sum=0.1234,
                source_mode_type="new_api",
                enqueued_at=100.0,
            )
        )
        runtime._scheduler.submit(
            PurchaseHitBatch(
                query_item_name="AK-NEW",
                product_list=[{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                total_price=89.0,
                total_wear_sum=0.2234,
                source_mode_type="new_api",
                enqueued_at=100.03,
            )
        )
        clock_values = iter([100.049, 100.051, 100.051, 100.051, 100.051, 100.051])
        monkeypatch.setattr(runtime, "_queue_now", lambda: next(clock_values))

        first = asyncio.run(runtime._drain_scheduler())
        second = asyncio.run(runtime._drain_scheduler())

        assert first == "retry"
        assert second == "dispatched"
        assert wait_until(lambda: len(gateway.calls) == 1)
        assert gateway.calls[0]["query_item_name"] == "AK-NEW"
    finally:
        service.stop()


def test_purchase_runtime_service_stale_success_outcome_cannot_override_auth_invalid():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch, PurchaseWorkerOutcome

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime

    try:
        runtime.mark_account_auth_invalid(account_id="a1", error="Not login")
        runtime._finish_account_dispatch(
            account_id="a1",
            batch=PurchaseHitBatch(
                query_item_name="AK-STALE",
                product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                total_price=88.0,
                total_wear_sum=0.1234,
            ),
            outcome=PurchaseWorkerOutcome(
                status="success",
                purchased_count=1,
                submitted_count=1,
                selected_steam_id="steam-1",
                pool_state="active",
                capability_state="bound",
                requires_remote_refresh=False,
                error=None,
            ),
            generation=runtime._dispatch_generation,
        )

        snapshot = service.get_status()
        assert snapshot["active_account_count"] == 0
        assert snapshot["accounts"][0]["purchase_capability_state"] == "expired"
        assert snapshot["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid"
    finally:
        service.stop()


def test_purchase_runtime_service_stale_no_account_effect_does_not_clear_backlog_after_other_account_recovers():
    from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import (
        PurchaseRuntimeService,
        _DispatchCompletionEffects,
    )
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            account_id: type(
                "Snapshot",
                (),
                {
                    "account_id": account_id,
                    "selected_steam_id": f"steam-{account_id}",
                    "inventories": [
                        {"steamId": f"steam-{account_id}", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
            for account_id in ("a1", "a2")
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1"), build_account("a2")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()
    runtime = service._runtime
    runtime._scheduler.submit(
        PurchaseHitBatch(
            query_item_name="AK-RACE",
            product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            total_price=88.0,
            total_wear_sum=0.1234,
            source_mode_type="new_api",
        )
    )

    try:
        with runtime._state_lock:
            a2 = runtime._account_states["a2"]
            a2.capability_state = PurchaseCapabilityState.EXPIRED
            a2.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
            runtime._sync_scheduler_state(a2)

            a1 = runtime._account_states["a1"]
            a1.capability_state = PurchaseCapabilityState.EXPIRED
            a1.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
            scheduler_effects = runtime._sync_scheduler_state(a1)
            stale_effects = _DispatchCompletionEffects(
                account_id=a1.account_id,
                expected_state_version=a1.state_version,
                expected_generation=runtime._dispatch_generation,
                scheduler_effects=scheduler_effects,
            )

            a2.capability_state = PurchaseCapabilityState.BOUND
            a2.pool_state = PurchasePoolState.ACTIVE
            runtime._sync_scheduler_state(a2)

        runtime._run_dispatch_completion_effects(stale_effects)

        snapshot = service.get_status()
        assert snapshot["active_account_count"] == 1
        assert snapshot["queue_size"] == 1
        assert not any(
            event.get("status") == "backlog_cleared_no_purchase_accounts"
            for event in snapshot["recent_events"]
        )
    finally:
        service.stop()


def test_purchase_runtime_service_success_reconcile_does_not_hang_stop_or_commit_after_stop():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    class BlockingInventoryRefreshGateway:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.refresh_started = threading.Event()
            self.release_refresh = threading.Event()
            self._call_index = 0

        async def refresh(self, *, account):
            self.calls.append({"account_id": account.account_id})
            self._call_index += 1
            if self._call_index == 1:
                return InventoryRefreshResult.success(
                    inventories=[
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 945, "inventory_max": 1000},
                    ]
                )
            self.refresh_started.set()
            await asyncio.to_thread(self.release_refresh.wait, 1.0)
            return InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-remote-1", "nickname": "刷新仓", "inventory_num": 920, "inventory_max": 1000},
                ]
            )

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 945, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    purchase_gateway = StubExecutionGateway(PurchaseExecutionResult.success(purchased_count=10))
    refresh_gateway = BlockingInventoryRefreshGateway()
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        execution_gateway_factory=lambda: purchase_gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    refresh_gateway.calls.clear()
    saved_before_stop = len(snapshot_repository.saved_payloads)
    accepted = service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK-STOP-RACE",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    stop_thread = None
    try:
        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(refresh_gateway.refresh_started.is_set, timeout=1.0)

        stop_thread = threading.Thread(target=service.stop, daemon=True)
        stop_thread.start()
        stop_completed_before_refresh_release = wait_until(lambda: not stop_thread.is_alive(), timeout=0.5)

        refresh_gateway.release_refresh.set()
        stop_thread.join(timeout=1.0)
        time.sleep(0.3)

        assert stop_completed_before_refresh_release is True
        assert stop_thread.is_alive() is False
        assert runtime is not None
        assert runtime._total_purchased_count == 0
        assert len(snapshot_repository.saved_payloads) == saved_before_stop
        assert all(event.get("status") != "success" for event in runtime._recent_events)
    finally:
        refresh_gateway.release_refresh.set()
        if stop_thread is not None:
            stop_thread.join(timeout=1.0)
        if service._runtime is not None:
            service.stop()


def test_purchase_runtime_service_releases_account_before_success_post_process_finishes():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    class BlockingInventoryRefreshGateway:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []
            self.refresh_started = threading.Event()
            self.release_refresh = threading.Event()
            self._call_index = 0

        async def refresh(self, *, account):
            self.calls.append({"account_id": account.account_id})
            self._call_index += 1
            if self._call_index == 1:
                return InventoryRefreshResult.success(
                    inventories=[
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 945, "inventory_max": 1000},
                    ]
                )
            self.refresh_started.set()
            await asyncio.to_thread(self.release_refresh.wait, 1.0)
            return InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-remote-1", "nickname": "刷新仓", "inventory_num": 920, "inventory_max": 1000},
                ]
            )

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 945, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    purchase_gateway = StubExecutionGateway(PurchaseExecutionResult.success(purchased_count=10))
    refresh_gateway = BlockingInventoryRefreshGateway()
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        execution_gateway_factory=lambda: purchase_gateway,
        max_inflight_per_account=1,
    )
    service.start()
    refresh_gateway.calls.clear()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-ASYNC-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )

        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(refresh_gateway.refresh_started.is_set, timeout=1.0)

        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261112",
                "query_item_name": "AK-ASYNC-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261112",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )

        assert second == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(purchase_gateway.calls) == 2, timeout=0.3)
    finally:
        refresh_gateway.release_refresh.set()
        service.stop()


def test_purchase_runtime_service_auth_invalid_drops_queued_success_post_process(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch, PurchaseWorkerOutcome

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1)),
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    started = threading.Event()
    release = threading.Event()
    original_process = getattr(runtime, "_process_post_process_job")

    def blocking_process(job):
        started.set()
        release.wait(1.0)
        return original_process(job)

    monkeypatch.setattr(runtime, "_process_post_process_job", blocking_process)

    try:
        runtime._finish_account_dispatch(
            account_id="a1",
            batch=PurchaseHitBatch(
                query_item_name="AK-ASYNC-STALE",
                product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                total_price=88.0,
                total_wear_sum=0.1234,
            ),
            outcome=PurchaseWorkerOutcome(
                status="success",
                purchased_count=1,
                submitted_count=1,
                selected_steam_id="steam-1",
                pool_state="active",
                capability_state="bound",
                requires_remote_refresh=False,
                error=None,
            ),
            generation=runtime._dispatch_generation,
        )

        assert wait_until(started.is_set, timeout=1.0)
        runtime.mark_account_auth_invalid(account_id="a1", error="Not login")
        release.set()

        assert wait_until(lambda: service.get_status()["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid")
        snapshot = service.get_status()
        assert snapshot["accounts"][0]["purchase_capability_state"] == "expired"
        assert snapshot["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid"
        assert snapshot["accounts"][0]["selected_inventory_remaining_capacity"] == 90
        assert snapshot["accounts"][0]["last_error"] == "Not login"
        assert snapshot["accounts"][0]["total_purchased_count"] == 0
    finally:
        release.set()
        service.stop()


def test_purchase_runtime_service_emits_purchase_stats_events():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseExecutionResult
    from app_backend.infrastructure.stats.runtime.stats_events import (
        PurchaseCreateOrderStatsEvent,
        PurchaseSubmitOrderStatsEvent,
    )

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = StubExecutionGateway(
        PurchaseExecutionResult(
            status="success",
            purchased_count=1,
            submitted_count=2,
            error=None,
            create_order_latency_ms=210.0,
            submit_order_latency_ms=450.0,
        )
    )
    stats_sink = StubStatsSink()
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        stats_sink=stats_sink,
    )
    service.start()

    try:
        accepted = service.accept_query_hit(
            {
                "query_config_id": "cfg-1",
                "query_item_id": "item-1",
                "runtime_session_id": "run-1",
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [
                    {"productId": "p-1", "price": 88.0, "actRebateAmount": 0},
                    {"productId": "p-2", "price": 89.0, "actRebateAmount": 0},
                ],
                "total_price": 177.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
                "detail_min_wear": 0.12,
                "detail_max_wear": 0.3,
                "max_price": 123.45,
            }
        )

        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 1 and len(stats_sink.events) == 2)

        create_event = stats_sink.events[0]
        submit_event = stats_sink.events[1]
        assert isinstance(create_event, PurchaseCreateOrderStatsEvent)
        assert isinstance(submit_event, PurchaseSubmitOrderStatsEvent)
        assert create_event.query_item_id == "item-1"
        assert create_event.runtime_session_id == "run-1"
        assert create_event.submitted_count == 2
        assert create_event.create_order_latency_ms == 210.0
        assert create_event.status == "success"
        assert submit_event.submitted_count == 2
        assert submit_event.success_count == 1
        assert submit_event.failed_count == 1
        assert submit_event.submit_order_latency_ms == 450.0
        assert submit_event.status == "success"
    finally:
        service.stop()


def test_purchase_runtime_service_ignores_stats_sink_failures():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseExecutionResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = StubExecutionGateway(
        PurchaseExecutionResult(
            status="success",
            purchased_count=1,
            submitted_count=1,
            error=None,
            create_order_latency_ms=210.0,
            submit_order_latency_ms=450.0,
        )
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        stats_sink=StubStatsSink(error=RuntimeError("stats down")),
    )
    service.start()

    try:
        accepted = service.accept_query_hit(
            {
                "query_config_id": "cfg-1",
                "query_item_id": "item-1",
                "runtime_session_id": "run-1",
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )

        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: service.get_status()["total_purchased_count"] == 1)
        snapshot = service.get_status()
        assert snapshot["total_purchased_count"] == 1
        assert snapshot["recent_events"][0]["status"] == "success"
    finally:
        service.stop()


def test_purchase_runtime_service_marks_account_auth_invalid_without_dropping_capability_registration():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = StubExecutionGateway(PurchaseExecutionResult.auth_invalid("Not login"))
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    assert wait_until(lambda: service.get_status()["accounts"][0]["purchase_capability_state"] == "expired")
    snapshot = service.get_status()
    assert snapshot["queue_size"] == 0
    assert snapshot["total_purchased_count"] == 0
    assert snapshot["accounts"][0]["purchase_capability_state"] == "expired"
    assert snapshot["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid"
    assert snapshot["recent_events"][0]["status"] == "auth_invalid"


def test_purchase_runtime_service_treats_payment_success_no_items_as_product_contention_not_account_error():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = StubExecutionGateway(
        PurchaseExecutionResult(
            status="payment_success_no_items",
            purchased_count=0,
            submitted_count=1,
            error="支付失败: 订单数据发生变化,请刷新页面重试",
            status_code=409,
            request_method="POST",
            request_path="/pay/order/v1/pay",
            request_body={
                "bizOrderId": "order-1",
                "orderType": 4,
                "payAmount": "88.00",
                "receiveSteamId": "steam-1",
            },
            response_text='{"errorMsg":"订单数据发生变化,请刷新页面重试"}',
        )
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    accepted = service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    assert accepted == {"accepted": True, "status": "queued"}
    assert wait_until(lambda: len(service.get_status()["recent_events"]) >= 1)

    snapshot = service.get_status()
    persisted = account_repository.get_account("a1")
    assert snapshot["accounts"][0]["purchase_pool_state"] == "active"
    assert snapshot["accounts"][0]["last_error"] is None
    assert snapshot["recent_events"][0]["status"] == "payment_success_no_items"
    assert snapshot["recent_events"][0]["message"] == "购买了但是没有买到物品：订单数据发生变化,请刷新页面重试"
    assert snapshot["recent_events"][0]["request_body"] == {
        "bizOrderId": "order-1",
        "orderType": 4,
        "payAmount": "88.00",
        "receiveSteamId": "steam-1",
    }
    assert snapshot["recent_events"][0]["response_text"] == '{"errorMsg":"订单数据发生变化,请刷新页面重试"}'
    assert persisted.last_error is None
    assert persisted.purchase_pool_state == "active"


def test_purchase_runtime_service_rechecks_remote_inventory_when_purchase_exhausts_local_capacity():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 945, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    purchase_gateway = StubExecutionGateway(PurchaseExecutionResult.success(purchased_count=10))
    refresh_gateway = StubInventoryRefreshGateway(
        [
            InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-1", "inventory_num": 945, "inventory_max": 1000},
                ]
            ),
            InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-remote-1", "inventory_num": 920, "inventory_max": 1000},
                    {"steamId": "steam-remote-2", "inventory_num": 880, "inventory_max": 1000},
                ]
            ),
        ]
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        execution_gateway_factory=lambda: purchase_gateway,
    )
    service.start()
    refresh_gateway.calls.clear()

    service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    assert wait_until(
        lambda: refresh_gateway.calls == [{"account_id": "a1"}]
        and service.get_status()["accounts"][0]["selected_steam_id"] == "steam-remote-1"
    )
    snapshot = service.get_status()
    assert refresh_gateway.calls == [{"account_id": "a1"}]
    assert snapshot["total_purchased_count"] == 10
    assert snapshot["active_account_count"] == 1
    assert snapshot["accounts"][0]["purchase_pool_state"] == "active"
    assert snapshot["accounts"][0]["selected_steam_id"] == "steam-remote-1"
    assert snapshot_repository.saved_payloads[-1]["selected_steam_id"] == "steam-remote-1"
    assert snapshot_repository.saved_payloads[-1]["inventories"][0]["steamId"] == "steam-remote-1"


def test_purchase_runtime_service_pauses_account_when_remote_inventory_recheck_confirms_empty():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 945, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    purchase_gateway = StubExecutionGateway(PurchaseExecutionResult.success(purchased_count=10))
    refresh_gateway = StubInventoryRefreshGateway(
        [
            InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-1", "inventory_num": 945, "inventory_max": 1000},
                ]
            ),
            InventoryRefreshResult.success(inventories=[]),
        ]
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        execution_gateway_factory=lambda: purchase_gateway,
    )
    service.start()
    refresh_gateway.calls.clear()

    service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    assert wait_until(
        lambda: refresh_gateway.calls == [{"account_id": "a1"}]
        and service.get_status()["active_account_count"] == 0
        and service.get_status()["accounts"][0]["purchase_pool_state"] == "paused_no_inventory"
        and service.get_status()["accounts"][0]["selected_steam_id"] is None
    )
    snapshot = service.get_status()
    assert refresh_gateway.calls == [{"account_id": "a1"}]
    assert snapshot["total_purchased_count"] == 10
    assert snapshot["active_account_count"] == 0
    assert snapshot["accounts"][0]["purchase_pool_state"] == "paused_no_inventory"
    assert snapshot["accounts"][0]["selected_steam_id"] is None
    assert snapshot["recent_events"][0]["status"] == "paused_no_inventory"


def test_purchase_runtime_service_recovery_check_reactivates_paused_account():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository()
    refresh_gateway = StubInventoryRefreshGateway(
        [
            InventoryRefreshResult.success(inventories=[]),
            InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-restore-1", "inventory_num": 930, "inventory_max": 1000},
                ]
            ),
        ]
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        recovery_delay_seconds_provider=lambda: 0.01,
    )
    service.start()

    try:
        assert wait_until(lambda: service.get_status()["active_account_count"] == 1)
        snapshot = service.get_status()
        assert snapshot["accounts"][0]["purchase_pool_state"] == "active"
        assert snapshot["accounts"][0]["selected_steam_id"] == "steam-restore-1"
        assert snapshot["recent_events"][0]["status"] == "inventory_recovered"
    finally:
        service.stop()


def test_purchase_runtime_service_recovery_check_reschedules_when_inventory_still_empty():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository()
    refresh_gateway = StubInventoryRefreshGateway(
        [
            InventoryRefreshResult.success(inventories=[]),
            InventoryRefreshResult.success(inventories=[]),
            InventoryRefreshResult.success(
                inventories=[
                    {"steamId": "steam-restore-2", "inventory_num": 920, "inventory_max": 1000},
                ]
            ),
        ]
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        recovery_delay_seconds_provider=lambda: 0.01,
    )
    service.start()

    try:
        assert wait_until(lambda: service.get_status()["active_account_count"] == 1, timeout=1.5)
        snapshot = service.get_status()
        assert len(refresh_gateway.calls) >= 3
        assert snapshot["accounts"][0]["purchase_pool_state"] == "active"
        assert snapshot["accounts"][0]["selected_steam_id"] == "steam-restore-2"
    finally:
        service.stop()


def test_purchase_runtime_service_marks_account_auth_invalid_from_query_not_login_signal():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
    )

    service.start()
    service.mark_account_auth_invalid(account_id="a1", error="Not login")
    snapshot = service.get_status()

    assert snapshot["active_account_count"] == 0
    assert snapshot["accounts"][0]["purchase_capability_state"] == "expired"
    assert snapshot["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid"
    assert snapshot["accounts"][0]["last_error"] == "Not login"
    assert snapshot["recent_events"][0]["status"] == "auth_invalid"
    assert account_repository.get_account("a1").purchase_capability_state == "expired"


def test_purchase_runtime_service_inflight_success_does_not_reactivate_auth_invalid_account():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        accepted = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        service.mark_account_auth_invalid(account_id="a1", error="Not login")
        gateway.release.set()

        assert wait_until(lambda: service.get_status()["accounts"][0]["purchase_capability_state"] == "expired")
        snapshot = service.get_status()
        assert snapshot["active_account_count"] == 0
        assert snapshot["accounts"][0]["purchase_pool_state"] == "paused_auth_invalid"
        assert snapshot["accounts"][0]["selected_inventory_remaining_capacity"] == 90

        next_hit = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )
        assert next_hit == {"accepted": False, "status": "ignored_no_available_accounts"}
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_auth_invalid_skips_later_runner_jobs():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    refresh_gateway = StubInventoryRefreshGateway(
        InventoryRefreshResult.success(
            inventories=[
                {"steamId": "steam-recovered", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
            ]
        )
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime

    first_batch = PurchaseHitBatch(
        query_item_name="AK-1",
        external_item_id="1380979899390261111",
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
        product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
        total_price=88.0,
        total_wear_sum=0.1234,
        source_mode_type="new_api",
    )
    second_hit = {
        "external_item_id": "1380979899390262222",
        "query_item_name": "AK-2",
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
        "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
        "total_price": 89.0,
        "total_wear_sum": 0.2234,
        "mode_type": "new_api",
    }
    second_batch = runtime._hit_inbox.accept(second_hit)
    assert second_batch is not None

    try:
        runtime._start_account_dispatch("a1", first_batch)
        assert wait_until(gateway.started.is_set)
        runtime._start_account_dispatch("a1", second_batch)

        service.mark_account_auth_invalid(account_id="a1", error="Not login")
        gateway.release.set()
        time.sleep(0.3)
        detail = service.refresh_account_inventory_detail("a1")
        assert detail is not None
        time.sleep(0.2)

        snapshot = service.get_status()
        assert len(gateway.calls) == 1
        assert gateway.calls[0]["query_item_name"] == "AK-1"
        assert snapshot["accounts"][0]["purchase_capability_state"] == "bound"
        assert snapshot["accounts"][0]["purchase_pool_state"] == "active"
        assert snapshot["active_account_count"] == 1
        assert runtime._tracked_dispatch_batches == {}
        assert all(event.get("query_item_name") != "AK-2" for event in snapshot["recent_events"])
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_auth_invalid_canceled_before_gateway_start_forgets_dedupe_cache():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    refresh_gateway = StubInventoryRefreshGateway(
        InventoryRefreshResult.success(
            inventories=[
                {"steamId": "steam-recovered", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
            ]
        )
    )
    gateway = PreGatewayBlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    assert runtime is not None

    try:
        accepted = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-CANCEL",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.entered.is_set)

        service.mark_account_auth_invalid(account_id="a1", error="Not login")

        assert wait_until(lambda: service.get_status()["accounts"][0]["purchase_capability_state"] == "expired")
        assert wait_until(lambda: runtime._hit_inbox._cache == {})
        assert gateway.started.is_set() is False
        assert gateway.calls == []

        detail = service.refresh_account_inventory_detail("a1")
        assert detail is not None
        assert wait_until(lambda: service.get_status()["active_account_count"] == 1)

        gateway.release.set()
        replayed = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-CANCEL-RETRY",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )

        assert replayed == {"accepted": True, "status": "queued"}
        assert wait_until(
            lambda: len(gateway.calls) == 1 and gateway.calls[0]["query_item_name"] == "AK-CANCEL-RETRY"
        )
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_post_gateway_cancelled_error_does_not_restore_dispatched_batch():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = PostGatewayCancelledExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    assert runtime is not None

    try:
        accepted = service.accept_query_hit(
            {
                "external_item_id": "1380979899390266666",
                "query_item_name": "AK-CANCELLED",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390266666",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.6234,
                "mode_type": "new_api",
            }
        )

        assert accepted == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)
        assert wait_until(lambda: runtime._account_states["a1"].busy is False)
        assert runtime._scheduler.queue_size() == 0
        assert wait_until(gateway.replayed.is_set, timeout=0.3) is False
        assert len(gateway.calls) == 1

        replayed = service.accept_query_hit(
            {
                "external_item_id": "1380979899390267777",
                "query_item_name": "AK-CANCELLED-RETRY",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390267777",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.6234,
                "mode_type": "new_api",
            }
        )

        assert replayed == {"accepted": False, "status": "duplicate_filtered"}
        assert gateway.replayed.is_set() is False
        assert len(gateway.calls) == 1
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_mark_auth_invalid_does_not_forget_batch_still_running_on_other_account():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            account_id: type(
                "Snapshot",
                (),
                {
                    "account_id": account_id,
                    "selected_steam_id": f"steam-{account_id}",
                    "inventories": [
                        {"steamId": f"steam-{account_id}", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
            for account_id in ("a1", "a2")
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1"), build_account("a2")]),
        settings_repository=FakeSettingsRepository({"per_batch_ip_fanout_limit": 2}),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    first_batch = PurchaseHitBatch(
        query_item_name="AK-1",
        external_item_id="1380979899390261111",
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
        product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
        total_price=88.0,
        total_wear_sum=0.1234,
        source_mode_type="new_api",
    )
    second_hit = {
        "external_item_id": "1380979899390262222",
        "query_item_name": "AK-2",
        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
        "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
        "total_price": 89.0,
        "total_wear_sum": 0.2234,
        "mode_type": "new_api",
    }
    second_batch = runtime._hit_inbox.accept(second_hit)
    assert second_batch is not None

    try:
        runtime._start_account_dispatch("a1", first_batch)
        assert wait_until(
            lambda: any(
                call["account_id"] == "a1" and call["query_item_name"] == "AK-1"
                for call in gateway.calls
            )
        )

        runtime._start_account_dispatch("a1", second_batch)
        runtime._start_account_dispatch("a2", second_batch)
        assert wait_until(
            lambda: any(
                call["account_id"] == "a2" and call["query_item_name"] == "AK-2"
                for call in gateway.calls
            )
        )

        service.mark_account_auth_invalid(account_id="a1", error="Not login")

        duplicate = service.accept_query_hit(
            {
                    "external_item_id": "1380979899390263333",
                "query_item_name": "AK-2-DUP",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390263333",
                "product_list": [{"productId": "p-3", "price": 90.0, "actRebateAmount": 0}],
                "total_price": 90.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )

        assert duplicate == {"accepted": False, "status": "duplicate_filtered"}
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_skipped_dispatch_clears_popped_batch_when_last_account_invalidates():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()
    runtime = service._runtime
    runner = runtime._dispatch_runners["a1"]
    original_should_process = runner._should_process
    should_process_calls = 0

    def wrapped_should_process(generation: int) -> bool:
        nonlocal should_process_calls
        should_process_calls += 1
        if should_process_calls == 1:
            return original_should_process(generation)
        service.mark_account_auth_invalid(account_id="a1", error="Not login")
        return False

    runner._should_process = wrapped_should_process

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )
        assert second == {"accepted": True, "status": "queued"}

        gateway.release.set()

        assert wait_until(
            lambda: service.get_status()["active_account_count"] == 0
            and service.get_status()["queue_size"] == 0
        )
        snapshot = service.get_status()
        assert len(gateway.calls) == 1
        assert gateway.calls[0]["query_item_name"] == "AK-1"
        assert any(
            event.get("status") == "backlog_cleared_no_purchase_accounts"
            for event in snapshot["recent_events"]
        )
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_mark_auth_invalid_blocks_accept_until_scheduler_sync(monkeypatch):
    import threading

    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()
    runtime = service._runtime
    entered_sync = threading.Event()
    release_sync = threading.Event()
    original_sync = runtime._sync_scheduler_state

    def wrapped_sync(state):
        entered_sync.set()
        release_sync.wait(timeout=1.0)
        return original_sync(state)

    monkeypatch.setattr(runtime, "_sync_scheduler_state", wrapped_sync)

    auth_thread = threading.Thread(
        target=lambda: service.mark_account_auth_invalid(account_id="a1", error="Not login"),
        daemon=True,
    )
    auth_thread.start()
    accept_result: dict[str, object] = {}

    try:
        assert wait_until(entered_sync.is_set)

        accept_thread = threading.Thread(
            target=lambda: accept_result.setdefault(
                "result",
                service.accept_query_hit(
                    {
                        "external_item_id": "1380979899390261111",
                        "query_item_name": "AK-RACE",
                        "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                        "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                        "total_price": 88.0,
                        "total_wear_sum": 0.1234,
                        "mode_type": "new_api",
                    }
                ),
            ),
            daemon=True,
        )
        accept_thread.start()
        time.sleep(0.05)

        assert accept_thread.is_alive()

        release_sync.set()
        auth_thread.join(timeout=1.0)
        accept_thread.join(timeout=1.0)

        assert accept_result["result"] == {"accepted": False, "status": "ignored_no_available_accounts"}
    finally:
        release_sync.set()
        auth_thread.join(timeout=1.0)
        service.stop()


def test_purchase_runtime_service_restore_or_drop_batch_does_not_requeue_into_new_session(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()
    runtime = service._runtime
    runtime.bind_query_runtime_session(
        query_config_id="cfg-old",
        query_config_name="旧配置",
        runtime_session_id="run-old",
    )
    batch = PurchaseHitBatch(
        query_item_name="AK-OLD",
        query_config_id="cfg-old",
        runtime_session_id="run-old",
        external_item_id="1380979899390261111",
        product_url="https://www.c5game.com/csgo/730/asset/1380979899390261111",
        product_list=[{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
        total_price=88.0,
        total_wear_sum=0.1234,
        source_mode_type="new_api",
        enqueued_at=runtime._queue_now(),
    )
    bind_done = threading.Event()

    original_signal = runtime._signal_drain_worker

    def wrapped_signal() -> None:
        runtime.bind_query_runtime_session(
            query_config_id="cfg-new",
            query_config_name="新配置",
            runtime_session_id="run-new",
        )
        bind_done.set()
        original_signal()

    monkeypatch.setattr(runtime, "_signal_drain_worker", wrapped_signal)

    try:
        result = runtime._restore_or_drop_undispatched_batch(batch, generation=runtime._dispatch_generation)

        assert result == "requeued"
        assert bind_done.is_set()
        snapshot = service.get_status()
        assert snapshot["runtime_session_id"] == "run-new"
        assert snapshot["queue_size"] == 0
    finally:
        service.stop()


def test_purchase_runtime_service_stale_clear_backlog_does_not_clear_new_session_queue():
    from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import (
        PurchaseRuntimeService,
        _DispatchCompletionEffects,
    )
    from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseHitBatch

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()
    runtime = service._runtime
    runtime.bind_query_runtime_session(
        query_config_id="cfg-old",
        query_config_name="旧配置",
        runtime_session_id="run-old",
    )
    with runtime._state_lock:
        state = runtime._account_states["a1"]
        state.capability_state = PurchaseCapabilityState.EXPIRED
        state.pool_state = PurchasePoolState.PAUSED_AUTH_INVALID
        scheduler_effects = runtime._sync_scheduler_state(state)
        stale_effects = _DispatchCompletionEffects(
            account_id=state.account_id,
            expected_state_version=state.state_version,
            expected_generation=runtime._dispatch_generation,
            scheduler_effects=scheduler_effects,
        )

    runtime.bind_query_runtime_session(
        query_config_id="cfg-new",
        query_config_name="新配置",
        runtime_session_id="run-new",
    )
    runtime._scheduler.submit(
        PurchaseHitBatch(
            query_item_name="AK-NEW",
            query_config_id="cfg-new",
            runtime_session_id="run-new",
            external_item_id="1380979899390262222",
            product_url="https://www.c5game.com/csgo/730/asset/1380979899390262222",
            product_list=[{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
            total_price=89.0,
            total_wear_sum=0.2234,
            source_mode_type="new_api",
            enqueued_at=runtime._queue_now(),
        )
    )

    try:
        runtime._run_dispatch_completion_effects(stale_effects)

        snapshot = service.get_status()
        assert snapshot["runtime_session_id"] == "run-new"
        assert snapshot["queue_size"] == 1
    finally:
        service.stop()


def test_purchase_runtime_service_does_not_leave_backlog_when_last_account_invalidates_during_enqueue(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: RecordingAccountGateway(PurchaseExecutionResult.success(purchased_count=1)),
    )
    service.start()
    runtime = service._runtime

    def invalidate_then_claim(*, limit_per_bucket: int):
        runtime.mark_account_auth_invalid(account_id="a1", error="Not login")
        return []

    monkeypatch.setattr(runtime._scheduler, "claim_idle_accounts_by_bucket", invalidate_then_claim)

    try:
        result = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-RACE",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )

        snapshot = service.get_status()
        assert result == {"accepted": False, "status": "ignored_no_available_accounts"}
        assert snapshot["active_account_count"] == 0
        assert snapshot["queue_size"] == 0
    finally:
        service.stop()


def test_purchase_runtime_service_rejects_hit_after_last_account_becomes_unavailable():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
    )

    service.start()
    service.mark_account_auth_invalid(account_id="a1", error="Not login")

    result = service.accept_query_hit(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        }
    )

    snapshot = service.get_status()

    assert result == {"accepted": False, "status": "ignored_no_available_accounts"}
    assert snapshot["active_account_count"] == 0
    assert snapshot["queue_size"] == 0
    assert snapshot["purchase_failed_count"] == 0
    assert snapshot["recent_events"][0]["status"] == "ignored_no_available_accounts"


def test_purchase_runtime_service_buffers_recent_events_until_snapshot_flush():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()
    runtime = service._runtime

    try:
        runtime._push_event(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-BUFFER",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            },
            status="queued",
            message="命中已进入购买池",
            notify=False,
        )

        assert runtime._recent_events == []
        snapshot = runtime.snapshot()
        assert snapshot["recent_events"][0]["status"] == "queued"
        assert snapshot["recent_events"][0]["query_item_name"] == "AK-BUFFER"
    finally:
        service.stop()


def test_purchase_runtime_service_status_without_recent_events_does_not_flush_diagnostics_buffer():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()
    runtime = service._runtime

    try:
        runtime._push_event(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-HIDDEN",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            },
            status="queued",
            message="命中已进入购买池",
            notify=False,
        )

        assert runtime._recent_events == []

        snapshot = service.get_status(include_recent_events=False)

        assert snapshot["recent_events"] == []
        assert runtime._recent_events == []
    finally:
        service.stop()


def test_purchase_runtime_service_hot_hit_logging_does_not_materialize_product_list():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import _DefaultPurchaseRuntime

    class GuardedProducts:
        def __iter__(self):
            raise AssertionError("hot hit logging should not iterate product_list on the caller thread")

    runtime = _DefaultPurchaseRuntime(
        [],
        inventory_refresh_gateway_factory=None,
        recovery_delay_seconds_provider=None,
        execution_gateway_factory=lambda: object(),
    )

    runtime._push_event(
        {
            "external_item_id": "1380979899390261111",
            "query_item_name": "AK-GUARDED",
            "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
            "product_list": GuardedProducts(),
            "total_price": 88.0,
            "total_wear_sum": 0.1234,
            "mode_type": "new_api",
        },
        status="queued",
        message="命中已进入购买池",
        notify=False,
    )

    assert runtime._diagnostics_event_queue.qsize() == 1


def test_purchase_runtime_service_direct_hit_path_reuses_caller_payload(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=FakeInventorySnapshotRepository(),
    )
    service.start()
    runtime = service._runtime
    hit = _build_hit_payload()
    seen: dict[str, object] = {}

    def fake_accept_now(payload: dict[str, object]) -> dict[str, object]:
        seen["same_object"] = payload is hit
        return {"accepted": True, "status": "queued"}

    monkeypatch.setattr(runtime, "_accept_query_hit_now", fake_accept_now)

    try:
        result = asyncio.run(service.accept_query_hit_async(hit))
    finally:
        service.stop()

    assert result == {"accepted": True, "status": "queued"}
    assert seen == {"same_object": True}


def test_purchase_runtime_service_fast_hit_path_reuses_caller_payload(monkeypatch):
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=FakeInventorySnapshotRepository(),
    )
    service.start()
    runtime = service._runtime
    hit = _build_hit_payload()
    seen: dict[str, object] = {}

    def fake_prepare(payload: dict[str, object]) -> dict[str, object]:
        seen["same_object"] = payload is hit
        return {"batch": None, "result": {"accepted": False, "status": "duplicate_filtered"}}

    monkeypatch.setattr(runtime, "_prepare_fast_query_hit", fake_prepare)

    try:
        result = asyncio.run(service.accept_query_hit_fast_async(hit))
    finally:
        service.stop()

    assert result == {"accepted": False, "status": "duplicate_filtered"}
    assert seen == {"same_object": True}


def test_purchase_runtime_service_queued_hit_path_keeps_detached_payload_copy():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=FakeInventorySnapshotRepository(),
    )
    service.start()
    runtime = service._runtime
    hit = _build_hit_payload()

    try:
        result = service.enqueue_query_hit(hit)
        queued_payload = runtime._hit_intake_queue.get_nowait()
    finally:
        service.stop()

    hit["query_item_name"] = "AK-MUTATED"
    hit["product_list"].append({"productId": "p-2", "price": 99.0, "actRebateAmount": 0})

    assert result == {"accepted": True, "status": "queued"}
    assert queued_payload is not hit
    assert queued_payload["query_item_name"] == "AK-47"
    assert len(queued_payload["product_list"]) == 1


def test_purchase_runtime_service_hit_entrypoints_advertise_readonly_safe_query_payload():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    safe_methods = (
        PurchaseRuntimeService.accept_query_hit,
        PurchaseRuntimeService.accept_query_hit_async,
        PurchaseRuntimeService.accept_query_hit_fast_async,
        PurchaseRuntimeService.enqueue_query_hit,
    )

    assert all(getattr(method, "_query_hit_readonly_safe", False) is True for method in safe_methods)


def test_purchase_runtime_service_mark_account_auth_invalid_clears_stale_recovery_due_at_without_runtime():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account = build_account("a1")
    account.purchase_recovery_due_at = (datetime.now() + timedelta(seconds=180)).isoformat()
    account_repository = FakeAccountRepository([account])
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
    )

    service.mark_account_auth_invalid(account_id="a1", error="Not login")

    detail = service.get_account_inventory_detail("a1")
    stored = account_repository.get_account("a1")

    assert detail is not None
    assert detail["auto_refresh_due_at"] is None
    assert stored is not None
    assert stored.purchase_recovery_due_at is None
    assert stored.purchase_capability_state == "expired"
    assert stored.purchase_pool_state == "paused_auth_invalid"


def test_purchase_runtime_service_clears_queued_hits_when_last_account_becomes_unavailable():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "nickname": "主仓", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK-1",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )
        assert first == {"accepted": True, "status": "queued"}
        assert wait_until(gateway.started.is_set)

        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390262222",
                "query_item_name": "AK-2",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390262222",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2234,
                "mode_type": "new_api",
            }
        )
        assert second == {"accepted": True, "status": "queued"}
        assert service.get_status()["queue_size"] == 1

        service.mark_account_auth_invalid(account_id="a1", error="Not login")

        snapshot = service.get_status()
        assert snapshot["active_account_count"] == 0
        assert snapshot["queue_size"] == 0
        assert any(
            event.get("status") == "backlog_cleared_no_purchase_accounts"
            for event in snapshot["recent_events"]
        )
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_fans_out_one_batch_across_idle_accounts_per_bucket_limit():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    accounts = [
        build_account("b1-1", browser_proxy_mode="custom", browser_proxy_url="http://bucket-1"),
        build_account("b1-2", browser_proxy_mode="custom", browser_proxy_url="http://bucket-1"),
        build_account("b2-1", browser_proxy_mode="custom", browser_proxy_url="http://bucket-2"),
        build_account("b2-2", browser_proxy_mode="custom", browser_proxy_url="http://bucket-2"),
        build_account("b2-3", browser_proxy_mode="custom", browser_proxy_url="http://bucket-2"),
    ]
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            account.account_id: type(
                "Snapshot",
                (),
                {
                    "account_id": account.account_id,
                    "selected_steam_id": f"steam-{account.account_id}",
                    "inventories": [
                        {"steamId": f"steam-{account.account_id}", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
            for account in accounts
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository(accounts),
        settings_repository=FakeSettingsRepository({"per_batch_ip_fanout_limit": 2}),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()

    try:
        result = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1234,
                "mode_type": "new_api",
            }
        )

        assert result == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(gateway.calls) == 4)
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_next_batch_uses_remaining_idle_accounts_in_same_bucket():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    accounts = [
        build_account(f"b1-{index}", browser_proxy_mode="custom", browser_proxy_url="http://bucket-1")
        for index in range(6)
    ]
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            account.account_id: type(
                "Snapshot",
                (),
                {
                    "account_id": account.account_id,
                    "selected_steam_id": f"steam-{account.account_id}",
                    "inventories": [
                        {"steamId": f"steam-{account.account_id}", "inventory_num": 910, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
            for account in accounts
        }
    )
    gateway = BlockingExecutionGateway(PurchaseExecutionResult.success(purchased_count=1))
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository(accounts),
        settings_repository=FakeSettingsRepository({"per_batch_ip_fanout_limit": 4}),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
        max_inflight_per_account=1,
    )
    service.start()

    try:
        first = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
                "total_price": 88.0,
                "total_wear_sum": 0.1111,
                "mode_type": "new_api",
            }
        )
        second = service.accept_query_hit(
            {
                "external_item_id": "1380979899390261111",
                "query_item_name": "AK",
                "product_url": "https://www.c5game.com/csgo/730/asset/1380979899390261111",
                "product_list": [{"productId": "p-2", "price": 89.0, "actRebateAmount": 0}],
                "total_price": 89.0,
                "total_wear_sum": 0.2222,
                "mode_type": "new_api",
            }
        )

        assert first == {"accepted": True, "status": "queued"}
        assert second == {"accepted": True, "status": "queued"}
        assert wait_until(lambda: len(gateway.calls) == 6)
    finally:
        gateway.release.set()
        service.stop()


def test_purchase_runtime_service_purchase_disable_removes_account_from_pool_without_global_disable():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    account_repository = FakeAccountRepository([build_account("a1")])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": "steam-1",
                    "inventories": [
                        {"steamId": "steam-1", "inventory_num": 900, "inventory_max": 1000},
                    ],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": None,
                },
            )()
        }
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
    )
    service.start()

    updated = service.update_account_purchase_config(
        account_id="a1",
        purchase_disabled=True,
        selected_steam_id="steam-1",
    )

    snapshot = service.get_status()
    stored = account_repository.get_account("a1")

    assert "disabled" not in updated
    assert updated["purchase_disabled"] is True
    assert snapshot["active_account_count"] == 0
    assert stored is not None
    assert stored.purchase_disabled is True


def test_purchase_runtime_service_reenabling_purchase_runs_overdue_recovery_immediately():
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.purchase.runtime.runtime_events import InventoryRefreshResult

    overdue_account = build_account("a1")
    overdue_account.purchase_disabled = True
    overdue_account.purchase_recovery_due_at = "2026-03-16T19:59:00.000000"
    account_repository = FakeAccountRepository([overdue_account])
    snapshot_repository = FakeInventorySnapshotRepository(
        {
            "a1": type(
                "Snapshot",
                (),
                {
                    "account_id": "a1",
                    "selected_steam_id": None,
                    "inventories": [],
                    "refreshed_at": "2026-03-16T20:00:00",
                    "last_error": "没有可用仓库",
                },
            )()
        }
    )
    refresh_gateway = StubInventoryRefreshGateway(
        InventoryRefreshResult.success(
            inventories=[
                {"steamId": "steam-recovered", "inventory_num": 920, "inventory_max": 1000},
            ]
        )
    )
    service = PurchaseRuntimeService(
        account_repository=account_repository,
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        inventory_refresh_gateway_factory=lambda: refresh_gateway,
        recovery_delay_seconds_provider=lambda: 60.0,
    )
    service.start()
    refresh_gateway.calls.clear()

    updated = service.update_account_purchase_config(
        account_id="a1",
        purchase_disabled=False,
        selected_steam_id=None,
    )

    assert wait_until(lambda: service.get_status()["active_account_count"] == 1)
    snapshot = service.get_status()
    assert updated["purchase_disabled"] is False
    assert refresh_gateway.calls == [{"account_id": "a1"}]
    assert snapshot["accounts"][0]["purchase_pool_state"] == "active"
    assert snapshot["accounts"][0]["selected_steam_id"] == "steam-recovered"
