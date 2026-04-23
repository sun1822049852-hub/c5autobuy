# Program Access Registration Cooldown Hard Lock And Email Validation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复程序账号注册发码链路中“改邮箱绕过 60 秒冷却”和“明显不完整邮箱仍可发码”两个问题，并保持 renderer 与本地 backend 对失败冷却的展示一致。

**Architecture:** 只在受影响的三层做最小修复：远端 control-plane 负责真正的发码硬冷却与邮箱校验；本地 backend 负责把 program access 稳定 `device_id` 作为远端 `install_id` 透传给注册三接口，并把失败冷却字段透传给 renderer；renderer 负责保留和展示冷却，不再因“修改邮箱”把它清空。保持现有三步注册状态机和已完成的注册 v3 接口不变。

**Tech Stack:** Node.js control-plane server + SQLite store；FastAPI local backend；React + Vitest renderer

---

## Chunk 1: Lock The Regressions With Failing Tests

### Task 1: 锁定 renderer 的冷却保留与失败冷却覆盖

**Files:**
- Modify: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`

- [x] **Step 1: 写失败测试，锁定点击“修改邮箱”后仍保留剩余冷却**
- [x] **Step 2: 写失败测试，锁定 `REGISTER_SEND_RETRY_LATER` 的 `retry_after_seconds` 会覆盖前端冷却**
- [x] **Step 3: 运行 focused renderer test，确认红灯**

Run: `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`

### Task 2: 锁定 control-plane 的设备级 60 秒硬冷却与邮箱 typo 拦截

**Files:**
- Modify: `program_admin_console/tests/control-plane-server.test.js`

- [x] **Step 1: 写失败测试，锁定同一安装实例 60 秒内换邮箱再次发码仍返回 `REGISTER_SEND_RETRY_LATER`**
- [x] **Step 2: 写失败测试，锁定 `1822049852@qq.CO` 返回 `REGISTER_INPUT_INVALID`**
- [x] **Step 3: 运行 focused control-plane test，确认红灯**

Run: `npm --prefix program_admin_console run test:server`

### Task 3: 锁定本地 backend 错误包络透传 `retry_after_seconds`

**Files:**
- Modify: `tests/backend/test_remote_entitlement_gateway.py`
- Modify: `tests/backend/test_program_auth_routes.py`

- [x] **Step 1: 写失败测试，锁定 gateway 在远端限流时保留 `retry_after_seconds` payload**
- [x] **Step 2: 写失败测试，锁定 `/program-auth/register/send-code` 错误 detail 带出 `retry_after_seconds`**
- [x] **Step 3: 运行 focused backend tests，确认红灯**

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_auth_routes.py -q`

## Chunk 2: Implement The Minimal Fixes

### Task 4: 实现 control-plane 的邮箱校验收口与安装实例 60 秒硬冷却

**Files:**
- Modify: `program_admin_console/src/server.js`

- [x] **Step 1: 收紧邮箱校验，并增加明确的常见 typo 域名拦截（首刀至少覆盖 `qq.co`）**
- [x] **Step 2: 在 `evaluateRegisterSendLimits()` 中加入同安装实例 60 秒 1 次的硬冷却**
- [x] **Step 3: 保持现有邮箱/IP/设备/会话限流逻辑不被回退**
- [x] **Step 4: 回跑 control-plane test，确认转绿**

### Task 5: 实现本地 backend 对失败冷却字段的透传

**Files:**
- Modify: `app_backend/api/routes/program_auth.py`
- Modify: `app_backend/infrastructure/program_access/remote_control_plane_client.py`
- Modify: `app_backend/infrastructure/program_access/remote_entitlement_gateway.py`

- [x] **Step 1: 在 route 错误 detail 中透传 `ProgramAccessActionResult.payload`**
- [x] **Step 2: 在 remote gateway 的 route-only 错误映射里保留 `RemoteControlPlaneError.payload.retry_after_seconds`**
- [x] **Step 3: 在 remote control-plane client 中兼容 v3 `error_code`，并把稳定 `device_id` 作为 `install_id` 透传到 send/verify/complete**
- [x] **Step 4: 回跑 focused backend tests，确认转绿**

### Task 6: 实现 renderer 的冷却保留与失败冷却展示

**Files:**
- Modify: `app_desktop_web/src/program_access/program_access_sidebar_card.jsx`

- [x] **Step 1: 扩展错误解析，读出 `retry_after_seconds`**
- [x] **Step 2: 点击“修改邮箱”时回到第一步但保留当前冷却**
- [x] **Step 3: 第一页在剩余冷却期间禁用发码按钮**
- [x] **Step 4: 命中 `REGISTER_SEND_RETRY_LATER` 时用失败响应刷新剩余冷却**
- [x] **Step 5: 回跑 focused renderer test，确认转绿**

## Chunk 3: Verification And Logging

### Task 7: 跑受影响验证并同步记录

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if this round creates a new stable rule)
- Modify: `docs/superpowers/specs/2026-04-23-program-access-registration-cooldown-hard-lock-and-email-validation-design.md` (if implementation changes the final design)
- Modify: `docs/superpowers/plans/2026-04-23-program-access-registration-cooldown-hard-lock-and-email-validation.md`

- [x] **Step 1: 跑 focused backend verification**

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_auth_routes.py -q`

- [x] **Step 2: 跑 focused control-plane verification**

Run: `npm --prefix program_admin_console run test:server`

- [x] **Step 3: 跑 focused renderer verification**

Run: `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`

- [x] **Step 4: 跑受影响回归**

Run: `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/program_access_provider.test.jsx tests/renderer/program_auth_client.test.js --run`

- [x] **Step 5: 更新 session log，写清 bug 根因、已修范围、验证结果与剩余风险**
- [x] **Step 6: 只有形成新的稳定项目约束时才更新 memory**
- [x] **Step 7: 按真实执行进度勾选计划**
