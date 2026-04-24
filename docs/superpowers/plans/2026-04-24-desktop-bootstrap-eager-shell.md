# Desktop Bootstrap Eager Shell Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让桌面程序在 embedded backend 尚未 ready 时先进入主界面壳，backend ready 后再自动接管真实数据加载。

**Architecture:** Electron 主进程不再把 renderer 首次加载卡在 `/health` 之后，而是先加载 renderer，并通过 IPC 把 bootstrap 配置变更推送给前端。前端在 `backendStatus !== "ready"` 时只渲染主界面壳与启动中占位，等主进程推送 ready 配置后再初始化 bootstrap/client/page data。

**Tech Stack:** Electron main/preload IPC、React、Vitest、Testing Library

---

## Chunk 1: Bootstrap Push Contract

### Task 1: 锁定主进程 eager shell 启动行为

**Files:**
- Modify: `app_desktop_web/tests/electron/program_access_packaging.test.js`
- Modify: `app_desktop_web/electron-main.cjs`

- [ ] **Step 1: 写 failing test**
- [ ] **Step 2: 跑 electron focused test，确认当前仍先走 loading 而失败**
  Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js --run`
- [ ] **Step 3: 最小实现主进程 eager shell 启动与 bootstrap 更新推送**
- [ ] **Step 4: 重跑 focused test，确认转绿**
- [ ] **Step 5: 回读关键实现，确认没有把 startup failure / packaged release 语义改坏**

### Task 2: 建立 preload/renderer bootstrap 订阅入口

**Files:**
- Modify: `app_desktop_web/electron-preload.cjs`
- Modify: `app_desktop_web/src/desktop/bridge.js`

- [ ] **Step 1: 写/补 renderer 侧使用订阅入口的 failing test**
- [ ] **Step 2: 跑对应 renderer focused test，确认缺少订阅能力而失败**
- [ ] **Step 3: 实现 preload 暴露 `subscribeBootstrapConfig()` 与 bridge 封装**
- [ ] **Step 4: 重跑 focused test，确认转绿**

## Chunk 2: Renderer Startup Gate

### Task 3: 锁定 renderer “先亮壳、后接数据” 行为

**Files:**
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] **Step 1: 写 failing test：初始 `backendStatus=starting` 时先显示启动中壳且不请求首页数据，收到 ready 更新后再触发 `/app/bootstrap` 与首页请求**
- [ ] **Step 2: 跑 renderer focused test，确认当前行为失败**
  Run: `npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx --run`
- [ ] **Step 3: 最小实现 App 内 bootstrapConfig 订阅、启动中占位、ready 后再创建 client/manager 并渲染页面**
- [ ] **Step 4: 重跑 focused test，确认转绿**
- [ ] **Step 5: 复核 remote mode 现有 ready 行为不回退**

## Chunk 3: Verification And Record

### Task 4: 运行针对性验证并回写记录

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: 跑 electron focused tests**
  Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js --run`
- [ ] **Step 2: 跑 renderer focused tests**
  Run: `npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx --run`
- [ ] **Step 3: 跑受影响回归**
  Run: `npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx tests/renderer/app_state_persistence.test.jsx tests/renderer/app_remote_bootstrap.test.jsx --run`
- [ ] **Step 4: 跑构建验证**
  Run: `npm --prefix app_desktop_web run build`
- [ ] **Step 5: 更新 `docs/agent/session-log.md`，记录本轮目标、改动、验证结果与剩余风险**
