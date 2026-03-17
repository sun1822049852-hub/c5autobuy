# Query Runtime Preparation Detail Refresh Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在启动查询前增加一个准备步骤，自动按 12 小时阈值刷新商品详情，并允许手动重刷，且刷新与新增商品共用同一份账号轮询进度。

**Architecture:** 后端新增一个独立的商品详情预刷新服务和 `/query-runtime/prepare` 接口，专门负责筛选、刷新和汇总结果；现有 `/query-runtime/start` 保持纯启动。前端新增一个启动前准备对话框，点击“启动查询”时先打开该对话框，自动执行一次预刷新，用户确认后再真正启动查询。

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, PySide6, httpx, pytest

---

## Chunk 1: 后端刷新服务

### Task 1: 为“12 小时阈值筛选 + 详情更新”先写失败测试

**Files:**
- Create: `tests/backend/test_query_item_detail_refresh_service.py`
- Modify: `app_backend/infrastructure/repositories/query_config_repository.py`
- Modify: `app_backend/domain/models/query_config.py`

- [ ] **Step 1: 写失败测试，锁定 stale 判断规则**

```python
def test_refresh_service_marks_items_without_sync_time_or_older_than_12_hours_as_stale():
    ...
    assert summary["updated_count"] == 2
    assert summary["skipped_count"] == 1
```

- [ ] **Step 2: 写失败测试，锁定 `force_refresh=True` 会刷新全部商品**

```python
def test_refresh_service_force_refresh_updates_all_items():
    ...
```

- [ ] **Step 3: 写失败测试，锁定刷新不会覆盖用户阈值字段**

```python
def test_refresh_service_updates_detail_fields_without_overwriting_user_thresholds():
    ...
    assert item.max_wear == 0.25
    assert item.max_price == 199.0
```

- [ ] **Step 4: 跑测试确认先失败**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_item_detail_refresh_service.py" -v`

Expected: FAIL，因为刷新服务和详情更新 repository 方法还不存在。

### Task 2: 写最小后端刷新实现

**Files:**
- Create: `app_backend/application/use_cases/prepare_query_runtime.py`
- Create: `app_backend/infrastructure/query/refresh/query_item_detail_refresh_service.py`
- Modify: `app_backend/infrastructure/repositories/query_config_repository.py`

- [ ] **Step 1: 新增 repository 的详情更新方法**

```python
def update_item_detail(
    self,
    query_item_id: str,
    *,
    item_name: str | None,
    market_hash_name: str | None,
    min_wear: float | None,
    last_market_price: float | None,
    last_detail_sync_at: str,
) -> QueryItem:
    ...
```

- [ ] **Step 2: 实现刷新服务的 stale 判断和批量刷新**

```python
class QueryItemDetailRefreshService:
    def prepare(self, *, config_id: str, force_refresh: bool = False) -> dict[str, object]:
        ...
```

- [ ] **Step 3: 让刷新服务复用注入进来的 `ProductDetailCollector`**

```python
detail = await self._collector.fetch_detail(...)
```

- [ ] **Step 4: 跑服务测试确认转绿**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_item_detail_refresh_service.py" -v`

Expected: PASS

### Task 3: 补共享轮询进度的回归测试

**Files:**
- Modify: `tests/backend/test_backend_main_entry.py`
- Modify: `app_backend/main.py`

- [ ] **Step 1: 写失败测试，锁定 prepare 服务与新增商品使用同一个 collector 实例**

```python
def test_create_app_wires_prepare_service_with_shared_product_detail_collector():
    app = create_app(...)
    assert app.state.query_item_detail_refresh_service._collector is app.state.product_detail_collector
```

- [ ] **Step 2: 跑单测确认先失败**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_backend_main_entry.py::test_create_app_wires_prepare_service_with_shared_product_detail_collector" -v`

Expected: FAIL，因为主入口还没注入刷新服务。

- [ ] **Step 3: 在 `create_app()` 注入刷新服务，并复用已有 collector**

```python
query_item_detail_refresh_service = QueryItemDetailRefreshService(
    repository=query_config_repository,
    collector=product_detail_collector,
)
```

- [ ] **Step 4: 跑主入口测试确认转绿**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_backend_main_entry.py" -v`

Expected: PASS

## Chunk 2: 后端准备接口

### Task 4: 为 `/query-runtime/prepare` 写失败测试

**Files:**
- Modify: `app_backend/api/schemas/query_runtime.py`
- Modify: `app_backend/api/routes/query_runtime.py`
- Modify: `tests/backend/test_query_runtime_routes.py`

- [ ] **Step 1: 写失败测试，锁定 prepare 接口返回刷新摘要**

```python
async def test_prepare_query_runtime_returns_refresh_summary(client, app):
    ...
    assert response.json()["updated_count"] == 1
    assert response.json()["items"][0]["status"] == "updated"
```

- [ ] **Step 2: 写失败测试，锁定配置不存在时返回 404**

```python
async def test_prepare_query_runtime_returns_404_for_missing_config(client):
    ...
```

- [ ] **Step 3: 跑路由测试确认先失败**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_runtime_routes.py" -v`

Expected: FAIL，因为接口和 schema 还没接上。

### Task 5: 接上 prepare 路由和 use case

**Files:**
- Modify: `app_backend/api/schemas/query_runtime.py`
- Modify: `app_backend/api/routes/query_runtime.py`
- Modify: `app_backend/main.py`

- [ ] **Step 1: 增加 prepare request/response schema**

```python
class QueryRuntimePrepareRequest(BaseModel):
    config_id: str
    force_refresh: bool = False
```

- [ ] **Step 2: 在路由里新增 `POST /query-runtime/prepare`**

```python
@router.post("/prepare", response_model=QueryRuntimePrepareResponse)
async def prepare_query_runtime(...):
    ...
```

- [ ] **Step 3: 主入口把刷新服务挂到 `app.state`**

```python
app.state.query_item_detail_refresh_service = query_item_detail_refresh_service
```

- [ ] **Step 4: 跑路由测试确认转绿**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_runtime_routes.py" -v`

Expected: PASS

## Chunk 3: 前端准备对话框

### Task 6: 为前端客户端和准备对话框写失败测试

**Files:**
- Create: `app_frontend/app/dialogs/query_runtime_prepare_dialog.py`
- Modify: `app_frontend/app/services/backend_client.py`
- Modify: `tests/frontend/test_backend_client.py`
- Create: `tests/frontend/test_query_runtime_prepare_dialog.py`

- [ ] **Step 1: 写 backend client 的失败测试**

```python
async def test_backend_client_prepares_query_runtime(backend_client):
    ...
    prepared = await client.prepare_query_runtime(created["config_id"])
    assert prepared["threshold_hours"] == 12
```

- [ ] **Step 2: 写准备对话框的失败测试，锁定自动刷新和手动重刷**

```python
def test_prepare_dialog_auto_refreshes_on_open_and_can_force_refresh(qtbot):
    ...
```

- [ ] **Step 3: 跑前端相关测试确认先失败**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/frontend/test_backend_client.py" "tests/frontend/test_query_runtime_prepare_dialog.py" -v`

Expected: FAIL，因为 client 方法和对话框都不存在。

### Task 7: 实现准备对话框并接进窗口

**Files:**
- Create: `app_frontend/app/dialogs/query_runtime_prepare_dialog.py`
- Modify: `app_frontend/app/windows/query_system_window.py`
- Modify: `tests/frontend/test_query_system_window.py`

- [ ] **Step 1: 给 `BackendClient` 增加 `prepare_query_runtime()`**

```python
async def prepare_query_runtime(self, config_id: str, *, force_refresh: bool = False) -> dict[str, Any]:
    ...
```

- [ ] **Step 2: 实现准备对话框**

```python
class QueryRuntimePrepareDialog(QDialog):
    ...
```

- [ ] **Step 3: 修改 `QuerySystemWindow._start_runtime()`**

```python
def _start_runtime(self) -> None:
    dialog = self.prepare_runtime_dialog_factory(...)
    if dialog.exec() == int(QDialog.DialogCode.Accepted):
        self.controller.start_runtime_for_selected()
```

- [ ] **Step 4: 跑窗口和对话框测试确认转绿**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/frontend/test_query_runtime_prepare_dialog.py" "tests/frontend/test_query_system_window.py" -v`

Expected: PASS

## Chunk 4: 全量验证

### Task 8: 跑相关测试集和全量测试

**Files:**
- Modify: `README.md`（只有确实需要补充当前进度时才改）

- [ ] **Step 1: 跑后端相关测试**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_item_detail_refresh_service.py" "tests/backend/test_query_runtime_routes.py" "tests/backend/test_backend_main_entry.py" -v`

Expected: PASS

- [ ] **Step 2: 跑前端相关测试**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/frontend/test_backend_client.py" "tests/frontend/test_query_runtime_prepare_dialog.py" "tests/frontend/test_query_system_window.py" -v`

Expected: PASS

- [ ] **Step 3: 跑后端全量**

Run: `& ".venv/Scripts/python.exe" -m pytest tests/backend -q`

Expected: PASS

- [ ] **Step 4: 跑全量测试**

Run: `& ".venv/Scripts/python.exe" -m pytest -q`

Expected: PASS

- [ ] **Step 5: 不执行 git 操作**

Reason: 用户明确要求不要默认计划和执行 `git commit` / 分支相关动作。
