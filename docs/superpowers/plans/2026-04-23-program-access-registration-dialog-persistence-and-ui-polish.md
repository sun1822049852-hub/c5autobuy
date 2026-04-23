# Program Access Registration Dialog Persistence And UI Polish Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让程序账号注册第二段验证码页在当前 renderer 会话内可恢复，并完成默认告警过滤、输入框 placeholder 化与关闭按钮样式收口。

**Architecture:** 只修改 `ProgramAccessSidebarCard` 与其 renderer 测试、样式文件，不改 provider、远端接口和后端状态机。行为上把“关闭弹窗/切页面”从注册流重置条件中移除，但保留“主动切换到登录/找回密码、修改邮箱、注册完成”时的清理语义。

**Tech Stack:** React 19 + Vitest + Testing Library + CSS

---

## Chunk 1: Lock The Dialog Behavior And Visual Contract

### Task 1: 为注册第二段保持与告警过滤补红灯

**Files:**
- Modify: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`

- [x] **Step 1: 写失败测试，锁定关闭弹窗后重新打开仍回到第二段验证码页**

断言以下行为：
- 发码成功后进入第二段验证码页
- 点击右上角关闭按钮关闭弹窗
- 重新打开程序账号弹窗后仍停留在第二段
- 脱敏邮箱仍显示
- “重新发送验证码 (60s)” 仍显示当前倒计时文案

- [x] **Step 2: 写失败测试，锁定主动切回登录标签会清空注册草稿**

断言以下行为：
- 发码成功后进入第二段
- 点击“登录”标签
- 再点击“注册”标签时回到第一段邮箱页

- [x] **Step 3: 写失败测试，锁定默认 `program_auth_required` 不再显示**

断言以下行为：
- `lastProgramAuthError.code = "program_auth_required"` 时，不渲染错误码与默认提示文本
- 其它非默认错误仍继续显示

- [x] **Step 4: 运行 focused test，确认红灯来自现有关闭即重置与无差别告警渲染**

Run: `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`

Expected: FAIL，失败点落在关闭后被重置、切回注册仍停第一段、以及默认 program auth 告警仍显示。

### Task 2: 为 placeholder 与关闭按钮视觉契约补红灯

**Files:**
- Modify: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`

- [x] **Step 1: 写失败测试，锁定登录/注册输入框具备 placeholder**

至少覆盖：
- 登录账号输入框 placeholder
- 登录密码输入框 placeholder
- 注册邮箱输入框 placeholder
- 第二段验证码输入框 placeholder

- [x] **Step 2: 写失败测试，锁定关闭按钮文本为 `X` 且访问名仍为“关闭”**

- [x] **Step 3: 再次运行 focused test，确认红灯来自视觉契约缺失**

Run: `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`

Expected: FAIL，失败点落在缺少 placeholder 与关闭按钮文本仍为“关闭”。

## Chunk 2: Implement The Minimal Dialog Changes

### Task 3: 实现注册草稿保持与默认告警过滤

**Files:**
- Modify: `app_desktop_web/src/program_access/program_access_sidebar_card.jsx`

- [x] **Step 1: 把“关闭弹窗”与“主动离开注册模式”的重置逻辑拆开**

- [x] **Step 2: 关闭弹窗时只清理本地 notice/error，不清空第二段注册草稿**

- [x] **Step 3: 保留以下动作的显式重置**
- 点击“修改邮箱”
- 从注册切到登录/找回密码
- 注册完成

- [x] **Step 4: 过滤 `program_auth_required` 默认告警，只保留真实异常**

- [x] **Step 5: 回跑 focused test，确认行为红灯转绿**

### Task 4: 实现输入框 placeholder 与关闭按钮样式收口

**Files:**
- Modify: `app_desktop_web/src/program_access/program_access_sidebar_card.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [x] **Step 1: 为登录/注册/找回密码输入框补 placeholder，保留 `aria-label`**

- [x] **Step 2: 移除外置字段标题的视觉渲染，不改布局结构以外的逻辑**

- [x] **Step 3: 把输入框背景改为浅色背景，并收口 placeholder 颜色**

- [x] **Step 4: 把关闭按钮改成红底正方形 `X`，保留访问名“关闭”**

- [x] **Step 5: 回跑 focused test，确认视觉契约红灯转绿**

## Chunk 3: Verification And Handoff

### Task 5: 跑受影响 renderer 验证并同步记录

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if this round creates a stable reusable rule)
- Modify: `docs/superpowers/plans/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish.md`

- [x] **Step 1: 跑 focused component test**

Run: `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`

Expected: PASS

- [x] **Step 2: 跑 renderer 全量回归**

Run: `npm --prefix app_desktop_web test -- tests/renderer --run`

Expected: PASS

- [x] **Step 3: 重新构建 renderer**

Run: `npm --prefix app_desktop_web run build`

Expected: `vite build` 成功

- [x] **Step 4: 更新 session log，写清本轮 spec/plan、已改行为、验证结果与下一步人工点验**

- [x] **Step 5: 只有形成新的稳定约束时才更新 memory**

- [x] **Step 6: 按真实执行进度勾选本计划中的步骤**
