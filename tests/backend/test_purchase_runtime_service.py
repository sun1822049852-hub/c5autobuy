import asyncio
import threading
import time
from datetime import datetime, timedelta

from app_backend.domain.models.account import Account
from app_backend.infrastructure.purchase.runtime.runtime_events import PurchaseExecutionResult


def build_account(account_id: str, *, bound: bool = True) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
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
        disabled=False,
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


class FakeSettingsRepository:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


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

    async def execute(self, *, account, batch, selected_steam_id: str):
        self.calls.append(
            {
                "account_id": account.account_id,
                "selected_steam_id": selected_steam_id,
                "query_item_name": batch.query_item_name,
            }
        )
        return self._result


class BlockingExecutionGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []
        self.started = threading.Event()
        self.release = threading.Event()

    async def execute(self, *, account, batch, selected_steam_id: str):
        self.calls.append(
            {
                "account_id": account.account_id,
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
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
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
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
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
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
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
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
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
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
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
                        {"steamId": "steam-1", "inventory_num": 910, "inventory_max": 1000},
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

        assert wait_until(lambda: service.get_status()["runtime_session_id"] == "run-2")
        snapshot = service.get_status()
        assert snapshot["runtime_session_id"] == "run-2"
        assert snapshot["matched_product_count"] == 0
        assert snapshot["purchase_success_count"] == 0
        assert snapshot["purchase_failed_count"] == 0
    finally:
        gateway.release.set()
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

    assert wait_until(lambda: service.get_status()["total_purchased_count"] == 10)
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

    assert wait_until(lambda: service.get_status()["accounts"][0]["purchase_pool_state"] == "paused_no_inventory")
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

    assert updated["disabled"] is False
    assert updated["purchase_disabled"] is True
    assert snapshot["active_account_count"] == 0
    assert stored is not None
    assert stored.disabled is False
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
