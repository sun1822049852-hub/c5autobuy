# Query Executor Router Rename Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把查询运行时中名不副实的 `LegacyScannerAdapter` 正名为 `QueryExecutorRouter`，并把它变成主入口，同时保留一层超薄兼容壳，确保运行时行为不变。

**Architecture:** 新增 `query_executor_router.py` 作为主查询执行分发器，内部继续路由到 `NewApiQueryExecutor / FastApiQueryExecutor / TokenQueryExecutor`，并统一包装 `RuntimeAccountAdapter`。`AccountQueryWorker` 默认依赖切到新类；旧 `legacy_scanner_adapter.py` 退化为兼容转发层，不再承担主逻辑。

**Tech Stack:** Python 3, pytest

---

## Chunk 1: 新主类与主测试

### Task 1: 先把主行为测试迁到新名字

**Files:**
- Create: `tests/backend/test_query_executor_router.py`
- Modify: `tests/backend/test_legacy_scanner_adapter.py`

- [ ] **Step 1: 新建 `test_query_executor_router.py`，复制当前主行为测试语义**

```python
async def test_query_executor_router_routes_new_api_to_new_executor():
    ...
```

- [ ] **Step 2: 在新测试里覆盖这些行为**

```python
- new_api 正确分发
- fast_api 正确分发
- token 正确分发
- RuntimeAccountAdapter 可直接传入
- unsupported mode 返回失败结果
- executor 抛异常时返回失败结果
```

- [ ] **Step 3: 把旧测试文件压缩为兼容测试目标，不再承载主语义**

```python
def test_legacy_scanner_adapter_is_compat_wrapper():
    ...
```

- [ ] **Step 4: 跑新测试，确认先失败**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_executor_router.py" -v`

Expected: FAIL，因为生产代码还没有 `QueryExecutorRouter`。

### Task 2: 实现 `QueryExecutorRouter`

**Files:**
- Create: `app_backend/infrastructure/query/runtime/query_executor_router.py`
- Modify: `app_backend/infrastructure/query/runtime/__init__.py`

- [ ] **Step 1: 新增 `QueryExecutorRouter`，把当前 `LegacyScannerAdapter` 的核心分发逻辑迁过来**

```python
class QueryExecutorRouter:
    async def execute_query(...):
        ...
```

- [ ] **Step 2: 保持行为不变**

```python
- 继续包装 RuntimeAccountAdapter
- 继续分发到 3 个 executor
- 继续把异常收敛为 QueryExecutionResult
```

- [ ] **Step 3: 在 runtime 包导出新名字**

```python
from .query_executor_router import QueryExecutorRouter
```

- [ ] **Step 4: 跑新主测试确认转绿**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_executor_router.py" -v`

Expected: PASS

## Chunk 2: 接线迁移与兼容壳

### Task 3: 把 worker 默认依赖切到新主类

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/account_query_worker.py`
- Modify: `tests/backend/test_account_query_worker.py`

- [ ] **Step 1: 给 worker 测试增加一条默认依赖断言**

```python
def test_account_worker_defaults_to_query_executor_router():
    worker = AccountQueryWorker(...)
    assert worker._scanner_adapter.__class__.__name__ == "QueryExecutorRouter"
```

- [ ] **Step 2: 跑该测试确认先失败**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_account_query_worker.py::test_account_worker_defaults_to_query_executor_router" -v`

Expected: FAIL，因为 worker 现在默认还是 `LegacyScannerAdapter`。

- [ ] **Step 3: 修改 `AccountQueryWorker` 默认依赖**

```python
self._scanner_adapter = scanner_adapter or QueryExecutorRouter()
```

- [ ] **Step 4: 跑 worker 测试确认转绿**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_account_query_worker.py" -v`

Expected: PASS

### Task 4: 把旧类收缩为超薄兼容层

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py`
- Modify: `tests/backend/test_legacy_scanner_adapter.py`

- [ ] **Step 1: 给兼容层测试写失败断言，锁定它只是转发**

```python
async def test_legacy_scanner_adapter_delegates_to_query_executor_router():
    ...
```

- [ ] **Step 2: 跑兼容测试确认先失败**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_legacy_scanner_adapter.py" -v`

Expected: FAIL，因为旧类还承载主逻辑，不是显式兼容壳。

- [ ] **Step 3: 把 `LegacyScannerAdapter` 改成超薄转发层**

```python
class LegacyScannerAdapter(QueryExecutorRouter):
    pass
```

或：

```python
class LegacyScannerAdapter:
    def __init__(...):
        self._router = QueryExecutorRouter(...)
```

- [ ] **Step 4: 跑兼容测试确认转绿**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_legacy_scanner_adapter.py" -v`

Expected: PASS

## Chunk 3: 回归验证

### Task 5: 跑查询运行时相关回归

**Files:**
- No file changes required

- [ ] **Step 1: 跑重命名相关测试**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_executor_router.py" "tests/backend/test_legacy_scanner_adapter.py" "tests/backend/test_account_query_worker.py" -v`

Expected: PASS

- [ ] **Step 2: 跑查询执行器相关回归**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_new_api_query_executor.py" "tests/backend/test_fast_api_query_executor.py" "tests/backend/test_token_query_executor.py" "tests/backend/test_query_runtime_service.py" -v`

Expected: PASS

- [ ] **Step 3: 跑全量测试**

Run: `& ".venv/Scripts/python.exe" -m pytest -q`

Expected: PASS

- [ ] **Step 4: 不执行 git 操作**

Reason: 用户明确要求不要默认计划和执行 git 提交、分支、worktree。
