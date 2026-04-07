# Membership Thin Client Frontend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前项目收束成“远端会员 backend + Electron thin client + 只分发前端壳”的产品形态；本阶段先完成注册、登录、找回密码、会员闸门、多租户隔离和打包，不做支付，不做最终控制台 UI。

**Architecture:** FastAPI 继续作为唯一可信后端，所有用户、会话、会员、套餐限制与资源隔离都落在服务端。注册机制明确参考 `C:\Users\18220\Desktop\cs2_alchemy` 的 control-plane 设计，采用 `email/send-code -> register -> login -> refresh -> logout -> password reset`，但传输层保持当前 Electron 直连远端 FastAPI 的 token 模式，不照抄 sidecar/license/cookie 方案。控制台 UI 放到最后，先只补最小 auth entry，最终控制台再接 GitHub 开源 admin/template。

**Tech Stack:** Electron, React 19, Vite, Vitest, FastAPI, WebSocket, SQLAlchemy, SQLite（当前）/ PostgreSQL（后续可切换）

---

## File Map

- `app_backend/main.py`
  应用装配入口；后续注入 auth/membership 路由、依赖、配置与内部授予脚本。
- `app_backend/infrastructure/db/models.py`
  当前 SQLAlchemy 表定义；V1 直接在这里补 `users / auth_sessions / auth_email_codes / membership_plans / memberships`。
- `app_backend/infrastructure/db/base.py`
  当前 schema 初始化与幂等迁移入口；后续补 auth 表和 `owner_user_id` 字段迁移。
- `app_backend/api/routes/app_bootstrap.py`
  首屏聚合入口；后续补 `viewer / membership / limits`。
- `app_backend/api/websocket/runtime.py`
  当前未鉴权；后续补 token 校验与按用户过滤。
- `app_backend/api/routes/accounts.py`
- `app_backend/api/routes/account_center.py`
- `app_backend/api/routes/query_configs.py`
- `app_backend/api/routes/query_runtime.py`
- `app_backend/api/routes/purchase_runtime.py`
  当前业务路由；后续统一接入当前用户与会员闸门。
- `app_backend/infrastructure/repositories/account_repository.py`
- `app_backend/infrastructure/repositories/query_config_repository.py`
- `app_backend/infrastructure/repositories/query_settings_repository.py`
- `app_backend/infrastructure/repositories/account_session_bundle_repository.py`
- `app_backend/infrastructure/repositories/purchase_ui_preferences_repository.py`
- `app_backend/infrastructure/repositories/runtime_settings_repository.py`
  当前 repository 默认全局读写；后续全部按 `owner_user_id` 收口。
- `app_backend/infrastructure/browser_runtime/account_browser_profile_store.py`
  浏览器 profile 路径需改为按用户隔离。
- `app_desktop_web/src/api/http.js`
  当前没有 token 注入；后续改成带 access token 的统一 HTTP client。
- `app_desktop_web/src/api/account_center_client.js`
  当前前端 API client；后续接 `auth_client`、`/me`、`/me/membership`、401 refresh。
- `app_desktop_web/src/runtime/runtime_connection_manager.js`
  当前 `ws/runtime` 只带 `since_version`；后续补鉴权握手。
- `app_desktop_web/src/App.jsx`
  当前旧控制台根入口；本阶段只加最小 auth gate，不重造控制台。
- `app_desktop_web/electron_runtime_mode.cjs`
- `app_desktop_web/electron-main.cjs`
- `app_desktop_web/electron-preload.cjs`
- `app_desktop_web/src/desktop/bridge.js`
  Electron remote 壳与 preload bridge；后续补产品态强制 remote mode、会话持久化桥接。
- `docs/superpowers/specs/2026-04-06-membership-auth-design.md`
  当前 auth 设计基线；执行前先以这份 spec 为准。

## Scope

### In Scope

- 用户注册：参考 `cs2_alchemy`，先发邮箱验证码，再完成注册。
- 用户登录/登出/refresh。
- 密码找回：邮箱验证码 + 重置密码。
- `/me`、`/me/membership`、`/app/bootstrap` 的用户/会员摘要。
- 会员状态与套餐限制的服务端判定。
- 现有业务资源的 `owner_user_id` 隔离。
- Electron thin client 的鉴权接线与只打包前端壳。
- 当前阶段会员授予：内部脚本或内部接口。

### Out of Scope

- 支付接口、支付回调、订单对账、续费 webhook。
- 最终控制台 UI、控制台设计系统、自研 admin 框架。
- 分销、优惠券、邀请码、SSO、RBAC 后台。
- 离线 license、本地 sidecar 授权。

## Chunk 1: 后端 Auth 与 Membership 基线

### Task 1: 建立认证与会员数据模型

**Files:**
- Create: `app_backend/domain/models/user.py`
- Create: `app_backend/domain/models/membership.py`
- Create: `app_backend/domain/models/auth_session.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Create: `app_backend/infrastructure/repositories/auth_repository.py`
- Create: `app_backend/infrastructure/repositories/membership_repository.py`
- Test: `tests/backend/test_auth_repository.py`
- Test: `tests/backend/test_membership_repository.py`

- [ ] **Step 1: 在 `models.py` 增加 V1 所需表**
  表最小集合：`users`、`auth_sessions`、`auth_email_codes`、`membership_plans`、`memberships`。

- [ ] **Step 2: 在 `base.py` 增加幂等 schema 初始化与迁移**
  要求新库直接建表，老库启动时能补表，不破坏现有业务表。

- [ ] **Step 3: 建立 repository 层**
  Repository 至少支持：按用户名查用户、创建用户、创建/撤销 session、创建/消费邮箱验证码、读取当前会员摘要。

- [ ] **Step 4: 密码与 refresh token 统一 hash 策略**
  密码明确参考 `C:\Users\18220\Desktop\cs2_alchemy\node_sidecar\src\appAuthStore.js`，采用 `scrypt$<salt>$<digest>`；refresh token 只存 hash，不存明文。

- [ ] **Step 5: 先写 repository 测试**
  Run: `pytest tests/backend/test_auth_repository.py tests/backend/test_membership_repository.py -q`
  Expected: 新表可创建、`scrypt` 校验通过、session 与 membership 查询可用。

### Task 2: 实现 Auth HTTP 契约

**Files:**
- Create: `app_backend/api/routes/auth.py`
- Create: `app_backend/api/routes/membership.py`
- Create: `app_backend/api/schemas/auth.py`
- Create: `app_backend/api/schemas/membership.py`
- Create: `app_backend/application/services/password_hasher.py`
- Create: `app_backend/application/services/token_service.py`
- Create: `app_backend/application/services/auth_guard.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_auth_routes.py`
- Test: `tests/backend/test_membership_routes.py`

- [ ] **Step 1: 先按参考实现冻结接口**
  必做接口：`POST /auth/email/send-code`、`POST /auth/register`、`POST /auth/login`、`POST /auth/refresh`、`POST /auth/logout`、`POST /auth/password/send-reset-code`、`POST /auth/password/reset`、`GET /me`、`GET /me/membership`。

- [ ] **Step 2: 注册严格使用邮箱验证码流**
  不做裸 `username + password -> register`，必须先 `send-code`，再 `register`。

- [ ] **Step 3: 登录返回最小首屏上下文**
  返回 `access_token`、`refresh_token`、`viewer`、`membership`、`limits`，避免前端登录后还要补多次接口才能进主流程。

- [ ] **Step 4: 把 `get_current_user` 与 `get_current_membership` 依赖接到 `main.py`**
  `main.py` 注册新 router，并把 auth/membership repository、token service 注入 `app.state`。

- [ ] **Step 5: 跑接口测试**
  Run: `pytest tests/backend/test_auth_routes.py tests/backend/test_membership_routes.py -q`
  Expected: 覆盖注册、重复用户名、登录、refresh、logout、找回密码、`/me`、`/me/membership`。

### Task 3: 建立当前阶段会员授予机制

**Files:**
- Create: `app_backend/scripts/grant_membership.py`
- Create: `app_backend/scripts/seed_membership_plans.py`
- Optionally Create: `app_backend/api/routes/internal_membership.py`
- Test: `tests/backend/test_membership_grant.py`

- [ ] **Step 1: 先用脚本开会员，不接支付**
  脚本最小参数：`user_id`、`plan_code`、`starts_at`、`expires_at`。

- [ ] **Step 2: 初始化套餐种子**
  至少准备 `basic`、`pro` 两档，限制字段先只保留 `account_limit`、`query_concurrency_limit`、`feature_flags`。

- [ ] **Step 3: 是否送试用保持配置位**
  仅保留 `AUTO_TRIAL_PLAN_CODE` 选项，默认关闭，不直接写死。

- [ ] **Step 4: 跑脚本与 membership 测试**
  Run: `pytest tests/backend/test_membership_grant.py -q`
  Expected: 能给已注册用户授予会员并被 `/me/membership` 读取。

## Chunk 2: 业务资源多租户隔离

### Task 4: 给现有核心资源补 `owner_user_id`

**Files:**
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Modify: `app_backend/infrastructure/repositories/account_repository.py`
- Modify: `app_backend/infrastructure/repositories/query_config_repository.py`
- Modify: `app_backend/infrastructure/repositories/query_settings_repository.py`
- Modify: `app_backend/infrastructure/repositories/account_session_bundle_repository.py`
- Modify: `app_backend/infrastructure/repositories/purchase_ui_preferences_repository.py`
- Modify: `app_backend/infrastructure/repositories/runtime_settings_repository.py`
- Test: `tests/backend/test_account_repository.py`
- Test: `tests/backend/test_query_config_repository.py`
- Test: `tests/backend/test_account_session_bundle_repository.py`

- [ ] **Step 1: 给现有业务表补 `owner_user_id`**
  最低覆盖：`accounts`、`query_configs`、`query_config_items`、`query_mode_settings`、`query_settings_modes`、`account_session_bundles`、`purchase_ui_preferences`、`runtime_settings`。

- [ ] **Step 2: repository 默认只查当前用户**
  所有 `list/get/update/delete` 都必须把 `owner_user_id` 当隐式过滤条件。

- [ ] **Step 3: 老数据归属到内部种子用户**
  迁移策略先简单：把历史单租户数据归到 `system_seed_user`，不做复杂数据切分。

- [ ] **Step 4: 跑 repository 回归**
  Run: `pytest tests/backend/test_account_repository.py tests/backend/test_query_config_repository.py tests/backend/test_account_session_bundle_repository.py -q`
  Expected: A 用户看不到 B 用户数据，老功能不因 owner 迁移失效。

### Task 5: 运行时目录与浏览器环境按用户隔离

**Files:**
- Modify: `app_backend/infrastructure/browser_runtime/account_browser_profile_store.py`
- Modify: `app_backend/infrastructure/browser_runtime/managed_browser_runtime.py`
- Modify: `app_backend/infrastructure/repositories/account_session_bundle_repository.py`
- Test: `tests/backend/test_account_browser_profile_store.py`
- Test: `tests/backend/test_managed_browser_runtime.py`

- [ ] **Step 1: 把 runtime 根目录改成用户维度**
  目标结构：`app-private/users/<user_id>/browser-profiles`、`browser-sessions`、`session-bundles`、`diagnostics`。

- [ ] **Step 2: session bundle 与 profile path 都改成 user root**
  不能再只有 `account_id`，否则不同会员仍会共用环境。

- [ ] **Step 3: 跑运行时路径测试**
  Run: `pytest tests/backend/test_account_browser_profile_store.py tests/backend/test_managed_browser_runtime.py -q`
  Expected: 同账户名但不同用户不会落到同一路径。

## Chunk 3: 业务接口闸门与 Bootstrap 扩展

### Task 6: 给现有 API 与 WebSocket 接入 auth/membership guard

**Files:**
- Modify: `app_backend/api/routes/app_bootstrap.py`
- Modify: `app_backend/application/use_cases/get_app_bootstrap.py`
- Modify: `app_backend/api/schemas/app_bootstrap.py`
- Modify: `app_backend/api/routes/accounts.py`
- Modify: `app_backend/api/routes/account_center.py`
- Modify: `app_backend/api/routes/query_configs.py`
- Modify: `app_backend/api/routes/query_runtime.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Modify: `app_backend/api/routes/runtime_settings.py`
- Modify: `app_backend/api/websocket/runtime.py`
- Modify: `app_backend/api/websocket/accounts.py`
- Modify: `app_backend/api/websocket/tasks.py`
- Test: `tests/backend/test_app_bootstrap_route.py`
- Test: `tests/backend/test_runtime_update_websocket.py`
- Test: `tests/backend/test_account_routes.py`
- Test: `tests/backend/test_query_runtime_routes.py`

- [ ] **Step 1: 所有业务 route 接当前用户依赖**
  V1 起点：未登录直接 `401 auth_required`。

- [ ] **Step 2: 启动类与关键写接口加会员闸门**
  至少限制账号数量上限、查询并发上限、功能开关；错误码统一成 `membership_expired`、`plan_limit_exceeded`、`feature_not_enabled`。

- [ ] **Step 3: 扩展 `/app/bootstrap`**
  新增 `viewer`、`membership`、`limits`，保持现有 `query_system / purchase_system / diagnostics` 不破坏。

- [ ] **Step 4: `ws/runtime` 增加握手鉴权**
  优先支持 `Authorization` header；Electron 不方便时允许 query token fallback。

- [ ] **Step 5: 跑业务闸门测试**
  Run: `pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py tests/backend/test_account_routes.py tests/backend/test_query_runtime_routes.py -q`
  Expected: 未登录不可连、会员过期不可启动主流程、bootstrap 可返回 viewer/membership。

## Chunk 4: Electron Thin Client 鉴权接线

### Task 7: 增加前端 auth client、会话持久化与 HTTP/WS 鉴权

**Files:**
- Create: `app_desktop_web/src/api/auth_client.js`
- Create: `app_desktop_web/src/auth/session_store.js`
- Create: `app_desktop_web/src/auth/auth_state.js`
- Modify: `app_desktop_web/src/api/http.js`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/runtime/runtime_connection_manager.js`
- Modify: `app_desktop_web/electron-preload.cjs`
- Modify: `app_desktop_web/electron-main.cjs`
- Modify: `app_desktop_web/src/desktop/bridge.js`
- Test: `app_desktop_web/tests/renderer/http_client.test.js`
- Test: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`
- Test: `app_desktop_web/tests/renderer/auth_client.test.js`

- [ ] **Step 1: 新增 `auth_client`**
  契约与 `cs2_alchemy/node_sidecar/src/controlPlaneAuthClient.js` 对齐，但 base path 改为当前 FastAPI 路由。

- [ ] **Step 2: 会话存储放 Electron 壳，不直接散落到 renderer**
  推荐：refresh token 由 main/preload bridge 持久化到 `userData`，renderer 只通过 bridge 读写会话。

- [ ] **Step 3: `http.js` 自动带 access token，并在 401 时尝试 refresh**
  refresh 成功则重放请求；失败则清空会话并回到 auth gate。

- [ ] **Step 4: `runtime_connection_manager.js` 补带 token 的 WebSocket URL 或 header**
  连接失败时区分未登录、token 失效、服务不可达。

- [ ] **Step 5: 跑前端 transport 测试**
  Run: `npm --prefix app_desktop_web test -- tests/renderer/http_client.test.js tests/renderer/runtime_connection_manager.test.js tests/renderer/auth_client.test.js`
  Expected: token 注入、refresh 重试、ws 鉴权都可通过。

### Task 8: 只补最小 auth entry，不做最终控制台

**Files:**
- Modify: `app_desktop_web/src/App.jsx`
- Create: `app_desktop_web/src/features/auth/auth_gate.jsx`
- Create: `app_desktop_web/src/features/auth/login_page.jsx`
- Create: `app_desktop_web/src/features/auth/register_page.jsx`
- Create: `app_desktop_web/src/features/auth/reset_password_page.jsx`
- Test: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- Test: `app_desktop_web/tests/renderer/auth_gate.test.jsx`

- [ ] **Step 1: 先加 auth gate，再决定是否进入旧控制台**
  登录前只展示注册、登录、找回密码，不动最终控制台布局。

- [ ] **Step 2: 登录成功后复用现有 bootstrap + runtime websocket**
  这一步只做接线，不做控制台重造。

- [ ] **Step 3: 处理四种首屏阻塞态**
  `未登录`、`服务不可达`、`会员失效`、`服务维护`。

- [ ] **Step 4: 跑 auth entry 测试**
  Run: `npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/auth_gate.test.jsx`
  Expected: 登录前不会请求业务接口，登录后正常进入 bootstrap 流。

## Chunk 5: 打包与交付

### Task 9: 产品态只打包前端壳

**Files:**
- Modify: `app_desktop_web/electron_runtime_mode.cjs`
- Modify: `app_desktop_web/electron-main.cjs`
- Modify: `main_ui_node_desktop.js`
- Create: `app_desktop_web/electron-builder.yml`
- Test: `app_desktop_web/tests/electron/electron_remote_mode.test.js`
- Test: `app_desktop_web/tests/electron/electron_entrypoints.test.js`

- [ ] **Step 1: 产品态固定 remote mode**
  安装包不再尝试启动本地 Python backend，不依赖 `.venv`、`data/app.db`。

- [ ] **Step 2: 固化远端配置注入**
  内置正式 `DESKTOP_API_BASE_URL` 与 `DESKTOP_RUNTIME_WEBSOCKET_URL`，同时保留灰度覆盖能力。

- [ ] **Step 3: 打包 Windows installer 与 portable**
  产物必须能在无 Python 环境机器上直接启动。

- [ ] **Step 4: 跑 Electron 回归**
  Run: `npm --prefix app_desktop_web test -- tests/electron/electron_remote_mode.test.js tests/electron/electron_entrypoints.test.js`
  Expected: remote mode 生效，入口与 bootstrap 配置不回退到 embedded。

### Task 10: 交付前联调与验收

**Files:**
- Modify as needed: `docs/superpowers/specs/2026-04-06-membership-auth-design.md`
- Create: `docs/deployment/membership-thin-client-rollout.md`

- [ ] **Step 1: 跑后端定向回归**
  Run: `pytest tests/backend/test_auth_routes.py tests/backend/test_membership_routes.py tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py -q`

- [ ] **Step 2: 跑前端 remote/auth 回归**
  Run: `npm --prefix app_desktop_web test -- tests/electron/electron_remote_mode.test.js tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/runtime_connection_manager.test.js`

- [ ] **Step 3: 手工验收最小链路**
  `send-code -> register -> login -> bootstrap -> ws/runtime -> logout -> reset password`。

- [ ] **Step 4: 验证会员闸门**
  使用内部脚本授予/取消会员，确认前端提示与后端限制一致。

## Chunk 6: 控制台末阶段计划

### Task 11: 最后再接开源控制台模板

**Files:**
- Create later: `app_desktop_web/src_v2/` 或同级独立页面树

- [ ] **Step 1: 这一步不进入当前执行范围**
  当前只保留 backlog，不在本轮实现。

- [ ] **Step 2: 从 GitHub 选 React admin/template**
  筛选标准：React/Electron 兼容、商用许可清晰、表格表单基础完整、近 6 个月有维护。

- [ ] **Step 3: 集成顺序固定**
  先接 `login`、再接 `/me`、`/me/membership`、`/app/bootstrap`、`/ws/runtime`，最后才替换旧业务页面。

## Milestones

- [ ] **Milestone 1**
  后端 auth 与 membership 表、路由、脚本可用。

- [ ] **Milestone 2**
  所有核心资源完成 `owner_user_id` 隔离，`bootstrap` 与 `ws/runtime` 带鉴权。

- [ ] **Milestone 3**
  Electron 登录壳、session 持久化、401 refresh、remote-only 打包可用。

- [ ] **Milestone 4**
  再进入 GitHub 开源控制台模板选型与接线。

## Risks

- 当前代码是单租户默认假设，`owner_user_id` 改造面广，容易漏仓储与运行时路径。
- `ws/runtime` 若不先定鉴权策略，前端登录态和实时态会长期分裂。
- 若把最终控制台过早推进，会反向绑死接口契约，导致 auth/membership 重构返工。
- 若 refresh token 直接放 renderer 明文存储，桌面壳安全边界过弱。
- 不做支付并不影响当前阶段，但必须先准备内部授予脚本，否则无法验证会员闸门。

## Acceptance Criteria

- 用户可以完成邮箱验证码注册、用户名密码登录、登出、refresh、找回密码。
- `/me`、`/me/membership`、`/app/bootstrap` 能返回当前用户与会员摘要。
- 会员过期或无权限时，后端主流程接口与 `ws/runtime` 会被拒绝。
- 不同用户的数据、session bundle、browser profile、runtime 目录完全隔离。
- Electron 安装包只依赖远端 API，不再启动本地 Python backend。
- 当前阶段不接支付也能通过内部脚本完成会员开通与验收。
