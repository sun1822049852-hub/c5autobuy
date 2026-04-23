# Program Access Registration V3 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把程序账号注册从旧的“一屏式发码+注册”落到真实可用的三步流，并让 `main_ui_node_desktop.js` 打开的真实桌面链路按 `registration_flow_version` 在 v2/v3 之间正确切换。

**Architecture:** 保持“本地桌面只做代理、远端控制面统一鉴权”的既有结构不变，只补齐当前断掉的真实桌面链路。先锁定本地后端 `program_access` summary、`/program-auth/*` 本地代理与远端 client 的 v3 契约，再把 renderer client/provider/sidebar dialog 接到同一能力开关与三步状态机上，继续保留旧 v2 fallback，直到远端 rollout 完成。

**Tech Stack:** Python 3.11 + FastAPI + Pydantic + pytest；React 19 + Vitest；Electron renderer bootstrap；Node control-plane contract

---

## Chunk 1: Lock The Missing Local Registration V3 Contract

### Task 1: 锁定本地后端 summary 与路由契约红灯

**Files:**
- Modify: `tests/backend/test_app_bootstrap_route.py`
- Modify: `tests/backend/test_program_auth_routes.py`

- [x] **Step 1: 为 `/app/bootstrap` 与 `/program-auth/status` 写失败断言**

锁定 `program_access` / `ProgramAuthStatusResponse` 必须包含 `registration_flow_version`，并在 packaged-release 场景可返回 `3`。

- [x] **Step 2: 为本地 `/program-auth/register/verify-code` 与 `/program-auth/register/complete` 写失败路由测试**

锁定三件事：
- 本地必须存在这两个新路由；
- `verify-code` 成功响应必须携带 `verification_ticket`；
- `complete` 成功后必须沿用现有登录摘要链，回到“账号已创建，但当前未开通会员”。

- [x] **Step 3: 运行 focused backend tests，确认红灯来自缺字段/缺路由**

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_program_auth_routes.py -q`

Expected: FAIL，失败点落在 `registration_flow_version` 缺失，以及本地 `verify-code` / `complete` 路由尚未接入。

### Task 2: 锁定本地远端转发 client 与 gateway 红灯

**Files:**
- Modify: `tests/backend/test_remote_control_plane_client.py`
- Modify: `tests/backend/test_remote_entitlement_gateway.py`

- [x] **Step 1: 为 `RemoteControlPlaneClient` 写失败测试**

锁定以下映射：
- `send_register_code()` 走远端 `/api/auth/register/send-code`
- 新增 `verify_register_code()` 走远端 `/api/auth/register/verify-code`
- 新增 `complete_register()` 走远端 `/api/auth/register/complete`

- [x] **Step 2: 为 `RemoteEntitlementGateway` 写失败测试**

锁定 gateway 必须：
- 把 `registration_flow_version` 写进 summary；
- 暴露 `verify_register_code()` 与 `complete_register()`；
- 保留旧 `register()` 作为 v2 fallback。

- [x] **Step 3: 运行 focused backend tests，确认红灯来自 client/gateway 缺方法**

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_remote_control_plane_client.py tests/backend/test_remote_entitlement_gateway.py -q`

Expected: FAIL，失败点落在远端路径仍指向旧 `/api/auth/email/send-code` / `/api/auth/register`，且本地 gateway 尚未暴露 v3 bridge。

## Chunk 2: Implement The Local Backend Registration V3 Bridge

### Task 3: 扩展共享 summary、schema 与本地路由契约

**Files:**
- Modify: `app_backend/application/program_access.py`
- Modify: `app_backend/api/schemas/app_bootstrap.py`
- Modify: `app_backend/api/schemas/program_auth.py`
- Modify: `app_backend/api/routes/program_auth.py`
- Modify: `app_backend/infrastructure/program_access/local_pass_through_gateway.py`
- Modify: `app_backend/infrastructure/program_access/cached_program_access_gateway.py`

- [x] **Step 1: 给 `ProgramAccessSummary` 与 bootstrap/program-auth schema 加上 `registration_flow_version`**
- [x] **Step 2: 给 program-access gateway protocol 加上 `verify_register_code()` 与 `complete_register()`**
- [x] **Step 3: 在本地 pass-through / cached gateway 上补齐 not-ready fallback**
- [x] **Step 4: 在 FastAPI `/program-auth/*` 下接出 `verify-code` 与 `complete`，并返回前端需要的结构**
- [x] **Step 5: 回跑 Chunk 1 的 backend tests，确认转绿**

### Task 4: 接通远端 control-plane client 与 remote entitlement gateway

**Files:**
- Modify: `app_backend/infrastructure/program_access/remote_control_plane_client.py`
- Modify: `app_backend/infrastructure/program_access/remote_entitlement_gateway.py`

- [x] **Step 1: 把 `send_register_code()` 改到 `/api/auth/register/send-code`**
- [x] **Step 2: 新增 `verify_register_code()` 与 `complete_register()`，按远端 v3 响应解析票据与注册结果**
- [x] **Step 3: 在 `RemoteEntitlementGateway` 中实现 v3 action bridge，并根据远端 readiness 产出 `registration_flow_version`**
- [x] **Step 4: 保留旧 `register()`，只作为 `registration_flow_version != 3` 的 fallback**
- [x] **Step 5: 回跑 client/gateway tests，确认转绿**

## Chunk 3: Lock The Renderer Registration V3 Behavior

### Task 5: 锁定 renderer client/provider 的红灯

**Files:**
- Modify: `app_desktop_web/tests/renderer/program_auth_client.test.js`
- Modify: `app_desktop_web/tests/renderer/program_access_provider.test.jsx`

- [x] **Step 1: 保持现有红灯断言，锁定 renderer client 必须暴露 v3 方法**
- [x] **Step 2: 保持现有红灯断言，锁定 provider 只有在 `registration_flow_version=3` 时才暴露 v3 actions**
- [x] **Step 3: 运行 focused renderer bridge tests，确认失败原因仍是 client/provider 缺实现**

Run: `npm --prefix app_desktop_web test -- --run tests/renderer/program_auth_client.test.js tests/renderer/program_access_provider.test.jsx`

Expected: FAIL，失败点落在 `verifyRegisterCode` / `completeRegisterProgramAuth` 缺失，以及 provider 未按能力开关暴露 v3 actions。

### Task 6: 锁定三步注册 UI state machine 的红灯

**Files:**
- Modify: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`

- [x] **Step 1: 保持现有红灯断言，锁定 `registration_flow_version=3` 时第一步只显示邮箱页**
- [x] **Step 2: 锁定验证码通过前不得出现“注册用户名 / 注册密码”**
- [x] **Step 3: 锁定 `registration_flow_version=2` 时旧一屏式注册 UI 继续存在**
- [x] **Step 4: 运行 focused renderer UI tests，确认失败原因仍是旧表单未拆步**

Run: `npm --prefix app_desktop_web test -- --run tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/app_remote_bootstrap.test.jsx`

Expected: FAIL，失败点落在 v3 场景下仍直接渲染旧 `注册验证码 / 注册用户名 / 注册密码` 字段。

## Chunk 4: Implement The Renderer Registration V3 State Machine

### Task 7: 接通 renderer client、runtime summary 与 provider gating

**Files:**
- Modify: `app_desktop_web/src/api/program_auth_client.js`
- Modify: `app_desktop_web/src/program_access/program_access_runtime.js`
- Modify: `app_desktop_web/src/program_access/program_access_provider.jsx`
- Modify: `app_desktop_web/src/App.jsx`

- [x] **Step 1: 在 renderer client 上新增 `verifyRegisterCode()` 与 `completeRegisterProgramAuth()`**
- [x] **Step 2: 在 runtime normalization 中接收 `registration_flow_version`**
- [x] **Step 3: 在 provider 中按 `registration_flow_version` 暴露/隐藏 v3 actions，同时保留 v2 fallback**
- [x] **Step 4: 在 `App.jsx` 把新增 provider actions 传进 dialog 组件**
- [x] **Step 5: 回跑 bridge tests，确认转绿**

### Task 8: 把注册弹窗从旧一屏式表单改成三步状态机

**Files:**
- Modify: `app_desktop_web/src/program_access/program_access_sidebar_card.jsx`
- Modify: `app_desktop_web/src/styles/app.css` (only if current dialog layout needs minimal state-specific styling)

- [x] **Step 1: 为注册流新增 `register_email / register_code / register_credentials / register_success` 本地状态**
- [x] **Step 2: v3 第一页只保留邮箱输入与“下一步”，通过 `sendRegisterCode()` 进入验证码页**
- [x] **Step 3: 第二页接入 `verifyRegisterCode()`、重发验证码、修改邮箱与冷却展示**
- [x] **Step 4: 第三页接入 `completeRegisterProgramAuth()`，成功后复用既有“已登录/当前状态”落点**
- [x] **Step 5: `registration_flow_version != 3` 时保留旧一屏式注册 UI，不改找回密码与登录流程**
- [x] **Step 6: 回跑 UI tests，确认转绿**

## Chunk 5: Verification, Logging, And Handoff

### Task 9: 跑受影响验证并写断点记录

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if this round creates a new stable project rule)
- Modify: `docs/superpowers/plans/2026-04-22-program-access-registration-v3-implementation.md`

- [x] **Step 1: 跑 backend verification**

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_program_auth_routes.py tests/backend/test_remote_control_plane_client.py tests/backend/test_remote_entitlement_gateway.py -q`

- [x] **Step 2: 跑 renderer verification**

Run: `npm --prefix app_desktop_web test -- --run tests/renderer/program_auth_client.test.js tests/renderer/program_access_provider.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/app_remote_bootstrap.test.jsx`

- [x] **Step 3: 如 control-plane contract touched，再跑 Node verification**

Run: `npm --prefix program_admin_console run test:server`

- [x] **Step 4: 更新 session log，写清本会话做到哪一 chunk/task、已验证结果、未完成断点与下一步**
- [x] **Step 5: 只在形成新的稳定约束时更新 memory；否则明确说明本轮无需改 memory**
- [x] **Step 6: 按真实进度勾选本计划中的已完成步骤，确保新会话可直接接续**
