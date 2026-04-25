# Desktop Startup Thinning Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把桌面程序“首页可见”从整机冷启动里剥离出来，让账号中心首屏只等待 home/core slice，而把 query/purchase/browser 重货改成 deferred 或按页惰性初始化。

**Architecture:** 后端启动拆成三层：`core-home` 同步装配首页必须依赖，`runtime-full` 延后到首次进入查询/购买/诊断页时再确保 ready，`browser-actions` 延后到首次登录 / 打开 open-api / 详情刷新等动作时再初始化。前端启动时只拿 shell bootstrap 和账号中心列表，不再在首页首屏阶段偷偷回填 full bootstrap；首次进入 runtime 页时再拉 full bootstrap 和 websocket。

**Tech Stack:** Electron, React 19, FastAPI, Python 3.11, SQLite, Vitest, pytest

---

> Risk level: `risky`. This plan touches desktop startup, `/health` 语义边界、`/app/bootstrap`、账号中心首页数据源、以及 query/purchase/browser 的装配顺序。执行前建议放进 dedicated worktree；若只能在当前工作树推进，必须保持小步验证和可回退提交。

## Locked Decisions

- **Decision:** 账号中心首页允许先显示 repo-backed fallback 状态。
  - 首页目标是“尽快可见 + 能浏览账号基础信息”，不是“首屏即拥有完整 query/purchase runtime 真相”。
  - 当 runtime-full 尚未 ready 时，首页允许展示：
    - 账号基础字段
    - 代理、API key、备注、登录相关基础状态
    - purchase/query 的 fallback 文本或“运行时加载中”占位
  - 不允许在 fallback 阶段展示会误导用户已可执行 runtime 操作的假状态。
- **Decision:** 查询页、购买页、诊断页首次进入时，可以出现页面内 loading，不要求和首页同一时刻 ready。
- **Decision:** `query -> hit -> purchase` 主链语义不改；本计划只改启动装配顺序，不改运行态调度模型。

## Non-Goals

- 不重写 `purchase_runtime_service` 的调度架构。
- 不重写 `query_runtime_service` 的业务语义。
- 不借本轮启动优化顺手改程序会员产品逻辑、白名单逻辑、登录成功标准、或 open-api 复用链。
- 不把“首页更快出现”伪装成“整机 ready 更快”；必须保留明确的 page-level loading/guard。

## Acceptance Criteria

- 首页从桌面启动到可浏览账号列表，不再等待 query/purchase/browser heavy slice。
- 首页首屏阶段不再触发 full `/app/bootstrap`。
- 首页首屏阶段不再隐式初始化 `purchase_runtime_service` / `query_runtime_service` / browser-action heavy services。
- 首次进入 query/purchase/diagnostics 页时，能够显式触发对应 ensure，并给出页面内 loading，而不是白屏/黑屏/500。
- 登录、open-api、程序会员状态、以及 `query -> hit -> purchase` 主链行为不退化。

## Rollback Principle

- 若 Task 4 之后发现首页 fallback 导致用户误判当前可购买/可运行状态，先回退账号中心 snapshot 切换，不要硬顶着继续做 runtime-full 拆分。
- 若 Task 5 之后 runtime routes 出现偶发 500/AttributeError，先回退 route-level ensure 改动，不要继续叠加前端 lazy 行为。
- 若 Task 6 之后 browser lazy init 打断登录/open-api 成功链，立即回退 browser-actions lazy 化，保留 core/runtime 的已完成拆分。

## File Map

- `app_backend/main.py`
  当前单体装配入口。需要从“一个 `_sync_heavy_init()` 把所有服务全建完”拆成多 slice registry。
- `app_backend/api/routes/app_bootstrap.py`
  需要把 `scope=shell` 固定为 core-only，`scope=full` 改成显式触发 runtime slice ensure。
- `app_backend/application/use_cases/get_app_bootstrap.py`
  需要拆开 shell/full 依赖，不允许 shell path 再隐式依赖 query/purchase/task/stats。
- `app_backend/api/routes/account_center.py`
  当前首页数据读 `purchase_runtime_service`；需要改成 home-safe snapshot source。
- `app_backend/application/use_cases/list_account_center_accounts.py`
- `app_backend/application/use_cases/get_account_center_account.py`
  当前只是 purchase runtime 的薄壳；需要改成依赖新的 account-center snapshot service。
- `app_backend/api/routes/accounts.py`
  登录 / open-api / 登录冲突处理等动作需要从 app.state 直接拿 browser-heavy 服务，改成按需 ensure browser slice。
- `app_backend/api/routes/query_runtime.py`
- `app_backend/api/routes/purchase_runtime.py`
- `app_backend/api/routes/query_configs.py`
- `app_backend/api/routes/runtime_settings.py`
- `app_backend/api/routes/diagnostics.py`
  这些 route 需要统一走 runtime slice accessor，而不是默认假设 app 启动时已经全建好。
- `app_backend/api/websocket/runtime.py`
  runtime websocket 必须等 runtime slice ready；不能再让首页首屏为它买单。
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
  仍保留既有主链语义，但不再要求 desktop home 启动时同步装配。
- `app_backend/infrastructure/query/runtime/query_runtime_service.py`
  同上，迁到 runtime-full slice。
- `app_backend/infrastructure/browser_runtime/managed_browser_runtime.py`
  保持当前浏览器 runtime 行为，但初始化改为 browser-actions slice lazy load。
- `app_backend/application/services/account_balance_service.py`
  账号余额刷新不应继续绑死首页 ready；要么留在 core-home 但异步 warm，要么挪到 browser-actions/runtime slice。
- `app_desktop_web/src/App.jsx`
  当前首页 ready 后会 `runtimeConnectionManager.bootstrap()`，而该逻辑会 shell 后自动补 full；要改成真正的 home-shell-only。
- `app_desktop_web/src/runtime/runtime_connection_manager.js`
  需要把 `shell bootstrap` 与 `full bootstrap` 分开，禁止首页阶段后台偷跑 full bootstrap。
- `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
  首页应只依赖账号列表接口，不再隐式依赖 runtime-full。
- `app_desktop_web/src/features/query-system/query_system_page.jsx`
- `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- `app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx`
  页面首次激活时负责触发 full bootstrap / runtime ensure，并显示本页 loading，而不是把成本前置到桌面首屏。
- `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`
  前端行为回归。
- `app_desktop_web/tests/electron/python_backend.test.js`
- `app_desktop_web/tests/electron/electron_remote_mode.test.js`
  Electron/embedded backend readiness 回归。
- `tests/backend/test_backend_health.py`
- `tests/backend/test_desktop_web_backend_bootstrap.py`
- `tests/backend/test_account_center_routes.py`
- `tests/backend/test_app_bootstrap_route.py`
- `tests/backend/test_query_runtime_routes.py`
- `tests/backend/test_purchase_runtime_routes.py`
- `tests/backend/test_runtime_settings_routes.py`
- `tests/backend/test_query_config_routes.py`
  后端分层启动与按需 ensure 回归。
- `docs/agent/session-log.md`
  记录本轮启动链瘦身的分层策略、验证和剩余风险。

## 首页必须 / Deferred / Lazy 清单

### 首页同步必须

- Electron 主窗口与 preload bridge
- FastAPI app skeleton 与 `/health`
- SQLite engine / schema / session factory
- `account_repository`
- `proxy_pool_repository`
- `account_session_bundle_repository`
- `program_access_gateway`
- `runtime_update_hub` 的 shell 版本号来源
- 新的 `account_center_snapshot_service`
- `/app/bootstrap?scope=shell`
- `/program-auth/status`
- `/account-center/accounts`

### Deferred 到 runtime-full

- `stats_repository` + `StatsPipeline`
- `query_config_repository`
- `query_settings_repository`
- `inventory_snapshot_repository`
- `purchase_ui_preferences_repository`
- `runtime_settings_repository`
- `task_manager`
- `query_runtime_service`
- `purchase_runtime_service`
- runtime websocket 路由所需对象
- full `/app/bootstrap`
- diagnostics 汇总里依赖 runtime/task 的部分

### Lazy 到 browser-actions

- `ManagedBrowserRuntime`
- `AccountBrowserProfileStore`
- `BrowserLoginAdapter`
- `OpenApiBindingSyncService`
- `OpenApiBindingPageLauncher`
- `ProductDetailFetcher` / `ProductDetailCollector` / `QueryItemDetailRefreshService`
- `AccountBalanceService` 的重刷新链（若不能留在 core，则改为 action-triggered/async warm）

## Chunk 1: Lock The New Startup Contract Before Refactor

### Task 1: 锁定 backend “home ready 不等 runtime-full” 契约

**Files:**
- Create: `tests/backend/test_backend_startup_slices.py`
- Modify: `tests/backend/test_backend_health.py`
- Modify: `tests/backend/test_desktop_web_backend_bootstrap.py`

- [ ] **Step 1: 写 failing tests**
  目标断言：
  - deferred 模式下，`/health` ready 只要求 core-home ready
  - `/app/bootstrap?scope=shell`、`/program-auth/status`、`/account-center/accounts` 在 runtime-full 未初始化时也能成功
  - `scope=full` 首次请求会显式触发 runtime-full ensure，而不是要求 desktop 启动时提前装好

- [ ] **Step 2: 跑 backend focused tests，确认当前失败**

Run:

```bash
./.venv/Scripts/python.exe -m pytest tests/backend/test_backend_health.py tests/backend/test_desktop_web_backend_bootstrap.py tests/backend/test_backend_startup_slices.py -q
```

Expected:
- FAIL，原因是当前 `/account-center/accounts` 和 full bootstrap 仍直接依赖 `purchase_runtime_service` / `query_runtime_service`

- [ ] **Step 3: 只修到能表达新契约，不先做性能优化实现**

- [ ] **Step 4: 重跑同一组 tests，确认转绿**

### Task 2: 锁定前端“首页只吃 shell，不偷跑 full bootstrap” 契约

**Files:**
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 写 failing tests**
  目标断言：
  - 桌面首页 ready 后只请求 shell bootstrap 和账号列表
  - 不在 account-center 首屏阶段后台触发 full bootstrap
  - 首次进入 query-system / purchase-system 时才触发 full bootstrap

- [ ] **Step 2: 跑 renderer focused tests，确认当前失败**

Run:

```bash
npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/account_center_page.test.jsx tests/renderer/query_system_page.test.jsx tests/renderer/purchase_system_page.test.jsx --run
```

Expected:
- FAIL，原因是当前 `runtimeConnectionManager.bootstrap()` 在首页 ready 后会 shell 后自动 backfill full bootstrap

- [ ] **Step 3: 保留现有首页可用语义，只锁定新懒加载边界**

- [ ] **Step 4: 重跑同一组 tests，确认转绿**

## Chunk 2: Split Backend Startup Into Core / Runtime / Browser Slices

### Task 3: 建立 startup slice registry

**Files:**
- Create: `app_backend/startup/__init__.py`
- Create: `app_backend/startup/service_registry.py`
- Create: `app_backend/startup/build_core_home_services.py`
- Create: `app_backend/startup/build_runtime_full_services.py`
- Create: `app_backend/startup/build_browser_action_services.py`
- Modify: `app_backend/main.py`

- [ ] **Step 1: 写 failing tests，锁定 `app.state` 上新的 ensure 入口**
  新入口至少包括：
  - `ensure_runtime_full_ready()`
  - `ensure_browser_actions_ready()`
  - `account_center_snapshot_service`

- [ ] **Step 2: 跑 Task 1 的 backend tests，确认缺少新入口而失败**

- [ ] **Step 3: 最小实现 startup registry**
  约束：
  - `create_app()` 同步只建 core-home
  - runtime-full 用 promise/lock 防重入
  - browser-actions 用独立 lock，首次登录/open-api 时再建
  - `/health ready=true` 只表示 desktop home takeover 所需接口 ready，不再等 runtime-full

- [ ] **Step 4: 重跑 Task 1 tests，确认 registry 契约转绿**

### Task 4: 把账号中心首页从 purchase runtime 解耦

**Files:**
- Create: `app_backend/application/services/account_center_snapshot_service.py`
- Modify: `app_backend/application/use_cases/list_account_center_accounts.py`
- Modify: `app_backend/application/use_cases/get_account_center_account.py`
- Modify: `app_backend/api/routes/account_center.py`
- Modify: `tests/backend/test_account_center_routes.py`

- [ ] **Step 1: 写 failing tests**
  断言：
  - 没有 `purchase_runtime_service` 也能列账号中心首页数据
  - 首页返回字段结构不变
  - 当前买量/查询 runtime 未初始化时，首页使用 repository-backed fallback，而不是 500

- [ ] **Step 2: 跑对应 route tests，确认当前失败**

Run:

```bash
./.venv/Scripts/python.exe -m pytest tests/backend/test_account_center_routes.py -q
```

Expected:
- FAIL，原因是 route 仍硬依赖 `request.app.state.purchase_runtime_service`

- [ ] **Step 3: 最小实现 repo-backed snapshot service**
  约束：
  - 不改登录、白名单、购买主链语义
  - 只把“首页列表展示数据源”从 runtime service 改成 home-safe service
  - fallback 字段必须显式可辨识，例如：
    - runtime 相关状态文本标成“运行时未加载”/“待进入购买页后获取”
    - 禁止伪造 `running` / `purchasable` / `selected_warehouse` 之类依赖 runtime 真相的状态

- [ ] **Step 4: 重跑 tests，确认转绿**

### Task 5: 把 full bootstrap / runtime routes 改成显式 ensure runtime-full

**Files:**
- Modify: `app_backend/api/routes/app_bootstrap.py`
- Modify: `app_backend/application/use_cases/get_app_bootstrap.py`
- Modify: `app_backend/api/routes/query_runtime.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Modify: `app_backend/api/routes/query_configs.py`
- Modify: `app_backend/api/routes/runtime_settings.py`
- Modify: `app_backend/api/routes/diagnostics.py`
- Modify: `app_backend/api/websocket/runtime.py`
- Modify: `tests/backend/test_app_bootstrap_route.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_runtime_settings_routes.py`
- Modify: `tests/backend/test_query_config_routes.py`

- [ ] **Step 1: 写 failing tests**
  断言：
  - shell bootstrap 不触发 runtime-full
  - full bootstrap 首次请求会触发 runtime-full ensure
  - runtime route/websocket 在 slice ready 前不会直接 AttributeError/500

- [ ] **Step 2: 跑 backend focused tests，确认当前失败**

Run:

```bash
./.venv/Scripts/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_query_runtime_routes.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_runtime_settings_routes.py tests/backend/test_query_config_routes.py -q
```

- [ ] **Step 3: 最小实现 route-level ensure**
  约束：
  - 不重写 query -> hit -> purchase 主链
  - 只改装配顺序与首次 ensure 入口

- [ ] **Step 4: 重跑同一组 tests，确认转绿**

### Task 6: 把登录/open-api/browser 相关重货改成按动作 lazy ensure

**Files:**
- Modify: `app_backend/api/routes/accounts.py`
- Modify: `tests/backend/test_account_center_routes.py`
- Modify: `app_backend/main.py`

- [ ] **Step 1: 写 failing tests**
  断言：
  - app 启动后未登录前，不会先构造 browser-actions slice
  - 调 `POST /accounts/{id}/login` / `open-api/*` 时才 ensure browser-actions

- [ ] **Step 2: 跑 route tests，确认当前失败**

- [ ] **Step 3: 实现 lazy accessor**
  约束：
  - 登录成功、open-api 打开与复用链语义不变
  - 不能把 browser lazy init 失败反向绑死首页启动成功链

- [ ] **Step 4: 重跑 tests，确认转绿**

## Chunk 3: Make The Frontend Respect The New Slice Boundaries

### Task 7: 首页阶段只拿 shell bootstrap

**Files:**
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/runtime/runtime_connection_manager.js`
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`

- [ ] **Step 1: 让测试先失败**
  期望行为：
  - `App.jsx` 在 account-center 首屏只调用 shell bootstrap
  - `runtime_connection_manager` 不再自动后台补 full bootstrap

- [ ] **Step 2: 跑 renderer focused tests**

Run:

```bash
npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx --run
```

- [ ] **Step 3: 最小实现 shell/full 分离 API**
  可以采用：
  - `bootstrapShellOnly()`
  - `ensureFullBootstrap()`
  - 或 `bootstrap({ requireFull: false, backgroundFull: false })`

- [ ] **Step 4: 重跑 tests，确认转绿**

### Task 8: 进入 query/purchase/diagnostics 页面时再 ensure runtime-full

**Files:**
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx`
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] **Step 1: 写 failing tests**
  断言：
  - 首页不再为 query/purchase/diagnostics 支付启动成本
  - 首次切入这些页时显示本页 loading，再取 full bootstrap

- [ ] **Step 2: 跑对应 renderer tests，确认当前失败**

- [ ] **Step 3: 最小实现 page-entry ensure**
  约束：
  - 不能打破 keepalive 语义
  - 不要让切页重新反复 full bootstrap
  - 首次 ensure 期间要提供页面内 loading/guard，禁止让用户直接操作依赖 runtime-full 的按钮

- [ ] **Step 4: 重跑 tests，确认转绿**

## Chunk 4: Verify Startup Cost Actually Moved

### Task 9: 跑 focused verification 并记录新的启动分层证据

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: 跑 Electron 启动相关测试**

```bash
npm --prefix app_desktop_web test -- tests/electron/electron_remote_mode.test.js tests/electron/python_backend.test.js --run
```

- [ ] **Step 2: 跑 renderer 首屏与 runtime-page 回归**

```bash
npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/account_center_page.test.jsx tests/renderer/query_system_page.test.jsx tests/renderer/purchase_system_page.test.jsx tests/renderer/diagnostics_sidebar.test.jsx --run
```

- [ ] **Step 3: 跑 backend route/startup 回归**

```bash
./.venv/Scripts/python.exe -m pytest tests/backend/test_backend_health.py tests/backend/test_desktop_web_backend_bootstrap.py tests/backend/test_backend_startup_slices.py tests/backend/test_account_center_routes.py tests/backend/test_app_bootstrap_route.py tests/backend/test_query_runtime_routes.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_runtime_settings_routes.py tests/backend/test_query_config_routes.py -q
```

- [ ] **Step 4: 跑真实启动 trace，确认首页阶段只出现 shell/bootstrap 路径**

```powershell
$env:C5_STARTUP_TRACE='1'
node main_ui_node_desktop.js
```

Expected:
- `desktop.static_shell.visible`
- `desktop.window.visible`
- `desktop.backend.ready`
- 首页阶段不再伴随 query/purchase/runtime-full 初始化痕迹

- [ ] **Step 5: 更新 `docs/agent/session-log.md`**
  必须记录：
  - 首页同步必须链最终名单
  - deferred / lazy 的最终名单
  - 手测或 trace 证据
  - 仍未解决的慢链（若存在）

## Suggested First Execution Boundary

- 先只执行 `Chunk 1 + Task 3 + Task 4`，不要一口气把 browser-actions lazy 和前端 page-entry ensure 全部一起做。
- 第一阶段完成标志：
  - 首页 ready 不再依赖 runtime-full
  - 首页账号列表已能用 fallback source 稳定返回
  - shell/full bootstrap contract 已锁死
- 第一阶段若不稳，不进入 Task 5~8。
