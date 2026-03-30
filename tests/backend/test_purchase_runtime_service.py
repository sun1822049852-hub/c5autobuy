import asyncio
import threading
import time
from datetime import datetime, timedelta

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


def wait_until(predicate, *, timeout: float = 1.0, interval: float = 0.01) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


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

    def wrapped_start_dispatch(account_id: str, batch) -> None:
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
        original_start_dispatch(account_id, batch)
        binder.join(timeout=1.0)

    monkeypatch.setattr(runtime, "_start_account_dispatch", wrapped_start_dispatch)

    try:
        dispatched = asyncio.run(runtime._drain_scheduler())
        assert dispatched == "dispatched"
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
        assert len(gateway.calls) == 1
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
