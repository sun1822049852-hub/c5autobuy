import asyncio

from app_backend.domain.models.account import Account
from app_backend.infrastructure.purchase.runtime.inventory_state import InventoryState
from app_backend.infrastructure.purchase.runtime.runtime_events import (
    PurchaseExecutionResult,
    PurchaseHitBatch,
)
from app_backend.infrastructure.purchase.runtime.account_purchase_worker import AccountPurchaseWorker
from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter


def build_account(account_id: str = "a1") -> Account:
    return Account(
        account_id=account_id,
        default_name=f"账号-{account_id}",
        remark_name=None,
        browser_proxy_mode="direct",
        browser_proxy_url=None,
        api_proxy_mode="direct",
        api_proxy_url=None,
        api_key=None,
        c5_user_id="10001",
        c5_nick_name="测试账号",
        cookie_raw="NC5_accessToken=token-value",
        purchase_capability_state="bound",
        purchase_pool_state="active",
        last_login_at="2026-03-16T20:00:00",
        last_error=None,
        created_at="2026-03-16T20:00:00",
        updated_at="2026-03-16T20:00:00",
    )


def build_batch() -> PurchaseHitBatch:
    return PurchaseHitBatch(
        query_item_name="AK-47",
        product_list=[{"productId": "1", "price": 123.45}],
        total_price=123.45,
        total_wear_sum=0.1234,
        source_mode_type="token",
    )


def build_inventory_state() -> InventoryState:
    state = InventoryState(min_capacity_threshold=50)
    state.load_snapshot(
        [
            {"steamId": "s1", "inventory_num": 910, "inventory_max": 1000},
            {"steamId": "s2", "inventory_num": 850, "inventory_max": 1000},
        ]
    )
    return state


class SpyGateway:
    def __init__(self, result: PurchaseExecutionResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    async def execute(self, *, account, batch, selected_steam_id: str, **_kwargs):
        account_id = getattr(account, "account_id", None)
        if account_id is None:
            get_account_id = getattr(account, "get_account_id", None)
            if callable(get_account_id):
                account_id = get_account_id()
        self.calls.append(
            {
                "account": account,
                "account_id": account_id,
                "selected_steam_id": selected_steam_id,
                "query_item_name": batch.query_item_name,
            }
        )
        return self._result


def test_account_purchase_worker_leaves_inventory_commit_to_runtime_on_success():
    inventory_state = build_inventory_state()
    gateway = SpyGateway(PurchaseExecutionResult.success(purchased_count=2))
    worker = AccountPurchaseWorker(
        account=build_account(),
        inventory_state=inventory_state,
        execution_gateway=gateway,
    )

    outcome = asyncio.run(worker.process(build_batch()))

    assert outcome.status == "success"
    assert outcome.purchased_count == 2
    assert outcome.selected_steam_id == "s1"
    assert inventory_state.selected_inventory is not None
    assert inventory_state.selected_inventory["inventory_num"] == 910


def test_account_purchase_worker_marks_auth_invalid_without_inventory_refresh():
    inventory_state = build_inventory_state()
    gateway = SpyGateway(PurchaseExecutionResult.auth_invalid("登录已失效"))
    worker = AccountPurchaseWorker(
        account=build_account(),
        inventory_state=inventory_state,
        execution_gateway=gateway,
    )

    outcome = asyncio.run(worker.process(build_batch()))

    assert outcome.status == "auth_invalid"
    assert outcome.pool_state == "paused_auth_invalid"
    assert outcome.capability_state == "expired"
    assert outcome.requires_remote_refresh is False


def test_account_purchase_worker_preserves_gateway_debug_fields_on_failure():
    inventory_state = build_inventory_state()
    gateway = SpyGateway(
        PurchaseExecutionResult(
            status="payment_failed",
            purchased_count=0,
            submitted_count=1,
            error="库存不足",
            status_code=409,
            request_method="POST",
            request_path="/purchase/orders",
            response_text="{\"error\":\"sold out\"}",
        )
    )
    worker = AccountPurchaseWorker(
        account=build_account(),
        inventory_state=inventory_state,
        execution_gateway=gateway,
    )

    outcome = asyncio.run(worker.process(build_batch()))

    assert outcome.status == "payment_failed"
    assert outcome.status_code == 409
    assert outcome.request_method == "POST"
    assert outcome.request_path == "/purchase/orders"
    assert outcome.response_text == "{\"error\":\"sold out\"}"


def test_account_purchase_worker_passes_selected_steam_id_to_execution_gateway():
    inventory_state = build_inventory_state()
    gateway = SpyGateway(PurchaseExecutionResult.success(purchased_count=1))
    worker = AccountPurchaseWorker(
        account=build_account(),
        inventory_state=inventory_state,
        execution_gateway=gateway,
    )

    asyncio.run(worker.process(build_batch()))

    assert gateway.calls[0]["selected_steam_id"] == "s1"


def test_account_purchase_worker_reuses_provided_runtime_account_across_runs():
    inventory_state = build_inventory_state()
    gateway = SpyGateway(PurchaseExecutionResult.success(purchased_count=1))
    shared_runtime_account = RuntimeAccountAdapter(build_account())
    worker = AccountPurchaseWorker(
        account=build_account(),
        inventory_state=inventory_state,
        execution_gateway=gateway,
        runtime_account=shared_runtime_account,
    )

    asyncio.run(worker.process(build_batch()))
    asyncio.run(worker.process(build_batch()))

    assert gateway.calls[0]["account"] is shared_runtime_account
    assert gateway.calls[1]["account"] is shared_runtime_account
