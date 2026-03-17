# Query Runtime Global Item Scheduler Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让查询运行时改为“配置级全局商品调度 + 账号模式独立就绪”的 legacy 对齐实现，同时保持现有前后端接口不破。

**Architecture:** 在 `QueryTaskRuntime` 下新增配置级 `QueryItemScheduler`，由它统一分配当前配置中的商品；`ModeRunner` 退回到模式容器角色，只负责资格筛选、时间窗口、账号 worker task 管理和模式级统计；单账号查询仍由 `AccountQueryWorker` 调用 legacy scanner。

**Tech Stack:** Python, asyncio, FastAPI, PySide6, pytest, legacy scanner bridge

---

## 文件结构

- Create: `app_backend/infrastructure/query/runtime/query_item_scheduler.py`
  - 配置级全局商品调度器
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
  - 挂载全局商品调度器并传给各模式 runner
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
  - 从“模式统一一轮”改为“账号 worker 独立 loop”
- Modify: `app_backend/infrastructure/query/runtime/account_query_worker.py`
  - 暴露更清晰的运行状态辅助
- Modify: `tests/backend/test_mode_execution_runner.py`
  - 改写为 legacy 对齐行为测试
- Create: `tests/backend/test_query_item_scheduler.py`
  - 覆盖全局商品分配与商品最小冷却
- Modify: `tests/backend/test_query_runtime_service.py`
  - 验证新的任务容器协作关系
- Modify: `tests/backend/test_query_purchase_bridge.py`
  - 确认命中转发不回归

## Chunk 1: 全局商品调度器

### Task 1: 先写调度器失败测试

**Files:**
- Create: `tests/backend/test_query_item_scheduler.py`
- Create: `app_backend/infrastructure/query/runtime/query_item_scheduler.py`

- [ ] **Step 1: 写失败测试，锁定全局轮转分配**

```python
def test_query_item_scheduler_round_robins_items_globally():
    scheduler = QueryItemScheduler(items=[item1, item2], min_cooldown_seconds=0.1)
    first = scheduler.reserve_next(now=10.0)
    second = scheduler.reserve_next(now=10.0)
    assert first.query_item_id == "item-1"
    assert second.query_item_id == "item-2"
```

- [ ] **Step 2: 写失败测试，锁定单商品最小冷却**

```python
def test_query_item_scheduler_delays_repeated_item_until_cooldown():
    scheduler = QueryItemScheduler(items=[item1], min_cooldown_seconds=0.1)
    first = scheduler.reserve_next(now=10.0)
    second = scheduler.reserve_next(now=10.0)
    assert first.execute_at == 10.0
    assert second.execute_at == 10.1
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_item_scheduler.py -q`
Expected: FAIL，提示缺少调度器实现

- [ ] **Step 4: 实现最小 `QueryItemScheduler`**

- [ ] **Step 5: 复跑测试确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_item_scheduler.py -q`
Expected: PASS

## Chunk 2: 模式运行粒度改正

### Task 2: 先写失败测试，锁定“账号独立就绪”

**Files:**
- Modify: `tests/backend/test_mode_execution_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`

- [ ] **Step 1: 写失败测试，验证同一模式下多个账号独立申请商品**

```python
async def test_mode_runner_workers_request_items_independently():
    ...
    assert calls == [("a1", "item-1"), ("a2", "item-2")]
```

- [ ] **Step 2: 写失败测试，验证不再使用内部 `_next_query_item` 批处理轮转**

```python
async def test_mode_runner_uses_shared_item_scheduler_not_local_rotation():
    ...
    assert scheduler.calls == ["a1", "a2"]
```

- [ ] **Step 3: 运行模式测试并确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_mode_execution_runner.py -q`
Expected: FAIL，提示当前实现仍是按模式一轮批量分配

- [ ] **Step 4: 重构 `ModeRunner` 为 worker task 模型**

- [ ] **Step 5: 复跑模式测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_mode_execution_runner.py -q`
Expected: PASS

## Chunk 3: 任务容器协作

### Task 3: 先写失败测试，锁定任务容器会共享一个商品调度器

**Files:**
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`

- [ ] **Step 1: 写失败测试，验证三个模式拿到同一个 scheduler 实例**

```python
def test_query_task_runtime_shares_one_query_item_scheduler_across_modes():
    ...
    assert seen_schedulers["new_api"] is seen_schedulers["fast_api"]
    assert seen_schedulers["fast_api"] is seen_schedulers["token"]
```

- [ ] **Step 2: 运行任务容器测试并确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py -q`
Expected: FAIL

- [ ] **Step 3: 在 `QueryTaskRuntime` 中接入共享 scheduler**

- [ ] **Step 4: 复跑测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py -q`
Expected: PASS

## Chunk 4: 回归与桥接

### Task 4: 确认购买桥和现有查询错误处理不回归

**Files:**
- Modify: `tests/backend/test_query_purchase_bridge.py`
- Modify: `tests/backend/test_account_query_worker.py`
- Modify: `app_backend/infrastructure/query/runtime/account_query_worker.py`

- [ ] **Step 1: 补失败测试，验证命中转发仍正常**
- [ ] **Step 2: 补失败测试，验证 403 / 429 / Not login 仍按原规则处理**
- [ ] **Step 3: 运行定向测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_purchase_bridge.py tests/backend/test_account_query_worker.py -q`
Expected: FAIL

- [ ] **Step 4: 最小修改实现通过**
- [ ] **Step 5: 复跑定向测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_purchase_bridge.py tests/backend/test_account_query_worker.py -q`
Expected: PASS

## Chunk 5: 最终验证

### Task 5: 完整回归

**Files:**
- Verify only

- [ ] **Step 1: 运行查询相关后端测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_item_scheduler.py tests/backend/test_mode_execution_runner.py tests/backend/test_account_query_worker.py tests/backend/test_query_runtime_service.py tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 2: 运行全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS

- [ ] **Step 3: 汇报结果，不宣称未验证的内容**

注：本计划只写到实现和验证，不包含 git 提交。
