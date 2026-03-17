# Query Runtime Mode-Scoped Item Schedulers Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把查询运行时的调度语义锁定为“每种查询方式一个独立调度器”，并用测试与最小实现确保模式之间的商品轮转和商品冷却完全隔离。

**Architecture:** 当前代码已经部分接近目标：每个 `ModeRunner` 都会注入一个 `QueryItemScheduler`，同模式内查询组共享它。实现阶段不重写整个运行时，而是先做行为审计和测试锁定，再根据测试结果对 `QueryTaskRuntime`、`ModeRunner`、`QueryItemScheduler` 做最小改动，让“模式级独立调度器”成为清晰、可验证、不会再被文档带偏的正式语义。

**Tech Stack:** Python, asyncio, FastAPI, PySide6, pytest

---

## 文件结构

- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
  - 明确表达“每个模式一个 scheduler 实例”的运行时组装语义
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
  - 保持“同模式共享一个 scheduler、不同模式互不干扰”的执行边界
- Modify: `app_backend/infrastructure/query/runtime/query_item_scheduler.py`
  - 保证调度状态完全是实例级，不出现跨实例共享
- Modify: `tests/backend/test_query_runtime_service.py`
  - 锁定“不同模式不同 scheduler、同模式共用该模式 scheduler”
- Modify: `tests/backend/test_mode_execution_runner.py`
  - 锁定“同模式内多个查询组共享本模式 scheduler”
- Modify: `tests/backend/test_query_item_scheduler.py`
  - 锁定“不同 scheduler 实例之间商品冷却互不影响”
- Verify: `tests/backend/test_account_query_worker.py`
  - 确认 `403 / 429 / Not login` 行为不回归
- Verify: `tests/backend/test_query_purchase_bridge.py`
  - 确认查询命中转购买不回归

## Chunk 1: 审计并锁定模式级调度器隔离

### Task 1: 为“不同模式不同调度器”补充特征测试

**Files:**
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_item_scheduler.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_item_scheduler.py`

- [ ] **Step 1: 在 `test_query_runtime_service.py` 中补一个特征测试，明确三个模式拿到三个不同的 scheduler 实例**

```python
def test_query_task_runtime_builds_distinct_scheduler_per_mode():
    seen_schedulers = {}

    class FakeModeRunner:
        def __init__(self, mode_setting, accounts, *, query_items=None, query_item_scheduler=None) -> None:
            seen_schedulers[mode_setting.mode_type] = query_item_scheduler

        def snapshot(self) -> dict[str, object]:
            return {
                "mode_type": "new_api",
                "enabled": True,
                "eligible_account_count": 0,
                "active_account_count": 0,
                "in_window": True,
                "next_window_start": None,
                "next_window_end": None,
                "query_count": 0,
                "found_count": 0,
                "last_error": None,
                "recent_events": [],
            }
```

- [ ] **Step 2: 在同一个测试中断言三个模式的 scheduler 都存在且两两不同**

```python
    QueryTaskRuntime(
        build_config("cfg-1"),
        [build_account("a1", api_key="api-1")],
        mode_runner_factory=lambda mode_setting, accounts, **kwargs: FakeModeRunner(mode_setting, accounts, **kwargs),
    )

    assert set(seen_schedulers) == {"new_api", "fast_api", "token"}
    assert seen_schedulers["new_api"] is not None
    assert seen_schedulers["fast_api"] is not None
    assert seen_schedulers["token"] is not None
    assert seen_schedulers["new_api"] is not seen_schedulers["fast_api"]
    assert seen_schedulers["fast_api"] is not seen_schedulers["token"]
    assert seen_schedulers["new_api"] is not seen_schedulers["token"]
```

- [ ] **Step 3: 在 `test_query_item_scheduler.py` 中补一个特征测试，明确不同实例之间不共享商品冷却**

```python
async def test_query_item_scheduler_instances_do_not_share_cooldown_state():
    scheduler_a = QueryItemScheduler([build_item("item-1")], min_cooldown_seconds=0.1)
    scheduler_b = QueryItemScheduler([build_item("item-1")], min_cooldown_seconds=0.1)

    first_a = await scheduler_a.reserve_next(now=10.0)
    first_b = await scheduler_b.reserve_next(now=10.0)
    second_a = await scheduler_a.reserve_next(now=10.0)

    assert first_a is not None
    assert first_b is not None
    assert second_a is not None
    assert first_a.execute_at == 10.0
    assert first_b.execute_at == 10.0
    assert second_a.execute_at == 10.1
```

- [ ] **Step 4: 运行审计测试，记录当前实现是否已满足该语义**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py tests/backend/test_query_item_scheduler.py -q`
Expected: 如果当前实现已对齐，测试直接 PASS；如果存在隐藏耦合，测试 FAIL 并暴露问题。

- [ ] **Step 5: 如果测试失败，只对 `query_task_runtime.py` 或 `query_item_scheduler.py` 做最小修正**

```python
# query_task_runtime.py
item_scheduler_factory = query_item_scheduler_factory or self._build_default_query_item_scheduler
self._mode_runners = [
    self._build_mode_runner(
        factory,
        mode_setting,
        self._accounts,
        query_items=list(self._config.items),
        query_item_scheduler=item_scheduler_factory(list(self._config.items)),
        hit_sink=self._hit_sink,
    )
    for mode_setting in config.mode_settings
]
```

- [ ] **Step 6: 复跑审计测试，确认模式之间的 scheduler 隔离被锁定**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py tests/backend/test_query_item_scheduler.py -q`
Expected: PASS

## Chunk 2: 锁定同模式内查询组共享本模式调度器

### Task 2: 为“同模式共享、不同模式隔离”补强 ModeRunner 测试

**Files:**
- Modify: `tests/backend/test_mode_execution_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`

- [ ] **Step 1: 在 `test_mode_execution_runner.py` 中补一个测试，明确同模式内多个查询组共用传入的 scheduler**

```python
async def test_mode_runner_workers_share_mode_scheduler_only_within_same_mode():
    reserved_by = []

    class FakeScheduler:
        def __init__(self) -> None:
            self._items = [build_item("item-1"), build_item("item-2")]
            self._index = 0

        def reset(self) -> None:
            self._index = 0

        async def reserve_next(self, *, now=None):
            item = self._items[self._index]
            self._index = (self._index + 1) % len(self._items)
            reserved_by.append(item.query_item_id)
            return type("Reservation", (), {"query_item": item, "execute_at": 10.0})()
```

- [ ] **Step 2: 用两个账号启动一个 `new_api` runner，断言调度顺序来自同一个 scheduler 实例**

```python
    runner = ModeRunner(
        build_mode("new_api"),
        [build_account("a1", api_key="api-1"), build_account("a2", api_key="api-2")],
        query_items=[build_item("unused")],
        query_item_scheduler=FakeScheduler(),
        worker_factory=lambda mode_type, account: FakeWorker(account),
    )

    runner.start()
    await runner.run_once()

    assert reserved_by == ["item-1", "item-2"]
```

- [ ] **Step 3: 运行 `ModeRunner` 定向测试，确认同模式共享调度器语义被锁定**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_mode_execution_runner.py -q`
Expected: PASS if current implementation already aligned; otherwise FAIL exposing regression.

- [ ] **Step 4: 如果测试失败，只在 `mode_runner.py` 中做最小修正，不要改前后端协议**

```python
reservation = await self._query_item_scheduler.reserve_next(now=self._now_provider())
if reservation is None:
    ...
event = await worker.run_once(reservation.query_item)
```

- [ ] **Step 5: 复跑 `ModeRunner` 定向测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_mode_execution_runner.py -q`
Expected: PASS

## Chunk 3: 明确运行时语义，避免文档和代码再次背离

### Task 3: 只做最小实现整理，让“模式级独立调度器”在代码上更显式

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `tests/backend/test_query_runtime_service.py`

- [ ] **Step 1: 在 `query_task_runtime.py` 中把 scheduler 构造局部变量命名成模式级语义，而不是隐式内联创建**

```python
mode_query_items = list(self._config.items)
self._mode_runners = [
    self._build_mode_runner(
        factory,
        mode_setting,
        self._accounts,
        query_items=mode_query_items,
        query_item_scheduler=item_scheduler_factory(list(mode_query_items)),
        hit_sink=self._hit_sink,
    )
    for mode_setting in config.mode_settings
]
```

- [ ] **Step 2: 如果上一步引入了共享列表或构造顺序问题，修正为每个模式单独拿一个 scheduler、共享同一份配置商品数据**

```python
query_items = list(self._config.items)
for mode_setting in config.mode_settings:
    scheduler = item_scheduler_factory(list(query_items))
    ...
```

- [ ] **Step 3: 运行 `QueryTaskRuntime` 定向测试，确保整理不改变现有行为**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py -q`
Expected: PASS

## Chunk 4: 确认错误处理和购买桥没有被调度审计带崩

### Task 4: 只做回归验证，除非失败才动代码

**Files:**
- Verify: `tests/backend/test_account_query_worker.py`
- Verify: `tests/backend/test_query_purchase_bridge.py`
- Modify if needed: `app_backend/infrastructure/query/runtime/account_query_worker.py`
- Modify if needed: `app_backend/infrastructure/query/runtime/mode_runner.py`

- [ ] **Step 1: 运行查询 worker 回归测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_query_worker.py -q`
Expected: PASS

- [ ] **Step 2: 运行查询命中转购买桥回归测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 3: 只有当测试失败时，才做最小修正**

```python
if inspect.isawaitable(result):
    await result
```

- [ ] **Step 4: 复跑回归测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_query_worker.py tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

## Chunk 5: 最终验证

### Task 5: 整体校验模式级独立调度器语义

**Files:**
- Verify only

- [ ] **Step 1: 运行查询调度相关后端测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_item_scheduler.py tests/backend/test_mode_execution_runner.py tests/backend/test_query_runtime_service.py tests/backend/test_account_query_worker.py tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 2: 运行全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS

- [ ] **Step 3: 汇报验证结果，只报告已跑过的内容**

注：本计划不包含 git 提交；若特征测试在第一轮已全部通过，后续实现改动应保持最小，避免为“已经正确的行为”做无意义重写。
