# Purchase Execution Gateway Replacement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变购买运行时接口、库存状态机和外部行为的前提下，把购买执行链路从 legacy `autobuy.py` 中剥离出来，接入新架构自己的执行网关。

**Architecture:** 新增一个新的购买执行网关，内部按旧语义拆成“创建订单”和“支付订单”两个步骤，直接使用 `RuntimeAccountAdapter`、`xsign.py` 和浏览器会话发请求并返回 `PurchaseExecutionResult`。`PurchaseRuntimeService` 和 `AccountPurchaseWorker` 保持现有调用方式与库存协调逻辑不变，只替换默认执行网关来源。

**Tech Stack:** Python, asyncio, aiohttp, pytest, Node.js-backed `xsign.py`

---

## 文件结构

- Create: `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`
  - 新的购买执行网关，负责下单与支付
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
  - 默认执行网关从旧实现切到新网关
- Modify: `app_backend/infrastructure/purchase/runtime/__init__.py`
  - 导出新网关
- Create: `tests/backend/test_purchase_execution_gateway.py`
  - 覆盖新网关的下单、支付、鉴权与请求形状
- Modify: `tests/backend/test_purchase_runtime_gateway_wiring.py`
  - 改为验证新网关兼容旧请求语义，或重命名为兼容烟测
- Verify: `tests/backend/test_account_purchase_worker_runtime.py`
  - 确认 worker 行为不回归
- Verify: `tests/backend/test_purchase_runtime_service.py`
  - 确认购买运行时整体行为不回归
- Modify: `README.md`
  - 更新购买执行去 legacy 进度

## Chunk 1: 购买执行网关单测先行

### Task 1: 写 `PurchaseExecutionGateway` 的失败测试

**Files:**
- Create: `tests/backend/test_purchase_execution_gateway.py`
- Create: `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`

- [ ] **Step 1: 写失败测试，锁定“下单成功 + 支付成功”主路径**

```python
async def test_purchase_execution_gateway_executes_order_then_payment():
    signer = FakeSigner(result="fake-sign")
    session = FakeSession(
        responses=[
            (200, json.dumps({"success": True, "data": "order-1"})),
            (200, json.dumps({"success": True, "data": {"successCount": 2}})),
        ]
    )
    gateway = PurchaseExecutionGateway(xsign_wrapper=signer)
    result = await gateway.execute(account=build_account(), batch=build_batch(), selected_steam_id="steam-1", session=session)
    assert result.status == "success"
    assert result.purchased_count == 2
    assert session.calls[0]["url"].endswith("/support/trade/order/buy/v2/create")
    assert session.calls[1]["url"].endswith("/pay/order/v1/pay")
```

- [ ] **Step 2: 写失败测试，锁定 `Not login / 403` 映射为 `auth_invalid`**

```python
async def test_purchase_execution_gateway_maps_order_not_login_to_auth_invalid():
    ...
    assert result.status == "auth_invalid"


async def test_purchase_execution_gateway_maps_payment_not_login_to_auth_invalid():
    ...
    assert result.status == "auth_invalid"
```

- [ ] **Step 3: 写失败测试，锁定普通错误和边界值**

```python
async def test_purchase_execution_gateway_returns_order_failed_for_regular_order_error():
    ...
    assert result.status == "order_failed"


async def test_purchase_execution_gateway_returns_payment_failed_for_regular_payment_error():
    ...
    assert result.status == "payment_failed"


async def test_purchase_execution_gateway_returns_payment_success_no_items_when_success_count_zero():
    ...
    assert result.status == "payment_success_no_items"
```

- [ ] **Step 4: 写失败测试，锁定 `x-sign`、timeout、请求异常和请求形状**

```python
async def test_purchase_execution_gateway_returns_xsign_error_text():
    ...
    assert "生成x-sign失败:" in str(result.error)


async def test_purchase_execution_gateway_keeps_legacy_order_body_and_headers():
    ...
    assert session.calls[0]["json"]["productList"] == build_batch().product_list
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
    assert session.calls[0]["headers"]["Cookie"] == build_account().cookie_raw


async def test_purchase_execution_gateway_keeps_legacy_payment_body_and_headers():
    ...
    assert session.calls[1]["json"]["bizOrderId"] == "order-1"
    assert session.calls[1]["json"]["payAmount"] == "88.00"
```

- [ ] **Step 5: 运行测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_execution_gateway.py -q`
Expected: FAIL，提示 `PurchaseExecutionGateway` 不存在或行为未实现。

## Chunk 2: 最小实现购买执行网关

### Task 2: 实现 `PurchaseExecutionGateway`

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`
- Create: `tests/backend/test_purchase_execution_gateway.py`

- [ ] **Step 1: 实现最小请求构建方法，保持 legacy 下单语义**

```python
class PurchaseExecutionGateway:
    ORDER_API_PATH = "support/trade/order/buy/v2/create"
    PAY_API_PATH = "pay/order/v1/pay"

    @staticmethod
    def build_order_request_body(batch, selected_steam_id: str) -> dict[str, object]:
        return {
            "type": 4,
            "productId": str(batch.external_item_id),
            "price": format(float(batch.total_price), ".2f"),
            "delivery": 0,
            "pageSource": "",
            "receiveSteamId": str(selected_steam_id),
            "productList": list(batch.product_list),
            "actRebateAmount": 0,
        }
```

- [ ] **Step 2: 实现最小支付请求体构建**

```python
@staticmethod
def build_payment_request_body(order_id: str, pay_amount: float, selected_steam_id: str) -> dict[str, object]:
    return {
        "bizOrderId": str(order_id),
        "orderType": 4,
        "payAmount": format(float(pay_amount), ".2f"),
        "receiveSteamId": str(selected_steam_id),
    }
```

- [ ] **Step 3: 实现懒加载 signer，默认直接使用 `xsign.py`**

```python
@lru_cache(maxsize=1)
def get_default_xsign_wrapper():
    return XSignWrapper(wasm_path=str(repo_root / "test.wasm"), persistent=True, timeout=10)
```

- [ ] **Step 4: 实现 `execute()`，内部串行调用 `create_order()` 和 `process_payment()`**

```python
async def execute(self, *, account, batch, selected_steam_id: str) -> PurchaseExecutionResult:
    runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
    ...
```

- [ ] **Step 5: 实现下单/支付的错误映射兼容**

```python
if self._is_auth_invalid(error):
    return PurchaseExecutionResult.auth_invalid(error or "Not login")
return PurchaseExecutionResult(status="order_failed", purchased_count=0, error=error)
```

- [ ] **Step 6: 复跑执行网关测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_execution_gateway.py -q`
Expected: PASS

## Chunk 3: 切换购买运行时默认网关

### Task 3: 让运行时默认使用新购买执行网关

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/purchase/runtime/__init__.py`
- Modify: `tests/backend/test_purchase_runtime_gateway_wiring.py`

- [ ] **Step 1: 改写兼容烟测，锁定新网关仍保持旧请求形状**

```python
async def test_purchase_execution_gateway_smoke_keeps_legacy_request_shape():
    ...
    assert session.calls[0]["url"].endswith("/support/trade/order/buy/v2/create")
    assert session.calls[1]["url"].endswith("/pay/order/v1/pay")
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
```

- [ ] **Step 2: 运行兼容烟测确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_gateway_wiring.py -q`
Expected: FAIL，提示仍绑定 legacy 网关或新网关未接入。

- [ ] **Step 3: 修改默认执行网关工厂**

```python
from app_backend.infrastructure.purchase.runtime.purchase_execution_gateway import PurchaseExecutionGateway
...
self._execution_gateway_factory = execution_gateway_factory or PurchaseExecutionGateway
```

- [ ] **Step 4: 导出新网关**

```python
from .purchase_execution_gateway import PurchaseExecutionGateway
```

- [ ] **Step 5: 复跑兼容烟测**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_gateway_wiring.py -q`
Expected: PASS

## Chunk 4: 运行时回归

### Task 4: 确认 worker 和购买运行时不回归

**Files:**
- Verify: `tests/backend/test_account_purchase_worker_runtime.py`
- Verify: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: 运行 `AccountPurchaseWorker` 回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_purchase_worker_runtime.py -q`
Expected: PASS

- [ ] **Step 2: 运行购买运行时回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py -q`
Expected: PASS

- [ ] **Step 3: 只有测试失败时才做最小修正**

```python
if result.status == "auth_invalid":
    ...
if result.status == "success":
    ...
```

- [ ] **Step 4: 复跑运行时回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_purchase_worker_runtime.py tests/backend/test_purchase_runtime_service.py -q`
Expected: PASS

## Chunk 5: 最终验证

### Task 5: 整体验证购买执行替换不破外部合同

**Files:**
- Modify: `README.md`
- Verify only

- [ ] **Step 1: 更新 README 中购买链路去 legacy 进度**

```markdown
- 购买执行链路已从 `autobuy.py` 中剥离
- 购买模块当前仅剩库存刷新仍依赖 legacy
```

- [ ] **Step 2: 运行购买执行替换相关定向测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_execution_gateway.py tests/backend/test_purchase_runtime_gateway_wiring.py tests/backend/test_account_purchase_worker_runtime.py tests/backend/test_purchase_runtime_service.py -q`
Expected: PASS

- [ ] **Step 3: 运行全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS

- [ ] **Step 4: 汇报结果，只报告已验证内容**

注：本计划不包含 git 提交；相关 legacy gateway 已在后续清理完成。
