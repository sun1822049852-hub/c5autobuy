# Purchase Runtime Engine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在新重构架构中实现独立的购买运行时，打通“查询命中 -> 购买调度 -> 账户执行 -> 库存回写 -> GUI 展示”的闭环，并保留 legacy 的库存与购买池行为。

**Architecture:** 新增 `app_backend.infrastructure.purchase.runtime` 作为购买后端核心，使用独立的运行时服务、命中 inbox、调度器、账户工作者、库存状态机和 legacy-compatible 执行网关。查询模块只通过命中事件向购买运行时投递批次；前端新增独立购买运行页，账号中心仅展示能力与池状态。用户已明确要求不做 git 提交，因此本计划保留 TDD 与验证步骤，但不包含 commit 步骤。

**Tech Stack:** Python, FastAPI, SQLAlchemy/SQLite, PySide6, pytest, legacy `autobuy.py` adapter

---

## 文件结构

### 后端数据库与仓储

- Modify: `app_backend/infrastructure/db/models.py`
  - 增加购买运行设置表和账户库存快照表
- Create: `app_backend/infrastructure/repositories/purchase_runtime_settings_repository.py`
  - 全局 `query_only` 和白名单配置读写
- Create: `app_backend/infrastructure/repositories/account_inventory_snapshot_repository.py`
  - 账号库存快照和 `selected_steam_id` 读写

### 后端领域与应用

- Modify: `app_backend/domain/enums/account_states.py`
  - 增加 `active`、`paused_auth_invalid` 等购买池状态
- Create: `app_backend/domain/models/purchase_runtime_settings.py`
  - 购买运行时全局配置领域模型
- Create: `app_backend/domain/models/account_inventory_snapshot.py`
  - 账号库存快照领域模型
- Create: `app_backend/application/use_cases/get_purchase_runtime_status.py`
- Create: `app_backend/application/use_cases/start_purchase_runtime.py`
- Create: `app_backend/application/use_cases/stop_purchase_runtime.py`
- Create: `app_backend/application/use_cases/get_purchase_runtime_settings.py`
- Create: `app_backend/application/use_cases/update_purchase_runtime_settings.py`

### 后端购买运行时

- Create: `app_backend/infrastructure/purchase/runtime/__init__.py`
- Create: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
  - 购买命中、调度、执行、库存恢复事件定义
- Create: `app_backend/infrastructure/purchase/runtime/purchase_hit_inbox.py`
  - 命中去重与入队
- Create: `app_backend/infrastructure/purchase/runtime/inventory_state.py`
  - 仓库快照、目标仓库选择、本地容量递推、远端刷新确认
- Create: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`
  - 全局购买队列、轮询分发、购买池状态维护
- Create: `app_backend/infrastructure/purchase/runtime/account_purchase_worker.py`
  - 单账户购买执行器
- Create: `app_backend/infrastructure/purchase/runtime/execution_gateway.py`
  - 购买执行网关协议
- Create: 旧购买执行适配器文件
  - legacy-compatible 下单/支付适配器
- Create: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
  - 购买运行时总服务

### 查询桥接

- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
  - 接收购买运行时命中 sink
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
  - 将命中 sink 下发给模式执行器
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
  - 对命中事件触发购买桥接

### API / 应用入口

- Create: `app_backend/api/schemas/purchase_runtime.py`
  - 购买运行时 snapshot、设置、最近事件 schema
- Create: `app_backend/api/routes/purchase_runtime.py`
  - 购买运行时接口
- Modify: `app_backend/main.py`
  - 注入购买仓储、购买运行时 service、路由和 query bridge

### 前端

- Create: `app_frontend/app/viewmodels/purchase_runtime_vm.py`
  - 购买运行页视图模型
- Create: `app_frontend/app/controllers/purchase_runtime_controller.py`
  - 调用购买运行时 API
- Create: `app_frontend/app/widgets/purchase_runtime_panel.py`
  - 运行摘要、白名单、事件列表、账户池列表
- Create: `app_frontend/app/windows/purchase_runtime_window.py`
  - 独立购买运行页
- Modify: `app_frontend/app/services/backend_client.py`
  - 增加购买运行时 API 调用
- Modify: `app_frontend/app/windows/workspace_window.py`
  - 增加购买页导航
- Modify: `app_frontend/main.py`
  - 注入购买运行页
- Modify: `app_frontend/app/formatters/account_display.py`
  - 补全新的购买池状态标签
- Modify: `app_frontend/app/widgets/account_detail_panel.py`
  - 展示新的池状态文案

### 测试

- Create: `tests/backend/test_purchase_runtime_settings_repository.py`
- Create: `tests/backend/test_account_inventory_snapshot_repository.py`
- Create: `tests/backend/test_purchase_hit_inbox.py`
- Create: `tests/backend/test_inventory_state.py`
- Create: `tests/backend/test_purchase_scheduler.py`
- Create: `tests/backend/test_account_purchase_worker_runtime.py`
- Create: `tests/backend/test_purchase_runtime_service.py`
- Create: `tests/backend/test_purchase_runtime_routes.py`
- Create: `tests/backend/test_query_purchase_bridge.py`
- Modify: `tests/frontend/test_backend_client.py`
- Create: `tests/frontend/test_purchase_runtime_vm.py`
- Create: `tests/frontend/test_purchase_runtime_controller.py`
- Create: `tests/frontend/test_purchase_runtime_panel.py`
- Create: `tests/frontend/test_purchase_runtime_window.py`
- Modify: `tests/frontend/test_workspace_window.py`
- Modify: `tests/frontend/test_account_detail_panel.py`

## Chunk 1: 持久化与基础契约

### Task 1: 为购买运行设置与库存快照建立持久化契约

**Files:**
- Modify: `app_backend/infrastructure/db/models.py`
- Create: `app_backend/domain/models/purchase_runtime_settings.py`
- Create: `app_backend/domain/models/account_inventory_snapshot.py`
- Create: `app_backend/infrastructure/repositories/purchase_runtime_settings_repository.py`
- Create: `app_backend/infrastructure/repositories/account_inventory_snapshot_repository.py`
- Test: `tests/backend/test_purchase_runtime_settings_repository.py`
- Test: `tests/backend/test_account_inventory_snapshot_repository.py`

- [ ] **Step 1: 写失败测试，定义购买设置和库存快照的 round-trip 行为**

```python
def test_purchase_runtime_settings_round_trip(tmp_path):
    repo = build_settings_repo(tmp_path)
    saved = repo.save(query_only=True, whitelist_account_ids=["a1", "a2"])
    loaded = repo.get()
    assert loaded.query_only is True
    assert loaded.whitelist_account_ids == ["a1", "a2"]


def test_account_inventory_snapshot_round_trip(tmp_path):
    repo = build_snapshot_repo(tmp_path)
    saved = repo.save(
        account_id="a1",
        selected_steam_id="s-1",
        inventories=[
            {"steamId": "s-1", "inventory_num": 940, "inventory_max": 1000},
            {"steamId": "s-2", "inventory_num": 850, "inventory_max": 1000},
        ],
    )
    loaded = repo.get("a1")
    assert loaded.selected_steam_id == "s-1"
    assert loaded.inventories[0]["steamId"] == "s-1"
```

- [ ] **Step 2: 运行仓储测试，确认按“缺少表或仓储”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_settings_repository.py tests/backend/test_account_inventory_snapshot_repository.py -q`
Expected: FAIL，提示 repository / table / model 不存在

- [ ] **Step 3: 增加数据表、领域模型和 SQLite 仓储**

```python
@dataclass(slots=True)
class PurchaseRuntimeSettings:
    query_only: bool
    whitelist_account_ids: list[str]
    updated_at: str


@dataclass(slots=True)
class AccountInventorySnapshot:
    account_id: str
    selected_steam_id: str | None
    inventories: list[dict[str, Any]]
    refreshed_at: str | None
    last_error: str | None
```

- [ ] **Step 4: 复跑仓储测试，确认两个仓储都能稳定 round-trip**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_settings_repository.py tests/backend/test_account_inventory_snapshot_repository.py -q`
Expected: PASS

### Task 2: 扩展账户池状态枚举与展示标签

**Files:**
- Modify: `app_backend/domain/enums/account_states.py`
- Modify: `app_frontend/app/formatters/account_display.py`
- Modify: `app_frontend/app/widgets/account_detail_panel.py`
- Test: `tests/frontend/test_account_detail_panel.py`

- [ ] **Step 1: 写失败测试，定义新增购买池状态文案**

```python
def test_account_detail_panel_formats_active_and_paused_auth_invalid(qtbot):
    panel = build_panel(
        purchase_capability_state="bound",
        purchase_pool_state="active",
    )
    assert panel.purchase_pool_input.text() == "运行中"
```

- [ ] **Step 2: 运行前端测试，确认按“未知状态文案”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend/test_account_detail_panel.py -q`
Expected: FAIL，提示标签或 tone 不匹配

- [ ] **Step 3: 扩展状态枚举、格式化函数和 detail panel tone 规则**

```python
class PurchasePoolState:
    ACTIVE = "active"
    PAUSED_AUTH_INVALID = "paused_auth_invalid"
```

- [ ] **Step 4: 复跑 detail panel 测试，确认新增状态可见**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend/test_account_detail_panel.py -q`
Expected: PASS

## Chunk 2: 购买运行时核心

### Task 3: 先实现命中 inbox 的去重与入队

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Create: `app_backend/infrastructure/purchase/runtime/purchase_hit_inbox.py`
- Test: `tests/backend/test_purchase_hit_inbox.py`

- [ ] **Step 1: 写失败测试，覆盖 `total_wear_sum` 去重和无磨损直通**

```python
def test_purchase_hit_inbox_deduplicates_same_wear_sum_within_window():
    inbox = PurchaseHitInbox(cache_duration=5.0, now_provider=lambda: 100.0)
    assert inbox.accept(build_hit(total_wear_sum=1.2345)) is True
    assert inbox.accept(build_hit(total_wear_sum=1.2345)) is False


def test_purchase_hit_inbox_passes_hits_without_wear_sum():
    inbox = PurchaseHitInbox()
    assert inbox.accept(build_hit(total_wear_sum=None)) is True
```

- [ ] **Step 2: 运行 inbox 测试，确认按“类不存在或逻辑缺失”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_hit_inbox.py -q`
Expected: FAIL

- [ ] **Step 3: 写最小实现，输出可投递的命中批次对象**

```python
@dataclass(slots=True)
class PurchaseHitBatch:
    query_item_name: str
    product_list: list[dict[str, Any]]
    total_price: float
    total_wear_sum: float | None
    source_mode_type: str
```

- [ ] **Step 4: 复跑 inbox 测试，确认去重逻辑绿灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_hit_inbox.py -q`
Expected: PASS

### Task 4: 先把库存状态机独立出来，再谈调度

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/inventory_state.py`
- Test: `tests/backend/test_inventory_state.py`

- [ ] **Step 1: 写失败测试，覆盖目标仓库选择、本地递推、切仓与远端确认触发**

```python
def test_inventory_state_prefers_smaller_remaining_capacity_above_threshold():
    state = InventoryState(min_capacity_threshold=50)
    state.load_snapshot(
        [
            {"steamId": "s1", "inventory_num": 910, "inventory_max": 1000},
            {"steamId": "s2", "inventory_num": 850, "inventory_max": 1000},
        ]
    )
    assert state.selected_steam_id == "s1"


def test_inventory_state_updates_local_capacity_after_purchase():
    state = build_state(selected_steam_id="s1")
    result = state.apply_purchase_success(purchased_count=20)
    assert result.requires_remote_refresh is False


def test_inventory_state_switches_selected_steam_id_when_target_changes():
    state = build_state(
        selected_steam_id="s1",
        inventories=[
            {"steamId": "s1", "inventory_num": 960, "inventory_max": 1000},
            {"steamId": "s2", "inventory_num": 900, "inventory_max": 1000},
        ],
    )
    result = state.apply_purchase_success(purchased_count=10)
    assert state.selected_steam_id == "s2"
```

- [ ] **Step 2: 运行库存状态测试，确认按“状态机不存在”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_inventory_state.py -q`
Expected: FAIL

- [ ] **Step 3: 实现独立库存状态机，避免把逻辑塞进 scheduler**

```python
class InventoryState:
    def load_snapshot(self, inventories: list[dict[str, Any]]) -> None: ...
    def apply_purchase_success(self, purchased_count: int) -> InventoryTransition: ...
    def refresh_from_remote(self, inventories: list[dict[str, Any]]) -> InventoryTransition: ...
```

- [ ] **Step 3.1: 明确 `selected_steam_id` 是状态机的一等输出**

```python
class InventoryState:
    selected_steam_id: str | None
```

要求：

- 初始化选仓后必须写入 `selected_steam_id`
- 本地切仓后必须更新 `selected_steam_id`
- 远端刷新后重新选仓也必须更新 `selected_steam_id`

- [ ] **Step 4: 复跑库存状态测试，确认选仓和本地递推正确**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_inventory_state.py -q`
Expected: PASS

### Task 5: 把调度器做成只管“队列 + 池 + 轮询”

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`
- Test: `tests/backend/test_purchase_scheduler.py`

- [ ] **Step 1: 写失败测试，覆盖轮询分发、白名单过滤、无库存移池、恢复回池**

```python
def test_purchase_scheduler_round_robins_across_active_accounts():
    scheduler = build_scheduler(active_account_ids=["a1", "a2"])
    assert scheduler.select_next_account_id() == "a1"
    assert scheduler.select_next_account_id() == "a2"


def test_purchase_scheduler_removes_account_from_pool_without_dropping_capability():
    scheduler = build_scheduler(active_account_ids=["a1"])
    scheduler.mark_no_inventory("a1")
    assert "a1" not in scheduler.available_account_ids()
    assert scheduler.account_pool_state("a1") == "paused_no_inventory"
```

- [ ] **Step 2: 运行调度器测试，确认按“调度器不存在”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_scheduler.py -q`
Expected: FAIL

- [ ] **Step 3: 实现只负责队列和池状态的 scheduler，不混执行细节**

```python
class PurchaseScheduler:
    def submit(self, batch: PurchaseHitBatch) -> None: ...
    def register_account(self, account_id: str, *, available: bool) -> None: ...
    def mark_no_inventory(self, account_id: str) -> None: ...
    def mark_inventory_recovered(self, account_id: str) -> None: ...
```

- [ ] **Step 4: 复跑调度器测试，确认轮询和池状态逻辑绿灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_scheduler.py -q`
Expected: PASS

### Task 6: 单账户购买工作者只做执行和状态回写

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/execution_gateway.py`
- Create: 旧购买执行适配器文件
- Create: `app_backend/infrastructure/purchase/runtime/account_purchase_worker.py`
- Test: `tests/backend/test_account_purchase_worker_runtime.py`

- [ ] **Step 1: 写失败测试，覆盖成功购买、鉴权失效、库存不足三类结果**

```python
def test_account_purchase_worker_updates_inventory_on_success():
    worker = build_worker(execution_result=PurchaseExecutionResult.success(purchased_count=2))
    outcome = asyncio.run(worker.process(build_batch()))
    assert outcome.status == "success"
    assert outcome.purchased_count == 2
    assert outcome.selected_steam_id == "s1"


def test_account_purchase_worker_marks_auth_invalid_without_retrying_inventory_refresh():
    worker = build_worker(execution_result=PurchaseExecutionResult.auth_invalid("expired"))
    outcome = asyncio.run(worker.process(build_batch()))
    assert outcome.pool_state == "paused_auth_invalid"
    assert outcome.capability_state == "expired"


def test_account_purchase_worker_passes_selected_steam_id_to_execution_gateway():
    gateway = SpyGateway()
    worker = build_worker(execution_gateway=gateway, selected_steam_id="s1")
    asyncio.run(worker.process(build_batch()))
    assert gateway.calls[0]["selected_steam_id"] == "s1"
```

- [ ] **Step 2: 运行 worker 测试，确认按“执行网关协议不存在”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_purchase_worker_runtime.py -q`
Expected: FAIL

- [ ] **Step 3: 先实现协议和 worker，legacy 网关只保留最小适配入口**

```python
class PurchaseExecutionGateway(Protocol):
    async def execute(self, *, account, batch, selected_steam_id: str) -> PurchaseExecutionResult: ...
```

要求：

- `selected_steam_id` 是执行入参，不允许在网关内部再随意选仓
- legacy-compatible 网关需要把它映射到下单请求的 `receiveSteamId`

- [ ] **Step 4: 复跑 worker 测试，确认状态回写逻辑稳定**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_purchase_worker_runtime.py -q`
Expected: PASS

## Chunk 3: 购买运行时服务与查询桥接

### Task 7: 先把购买运行时 service 立起来，再接 API

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Create: `app_backend/application/use_cases/get_purchase_runtime_status.py`
- Create: `app_backend/application/use_cases/start_purchase_runtime.py`
- Create: `app_backend/application/use_cases/stop_purchase_runtime.py`
- Create: `app_backend/application/use_cases/get_purchase_runtime_settings.py`
- Create: `app_backend/application/use_cases/update_purchase_runtime_settings.py`
- Test: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: 写失败测试，定义 idle snapshot、start/stop、settings 更新行为**

```python
def test_purchase_runtime_service_returns_idle_snapshot_when_stopped():
    snapshot = service.get_status()
    assert snapshot["running"] is False
    assert snapshot["active_account_count"] == 0


def test_purchase_runtime_service_updates_global_settings():
    updated = service.update_settings(query_only=True, whitelist_account_ids=["a1"])
    assert updated["settings"]["query_only"] is True
```

- [ ] **Step 2: 运行 service 测试，确认按“服务不存在或字段缺失”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py -q`
Expected: FAIL

- [ ] **Step 3: 组装 runtime service，持有 inbox、scheduler、worker 工厂和仓储**

```python
class PurchaseRuntimeService:
    def start(self) -> tuple[bool, str]: ...
    def stop(self) -> tuple[bool, str]: ...
    def get_status(self) -> dict[str, Any]: ...
    def update_settings(self, *, query_only: bool, whitelist_account_ids: list[str]) -> dict[str, Any]: ...
```

- [ ] **Step 4: 复跑 service 测试，确认 snapshot 和 settings API 绿灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py -q`
Expected: PASS

### Task 8: 把查询命中桥接进购买运行时

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Create: `tests/backend/test_query_purchase_bridge.py`

- [ ] **Step 1: 写失败测试，定义“有命中就投递、仅查询模式就拦截”的桥接行为**

```python
def test_query_hit_is_forwarded_to_purchase_runtime_when_purchase_runtime_running():
    purchase_service = StubPurchaseRuntimeService()
    runtime = build_query_runtime_service(purchase_runtime_service=purchase_service)
    runtime.start(config_id="cfg-1")
    assert purchase_service.accepted_hits[0]["query_item_name"] == "AK"


def test_query_hit_is_marked_blocked_when_query_only_enabled():
    purchase_service = StubPurchaseRuntimeService(query_only=True)
    runtime = build_query_runtime_service(purchase_runtime_service=purchase_service)
    runtime.start(config_id="cfg-1")
    assert purchase_service.blocked_hits == 1
```

- [ ] **Step 2: 运行桥接测试，确认按“没有 event sink”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_purchase_bridge.py -q`
Expected: FAIL

- [ ] **Step 3: 在 query runtime 里加命中 sink，只对 `match_count > 0` 的事件投递**

```python
class QueryTaskRuntime:
    def __init__(..., hit_sink=None):
        self._hit_sink = hit_sink
```

- [ ] **Step 4: 复跑桥接测试，确认查询和购买通过事件解耦**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

### Task 9: 增加购买运行时 API 与应用入口注入

**Files:**
- Create: `app_backend/api/schemas/purchase_runtime.py`
- Create: `app_backend/api/routes/purchase_runtime.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_purchase_runtime_routes.py`

- [ ] **Step 1: 写失败测试，定义状态、启停、设置更新三个接口**

```python
async def test_purchase_runtime_routes_return_snapshot(client):
    response = await client.get("/purchase-runtime/status")
    assert response.status_code == 200
    assert response.json()["running"] is False


async def test_purchase_runtime_settings_route_updates_whitelist(client):
    response = await client.put("/purchase-runtime/settings", json={"query_only": False, "whitelist_account_ids": ["a1"]})
    assert response.json()["settings"]["whitelist_account_ids"] == ["a1"]
```

- [ ] **Step 2: 运行路由测试，确认按“路由不存在”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_routes.py -q`
Expected: FAIL

- [ ] **Step 3: 添加 schema、route 和 `create_app` 注入**

```python
app.state.purchase_runtime_service = purchase_runtime_service
app.include_router(purchase_runtime_routes.router)
```

- [ ] **Step 4: 复跑路由测试，确认购买运行时 API 可用**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_routes.py -q`
Expected: PASS

## Chunk 4: 前端购买运行页

### Task 10: 先补 BackendClient 和 ViewModel/Controller

**Files:**
- Modify: `app_frontend/app/services/backend_client.py`
- Create: `app_frontend/app/viewmodels/purchase_runtime_vm.py`
- Create: `app_frontend/app/controllers/purchase_runtime_controller.py`
- Modify: `tests/frontend/test_backend_client.py`
- Create: `tests/frontend/test_purchase_runtime_vm.py`
- Create: `tests/frontend/test_purchase_runtime_controller.py`

- [ ] **Step 1: 写失败测试，定义购买运行时 API 调用和 ViewModel 格式化**

```python
async def test_backend_client_fetches_purchase_runtime_status(httpx_mock):
    payload = await client.get_purchase_runtime_status()
    assert payload["running"] is False


def test_purchase_runtime_vm_formats_summary_and_account_rows():
    vm.load_status(build_snapshot(active_account_count=2))
    assert vm.summary["active_account_count"] == "2"
```

- [ ] **Step 2: 运行客户端和 VM/Controller 测试，确认按“方法不存在”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend/test_backend_client.py tests/frontend/test_purchase_runtime_vm.py tests/frontend/test_purchase_runtime_controller.py -q`
Expected: FAIL

- [ ] **Step 3: 增加购买运行时 API 方法、ViewModel 映射和 Controller 动作**

```python
async def get_purchase_runtime_status(self) -> dict[str, Any]: ...
async def update_purchase_runtime_settings(self, payload: dict[str, Any]) -> dict[str, Any]: ...
```

- [ ] **Step 4: 复跑客户端和 VM/Controller 测试，确认前端数据层绿灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend/test_backend_client.py tests/frontend/test_purchase_runtime_vm.py tests/frontend/test_purchase_runtime_controller.py -q`
Expected: PASS

### Task 11: 增加购买运行页并接入工作台导航

**Files:**
- Create: `app_frontend/app/widgets/purchase_runtime_panel.py`
- Create: `app_frontend/app/windows/purchase_runtime_window.py`
- Modify: `app_frontend/app/windows/workspace_window.py`
- Modify: `app_frontend/main.py`
- Create: `tests/frontend/test_purchase_runtime_panel.py`
- Create: `tests/frontend/test_purchase_runtime_window.py`
- Modify: `tests/frontend/test_workspace_window.py`

- [ ] **Step 1: 写失败测试，定义购买页导航和运行页展示**

```python
def test_workspace_window_exposes_purchase_page(qtbot):
    window = build_workspace_window()
    assert window.purchase_runtime_button.text() == "购买运行"


def test_purchase_runtime_window_submits_settings_and_refreshes_runtime(qtbot):
    window = build_purchase_window()
    window.query_only_checkbox.setChecked(True)
    window._save_settings()
    assert window.status_label.text() == "设置已保存"
```

- [ ] **Step 2: 运行购买页前端测试，确认按“页面不存在”失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend/test_purchase_runtime_panel.py tests/frontend/test_purchase_runtime_window.py tests/frontend/test_workspace_window.py -q`
Expected: FAIL

- [ ] **Step 3: 新增购买运行页，包含摘要、白名单、事件、账户池列表**

```python
class PurchaseRuntimeWindow(QWidget):
    def __init__(..., view_model, controller, ...):
        self.query_only_checkbox = QCheckBox("仅查询模式")
        self.start_button = QPushButton("启动购买")
        self.stop_button = QPushButton("停止购买")
```

- [ ] **Step 4: 复跑购买页前端测试，确认工作台导航和运行页可用**

Run: `.\.venv\Scripts\python.exe -m pytest tests/frontend/test_purchase_runtime_panel.py tests/frontend/test_purchase_runtime_window.py tests/frontend/test_workspace_window.py -q`
Expected: PASS

## Chunk 5: 联调与回归

### Task 12: 建立购买运行时后端回归与查询联动验收

**Files:**
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_query_purchase_bridge.py`
- Modify: `tests/frontend/test_purchase_runtime_window.py`

- [ ] **Step 1: 增加集成测试，覆盖“启动购买 -> 接收命中 -> 入池/移池 -> GUI 刷新”主链路**

```python
async def test_purchase_runtime_end_to_end_handles_hit_and_inventory_pause(client, app):
    await client.post("/purchase-runtime/start")
    app.state.purchase_runtime_service.accept_query_hit(build_hit())
    snapshot = await client.get("/purchase-runtime/status")
    assert snapshot.json()["recent_events"][0]["status"] in {"queued", "success", "paused_no_inventory"}
```

- [ ] **Step 2: 运行购买模块后端集成测试，确认首次联调暴露缺口**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_query_purchase_bridge.py -q`
Expected: FAIL 至少一项，暴露联调缺口

- [ ] **Step 3: 补齐 snapshot 聚合、状态联动和前端刷新缺口**

```python
snapshot = {
    "running": True,
    "queue_size": scheduler.queue_size(),
    "active_account_count": scheduler.active_account_count(),
    "recent_events": self._recent_events.to_list(),
}
```

- [ ] **Step 4: 跑购买模块完整回归集**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_settings_repository.py tests/backend/test_account_inventory_snapshot_repository.py tests/backend/test_purchase_hit_inbox.py tests/backend/test_inventory_state.py tests/backend/test_purchase_scheduler.py tests/backend/test_account_purchase_worker_runtime.py tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_query_purchase_bridge.py tests/frontend/test_backend_client.py tests/frontend/test_purchase_runtime_vm.py tests/frontend/test_purchase_runtime_controller.py tests/frontend/test_purchase_runtime_panel.py tests/frontend/test_purchase_runtime_window.py tests/frontend/test_workspace_window.py tests/frontend/test_account_detail_panel.py -q`
Expected: PASS

## 执行提示

- 查询模块已有命中事件结构，不要重新发明购买批次格式，优先直接复用现有字段
- 库存快照与账号业务上强绑定，但不要污染 `accounts` 主表
- 购买能力和购买池状态必须继续分离
- 库存逻辑以 legacy 实际行为为准：
  - 初始化刷新一次快照
  - 选择剩余容量更小但仍满足阈值的目标仓库
  - 买后本地递推
  - 本地耗尽后再远端确认
- `selected_steam_id` 不是展示字段，而是当前目标仓库标识
  - 必须由库存状态机维护
  - 必须被账户工作者传给执行网关
  - 必须映射到 legacy 下单请求中的 `receiveSteamId`
- 用户明确要求：不要做 git 提交；实现完成后用测试和文档说明代替
