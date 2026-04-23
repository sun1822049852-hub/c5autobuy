# Program Access Registration V3 Rollout Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 只通过远端部署把注册 v3 真正上线，让 `main_ui_node_desktop.js` 的正式桌面入口切到三步注册 UI。

**Architecture:** 保持“桌面端按 readiness 决定 v2/v3”的既有灰度逻辑不变，不再改 renderer、本地 backend 或 release 配置。唯一动作是将当前仓库中的 `program_admin_console` 最小发布到 `8.138.39.139:18787`，并用远端接口、桌面 bootstrap、真人 UI 三段证据闭环验证。

**Tech Stack:** Node.js control plane, Docker, ECS/SSH rollout, Electron desktop bootstrap verification

---

## Chunk 1: Freeze Root Cause And Rollout Boundary

### Task 1: 复核“不是前端未实现，而是远端未部署”

**Files:**
- Modify: `docs/superpowers/specs/2026-04-23-program-access-registration-v3-rollout-design.md`
- Modify: `docs/agent/session-log.md`

- [x] **Step 1: 复核正式远端 readiness 现网结果**

Run: `curl http://8.138.39.139:18787/api/auth/register/readiness`

Expected: 当前仍返回 `404 route not found`，从而确认现网仍是旧控制面。

- [x] **Step 2: 复核本地仓库控制面源码已具备 v3 路由**

Run: `rg -n "/api/auth/register/readiness|/api/auth/register/send-code|/api/auth/register/verify-code|/api/auth/register/complete" program_admin_console/src/server.js`

Expected: 命中四个 v3 路由落点，证明问题在部署，不在缺实现。

- [x] **Step 3: 冻结 rollout 边界**

明确本次只部署 `program_admin_console`，不再改 renderer、本地 backend、登录入口、找回密码入口与主业务主链。

## Chunk 2: Prepare A Minimal And Revertible Release Unit

### Task 2: 在本地验证控制面发布包

**Files:**
- Modify: `docs/superpowers/plans/2026-04-23-program-access-registration-v3-rollout.md`

- [x] **Step 1: 跑 control-plane fresh verification**

Run: `npm --prefix program_admin_console test`

Expected: PASS

- [x] **Step 2: 生成仅包含 `program_admin_console` 的发布包**

Run: `tar -cf <rollout-tar> -C program_admin_console .`

Expected: tar 成功生成，且不夹带仓库其它模块。

- [x] **Step 3: 通过 SSH 登录远端并确认旧容器 / 旧镜像 / 挂载信息**

Run: `ssh admin@8.138.39.139 ...`

Expected: 能看到 `c5-program-admin`、`18787->8787`、数据卷与 key 挂载。

- [x] **Step 4: 在远端保留源码备份与旧镜像 tag**

Expected: 远端存在可直接回退的源码目录与旧镜像别名。

## Chunk 3: Roll Out The New Control Plane Container

### Task 3: 上传源码并构建新镜像

**Files:**
- Modify: `docs/agent/session-log.md`

- [x] **Step 1: 把最小发布包上传到远端工作目录**
- [x] **Step 2: 解包覆盖到 `c5-program-admin-src` 的新版本目录**
- [x] **Step 3: 用 Docker 在远端构建新的 `c5-program-admin` 镜像**

Expected: 镜像构建成功，旧容器仍继续提供服务，停机尚未开始。

### Task 4: 短停机切换 `18787` 上的控制面容器

**Files:**
- Modify: `docs/agent/session-log.md`

- [x] **Step 1: 停掉并移除旧 `c5-program-admin` 容器**
- [x] **Step 2: 用原端口、原 volume、原 key mount、原 SMTP env 启动新容器**
- [ ] **Step 3: 若启动失败，立即按旧镜像 tag 回退**

Expected: 新容器取代旧容器，对外继续监听 `http://8.138.39.139:18787`。

## Chunk 4: Prove The Real Desktop Path Has Switched To V3

### Task 5: 验证远端与桌面 bootstrap

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if new stable rollout rule emerges)

- [x] **Step 1: 验远端 readiness 不再 404**

Run: `curl http://8.138.39.139:18787/api/auth/register/readiness`

Expected: 返回 readiness JSON，且 `registration_flow_version=3`

- [x] **Step 2: 验远端 send-code 路由不再 404**

Run: `curl -X POST http://8.138.39.139:18787/api/auth/register/send-code ...`

Expected: 返回业务错误或成功包络，但不能再是 `route not found`

- [x] **Step 3: 验正式桌面 backend bootstrap 切到 v3**

Run: `curl http://127.0.0.1:<main_backend_port>/app/bootstrap`

Expected: `remote_entitlement / packaged_release / registration_flow_version=3`

- [ ] **Step 4: 记录真人 UI 点验结论**

Expected: 首屏只显示邮箱；验码前不出现账号名/密码字段。

## Chunk 5: Sync Handoff Records Truthfully

### Task 6: 按真实进度更新记录

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/superpowers/plans/2026-04-23-program-access-registration-v3-rollout.md`
- Modify: `docs/superpowers/specs/2026-04-23-program-access-registration-v3-rollout-design.md` (only if rollout boundary changes)

- [x] **Step 1: 追加 session-log，写清已完成、验证结果、剩余阻塞、下一步**
- [x] **Step 2: 按实际状态勾选本计划中的 chunk/task**
- [x] **Step 3: 只有形成新的稳定规则时才更新 memory；否则明确本轮无需改 memory**

Expected: 下个会话先读 `spec + plan + session-log` 即可从断点继续。
