# Purchase Page UI Freeze Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `localhost:60349` 的购买页实现为已冻结的最终形态：顶部紧凑运行栏、商品监控主列表、底部三按钮悬浮动作、独立可拖动 modal，以及商品抽屉中的命中来源与查询分配热应用。

**Architecture:** 先用 Vitest 和 pytest 锁定冻结稿契约，再补后端 `item_rows` 元数据与 `apply-runtime` 热应用通道，最后重排 renderer 页面骨架并把商品抽屉接到“配置保存 + 运行时热应用”闭环。整个实现必须保持查询 session / browser session 复用，不允许因为切配置、开 modal、改分配而重登或重启整条 runtime。

**Tech Stack:** React 19, FastAPI, Python, Vitest, Testing Library, pytest, CSS

---

## 文件结构

- Modify: `docs/superpowers/specs/2026-03-20-purchase-page-ui-freeze-design.md`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Create: `app_desktop_web/tests/renderer/floating_runtime_modal.test.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Create: `app_desktop_web/src/features/purchase-system/hooks/use_floating_runtime_modal_state.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/floating_runtime_modal.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_recent_events_modal.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_account_monitor_modal.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_mode_allocation_input.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/api/schemas/query_configs.py`
- Modify: `app_backend/api/routes/query_configs.py`
- Modify: `app_backend/application/use_cases/get_purchase_runtime_status.py`
- Create: `app_backend/application/use_cases/apply_query_item_runtime.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_stats_aggregator.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_mode_allocator.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_query_config_routes.py`
- Modify: `tests/backend/test_query_runtime_service.py`

## Chunk 1: 锁定 localhost:60349 购买页冻结契约

### Task 1: 用页面测试锁定最终布局与文案

**Files:**
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 写失败断言，移除对 `购买系统` Hero 标题和页面描述的依赖**
- [ ] **Step 2: 写失败断言，锁定顶部只显示当前配置、状态文案、`选择配置 / 切换配置` 与 `累计购买`**
- [ ] **Step 3: 写失败断言，锁定页面主区不再常驻 `最近事件` 和 `账号监控` 标题**
- [ ] **Step 4: 写失败断言，锁定底部悬浮动作条只保留 `最近事件`、`查看账号详情`、`开始扫货 / 停止扫货`**
- [ ] **Step 5: 写失败断言，锁定商品主行默认显示 `名称 / 价格 / 磨损 / 成功 / 命中 / 失败 / 查询次数`，并移除 `队列中 / 运行代号 / 已购 / 回执`**
- [ ] **Step 6: 写失败断言，锁定点击商品行后打开抽屉，而不是旧 accordion 详情卡**
- [ ] **Step 7: 运行定向测试，确认 RED**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_page.test.jsx`
Expected: FAIL because current page still渲染 Hero、常驻最近事件/账号表、旧文案和旧商品展开方式
- [ ] **Step 8: 提交测试基线**
```bash
git add app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "test(desktop-ui): lock frozen purchase page layout"
```

### Task 2: 给可拖动 / 可缩放 modal 建专用失败测试

**Files:**
- Create: `app_desktop_web/tests/renderer/floating_runtime_modal.test.jsx`

- [ ] **Step 1: 写失败测试，锁定 modal 接收初始位置与尺寸并渲染在对应样式上**
- [ ] **Step 2: 写失败测试，锁定拖动标题栏后会回调新的位置**
- [ ] **Step 3: 写失败测试，锁定拖动右下角 resize handle 后会回调新的尺寸**
- [ ] **Step 4: 写失败测试，锁定关闭后重新打开会使用最近一次位置和尺寸**
- [ ] **Step 5: 运行定向测试，确认 RED**
Run: `cd app_desktop_web && npm test -- tests/renderer/floating_runtime_modal.test.jsx`
Expected: FAIL with missing component or missing drag/resize persistence behavior
- [ ] **Step 6: 提交测试基线**
```bash
git add app_desktop_web/tests/renderer/floating_runtime_modal.test.jsx
git commit -m "test(desktop-ui): lock floating runtime modal behavior"
```

### Task 3: 给购买页热应用链路补前端 client 失败测试

**Files:**
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Modify: `app_desktop_web/src/api/account_center_client.js`

- [ ] **Step 1: 写失败测试，锁定 client 暴露 `applyQueryItemRuntime(configId, queryItemId)`**
- [ ] **Step 2: 写失败测试，锁定该方法调用 `POST /query-configs/{config_id}/items/{query_item_id}/apply-runtime`**
- [ ] **Step 3: 写失败测试，锁定购买页保存分配时仍先走 `PATCH /query-configs/.../items/...`，再走 `apply-runtime`**
- [ ] **Step 4: 运行定向测试，确认 RED**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_client.test.js`
Expected: FAIL because client still缺少 `applyQueryItemRuntime`
- [ ] **Step 5: 提交测试基线**
```bash
git add app_desktop_web/tests/renderer/purchase_system_client.test.js
git commit -m "test(desktop-ui): lock purchase runtime apply client"
```

## Chunk 2: 补齐后端抽屉所需数据与热应用接口

### Task 4: 用后端测试锁定 `item_rows` 的命中来源摘要

**Files:**
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/application/use_cases/get_purchase_runtime_status.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_stats_aggregator.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

- [ ] **Step 1: 写失败测试，锁定 `GET /purchase-runtime/status` 的 `item_rows[]` 包含 `source_mode_stats[]`**
- [ ] **Step 2: 写失败测试，锁定 `GET /purchase-runtime/status` 的 `item_rows[]` 包含 `recent_hit_sources[]`**
- [ ] **Step 3: 写失败测试，锁定来源摘要至少带 `mode_type / hit_count / last_hit_at / account_id / account_display_name`**
- [ ] **Step 4: 运行定向 pytest，确认 RED**
Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py -q`
Expected: FAIL because current `PurchaseRuntimeItemRowResponse` and stats snapshot still不返回命中来源摘要
- [ ] **Step 5: 最小实现 `PurchaseStatsAggregator` 的来源聚合，并经 `get_purchase_runtime_status` 合并到 `item_rows`**
- [ ] **Step 6: 复跑定向 pytest，确认 GREEN**
Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py -q`
Expected: PASS
- [ ] **Step 7: 提交来源摘要实现**
```bash
git add app_backend/api/schemas/purchase_runtime.py app_backend/application/use_cases/get_purchase_runtime_status.py app_backend/infrastructure/purchase/runtime/purchase_stats_aggregator.py app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py
git commit -m "feat(runtime): expose purchase item hit sources"
```

### Task 5: 用后端测试锁定 `apply-runtime` 接口与返回语义

**Files:**
- Modify: `tests/backend/test_query_config_routes.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `app_backend/api/schemas/query_configs.py`
- Modify: `app_backend/api/routes/query_configs.py`
- Create: `app_backend/application/use_cases/apply_query_item_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_mode_allocator.py`

- [ ] **Step 1: 写失败测试，锁定 `POST /query-configs/{config_id}/items/{query_item_id}/apply-runtime` 返回 `status/message/config_id/query_item_id`**
- [ ] **Step 2: 写失败测试，锁定返回状态覆盖 `applied / applied_waiting_resume / skipped_inactive / failed_after_save`**
- [ ] **Step 3: 写失败测试，锁定 live runtime 热应用不会调用 `QueryRuntimeService.stop()`，不会重建 session**
- [ ] **Step 4: 写失败测试，锁定热应用只影响 worker 下一次取任务时的 allocator 结果**
- [ ] **Step 5: 运行定向 pytest，确认 RED**
Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_service.py -q`
Expected: FAIL because current system still缺少 `apply-runtime` route 和 live item refresh path
- [ ] **Step 6: 最小实现 use case、route、`QueryRuntimeService.apply_query_item_runtime(...)` 与 runtime thread 内刷新通道**
- [ ] **Step 7: 复跑定向 pytest，确认 GREEN**
Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_service.py -q`
Expected: PASS
- [ ] **Step 8: 提交热应用接口实现**
```bash
git add app_backend/api/schemas/query_configs.py app_backend/api/routes/query_configs.py app_backend/application/use_cases/apply_query_item_runtime.py app_backend/infrastructure/query/runtime/query_runtime_service.py app_backend/infrastructure/query/runtime/query_task_runtime.py app_backend/infrastructure/query/runtime/mode_runner.py app_backend/infrastructure/query/runtime/query_mode_allocator.py tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_service.py
git commit -m "feat(runtime): add query item runtime apply endpoint"
```

## Chunk 3: 把购买页重排成冻结后的运行控制台

### Task 6: 实现页面骨架重排与顶部紧凑运行栏

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 删除购买页 Hero 结构，保留错误区、顶部运行栏、商品主区和底部悬浮动作条**
- [ ] **Step 2: 把 `选择配置 / 切换配置` 从底部动作条移到顶部运行栏**
- [ ] **Step 3: 让顶部运行栏只显示配置名、状态文案、配置动作、累计购买，移除 `队列中 / 运行代号 / 购买代号`**
- [ ] **Step 4: 让底部动作条只保留 `最近事件`、`查看账号详情`、`开始扫货 / 停止扫货`**
- [ ] **Step 5: 复跑页面定向测试，确认与骨架相关断言转绿**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_page.test.jsx`
Expected: PASS for compact runtime bar and floating action bar assertions
- [ ] **Step 6: 提交骨架重排实现**
```bash
git add app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat(desktop-ui): reshape purchase page shell"
```

### Task 7: 实现独立的最近事件 / 账号详情 floating modal

**Files:**
- Create: `app_desktop_web/src/features/purchase-system/hooks/use_floating_runtime_modal_state.js`
- Create: `app_desktop_web/src/features/purchase-system/components/floating_runtime_modal.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_recent_events_modal.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_account_monitor_modal.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/floating_runtime_modal.test.jsx`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 最小实现通用 floating modal 壳，支持拖动、缩放、最近位置/尺寸持久化**
- [ ] **Step 2: 用该壳包裹 `PurchaseRecentEvents`，实现 `最近事件` 独立 modal**
- [ ] **Step 3: 用该壳包裹 `PurchaseAccountTable`，实现 `查看账号详情` 独立 modal**
- [ ] **Step 4: 从主页面移除常驻 `最近事件` 与 `账号监控` 容器**
- [ ] **Step 5: 复跑 modal 与页面定向测试，确认 GREEN**
Run: `cd app_desktop_web && npm test -- tests/renderer/floating_runtime_modal.test.jsx tests/renderer/purchase_system_page.test.jsx`
Expected: PASS
- [ ] **Step 6: 提交 modal 实现**
```bash
git add app_desktop_web/src/features/purchase-system/hooks/use_floating_runtime_modal_state.js app_desktop_web/src/features/purchase-system/components/floating_runtime_modal.jsx app_desktop_web/src/features/purchase-system/components/purchase_recent_events_modal.jsx app_desktop_web/src/features/purchase-system/components/purchase_account_monitor_modal.jsx app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/floating_runtime_modal.test.jsx app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat(desktop-ui): move purchase diagnostics into floating modals"
```

## Chunk 4: 做商品抽屉、命中来源和分配热应用闭环

### Task 8: 让购买页先拿到“选中配置详情 + capacity summary + runtime overlay”

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`

- [ ] **Step 1: 在 hook 中补 `selected config detail` 加载，真相源使用 `GET /query-configs/{config_id}`**
- [ ] **Step 2: 在 hook 中补 `capacity summary` 加载，真相源使用 `GET /query-configs/capacity-summary`**
- [ ] **Step 3: 写合并逻辑：当前选中配置若正在运行，用 `purchase-runtime/status` 覆盖统计字段与 mode 状态；未运行则保留配置详情并把统计置空**
- [ ] **Step 4: 复跑 client 定向测试，确认 RED -> GREEN**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_client.test.js`
Expected: PASS
- [ ] **Step 5: 提交 hook 数据层实现**
```bash
git add app_desktop_web/src/api/account_center_client.js app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/tests/renderer/purchase_system_client.test.js
git commit -m "feat(desktop-ui): merge purchase config detail with runtime overlay"
```

### Task 9: 实现商品主行、抽屉中的命中来源与 mode 分配编辑

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_mode_allocation_input.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 把商品主行改成默认平铺，左侧显示 `名称 / 价格 / 磨损`，右侧显示 `成功 / 命中 / 失败 / 查询次数`**
- [ ] **Step 2: 抽屉中渲染命中来源区，优先按 `api查询器 / api高速查询器 / 浏览器查询器` 显示来源摘要**
- [ ] **Step 3: 新建 purchase 专用分配输入组件，显示 mode 目标值、剩余容量、超配提示、当前状态摘要**
- [ ] **Step 4: 抽屉中加入 `保存分配`，点击后先调 `updateQueryItem(...)`，再调 `applyQueryItemRuntime(...)`**
- [ ] **Step 5: 对 `applied / applied_waiting_resume / skipped_inactive / failed_after_save` 分别给出稳定提示，不回滚已保存配置**
- [ ] **Step 6: 复跑页面定向测试，确认 GREEN**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_page.test.jsx`
Expected: PASS for item row, drawer, hit source, and allocation save assertions
- [ ] **Step 7: 提交商品抽屉实现**
```bash
git add app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx app_desktop_web/src/features/purchase-system/components/purchase_mode_allocation_input.jsx app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat(desktop-ui): add purchase item drawer controls"
```

## Chunk 5: 回归验证与交接

### Task 10: 跑闭环回归并人工预览 localhost:60349

**Files:**
- Modify: `docs/superpowers/specs/2026-03-20-purchase-page-ui-freeze-design.md`
- Modify: `docs/superpowers/plans/2026-03-20-purchase-page-ui-freeze.md`

- [ ] **Step 1: 运行后端定向回归**
Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_service.py -q`
Expected: PASS
- [ ] **Step 2: 运行前端定向回归**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_client.test.js tests/renderer/floating_runtime_modal.test.jsx tests/renderer/purchase_system_page.test.jsx`
Expected: PASS
- [ ] **Step 3: 运行 web 前端全量测试**
Run: `cd app_desktop_web && npm test`
Expected: PASS
- [ ] **Step 4: 检查改动边界**
Run: `git diff --stat`
Expected: only purchase runtime backend, purchase page renderer, related tests, docs
- [ ] **Step 5: 人工打开桌面 web 预览**
Run: `node main_ui_account_center_desktop.js`
Expected: 可进入 `http://localhost:60349/`，购买页顶部无 Hero，底部为三按钮，`最近事件` 与 `查看账号详情` 各开各的 floating modal，商品抽屉可保存分配并给出热应用反馈
- [ ] **Step 6: 更新冻结稿中“当前实现与冻结稿的差距”段落**
- [ ] **Step 7: 提交收尾**
```bash
git add docs/superpowers/specs/2026-03-20-purchase-page-ui-freeze-design.md docs/superpowers/plans/2026-03-20-purchase-page-ui-freeze.md app_backend app_desktop_web
git commit -m "feat(desktop-ui): finish frozen purchase page runtime console"
```
