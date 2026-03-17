# Query Item Natural Wear Range Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐查询商品“天然最大磨损”独立字段链路，保持 `max_wear` 继续表示用户阈值，并把完整磨损范围展示到后端接口和前端界面。

**Architecture:** 在查询商品模型、数据库记录、仓储、API schema 中新增 `detail_max_wear` 字段；新增商品与启动前刷新都写入该字段；前端详情表格和准备对话框读取该字段显示“完整磨损范围”，不改现有查询执行器对 `max_wear` 的使用。

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, PySide6, pytest

---

## Chunk 1: 后端字段链路

### Task 1: 先写后端失败测试

**Files:**
- Modify: `tests/backend/test_query_config_repository.py`
- Modify: `tests/backend/test_query_config_routes.py`
- Modify: `tests/backend/test_query_item_detail_refresh_service.py`

- [ ] **Step 1: 给 repository 测试补 `detail_max_wear` 断言**

```python
assert stored.items[0].detail_max_wear == 0.7
```

- [ ] **Step 2: 给新增商品路由测试补 `detail_max_wear` 断言**

```python
assert payload["detail_max_wear"] == 0.7
```

- [ ] **Step 3: 给刷新服务测试补 `detail_max_wear` 更新断言**

```python
assert item.detail_max_wear == 0.77
assert item.max_wear == 0.25
```

- [ ] **Step 4: 跑相关测试确认先失败**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_config_repository.py" "tests/backend/test_query_config_routes.py" "tests/backend/test_query_item_detail_refresh_service.py" -v`

Expected: FAIL，因为生产代码还没有 `detail_max_wear` 字段链路。

### Task 2: 实现后端 `detail_max_wear`

**Files:**
- Modify: `app_backend/domain/models/query_config.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/repositories/query_config_repository.py`
- Modify: `app_backend/api/schemas/query_configs.py`
- Modify: `app_backend/infrastructure/query/collectors/product_detail_collector.py`
- Modify: `app_backend/application/use_cases/add_query_item.py`
- Modify: `app_backend/infrastructure/query/refresh/query_item_detail_refresh_service.py`

- [ ] **Step 1: 在领域模型和数据库记录中新增 `detail_max_wear`**
- [ ] **Step 2: 调整 repository 的 `add_item` / `update_item_detail` / `_to_domain` 映射**
- [ ] **Step 3: 新增商品时把 collector 的天然 `max_wear` 写到 `detail_max_wear`**
- [ ] **Step 4: 刷新服务更新 `detail_max_wear`，不覆盖用户 `max_wear`**
- [ ] **Step 5: schema 返回 `detail_max_wear`**
- [ ] **Step 6: 跑后端相关测试确认转绿**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_config_repository.py" "tests/backend/test_query_config_routes.py" "tests/backend/test_query_item_detail_refresh_service.py" -v`

Expected: PASS

## Chunk 2: 前端展示

### Task 3: 先写前端失败测试

**Files:**
- Modify: `tests/frontend/test_query_runtime_prepare_dialog.py`
- Modify: `tests/frontend/test_query_system_window.py`

- [ ] **Step 1: 给准备对话框测试补完整磨损范围显示断言**

```python
assert dialog.item_table.item(0, 3).text() == "0.1 ~ 0.7"
```

- [ ] **Step 2: 给配置窗口测试补商品列表显示断言**

```python
assert window.detail_panel.item_table.item(0, 1).text() == "0.0 ~ 0.7"
assert window.detail_panel.item_table.item(0, 2).text() == "0.25"
```

- [ ] **Step 3: 跑前端相关测试确认先失败**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/frontend/test_query_runtime_prepare_dialog.py" "tests/frontend/test_query_system_window.py" -v`

Expected: FAIL，因为界面还没展示完整磨损范围。

### Task 4: 实现前端展示

**Files:**
- Modify: `app_frontend/app/widgets/query_config_detail_panel.py`
- Modify: `app_frontend/app/dialogs/query_runtime_prepare_dialog.py`

- [ ] **Step 1: 配置详情表增加“完整磨损范围”和“用户阈值”明确展示**
- [ ] **Step 2: 准备对话框增加“完整磨损范围”列**
- [ ] **Step 3: 跑前端相关测试确认转绿**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/frontend/test_query_runtime_prepare_dialog.py" "tests/frontend/test_query_system_window.py" -v`

Expected: PASS

## Chunk 3: 验证

### Task 5: 跑回归测试

**Files:**
- No file changes required

- [ ] **Step 1: 跑后端相关回归**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_config_repository.py" "tests/backend/test_query_config_routes.py" "tests/backend/test_query_item_detail_refresh_service.py" "tests/backend/test_query_runtime_routes.py" -v`

Expected: PASS

- [ ] **Step 2: 跑前端相关回归**

Run: `& ".venv/Scripts/python.exe" -m pytest "tests/frontend/test_query_runtime_prepare_dialog.py" "tests/frontend/test_query_system_window.py" -v`

Expected: PASS

- [ ] **Step 3: 跑全量测试**

Run: `& ".venv/Scripts/python.exe" -m pytest -q`

Expected: PASS

- [ ] **Step 4: 不执行 git 操作**

Reason: 用户明确要求不要默认计划和执行 git 提交、分支、worktree。
