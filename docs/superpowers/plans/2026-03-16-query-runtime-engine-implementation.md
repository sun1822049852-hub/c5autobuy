# Query Runtime Engine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将查询模块的运行时从“静态状态壳子”升级为“真实可执行的三模式查询引擎”，并保持 UI 只做展示与控制。

**Architecture:** 复用 legacy 三种 scanner 的协议细节，在 `app_backend.infrastructure.query.runtime` 中重建任务级、模式级、账号级执行边界。后端负责时间窗、冷却、账号资格、事件和状态聚合，前端只消费增强后的状态快照。

**Tech Stack:** Python, FastAPI, PySide6, pytest, legacy scanner bridge

---

## 文件结构

### 后端核心

- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
  - 保持单任务生命周期入口
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
  - 从静态 snapshot 壳子升级为真实任务容器
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
  - 从资格统计器升级为模式级执行器
- Modify: `app_backend/infrastructure/query/runtime/window_scheduler.py`
  - 继续作为纯时间窗计算器使用
- Create: `app_backend/infrastructure/query/runtime/account_query_worker.py`
  - 单账号单模式执行单元
- Create: `app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py`
  - legacy scanner 统一桥接
- Create: `app_backend/infrastructure/query/runtime/runtime_account_adapter.py`
  - 新账号对象到 legacy 接口的最小适配器
- Create: `app_backend/infrastructure/query/runtime/runtime_events.py`
  - 任务、模式、账号事件与 snapshot 辅助结构

### API / Schema

- Modify: `app_backend/api/schemas/query_runtime.py`
  - 扩展模式级状态与任务级返回字段
- Modify: `app_backend/api/routes/query_runtime.py`
  - 保持现有路由，返回增强后的 snapshot

### 前端展示

- Modify: `app_frontend/app/widgets/query_runtime_panel.py`
  - 显示增强后的运行态
- Modify: `app_frontend/app/formatters/query_runtime_display.py`
  - 适配新增字段的展示格式

### 测试

- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Create: `tests/backend/test_mode_execution_runner.py`
- Create: `tests/backend/test_account_query_worker.py`
- Create: `tests/backend/test_legacy_scanner_adapter.py`
- Modify: `tests/frontend/test_query_runtime_panel.py`
- Modify: `tests/frontend/test_query_system_window.py`

## Chunk 1: Runtime Core Contracts

### Task 1: 扩展运行时返回模型的失败测试

**Files:**
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Test: `tests/backend/test_query_runtime_service.py`
- Test: `tests/backend/test_query_runtime_routes.py`

- [ ] **Step 1: 写失败测试，定义增强后的运行时 snapshot 结构**

```python
def test_runtime_service_returns_mode_window_and_counters():
    snapshot = service.get_status()
    assert snapshot["modes"]["new_api"]["in_window"] is True
    assert snapshot["modes"]["new_api"]["active_account_count"] == 1
    assert snapshot["modes"]["new_api"]["query_count"] == 0
```

- [ ] **Step 2: 运行测试，确认按“缺少字段”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py tests/backend/test_query_runtime_routes.py -q`
Expected: FAIL，提示 snapshot / schema 缺字段

- [ ] **Step 3: 最小改动 schema 和默认 idle snapshot**

```python
class QueryRuntimeModeResponse(BaseModel):
    mode_type: str
    enabled: bool
    eligible_account_count: int
    active_account_count: int
    in_window: bool
    query_count: int
    found_count: int
```

- [ ] **Step 4: 复跑测试，确认接口与 service 绿灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py tests/backend/test_query_runtime_routes.py -q`
Expected: PASS

## Chunk 2: 模式执行器

### Task 2: 为模式级时间窗和账号筛选写失败测试

**Files:**
- Create: `tests/backend/test_mode_execution_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Test: `tests/backend/test_mode_execution_runner.py`

- [ ] **Step 1: 写失败测试，覆盖三模式独立时间窗**

```python
def test_mode_runner_uses_its_own_window_setting():
    runner = ModeExecutionRunner(...)
    state = runner.snapshot(now=fixed_now)
    assert state["in_window"] is False
    assert state["next_window_start"] is not None
```

- [ ] **Step 2: 写失败测试，覆盖账号资格过滤**

```python
def test_mode_runner_filters_accounts_by_preference_and_capability():
    accounts = [
        build_account("a1", api_key="k1"),
        build_account("a2", api_key=None),
    ]
    assert runner.snapshot()["eligible_account_count"] == 1
```

- [ ] **Step 3: 运行测试，确认按“ModeRunner 仍是静态统计器”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_mode_execution_runner.py -q`
Expected: FAIL

- [ ] **Step 4: 将 `mode_runner.py` 升级为真正的 `ModeExecutionRunner`**

```python
class ModeExecutionRunner:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def snapshot(self) -> dict[str, object]: ...
```

- [ ] **Step 5: 复跑模式测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_mode_execution_runner.py -q`
Expected: PASS

### Task 3: 为单账号 worker 写失败测试

**Files:**
- Create: `tests/backend/test_account_query_worker.py`
- Create: `app_backend/infrastructure/query/runtime/account_query_worker.py`
- Create: `app_backend/infrastructure/query/runtime/runtime_events.py`
- Test: `tests/backend/test_account_query_worker.py`

- [ ] **Step 1: 写失败测试，定义 worker 成功事件**

```python
def test_account_worker_returns_query_success_event():
    event = worker.run_once()
    assert event.mode_type == "new_api"
    assert event.match_count == 2
```

- [ ] **Step 2: 写失败测试，定义 403 / 429 / not login 行为**

```python
def test_account_worker_disables_account_on_403():
    result = worker.run_once()
    assert result.disabled_reason == "HTTP 403 Forbidden"
```

- [ ] **Step 3: 运行测试，确认因缺 worker 实现而失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_query_worker.py -q`
Expected: FAIL

- [ ] **Step 4: 实现 `AccountQueryWorker` 和最小事件结构**

```python
@dataclass(slots=True)
class QueryExecutionEvent:
    mode_type: str
    account_id: str
    query_item_id: str
    match_count: int
    error: str | None
```

- [ ] **Step 5: 复跑 worker 测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_query_worker.py -q`
Expected: PASS

## Chunk 3: Legacy Scanner Bridge

### Task 4: 为 legacy scanner 适配层写失败测试

**Files:**
- Create: `tests/backend/test_legacy_scanner_adapter.py`
- Create: `app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py`
- Create: `app_backend/infrastructure/query/runtime/runtime_account_adapter.py`
- Test: `tests/backend/test_legacy_scanner_adapter.py`

- [ ] **Step 1: 写失败测试，约束模式到 scanner 的映射**

```python
def test_adapter_maps_mode_type_to_legacy_scanner():
    scanner = adapter.build(mode_type="token", ...)
    assert scanner.__class__.__name__ == "ProductQueryScanner"
```

- [ ] **Step 2: 写失败测试，约束账号适配器暴露 legacy 最小接口**

```python
def test_runtime_account_adapter_exposes_access_token_and_device_id():
    legacy_account = RuntimeAccountAdapter(account)
    assert legacy_account.get_x_access_token() == "token"
```

- [ ] **Step 3: 运行测试，确认缺实现失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_legacy_scanner_adapter.py -q`
Expected: FAIL

- [ ] **Step 4: 实现 adapter 与 runtime account bridge**

```python
class RuntimeAccountAdapter:
    def get_api_key(self) -> str | None: ...
    def get_x_access_token(self) -> str | None: ...
    def get_x_device_id(self) -> str | None: ...
```

- [ ] **Step 5: 复跑桥接测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_legacy_scanner_adapter.py -q`
Expected: PASS

## Chunk 4: 任务容器与生命周期

### Task 5: 为真实 `QueryTaskRuntime` 写失败测试

**Files:**
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Test: `tests/backend/test_query_runtime_service.py`

- [ ] **Step 1: 写失败测试，约束任务能启动模式 runner**

```python
def test_query_task_runtime_builds_three_mode_runners():
    runtime.start()
    snapshot = runtime.snapshot()
    assert set(snapshot["modes"]) == {"new_api", "fast_api", "token"}
```

- [ ] **Step 2: 写失败测试，约束停止时 runner 全部退出**

```python
def test_query_runtime_service_stop_stops_all_mode_runners():
    stopped, _ = service.stop()
    assert stopped is True
    assert service.get_status()["running"] is False
```

- [ ] **Step 3: 运行测试，确认按“任务容器无真实调度”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py -q`
Expected: FAIL

- [ ] **Step 4: 实现真实 `QueryTaskRuntime` 任务容器**

```python
class QueryTaskRuntime:
    def start(self) -> None:
        for runner in self._mode_runners:
            runner.start()
```

- [ ] **Step 5: 复跑 runtime service 测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py tests/backend/test_mode_execution_runner.py tests/backend/test_account_query_worker.py tests/backend/test_legacy_scanner_adapter.py -q`
Expected: PASS

## Chunk 5: 前端状态展示回归

### Task 6: 为前端运行态面板写失败测试

**Files:**
- Modify: `tests/frontend/test_query_runtime_panel.py`
- Modify: `tests/frontend/test_query_system_window.py`
- Modify: `app_frontend/app/widgets/query_runtime_panel.py`
- Modify: `app_frontend/app/formatters/query_runtime_display.py`
- Test: `tests/frontend/test_query_runtime_panel.py`
- Test: `tests/frontend/test_query_system_window.py`

- [ ] **Step 1: 写失败测试，要求模式表显示新增运行字段**

```python
def test_query_runtime_panel_renders_active_accounts_and_query_counts(qtbot):
    panel.load_status(status_payload)
    assert panel.mode_table.item(0, 2).text() == "1/2"
```

- [ ] **Step 2: 运行前端测试，确认因字段不存在失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend/test_query_runtime_panel.py tests/frontend/test_query_system_window.py -q`
Expected: FAIL

- [ ] **Step 3: 最小实现面板和 formatter 展示增强**

```python
rows.append({
    "eligible_account_count": f"{active}/{eligible}",
    "query_count": str(query_count),
})
```

- [ ] **Step 4: 复跑前端目标测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend/test_query_runtime_panel.py tests/frontend/test_query_system_window.py -q`
Expected: PASS

## Chunk 6: 总体验证

### Task 7: 查询模块回归验证

**Files:**
- Test: `tests/backend/test_query_config_repository.py`
- Test: `tests/backend/test_query_config_routes.py`
- Test: `tests/backend/test_query_item_collectors.py`
- Test: `tests/backend/test_query_runtime_service.py`
- Test: `tests/backend/test_query_runtime_routes.py`
- Test: `tests/frontend/test_query_system_vm.py`
- Test: `tests/frontend/test_query_system_controller.py`
- Test: `tests/frontend/test_query_runtime_panel.py`
- Test: `tests/frontend/test_query_mode_settings_dialog.py`
- Test: `tests/frontend/test_query_item_dialog.py`
- Test: `tests/frontend/test_query_system_window.py`
- Test: `tests/frontend/test_workspace_window.py`

- [ ] **Step 1: 跑后端查询模块回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_repository.py tests/backend/test_query_config_routes.py tests/backend/test_query_item_collectors.py tests/backend/test_query_runtime_service.py tests/backend/test_query_runtime_routes.py tests/backend/test_mode_execution_runner.py tests/backend/test_account_query_worker.py tests/backend/test_legacy_scanner_adapter.py -q`
Expected: PASS

- [ ] **Step 2: 跑前端查询模块回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend/test_query_system_vm.py tests/frontend/test_query_system_controller.py tests/frontend/test_query_runtime_panel.py tests/frontend/test_query_mode_settings_dialog.py tests/frontend/test_query_item_dialog.py tests/frontend/test_query_system_window.py tests/frontend/test_workspace_window.py -q`
Expected: PASS

- [ ] **Step 3: 跑全前端回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend -q`
Expected: PASS

- [ ] **Step 4: 人工验证**

Run:

```bash
.\.venv\Scripts\python.exe -m app_backend.main
```

验证点：

- 创建一个配置
- 给三种模式设置不同时间窗
- 启动查询
- `QueryRuntimePanel` 能看到模式分开运行
- 停止查询后状态回到 idle

## 备注

- 本计划故意不接购买链路
- 本计划优先保证“真实可查询”而不是“完全去 legacy”
- 本文档仅写计划，未执行 `git commit`，遵循当前会话约束
