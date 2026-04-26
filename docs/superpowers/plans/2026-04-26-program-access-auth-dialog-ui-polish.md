# Program Access Auth Dialog UI Polish Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收口程序账号登录 / 注册 / 找回密码弹窗的一轮 UI 与交互细化，只改 renderer 弹窗壳层、文案与前端状态机，不动后端接口与主业务主链。

**Architecture:** 保持 `ProgramAccessSidebarCard` 作为唯一交互入口，先用 renderer 测试冻结“只允许点 X 关闭、文案更新、注册邮箱保留、修改邮箱可取消返回、固定尺寸”这些契约，再做最小 JSX / state / CSS 修改。样式层通过固定 dialog shell 尺寸和内部滚动稳定视图，避免内容切换时弹窗跳动。

**Tech Stack:** React 19, Vitest, Testing Library, existing app CSS

---

### Task 1: Freeze Renderer Contracts

**Files:**
- Modify: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`

- [x] **Step 1: 改测试文案与交互预期**

覆盖以下行为：
- backdrop 点击不关闭，只有 `X` 可关闭
- 登录区标题 / 按钮 / placeholder 文案更新
- 注册修改邮箱后回到邮箱页时出现 `取消`，可返回验证码页
- 注册切到登录/找回密码再切回注册时邮箱仍保留
- dialog root 暴露固定尺寸 shell 契约

- [x] **Step 2: 补齐测试锚点，锁定后续实现必须满足的可观测契约**

Run: `npm --prefix app_desktop_web test -- program_access_sidebar_card.test.jsx`

### Task 2: Implement Minimal Dialog Changes

**Files:**
- Modify: `app_desktop_web/src/program_access/program_access_sidebar_card.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [x] **Step 1: 调整 dialog 关闭语义**

移除 backdrop 点击关闭，只保留显式 `X` 关闭入口。

- [x] **Step 2: 调整登录文案与标题显示**

把登录按钮与 placeholder 改成新文案，并收掉左上角重复“程序账号”。

- [x] **Step 3: 调整注册状态机**

让“修改邮箱”进入可返回的邮箱编辑页；从注册切到其他 tab 时保留邮箱值，不再无条件清空。

- [x] **Step 4: 固定 dialog 尺寸**

为 dialog shell 增加固定尺寸 class / 布局约束，内容区内部滚动，移动端保底可用。

### Task 3: Verify And Record

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `README.md` (only if this round changes user-facing collaboration/usage docs; otherwise note that README was checked and not changed)

- [x] **Step 1: 跑聚焦测试确认绿灯**

Run: `npm --prefix app_desktop_web test -- program_access_sidebar_card.test.jsx`

- [x] **Step 2: 回写会话日志并核对 README**

记录本轮做了什么、当前状态、下一步；若 README 无需改动，交付时明确说明已核对无需修改。
