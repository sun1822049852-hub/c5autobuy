# Diagnostics Page Session Log Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将通用诊断从常驻侧栏改为左侧导航中的独立页面，并让失败日志在当前会话内持续保留、可复制原始错误细节。

**Architecture:** 保留现有 `/diagnostics/sidebar` 聚合接口与轮询机制，但把轮询状态提升到 `App` 根部，构建前端会话日志池来持续累积诊断错误事件。查询、购买、登录三条链补齐原始错误细节字段并透传到诊断页，页面提供持续展示与复制能力，但不做数据库持久化。

**Tech Stack:** React, Vitest, Testing Library, FastAPI, Python dataclasses

---

## Chunk 1: Navigation And Diagnostics Page

### Task 1: 将诊断入口改为独立页面

**Files:**
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Modify: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] **Step 1: Write the failing test**

在 `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx` 改为断言：
- 左侧导航存在 `通用诊断` 按钮
- 默认首页不再渲染诊断面板
- 点击 `通用诊断` 后才进入诊断页并展示诊断内容

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- tests/renderer/diagnostics_sidebar.test.jsx`
Expected: FAIL，因为当前仍是常驻侧栏。

- [ ] **Step 3: Write minimal implementation**

实现：
- `AppShell` 删除 `diagnosticsPanel` 常驻槽位
- 导航新增 `diagnostics` 页面入口
- `App` 在 `activeItem === "diagnostics"` 时渲染诊断页面

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- tests/renderer/diagnostics_sidebar.test.jsx`
Expected: PASS

## Chunk 2: Session Log Retention

### Task 2: 让诊断日志在当前会话内持续保留

**Files:**
- Modify: `app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js`
- Modify: `app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx`
- Add or Modify: `app_desktop_web/src/features/diagnostics/*`
- Test: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] **Step 1: Write the failing test**

补测试覆盖：
- 轮询返回的新快照不应覆盖掉此前已出现的失败日志
- 错误日志即使后续接口不再返回，也仍留在诊断页

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- tests/renderer/diagnostics_sidebar.test.jsx`
Expected: FAIL，因为当前只保留最新快照。

- [ ] **Step 3: Write minimal implementation**

实现：
- 在 `useSidebarDiagnostics` 中维护会话日志池
- 基于事件签名去重并持续累积
- 成功事件做上限裁剪，失败事件高上限保留
- 诊断页读取“最新快照 + 会话日志历史”

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- tests/renderer/diagnostics_sidebar.test.jsx`
Expected: PASS

## Chunk 3: Raw Error Detail Propagation

### Task 3: 查询与购买失败事件补齐原始错误细节

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/query/runtime/account_query_worker.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/*_query_executor.py`
- Modify: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/application/use_cases/get_sidebar_diagnostics.py`
- Modify: `app_backend/api/schemas/diagnostics.py`
- Test: `tests/backend/test_diagnostics_routes.py`

- [ ] **Step 1: Write the failing test**

在 `tests/backend/test_diagnostics_routes.py` 增加断言，确保失败事件可透传：
- `status_code/http_status`
- `request_method/request_path`
- `response_text/raw_response`
- `error_message`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_diagnostics_routes.py -q`
Expected: FAIL，因为当前 schema 与 use case 不返回这些字段。

- [ ] **Step 3: Write minimal implementation**

实现：
- 查询 executor 失败结果携带调试字段
- 购买 gateway 失败结果携带调试字段
- 事件序列化与 diagnostics schema/use case 透传这些字段

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_diagnostics_routes.py -q`
Expected: PASS

### Task 4: 登录诊断保留任务原始事件 payload

**Files:**
- Modify: `app_backend/application/use_cases/get_sidebar_diagnostics.py`
- Modify: `app_backend/api/schemas/diagnostics.py`
- Modify: `tests/backend/test_task_manager.py`
- Modify: `tests/backend/test_diagnostics_routes.py`

- [ ] **Step 1: Write the failing test**

补测试，断言登录任务事件会返回 `payload/result/error` 中的调试字段。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/backend/test_task_manager.py tests/backend/test_diagnostics_routes.py -q`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

实现：
- diagnostics login task event 增加 payload 透传
- 最近任务项增加 error/result 调试字段

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/backend/test_task_manager.py tests/backend/test_diagnostics_routes.py -q`
Expected: PASS

## Chunk 4: Diagnostics Page UX

### Task 5: 诊断页展示并复制原始错误细节

**Files:**
- Modify: `app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx`
- Modify: `app_desktop_web/src/features/diagnostics/*`
- Possibly Add: `app_desktop_web/src/features/diagnostics/diagnostics_page.jsx`
- Test: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] **Step 1: Write the failing test**

补测试覆盖：
- 页面能展示历史失败日志细节
- 可看到 `HTTP xxx`、请求路径、原始返回
- 提供复制入口并写入 clipboard mock

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- tests/renderer/diagnostics_sidebar.test.jsx`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

实现：
- 诊断页布局改为页面视图
- 每类日志展示细节行
- 增加复制按钮或复制块
- 可选增加“清空会话日志”操作

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- tests/renderer/diagnostics_sidebar.test.jsx`
Expected: PASS

## Chunk 5: Final Verification

### Task 6: 全量回归

**Files:**
- Verify only

- [ ] **Step 1: Run targeted frontend tests**

Run: `npm test -- tests/renderer/diagnostics_sidebar.test.jsx tests/renderer/login_drawer.test.jsx tests/renderer/account_center_page.test.jsx`
Expected: PASS

- [ ] **Step 2: Run targeted backend tests**

Run: `python -m pytest tests/backend/test_diagnostics_routes.py tests/backend/test_task_manager.py -q`
Expected: PASS

- [ ] **Step 3: Run full frontend suite**

Run: `npm test`
Expected: PASS

- [ ] **Step 4: Run full backend suite**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web app_backend tests docs/superpowers/plans/2026-03-25-diagnostics-page-session-log-implementation.md
git commit -m "feat: move diagnostics into a dedicated page"
```
