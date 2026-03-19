# Purchase System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为新的 desktop web 购买系统落地“当前运行查询配置绑定 + 购买运行统计 + 购买页 UI”闭环，同时保持查询命中到购买分发的快链路不增延迟。

**Architecture:** 先补 purchase/query runtime 之间缺失的事件身份与状态契约，再引入独立的内存统计聚合器，最后把 `app_desktop_web` 的购买页接到现有 `/purchase-runtime/status` 增量扩展上。购买快链路继续走 `autobuy` 式 `total_wear_sum` 快速去重；统计旁路在 fast dedupe 前接收原始命中载荷，只做展示聚合，不参与分发或执行决策。

**Tech Stack:** Python, FastAPI, pytest, React, Vite, JavaScript, Vitest, Testing Library

---

## 文件结构

- Create: `app_backend/infrastructure/purchase/runtime/purchase_stats_aggregator.py`
- Create: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Create: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_account_table.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Create: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Create: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_hit_inbox.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/purchase/runtime/account_purchase_worker.py`
- Modify: `app_backend/infrastructure/query/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/api/schemas/query_runtime.py`
- Modify: `app_backend/application/use_cases/get_purchase_runtime_status.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_query_purchase_bridge.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

注：

- 本计划按 `@superpowers/test-driven-development` 执行，任何生产代码都必须先由失败测试锁定。
- 本计划按 `@superpowers/subagent-driven-development` 执行，实现任务完成后先做 spec compliance review，再做 code quality review。
- 按当前仓库既有计划约定，本计划不默认包含新的分支或 worktree 操作。

## Chunk 1: 购买链路身份与状态契约

### Task 1: 为命中身份透传与 query item 查询次数写失败测试

**Files:**
- Modify: `tests/backend/test_query_purchase_bridge.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`

- [ ] **Step 1: 写后端失败测试，锁定 query hit 必须全链路携带 `query_config_id`、`query_item_id` 与 `runtime_session_id`**

```python
def test_purchase_hit_batch_keeps_query_identity_fields():
    result = service.accept_query_hit({
        "query_config_id": "cfg-1",
        "query_item_id": "item-1",
        "runtime_session_id": "run-1",
        "query_item_name": "AK",
        "external_item_id": "ext-1",
        "product_list": [{"productId": "p-1", "price": 88.0, "actRebateAmount": 0}],
        "total_price": 88.0,
        "total_wear_sum": 0.1234,
        "mode_type": "new_api",
    })
    assert result["status"] == "queued"
```

- [ ] **Step 2: 写 query runtime 失败测试，锁定 `item_rows` 需要返回每个商品的 `query_count`**

```python
def test_query_runtime_status_exposes_item_query_count():
    snapshot = service.get_status()
    assert snapshot["item_rows"][0]["query_count"] == 3
```

- [ ] **Step 3: 写路由失败测试，锁定 waiting state 仍保留原配置绑定**

```python
async def test_query_runtime_waiting_snapshot_keeps_bound_config(client):
    response = await client.get("/query-runtime/status")
    assert response.json()["config_id"] == "cfg-1"
    assert response.json()["message"] == "等待购买账号恢复"
```

- [ ] **Step 4: 运行定向测试，确认因为字段未透传与 `query_count` 未暴露而失败**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_query_purchase_bridge.py" `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" -q
```

Expected:

- 新断言失败
- 失败原因直接指向缺少 `query_config_id` / `query_item_id` / `runtime_session_id` 或缺少 `item_rows.query_count`

### Task 2: 最小实现命中身份透传与 query runtime 商品查询次数

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/api/schemas/query_runtime.py`
- Modify: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_hit_inbox.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

- [ ] **Step 1: 在 query hit 事件和 purchase batch 模型中补齐 `query_config_id`、`query_item_id`、`runtime_session_id` 字段**

```python
@dataclass(slots=True)
class PurchaseHitBatch:
    query_config_id: str | None = None
    query_item_id: str | None = None
    runtime_session_id: str | None = None
```

- [ ] **Step 2: 让 `PurchaseHitInbox.accept()` 保留这些字段，而不是只压缩成 `query_item_name` 和 `external_item_id`**

- [ ] **Step 3: 在 query runtime 的 `item_rows` 中新增 `query_count`，口径冻结为“当前活动配置生命周期内、跨所有 mode 的真实查询执行次数总和”**

- [ ] **Step 4: 更新 query runtime schema / normalize 逻辑，让 `query_count` 能稳定出现在 `/query-runtime/status` 与 waiting snapshot 中**

- [ ] **Step 5: 复跑定向后端测试，确认身份透传与 `item_rows.query_count` 转绿**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_query_purchase_bridge.py" `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" -q
```

Expected:

- query/purchase 桥接测试通过
- query runtime 状态测试通过
- waiting state 仍正确保留绑定配置

## Chunk 2: 精确统计聚合器与购买状态扩展

### Task 3: 为统计旁路、失败件数边界与状态接口写失败测试

**Files:**
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_query_purchase_bridge.py`

- [ ] **Step 1: 写失败测试，锁定统计旁路接在 fast dedupe 之前，且 `matched_product_count` 以 `(runtime_session_id, query_item_id, productId)` 去重**

```python
def test_stats_aggregator_counts_unique_products_before_fast_dedupe():
    first = runtime.accept_query_hit(hit_with_product("p-1"))
    second = runtime.accept_query_hit(hit_with_product("p-1"))
    snapshot = runtime.get_status()
    assert snapshot["matched_product_count"] == 1
```

- [ ] **Step 2: 写失败测试，锁定 `purchase_success_count` / `purchase_failed_count` 只按件数累计，不承诺 `productId` 级结果归因**

```python
def test_partial_success_updates_piece_counts_only():
    snapshot = runtime.get_status()
    assert snapshot["purchase_success_count"] == 1
    assert snapshot["purchase_failed_count"] == 2
```

- [ ] **Step 3: 写失败测试，锁定哪些状态计入失败件数，哪些只记运行事件**

```python
def test_ignored_and_duplicate_do_not_increment_failed_piece_count():
    snapshot = runtime.get_status()
    assert snapshot["purchase_failed_count"] == 0
```

- [ ] **Step 4: 写路由失败测试，锁定 `/purchase-runtime/status` 走增量扩展，不破坏已有顶层字段与 `accounts`**

```python
async def test_purchase_runtime_status_includes_stats_and_keeps_accounts_shape(client):
    payload = (await client.get("/purchase-runtime/status")).json()
    assert "matched_product_count" in payload
    assert "accounts" in payload
    assert "submitted_product_count" in payload["accounts"][0]
```

- [ ] **Step 5: 写失败测试，锁定切换会话后旧飞行结果不会污染新统计**

```python
def test_old_runtime_session_results_are_ignored_after_reset():
    assert runtime.get_status()["runtime_session_id"] == "run-2"
    assert runtime.get_status()["purchase_success_count"] == 0
```

- [ ] **Step 6: 运行定向测试，确认因为缺少 stats aggregator 和状态扩展而失败**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_purchase_runtime_routes.py" `
  "tests/backend/test_query_purchase_bridge.py" -q
```

Expected:

- 新统计测试失败
- 失败原因指向缺少 `matched_product_count`、`runtime_session_id`、账号件数字段或失败件数边界逻辑

### Task 4: 最小实现精确统计聚合器与购买状态增量扩展

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/purchase_stats_aggregator.py`
- Modify: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/purchase/runtime/account_purchase_worker.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/application/use_cases/get_purchase_runtime_status.py`

- [ ] **Step 1: 新建 `PurchaseStatsAggregator`，维护：**
  - `runtime_session_id`
  - `matched_product_keys`
  - 商品维度计数
  - 账号维度件数
  - 全局 `matched_product_count / purchase_success_count / purchase_failed_count`

- [ ] **Step 2: 在 `PurchaseRuntimeService.accept_query_hit_async()` 中，于 fast dedupe 之前喂给 aggregator 原始命中载荷**

- [ ] **Step 3: 在购买工作者结果回流处更新件数统计，边界冻结为：**
  - `ignored_no_available_accounts` / `duplicate_filtered` / `queued` / `inventory_recovered` 不增加失败件数
  - `order_failed` / `payment_failed` / `invalid_batch` / `auth_invalid` / `paused_no_inventory` 按件数增加失败数

- [ ] **Step 4: 在重置、停止、切配置时重建 aggregator 并生成新 `runtime_session_id`**

- [ ] **Step 5: 扩展 `/purchase-runtime/status` 返回，但保持兼容：**
  - 保留现有顶层字段
  - 顶层新增 `runtime_session_id`
  - 顶层新增 `active_query_config`
  - 顶层新增 `matched_product_count / purchase_success_count / purchase_failed_count`
  - `accounts` 走增量扩展，补 `submitted_product_count / purchase_success_count / purchase_failed_count`
  - 新增 `item_rows`

- [ ] **Step 6: 仅在 use case / assembler 层组合 query runtime 状态，不让 `PurchaseRuntimeService` 反向依赖 `QueryRuntimeService`**

- [ ] **Step 7: 复跑定向后端测试，确认统计聚合与状态扩展转绿**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_purchase_runtime_routes.py" `
  "tests/backend/test_query_purchase_bridge.py" -q
```

Expected:

- 统计聚合器测试通过
- `/purchase-runtime/status` 兼容扩展测试通过
- 旧会话飞行结果隔离测试通过

## Chunk 3: Desktop Web 购买页与客户端联动

### Task 5: 为购买页客户端与页面行为写失败测试

**Files:**
- Create: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Create: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`

- [ ] **Step 1: 写客户端失败测试，锁定新增接口：**
  - `getPurchaseRuntimeStatus`
  - `startPurchaseRuntime`
  - `stopPurchaseRuntime`

- [ ] **Step 2: 写页面失败测试，锁定侧边栏 `购买系统` 可进入真实页面**

```jsx
it("switches into purchase system page", async () => {
  await user.click(screen.getByRole("button", { name: "购买系统" }));
  expect(await screen.findByRole("heading", { name: "购买系统" })).toBeInTheDocument();
});
```

- [ ] **Step 3: 写页面失败测试，锁定购买页展示：**
  - 当前绑定查询配置
  - 顶部件数摘要
  - 商品折叠列表
  - 账号统计区
  - 右下角 `开始扫货` / `停止扫货`

- [ ] **Step 4: 写页面失败测试，锁定 waiting state 仍显示绑定配置**

- [ ] **Step 5: 运行定向前端测试，确认因为缺少购买页与客户端方法而失败**

Run:

```powershell
npm --prefix "app_desktop_web" test -- `
  purchase_system_client.test.js `
  purchase_system_page.test.jsx
```

Expected:

- 新前端测试失败
- 失败原因指向缺少购买页入口、缺少客户端方法或缺少状态展示区

### Task 6: 最小实现 desktop web 购买页

**Files:**
- Create: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Create: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_account_table.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] **Step 1: 在客户端补齐 purchase runtime 读写接口**

- [ ] **Step 2: 在 `AppShell` 中启用 `购买系统` 导航项，保留现有账号中心 / 查询系统模式**

- [ ] **Step 3: 新建 `use_purchase_system_page.js`，先实现：**
  - 加载 `/purchase-runtime/status`
  - 启停购买运行时
  - 轮询刷新状态
  - 只消费增量扩展后的 `accounts` 与顶层统计字段

- [ ] **Step 4: 新建购买页组件，展示：**
  - 顶部运行摘要
  - 商品列表（使用 `item_rows`）
  - 账号表格（使用扩展后的 `accounts`）
  - 右下角启停动作区

- [ ] **Step 5: 保证 waiting state 时仍显示 `active_query_config`，而不是回退到“无配置”**

- [ ] **Step 6: 复跑定向前端测试，确认购买页基础闭环转绿**

Run:

```powershell
npm --prefix "app_desktop_web" test -- `
  purchase_system_client.test.js `
  purchase_system_page.test.jsx
```

Expected:

- desktop web 购买页可进入
- 购买页能显示绑定配置、件数摘要、商品统计和账号统计
- 启停按钮行为正确

## Chunk 4: 端到端回归与手工验收支撑

### Task 7: 写最终回归测试并验证查询购买联动

**Files:**
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 写后端回归测试，锁定 query runtime waiting 状态 + purchase runtime `active_query_config.state` 对齐**

- [ ] **Step 2: 写后端回归测试，锁定命中被 `duplicate_filtered` 挡掉时：**
  - `matched_product_count` 不重复增长
  - `recent_events` 仍可见实时运行事件

- [ ] **Step 3: 写前端回归测试，锁定商品列表中：**
  - `query_execution_count`
  - `matched_product_count`
  - `purchase_success_count`
  - `purchase_failed_count`
  文案正确映射

- [ ] **Step 4: 运行完整定向测试集，确认没有打碎现有购买 / 查询联动**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_purchase_runtime_routes.py" `
  "tests/backend/test_query_purchase_bridge.py" `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" -q

npm --prefix "app_desktop_web" test -- `
  purchase_system_client.test.js `
  purchase_system_page.test.jsx `
  query_system_page.test.jsx `
  query_system_editing.test.jsx
```

Expected:

- 定向后端测试全部通过
- 定向前端测试全部通过
- 查询与购买的联动状态保持一致

## 结语

执行时务必遵守以下顺序：

1. 先补事件身份和 query runtime 契约
2. 再上 stats aggregator 与状态接口扩展
3. 最后接 desktop web 购买页

不要先做前端页面再反推后端字段，否则会再次出现“UI 出来了，但统计语义和运行态不一致”的旧问题。
