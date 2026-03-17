# New API Query Executor Replacement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有接口、配置项和运行时协议的前提下，把 `new_api` 查询模式从 legacy `autobuy.py` 中剥离出来，接入新架构自己的查询执行模块。

**Architecture:** 新增一个只服务 `new_api` 的 `NewApiQueryExecutor`，让它直接使用 `RuntimeAccountAdapter` 和 `QueryItem` 发起请求并返回 `QueryExecutionResult`。`LegacyScannerAdapter` 先保留为模式分发层：`new_api` 走新执行器，`fast_api/token` 继续走 legacy，实现渐进替换而不是一次性重写。

**Tech Stack:** Python, asyncio, aiohttp, FastAPI, pytest

---

## 文件结构

- Create: `app_backend/infrastructure/query/runtime/new_api_query_executor.py`
  - `new_api` 专属查询执行器
- Modify: `app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py`
  - 让 `new_api` 分发到新执行器，保留 `fast_api/token` legacy 路径
- Modify: `app_backend/infrastructure/query/runtime/__init__.py`
  - 导出新执行器
- Create: `tests/backend/test_new_api_query_executor.py`
  - 覆盖 `new_api` 执行器成功/错误解析
- Modify: `tests/backend/test_legacy_scanner_adapter.py`
  - 锁定适配器路由行为
- Modify: `tests/backend/test_legacy_scanner_real_integration.py`
  - 锁定 `new_api` 新实现兼容旧语义，`fast_api/token` 仍走旧路径
- Verify: `tests/backend/test_account_query_worker.py`
  - 确认 `AccountQueryWorker` 上层行为不回归
- Verify: `tests/backend/test_query_purchase_bridge.py`
  - 确认命中转购买桥接不回归

## Chunk 1: `new_api` 执行器单测先行

### Task 1: 写 `NewApiQueryExecutor` 的失败测试

**Files:**
- Create: `tests/backend/test_new_api_query_executor.py`
- Create: `app_backend/infrastructure/query/runtime/new_api_query_executor.py`

- [ ] **Step 1: 写失败测试，锁定成功响应解析**

```python
async def test_new_api_query_executor_parses_success_response():
    executor = NewApiQueryExecutor()
    session = FakeSession(
        status=200,
        text=json.dumps(
            {
                "success": True,
                "data": {
                    "list": [
                        {"productId": "p1", "price": "88.80", "assetInfo": {"floatWear": "0.1234"}},
                        {"productId": "p2", "price": "66.60", "assetInfo": {"floatWear": "0.1000"}},
                    ]
                },
            }
        ),
    )
    runtime_account = RuntimeAccountAdapter(build_account())
    result = await executor.execute_query(account=runtime_account, query_item=build_item(), session=session)
    assert result.success is True
    assert result.match_count == 2
    assert result.total_price == 155.4
    assert result.total_wear_sum == 0.2234
```

- [ ] **Step 2: 写失败测试，锁定 429 兼容错误文本**

```python
async def test_new_api_query_executor_returns_legacy_429_error_text():
    executor = NewApiQueryExecutor()
    session = FakeSession(status=429, text="{}")
    result = await executor.execute_query(account=RuntimeAccountAdapter(build_account()), query_item=build_item(), session=session)
    assert result.success is False
    assert result.error == "HTTP 429 Too Many Requests"
```

- [ ] **Step 3: 写失败测试，锁定非 200 状态码兼容语义**

```python
async def test_new_api_query_executor_returns_http_error_text_for_non_200():
    executor = NewApiQueryExecutor()
    session = FakeSession(status=403, text="{}")
    result = await executor.execute_query(account=RuntimeAccountAdapter(build_account()), query_item=build_item(), session=session)
    assert result.success is False
    assert result.error == "HTTP 403 请求失败"
```

- [ ] **Step 4: 写失败测试，锁定 session 为空和 JSON 非法的错误语义**

```python
async def test_new_api_query_executor_returns_error_when_session_missing():
    executor = NewApiQueryExecutor()
    result = await executor.execute_query(account=RuntimeAccountAdapter(build_account()), query_item=build_item(), session=None)
    assert result.success is False
    assert result.error == "无法创建OpenAPI会话"


async def test_new_api_query_executor_returns_string_error_for_invalid_json():
    executor = NewApiQueryExecutor()
    session = FakeSession(status=200, text="{broken")
    result = await executor.execute_query(account=RuntimeAccountAdapter(build_account()), query_item=build_item(), session=session)
    assert result.success is False
    assert "解析响应失败" in result.error
```

- [ ] **Step 5: 运行测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_new_api_query_executor.py -q`
Expected: FAIL，提示 `NewApiQueryExecutor` 不存在或行为未实现。

## Chunk 2: 最小实现 `new_api` 执行器

### Task 2: 实现 `NewApiQueryExecutor`

**Files:**
- Create: `app_backend/infrastructure/query/runtime/new_api_query_executor.py`
- Create: `tests/backend/test_new_api_query_executor.py`

- [ ] **Step 1: 实现最小请求构建方法，保持 legacy `new_api` 语义**

```python
class NewApiQueryExecutor:
    BASE_URL = "https://openapi.c5game.com/merchant/market/v2/products/search"

    @staticmethod
    def build_request_params(account: RuntimeAccountAdapter) -> dict[str, str]:
        return {"app-key": str(account.get_api_key() or "")}

    @staticmethod
    def build_request_body(query_item: QueryItem, *, page_size: int = 50) -> dict[str, object]:
        return {
            "pageSize": page_size,
            "appId": 730,
            "marketHashName": query_item.market_hash_name,
            "priceMax": float(query_item.max_price),
            "wearMin": float(query_item.min_wear),
            "wearMax": float(query_item.max_wear),
        }
```

- [ ] **Step 2: 实现最小 `execute_query()`，支持注入 session 方便单测**

```python
async def execute_query(self, *, account: RuntimeAccountAdapter, query_item: QueryItem, session=None) -> QueryExecutionResult:
    started_at = time.perf_counter()
    ...
```

- [ ] **Step 3: 实现成功响应解析，产出兼容 `QueryExecutionResult`**

```python
product_list.append(
    {
        "productId": str(product.get("productId") or ""),
        "price": price,
        "actRebateAmount": 0,
    }
)
```

- [ ] **Step 4: 实现兼容错误文本**

```python
if status == 429:
    return QueryExecutionResult(..., error="HTTP 429 Too Many Requests", ...)
if status != 200:
    return QueryExecutionResult(..., error=f"HTTP {status} 请求失败", ...)
```

- [ ] **Step 5: 复跑执行器测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_new_api_query_executor.py -q`
Expected: PASS

## Chunk 3: 让适配器只把 `new_api` 路由到新执行器

### Task 3: 改造 `LegacyScannerAdapter` 为分发层

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py`
- Modify: `app_backend/infrastructure/query/runtime/__init__.py`
- Modify: `tests/backend/test_legacy_scanner_adapter.py`

- [ ] **Step 1: 写失败测试，锁定 `new_api` 不再走 legacy scanner class**

```python
async def test_legacy_scanner_adapter_routes_new_api_to_new_executor():
    executor = FakeNewApiExecutor()
    adapter = LegacyScannerAdapter(new_api_executor=executor, legacy_module=SimpleNamespace(...))
    result = await adapter.execute_query(mode_type="new_api", account=build_account(), query_item=build_item())
    assert executor.calls == [("a1", "1380979899390261111")]
    assert result.success is True
```

- [ ] **Step 2: 写失败测试，锁定 `fast_api/token` 仍走 legacy 路径**

```python
def test_legacy_scanner_adapter_build_scanner_keeps_fast_and_token_legacy():
    ...
    assert adapter.build_scanner("fast_api", account=build_account(), query_item=build_item()).__class__ is FakeFastScanner
    assert adapter.build_scanner("token", account=build_account(), query_item=build_item()).__class__ is FakeTokenScanner
```

- [ ] **Step 3: 运行适配器测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_legacy_scanner_adapter.py -q`
Expected: FAIL，提示 `new_api` 仍走 legacy 或构造参数不支持。

- [ ] **Step 4: 最小改造 `LegacyScannerAdapter`**

```python
class LegacyScannerAdapter:
    def __init__(self, *, legacy_module: Any | None = None, new_api_executor: NewApiQueryExecutor | None = None) -> None:
        self._legacy_module = legacy_module
        self._new_api_executor = new_api_executor or NewApiQueryExecutor()

    async def execute_query(...):
        runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
        if mode_type == "new_api":
            return await self._new_api_executor.execute_query(account=runtime_account, query_item=query_item)
        ...
```

- [ ] **Step 5: 复跑适配器测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_legacy_scanner_adapter.py -q`
Expected: PASS

## Chunk 4: 锁定新实现对旧语义的兼容

### Task 4: 更新真实烟测，确认 `new_api` 已不依赖 legacy scanner class

**Files:**
- Modify: `tests/backend/test_legacy_scanner_real_integration.py`
- Modify: `app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py`

- [ ] **Step 1: 改写 `new_api` 烟测，直接验证新执行器发出的请求格式仍与旧语义兼容**

```python
async def test_new_api_executor_smoke_keeps_legacy_request_shape(monkeypatch):
    ...
    assert session.calls[0]["params"] == {"app-key": "api-1"}
    assert session.calls[0]["json"]["marketHashName"] == "Test Item Name"
    assert session.calls[0]["json"]["priceMax"] == 100.0
    assert session.calls[0]["json"]["wearMin"] == 0.0
    assert session.calls[0]["json"]["wearMax"] == 0.25
```

- [ ] **Step 2: 保留 `fast_api/token` 烟测不动，确认它们仍走 legacy 行为**

```python
async def test_real_legacy_fast_api_execute_query_smoke(...):
    ...

async def test_real_legacy_token_execute_query_smoke(...):
    ...
```

- [ ] **Step 3: 运行烟测确认兼容**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_legacy_scanner_real_integration.py -q`
Expected: PASS

## Chunk 5: 运行时回归

### Task 5: 确认上层 worker 和购买桥不回归

**Files:**
- Verify: `tests/backend/test_account_query_worker.py`
- Verify: `tests/backend/test_query_purchase_bridge.py`
- Modify if needed: `app_backend/infrastructure/query/runtime/account_query_worker.py`

- [ ] **Step 1: 运行 `AccountQueryWorker` 回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_query_worker.py -q`
Expected: PASS

- [ ] **Step 2: 运行命中转购买桥回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 3: 只有测试失败时才做最小修正**

```python
if error == "HTTP 429 Too Many Requests":
    ...
if error == "Not login" or "HTTP 403" in error:
    ...
```

- [ ] **Step 4: 复跑回归测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_query_worker.py tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

## Chunk 6: 最终验证

### Task 6: 整体验证 `new_api` 替换不破外部合同

**Files:**
- Verify only

- [ ] **Step 1: 运行 `new_api` 替换相关定向测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_new_api_query_executor.py tests/backend/test_legacy_scanner_adapter.py tests/backend/test_legacy_scanner_real_integration.py tests/backend/test_account_query_worker.py tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 2: 运行全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS

- [ ] **Step 3: 汇报结果，只报告已验证内容**

注：本计划不包含 git 提交；如果 `new_api` 替换过程中发现旧语义里存在未文档化的边界行为，优先补测试锁定，再决定是否兼容复刻。
