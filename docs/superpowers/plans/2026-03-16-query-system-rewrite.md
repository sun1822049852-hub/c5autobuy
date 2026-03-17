# 查询系统重写 Implementation Plan

> **For agentic workers:** REQUIRED: Use `@superpowers:executing-plans` to implement this plan in this harness. Before claiming success, run `@superpowers:verification-before-completion`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有账号中心基础上，重写查询配置管理、三模式查询运行时和查询 GUI，同时保留原业务规则并清晰分层。

**Architecture:** 后端继续使用 `FastAPI + SQLAlchemy + SQLite`，扩展账号中心数据模型并新增查询配置/运行时模块。前端继续使用 `PySide6`，新增查询系统工作区，并通过统一的 `BackendClient` 调用后端接口。查询运行时采用“一套任务外壳 + 三个模式 runner”的结构，三种模式独立维护时间窗口、冷却与随机延迟。

**Tech Stack:** `FastAPI`, `Pydantic`, `SQLAlchemy`, `SQLite`, `httpx`, `PySide6`, `pytest`

**Implementation notes:**
- 不复用 legacy 查询运行时作为主执行入口，只把旧代码当业务参考。
- Git commit 步骤按用户偏好省略，不在本计划中安排。
- 当前 harness 没有可用的计划审稿 subagent，本计划采用人工校验路径。

---

## File Structure

### Existing files to modify

- `app_backend/infrastructure/db/models.py`
  - 增加查询配置、商品、模式配置、账号查询模式设置表。
- `app_backend/domain/models/account.py`
  - 为账号领域模型增加三种查询模式全局开关字段。
- `app_backend/infrastructure/repositories/account_repository.py`
  - 读写账号的查询模式全局开关。
- `app_backend/api/schemas/accounts.py`
  - 暴露账号查询模式开关字段与更新请求模型。
- `app_backend/api/routes/accounts.py`
  - 增加账号查询模式开关更新接口。
- `app_backend/application/use_cases/create_account.py`
  - 新账号默认初始化查询模式全局开关。
- `app_backend/application/use_cases/update_account.py`
  - 只保留账号基础字段更新，避免把查询运行参数混入账号编辑。
- `app_backend/main.py`
  - 注册查询配置仓库、商品采集服务、查询运行时服务。
- `app_frontend/app/services/backend_client.py`
  - 增加查询配置、商品、运行时相关 HTTP / WS 客户端方法。
- `app_frontend/app/windows/account_center_window.py`
  - 增加跳转查询系统工作区的入口，或被新的工作台窗口复用。
- `app_frontend/main.py`
  - 改为启动工作台主窗口，而不是只启动账号中心窗口。

### Backend files to create

- `app_backend/domain/enums/query_modes.py`
  - 三种查询模式常量与校验。
- `app_backend/domain/models/query_config.py`
  - `QueryConfig`、`QueryItem`、`QueryModeSetting` 领域模型。
- `app_backend/domain/models/query_runtime.py`
  - `QueryTaskStatus`、`QueryModeStatus`、`QueryTaskSnapshot` 领域模型。
- `app_backend/application/use_cases/list_query_configs.py`
- `app_backend/application/use_cases/create_query_config.py`
- `app_backend/application/use_cases/get_query_config.py`
- `app_backend/application/use_cases/update_query_config.py`
- `app_backend/application/use_cases/delete_query_config.py`
- `app_backend/application/use_cases/add_query_item.py`
- `app_backend/application/use_cases/update_query_item.py`
- `app_backend/application/use_cases/delete_query_item.py`
- `app_backend/application/use_cases/update_query_mode_setting.py`
- `app_backend/application/use_cases/update_account_query_modes.py`
- `app_backend/application/use_cases/start_query_runtime.py`
- `app_backend/application/use_cases/stop_query_runtime.py`
- `app_backend/application/use_cases/get_query_runtime_status.py`
- `app_backend/application/use_cases/parse_query_item_url.py`
- `app_backend/application/use_cases/fetch_query_item_detail.py`
- `app_backend/infrastructure/repositories/query_config_repository.py`
  - 查询配置、商品、模式设置的集中读写。
- `app_backend/infrastructure/query/collectors/product_url_parser.py`
  - URL 解析、`item_id` 提取。
- `app_backend/infrastructure/query/collectors/product_detail_collector.py`
  - 商品详情、磨损、市场名称采集。
- `app_backend/infrastructure/query/clients/new_api_client.py`
- `app_backend/infrastructure/query/clients/fast_api_client.py`
- `app_backend/infrastructure/query/clients/token_query_client.py`
- `app_backend/infrastructure/query/executors/new_api_executor.py`
- `app_backend/infrastructure/query/executors/fast_api_executor.py`
- `app_backend/infrastructure/query/executors/token_executor.py`
- `app_backend/infrastructure/query/runtime/window_scheduler.py`
  - 时间窗口计算、下一次执行时间计算。
- `app_backend/infrastructure/query/runtime/mode_runner.py`
  - 模式运行器基类。
- `app_backend/infrastructure/query/runtime/query_task_runtime.py`
  - 单任务运行时外壳。
- `app_backend/infrastructure/query/runtime/query_runtime_service.py`
  - 单例运行控制与状态汇总。
- `app_backend/api/schemas/query_configs.py`
- `app_backend/api/schemas/query_runtime.py`
- `app_backend/api/routes/query_configs.py`
- `app_backend/api/routes/query_runtime.py`
- `app_backend/api/websocket/query_runtime.py`

### Frontend files to create

- `app_frontend/app/windows/workspace_window.py`
  - 工作台主窗口，承载账号中心与查询系统两个工作区。
- `app_frontend/app/windows/query_system_window.py`
  - 查询系统页面壳子。
- `app_frontend/app/controllers/query_system_controller.py`
  - 查询系统控制器。
- `app_frontend/app/viewmodels/query_system_vm.py`
  - 查询系统视图模型。
- `app_frontend/app/widgets/query_config_list.py`
- `app_frontend/app/widgets/query_config_detail_panel.py`
- `app_frontend/app/widgets/query_runtime_panel.py`
- `app_frontend/app/dialogs/query_config_dialog.py`
- `app_frontend/app/dialogs/query_item_dialog.py`
- `app_frontend/app/dialogs/query_mode_settings_dialog.py`
- `app_frontend/app/formatters/query_runtime_display.py`

### Tests to create

- `tests/backend/test_account_query_mode_settings.py`
- `tests/backend/test_query_config_repository.py`
- `tests/backend/test_query_config_routes.py`
- `tests/backend/test_query_item_collectors.py`
- `tests/backend/test_query_runtime_service.py`
- `tests/backend/test_query_runtime_routes.py`
- `tests/backend/test_window_scheduler.py`
- `tests/frontend/test_query_system_vm.py`
- `tests/frontend/test_query_system_controller.py`
- `tests/frontend/test_query_system_window.py`
- `tests/frontend/test_query_runtime_panel.py`
- `tests/frontend/test_workspace_window.py`

## Chunk 1: Account-Side Query Mode Controls

### Task 1: Extend account storage with global query mode switches

**Files:**
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/domain/models/account.py`
- Modify: `app_backend/infrastructure/repositories/account_repository.py`
- Modify: `app_backend/application/use_cases/create_account.py`
- Test: `tests/backend/test_account_query_mode_settings.py`
- Test: `tests/backend/test_account_repository.py`

- [ ] **Step 1: Write the failing repository/domain tests**

```python
def test_create_account_initializes_query_mode_flags(repository):
    account = repository.create_account(...)
    assert account.new_api_enabled is True
    assert account.fast_api_enabled is True
    assert account.token_enabled is True
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_account_query_mode_settings.py tests/backend/test_account_repository.py -q`

Expected: FAIL with missing columns or missing account attributes.

- [ ] **Step 3: Implement the storage and domain changes**

```python
class AccountRecord(Base):
    new_api_enabled = mapped_column(Integer, nullable=False, default=1)
    fast_api_enabled = mapped_column(Integer, nullable=False, default=1)
    token_enabled = mapped_column(Integer, nullable=False, default=1)
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_account_query_mode_settings.py tests/backend/test_account_repository.py -q`

Expected: PASS.

- [ ] **Step 5: Run neighboring regressions**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_account_domain.py tests/backend/test_account_routes.py -q`

Expected: PASS with no account-center regression.

### Task 2: Add account query mode preference update use case and API

**Files:**
- Create: `app_backend/application/use_cases/update_account_query_modes.py`
- Modify: `app_backend/api/schemas/accounts.py`
- Modify: `app_backend/api/routes/accounts.py`
- Modify: `app_backend/infrastructure/repositories/account_repository.py`
- Test: `tests/backend/test_account_query_mode_settings.py`
- Test: `tests/backend/test_account_routes.py`

- [ ] **Step 1: Write failing use case / route tests**

```python
def test_patch_account_query_modes_updates_global_flags(client):
    response = client.patch(
        "/accounts/<account_id>/query-modes",
        json={"new_api_enabled": False, "fast_api_enabled": True, "token_enabled": False},
    )
    assert response.status_code == 200
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_account_query_mode_settings.py tests/backend/test_account_routes.py -q`

Expected: FAIL with missing endpoint or response fields.

- [ ] **Step 3: Implement preference update flow**

```python
return self._repository.update_account(
    account_id,
    new_api_enabled=payload.new_api_enabled,
    fast_api_enabled=payload.fast_api_enabled,
    token_enabled=payload.token_enabled,
)
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_account_query_mode_settings.py tests/backend/test_account_routes.py -q`

Expected: PASS.

- [ ] **Step 5: Smoke-test account-center backend**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_account_center_smoke.py -q`

Expected: PASS.

## Chunk 2: Query Config Domain and CRUD

### Task 3: Add query config / item / mode setting domain models and repository

**Files:**
- Create: `app_backend/domain/enums/query_modes.py`
- Create: `app_backend/domain/models/query_config.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Create: `app_backend/infrastructure/repositories/query_config_repository.py`
- Test: `tests/backend/test_query_config_repository.py`

- [ ] **Step 1: Write failing repository tests**

```python
def test_create_query_config_persists_three_mode_settings(repository):
    config = repository.create_config(name="test")
    assert {mode.mode_type for mode in config.mode_settings} == {"new_api", "fast_api", "token"}
```

- [ ] **Step 2: Run the targeted test and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_repository.py -q`

Expected: FAIL with missing repository or tables.

- [ ] **Step 3: Implement domain models, SQLAlchemy records, and repository**

```python
@dataclass(slots=True)
class QueryModeSetting:
    mode_type: str
    enabled: bool
    window_enabled: bool
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
```

- [ ] **Step 4: Re-run the targeted test**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_repository.py -q`

Expected: PASS.

- [ ] **Step 5: Verify schema bootstrap still works**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_backend_main_entry.py tests/backend/test_backend_health.py -q`

Expected: PASS.

### Task 4: Add query config CRUD and mode-setting HTTP APIs

**Files:**
- Create: `app_backend/application/use_cases/list_query_configs.py`
- Create: `app_backend/application/use_cases/create_query_config.py`
- Create: `app_backend/application/use_cases/get_query_config.py`
- Create: `app_backend/application/use_cases/update_query_config.py`
- Create: `app_backend/application/use_cases/delete_query_config.py`
- Create: `app_backend/application/use_cases/update_query_mode_setting.py`
- Create: `app_backend/api/schemas/query_configs.py`
- Create: `app_backend/api/routes/query_configs.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_query_config_routes.py`

- [ ] **Step 1: Write failing route tests**

```python
def test_create_query_config_returns_three_modes(client):
    response = client.post("/query-configs", json={"name": "日间配置", "description": ""})
    payload = response.json()
    assert response.status_code == 201
    assert len(payload["mode_settings"]) == 3
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_routes.py -q`

Expected: FAIL with missing router or schema.

- [ ] **Step 3: Implement use cases, schemas, and routes**

```python
router = APIRouter(prefix="/query-configs", tags=["query-configs"])
router.patch("/{config_id}/modes/{mode_type}", ...)
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_routes.py -q`

Expected: PASS.

- [ ] **Step 5: Re-run backend entry smoke tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_backend_main_entry.py tests/backend/test_backend_health.py -q`

Expected: PASS.

## Chunk 3: Product URL Parsing and Detail Collection

### Task 5: Build product URL parser and detail collector

**Files:**
- Create: `app_backend/infrastructure/query/collectors/product_url_parser.py`
- Create: `app_backend/infrastructure/query/collectors/product_detail_collector.py`
- Create: `app_backend/application/use_cases/parse_query_item_url.py`
- Create: `app_backend/application/use_cases/fetch_query_item_detail.py`
- Test: `tests/backend/test_query_item_collectors.py`

- [ ] **Step 1: Write failing collector tests**

```python
def test_parse_c5_product_url_extracts_external_item_id():
    result = ProductUrlParser().parse("https://www.c5game.com/csgo/730/.../123456")
    assert result.external_item_id == "123456"
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_item_collectors.py -q`

Expected: FAIL with missing parser/collector modules.

- [ ] **Step 3: Implement parser and collector contracts**

```python
class ProductUrlParseResult(BaseModel):
    product_url: str
    external_item_id: str
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_item_collectors.py -q`

Expected: PASS.

- [ ] **Step 5: Add one regression test for malformed URLs**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_item_collectors.py -q`

Expected: PASS with invalid URL rejection covered.

### Task 6: Wire query item add/update/delete and parse/detail endpoints

**Files:**
- Create: `app_backend/application/use_cases/add_query_item.py`
- Create: `app_backend/application/use_cases/update_query_item.py`
- Create: `app_backend/application/use_cases/delete_query_item.py`
- Modify: `app_backend/api/schemas/query_configs.py`
- Modify: `app_backend/api/routes/query_configs.py`
- Test: `tests/backend/test_query_config_routes.py`

- [ ] **Step 1: Write failing item workflow tests**

```python
def test_add_query_item_uses_parser_and_persists_thresholds(client, fake_collectors):
    response = client.post(
        "/query-configs/config-1/items",
        json={"product_url": "https://...", "max_wear": 0.12, "max_price": 99.5},
    )
    assert response.status_code == 201
    assert response.json()["external_item_id"] == "123456"
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_routes.py -q`

Expected: FAIL with missing item endpoints or payload fields.

- [ ] **Step 3: Implement item use cases and route handlers**

```python
payload = collector.fetch(...)
item = repository.add_item(
    config_id=config_id,
    external_item_id=parsed.external_item_id,
    market_hash_name=payload.market_hash_name,
    ...
)
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_routes.py -q`

Expected: PASS.

- [ ] **Step 5: Run full backend config slice**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_repository.py tests/backend/test_query_config_routes.py tests/backend/test_query_item_collectors.py -q`

Expected: PASS.

## Chunk 4: Query Runtime Core

### Task 7: Implement window scheduler utilities and runtime status models

**Files:**
- Create: `app_backend/domain/models/query_runtime.py`
- Create: `app_backend/infrastructure/query/runtime/window_scheduler.py`
- Test: `tests/backend/test_window_scheduler.py`

- [ ] **Step 1: Write failing scheduler tests**

```python
def test_same_day_window_returns_wait_until_start():
    scheduler = WindowScheduler(...)
    next_state = scheduler.compute(now=datetime(...))
    assert next_state.in_window is False
    assert next_state.next_run_at is not None
```

- [ ] **Step 2: Run the targeted test and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_window_scheduler.py -q`

Expected: FAIL with missing scheduler implementation.

- [ ] **Step 3: Implement time-window and cooldown calculation helpers**

```python
def compute_next_delay(base_range, random_delay_enabled, random_range):
    ...
```

- [ ] **Step 4: Re-run the targeted test**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_window_scheduler.py -q`

Expected: PASS.

- [ ] **Step 5: Add cross-day window coverage**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_window_scheduler.py -q`

Expected: PASS with same-day / cross-day / full-day cases covered.

### Task 8: Build QueryTaskRuntime shell and in-memory runtime service

**Files:**
- Create: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Create: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Create: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Create: `app_backend/application/use_cases/start_query_runtime.py`
- Create: `app_backend/application/use_cases/stop_query_runtime.py`
- Create: `app_backend/application/use_cases/get_query_runtime_status.py`
- Test: `tests/backend/test_query_runtime_service.py`

- [ ] **Step 1: Write failing runtime-service tests**

```python
def test_runtime_service_rejects_second_running_task(service, config_repo):
    assert service.start(config_id="cfg-1").ok is True
    assert service.start(config_id="cfg-2").ok is False
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_runtime_service.py -q`

Expected: FAIL with missing runtime service.

- [ ] **Step 3: Implement runtime shell and status snapshot flow**

```python
class QueryRuntimeService:
    def start(self, config_id: str) -> tuple[bool, str]:
        if self._running_task is not None:
            return False, "已有查询任务在运行"
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_runtime_service.py -q`

Expected: PASS.

- [ ] **Step 5: Verify stop / restart transitions**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_runtime_service.py -q`

Expected: PASS with start-stop-start lifecycle covered.

### Task 9: Implement `new_api` and `fast_api` mode executors and runners

**Files:**
- Create: `app_backend/infrastructure/query/clients/new_api_client.py`
- Create: `app_backend/infrastructure/query/clients/fast_api_client.py`
- Create: `app_backend/infrastructure/query/executors/new_api_executor.py`
- Create: `app_backend/infrastructure/query/executors/fast_api_executor.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Test: `tests/backend/test_query_runtime_service.py`

- [ ] **Step 1: Write failing API-mode runner tests**

```python
def test_runtime_filters_accounts_without_api_key(runtime, seeded_accounts):
    snapshot = runtime.start(config_id="cfg-api")
    assert snapshot.modes["new_api"].eligible_account_count == 1
    assert snapshot.modes["fast_api"].eligible_account_count == 1
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_runtime_service.py -q`

Expected: FAIL with empty mode runner behavior.

- [ ] **Step 3: Implement API-mode clients, executors, and runner wiring**

```python
eligible_accounts = [
    account for account in accounts
    if account.api_key and account.new_api_enabled
]
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_runtime_service.py -q`

Expected: PASS.

- [ ] **Step 5: Add isolated executor tests if client signing logic grows**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_runtime_service.py -q`

Expected: PASS with API-mode coverage expanded.

### Task 10: Implement `token` mode executor and complete runtime APIs

**Files:**
- Create: `app_backend/infrastructure/query/clients/token_query_client.py`
- Create: `app_backend/infrastructure/query/executors/token_executor.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Create: `app_backend/api/schemas/query_runtime.py`
- Create: `app_backend/api/routes/query_runtime.py`
- Create: `app_backend/api/websocket/query_runtime.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_query_runtime_routes.py`

- [ ] **Step 1: Write failing token-mode and route tests**

```python
def test_runtime_status_reports_token_mode_account_count(client, seeded_runtime):
    payload = client.get("/query-runtime/status").json()
    assert payload["modes"]["token"]["eligible_account_count"] == 1
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_runtime_routes.py -q`

Expected: FAIL with missing runtime route schema or token-mode stats.

- [ ] **Step 3: Implement token-mode executor, routes, and websocket snapshot publishing**

```python
router.post("/query-runtime/start")
router.post("/query-runtime/stop")
router.get("/query-runtime/status")
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_runtime_routes.py tests/backend/test_query_runtime_service.py -q`

Expected: PASS.

- [ ] **Step 5: Run full backend query slice**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_account_query_mode_settings.py tests/backend/test_query_config_routes.py tests/backend/test_query_item_collectors.py tests/backend/test_window_scheduler.py tests/backend/test_query_runtime_service.py tests/backend/test_query_runtime_routes.py -q`

Expected: PASS.

## Chunk 5: Frontend Integration

### Task 11: Extend BackendClient and add frontend-facing query-system contracts

**Files:**
- Modify: `app_frontend/app/services/backend_client.py`
- Test: `tests/frontend/test_backend_client.py`

- [ ] **Step 1: Write failing BackendClient tests**

```python
async def test_backend_client_lists_query_configs(fake_http_client):
    payload = await client.list_query_configs()
    assert payload[0]["name"] == "白天配置"
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_backend_client.py -q`

Expected: FAIL with missing client methods.

- [ ] **Step 3: Implement query-config and runtime client methods**

```python
async def start_query_runtime(self, config_id: str) -> dict[str, Any]:
    response = await http_client.post("/query-runtime/start", json={"config_id": config_id})
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_backend_client.py -q`

Expected: PASS.

- [ ] **Step 5: Run local backend server regression**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_local_backend_server.py -q`

Expected: PASS.

### Task 12: Add query-system view model, controller, and widgets

**Files:**
- Create: `app_frontend/app/viewmodels/query_system_vm.py`
- Create: `app_frontend/app/controllers/query_system_controller.py`
- Create: `app_frontend/app/widgets/query_config_list.py`
- Create: `app_frontend/app/widgets/query_config_detail_panel.py`
- Create: `app_frontend/app/dialogs/query_config_dialog.py`
- Create: `app_frontend/app/dialogs/query_item_dialog.py`
- Create: `app_frontend/app/dialogs/query_mode_settings_dialog.py`
- Create: `app_frontend/app/windows/query_system_window.py`
- Test: `tests/frontend/test_query_system_vm.py`
- Test: `tests/frontend/test_query_system_controller.py`
- Test: `tests/frontend/test_query_system_window.py`

- [ ] **Step 1: Write failing VM/controller tests**

```python
def test_query_system_vm_opens_selected_config_detail():
    vm = QuerySystemViewModel()
    vm.set_configs([...])
    vm.select_config("cfg-1")
    assert vm.detail_config.config_id == "cfg-1"
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_query_system_vm.py tests/frontend/test_query_system_controller.py tests/frontend/test_query_system_window.py -q`

Expected: FAIL with missing modules and widgets.

- [ ] **Step 3: Implement VM/controller/widget layer**

```python
class QuerySystemController:
    def load_configs(self) -> None:
        self.task_runner.submit(self._load_configs())
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_query_system_vm.py tests/frontend/test_query_system_controller.py tests/frontend/test_query_system_window.py -q`

Expected: PASS.

- [ ] **Step 5: Add visual regression coverage for mode-parameter editing**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_query_system_window.py -q`

Expected: PASS with dialogs and panel bindings covered.

### Task 13: Add runtime panel, workspace shell, and account-center integration

**Files:**
- Create: `app_frontend/app/widgets/query_runtime_panel.py`
- Create: `app_frontend/app/formatters/query_runtime_display.py`
- Create: `app_frontend/app/windows/workspace_window.py`
- Modify: `app_frontend/app/windows/account_center_window.py`
- Modify: `app_frontend/main.py`
- Test: `tests/frontend/test_query_runtime_panel.py`
- Test: `tests/frontend/test_workspace_window.py`
- Test: `tests/frontend/test_account_detail_panel.py`

- [ ] **Step 1: Write failing shell / runtime-panel tests**

```python
def test_workspace_window_switches_between_account_and_query_pages(qtbot):
    window = WorkspaceWindow(...)
    window.show_query_system()
    assert window.current_page_name() == "query"
```

- [ ] **Step 2: Run the targeted tests and verify failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_query_runtime_panel.py tests/frontend/test_workspace_window.py tests/frontend/test_account_detail_panel.py -q`

Expected: FAIL with missing workspace shell or query switches.

- [ ] **Step 3: Implement runtime panel, workspace shell, and account query-mode toggles**

```python
self.account_query_mode_group = QGroupBox("查询模式")
self.query_system_button = QPushButton("查询系统")
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_query_runtime_panel.py tests/frontend/test_workspace_window.py tests/frontend/test_account_detail_panel.py -q`

Expected: PASS.

- [ ] **Step 5: Run the full frontend slice**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_backend_client.py tests/frontend/test_query_system_vm.py tests/frontend/test_query_system_controller.py tests/frontend/test_query_system_window.py tests/frontend/test_query_runtime_panel.py tests/frontend/test_workspace_window.py tests/frontend/test_account_center_controller.py tests/frontend/test_account_center_window_status.py -q`

Expected: PASS.

## Chunk 6: End-to-End Verification

### Task 14: Verify the full query-system rewrite slice before handoff

**Files:**
- Modify: `docs/superpowers/specs/2026-03-16-query-system-rewrite-design.md` only if implementation drift requires a doc update
- Test: `tests/backend/*.py`
- Test: `tests/frontend/*.py`

- [ ] **Step 1: Run backend query-system tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_account_query_mode_settings.py tests/backend/test_query_config_repository.py tests/backend/test_query_config_routes.py tests/backend/test_query_item_collectors.py tests/backend/test_window_scheduler.py tests/backend/test_query_runtime_service.py tests/backend/test_query_runtime_routes.py -q`

Expected: PASS.

- [ ] **Step 2: Run frontend query-system tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/frontend/test_backend_client.py tests/frontend/test_query_system_vm.py tests/frontend/test_query_system_controller.py tests/frontend/test_query_system_window.py tests/frontend/test_query_runtime_panel.py tests/frontend/test_workspace_window.py -q`

Expected: PASS.

- [ ] **Step 3: Run full regression suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`

Expected: PASS with only known warnings.

- [ ] **Step 4: Compile touched Python files**

Run: `./.venv/Scripts/python.exe -m py_compile app_backend/main.py app_backend/api/routes/query_configs.py app_backend/api/routes/query_runtime.py app_backend/infrastructure/query/runtime/query_task_runtime.py app_frontend/main.py app_frontend/app/windows/workspace_window.py app_frontend/app/windows/query_system_window.py`

Expected: no output.

- [ ] **Step 5: Manual desktop smoke**

Run: `./.venv/Scripts/python.exe -m app_frontend.main`

Expected:
- 能进入工作台
- 能看到账号中心与查询系统
- 能创建查询配置
- 能配置三模式参数
- 能启动并停止单个查询任务
- 能看到运行状态与日志

---

Plan complete and saved to `docs/superpowers/plans/2026-03-16-query-system-rewrite.md`. Ready to execute?
