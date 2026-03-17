# Token Query Executor Replacement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有接口、配置项和运行时协议的前提下，把 `token` 查询模式从 legacy `autobuy.py` 中剥离出来，接入新架构自己的查询执行模块。

**Architecture:** 新增一个只服务 `token` 的 `TokenQueryExecutor`，让它直接使用 `RuntimeAccountAdapter`、浏览器会话和独立的 `xsign.py` 发起请求并返回 `QueryExecutionResult`。`LegacyScannerAdapter` 最终只保留模式分发职责：`new_api / fast_api / token` 都走新执行器，不再构造 legacy scanner。

**Tech Stack:** Python, asyncio, aiohttp, pytest, Node.js-backed `xsign.py`

---

## 文件结构

- Create: `app_backend/infrastructure/query/runtime/token_query_executor.py`
  - `token` 专属查询执行器
- Modify: `app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py`
  - 让 `token` 分发到新执行器，移除 query 侧 legacy scanner 路径
- Modify: `app_backend/infrastructure/query/runtime/__init__.py`
  - 导出新执行器
- Create: `tests/backend/test_token_query_executor.py`
  - 覆盖 `token` 执行器成功/错误解析与请求构造
- Modify: `tests/backend/test_legacy_scanner_adapter.py`
  - 锁定适配器路由行为
- Modify: `tests/backend/test_legacy_scanner_real_integration.py`
  - 锁定 `token` 新实现兼容旧语义
- Verify: `tests/backend/test_account_query_worker.py`
  - 确认 `AccountQueryWorker` 上层行为不回归
- Verify: `tests/backend/test_query_purchase_bridge.py`
  - 确认命中转购买桥接不回归
- Modify: `README.md`
  - 更新查询链路去 legacy 进度

## Chunk 1: `token` 执行器单测先行

### Task 1: 写 `TokenQueryExecutor` 的失败测试

**Files:**
- Create: `tests/backend/test_token_query_executor.py`
- Create: `app_backend/infrastructure/query/runtime/token_query_executor.py`

- [ ] **Step 1: 写失败测试，锁定成功响应解析与请求形状**

```python
async def test_token_query_executor_parses_success_response_and_keeps_request_shape():
    signer = FakeSigner(result="fake-sign")
    session = FakeSession(status=200, text=json.dumps({...}))
    executor = TokenQueryExecutor(xsign_wrapper=signer)
    result = await executor.execute_query(account=RuntimeAccountAdapter(build_account()), query_item=build_item(), session=session)
    assert result.success is True
    assert result.match_count == 1
    assert result.product_list[0]["productId"] == "p3"
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
    assert session.calls[0]["json"]["itemId"] == "1380979899390261111"
```

- [ ] **Step 2: 写失败测试，锁定 403 和 `Not login` 兼容语义**

```python
async def test_token_query_executor_returns_403_error_text():
    ...
    assert result.error == "HTTP 403 Forbidden"


async def test_token_query_executor_returns_not_login_text_for_plain_response():
    ...
    assert result.error == "Not login"
```

- [ ] **Step 3: 写失败测试，锁定 session 缺失、x-sign 失败、非法 JSON、timeout、请求异常**

```python
async def test_token_query_executor_returns_error_when_session_missing():
    ...
    assert result.error == "无法创建浏览器会话"


async def test_token_query_executor_returns_xsign_error_text():
    ...
    assert "x-sign生成失败:" in result.error


async def test_token_query_executor_returns_invalid_json_error_text():
    ...
    assert result.error == "响应不是有效的JSON格式"


async def test_token_query_executor_returns_timeout_error_text():
    ...
    assert result.error == "请求超时"


async def test_token_query_executor_returns_request_error_text():
    ...
    assert result.error == "请求错误: boom"
```

- [ ] **Step 4: 运行测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_token_query_executor.py -q`
Expected: FAIL，提示 `TokenQueryExecutor` 不存在或行为未实现。

## Chunk 2: 最小实现 `token` 执行器

### Task 2: 实现 `TokenQueryExecutor`

**Files:**
- Create: `app_backend/infrastructure/query/runtime/token_query_executor.py`
- Create: `tests/backend/test_token_query_executor.py`

- [ ] **Step 1: 实现最小请求构建方法，保持 legacy `token` 语义**

```python
class TokenQueryExecutor:
    API_PATH = "support/trade/product/batch/v1/sell/query"

    @staticmethod
    def build_request_body(query_item: QueryItem) -> dict[str, object]:
        return {
            "itemId": str(query_item.external_item_id),
            "maxPrice": str(query_item.max_price),
            "delivery": 0,
            "minWear": float(query_item.min_wear),
            "maxWear": float(query_item.max_wear),
            "limit": "200",
            "giftBuy": "",
        }
```

- [ ] **Step 2: 实现懒加载 signer，默认直接使用 `xsign.py`**

```python
@lru_cache(maxsize=1)
def get_default_xsign_wrapper():
    return XSignWrapper(wasm_path=str(repo_root / "test.wasm"), persistent=True, timeout=10)
```

- [ ] **Step 3: 实现最小 `execute_query()`，支持注入 session 和 signer 方便单测**

```python
async def execute_query(self, *, account: RuntimeAccountAdapter, query_item: QueryItem, session=None) -> QueryExecutionResult:
    started_at = time.perf_counter()
    ...
```

- [ ] **Step 4: 实现 `Not login`、403 和结果解析兼容逻辑**

```python
if status == 403:
    return QueryExecutionResult(..., error="HTTP 403 Forbidden", ...)
if isinstance(text, str) and "Not login" in text:
    return QueryExecutionResult(..., error="Not login", ...)
```

- [ ] **Step 5: 复跑执行器测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_token_query_executor.py -q`
Expected: PASS

## Chunk 3: 让适配器把 `token` 路由到新执行器

### Task 3: 改造 `LegacyScannerAdapter` 为纯分发层

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py`
- Modify: `app_backend/infrastructure/query/runtime/__init__.py`
- Modify: `tests/backend/test_legacy_scanner_adapter.py`

- [ ] **Step 1: 写失败测试，锁定 `token` 走 `TokenQueryExecutor`**

```python
async def test_legacy_scanner_adapter_routes_token_to_token_executor():
    executor = FakeTokenExecutor()
    adapter = LegacyScannerAdapter(token_executor=executor)
    result = await adapter.execute_query(mode_type="token", account=build_account(), query_item=build_item())
    assert executor.calls == [("a1", "1380979899390261111")]
```

- [ ] **Step 2: 删除或改写“token 仍走 legacy scanner”的旧断言**

```python
def test_legacy_scanner_adapter_build_scanner_raises_for_runtime_managed_modes():
    ...
```

- [ ] **Step 3: 运行适配器测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_legacy_scanner_adapter.py -q`
Expected: FAIL，提示 `token` 仍走 legacy 或构造参数不支持。

- [ ] **Step 4: 最小改造 `LegacyScannerAdapter`**

```python
class LegacyScannerAdapter:
    def __init__(..., new_api_executor=None, fast_api_executor=None, token_executor=None):
        ...

    async def execute_query(...):
        if mode_type == "token":
            return await self._token_executor.execute_query(account=runtime_account, query_item=query_item)
```

- [ ] **Step 5: 复跑适配器测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_legacy_scanner_adapter.py -q`
Expected: PASS

## Chunk 4: 锁定新实现对旧语义的兼容

### Task 4: 更新烟测，确认 `token` 已不依赖 legacy scanner class

**Files:**
- Modify: `tests/backend/test_legacy_scanner_real_integration.py`

- [ ] **Step 1: 改写 `token` 烟测，直接验证新执行器发出的请求格式仍与旧语义兼容**

```python
async def test_token_executor_smoke_keeps_legacy_request_shape():
    signer = FakeSigner(result="fake-sign")
    ...
    assert session.calls[0]["url"] == "https://www.c5game.com/api/v1/support/trade/product/batch/v1/sell/query"
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
    assert session.calls[0]["headers"]["x-access-token"] == "token-1"
    assert session.calls[0]["json"]["limit"] == "200"
```

- [ ] **Step 2: 运行烟测确认兼容**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_legacy_scanner_real_integration.py -q`
Expected: PASS

## Chunk 5: 运行时回归

### Task 5: 确认上层 worker 和购买桥不回归

**Files:**
- Verify: `tests/backend/test_account_query_worker.py`
- Verify: `tests/backend/test_query_purchase_bridge.py`

- [ ] **Step 1: 运行 `AccountQueryWorker` 回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_query_worker.py -q`
Expected: PASS

- [ ] **Step 2: 运行命中转购买桥回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 3: 只有测试失败时才做最小修正**

```python
if error == "Not login" or "HTTP 403" in error:
    ...
```

- [ ] **Step 4: 复跑回归测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_query_worker.py tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

## Chunk 6: 最终验证

### Task 6: 整体验证 `token` 替换不破外部合同

**Files:**
- Modify: `README.md`
- Verify only

- [ ] **Step 1: 更新 README 中“查询链路去 legacy”进度**

```markdown
- `token` 查询执行已从 `autobuy.py` legacy scanner 中剥离
- 查询链路已不再依赖 `autobuy.py`
```

- [ ] **Step 2: 运行 `token` 替换相关定向测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_token_query_executor.py tests/backend/test_legacy_scanner_adapter.py tests/backend/test_legacy_scanner_real_integration.py tests/backend/test_account_query_worker.py tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 3: 运行全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS

- [ ] **Step 4: 汇报结果，只报告已验证内容**

注：本计划不包含 git 提交；如果 `token` 替换过程中发现旧语义里存在未文档化的边界行为，优先补测试锁定，再决定是否兼容复刻。
