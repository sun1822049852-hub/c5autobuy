# Embedded Runtime Push For Local Desktop Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让本地 `embedded` 桌面模式也消费现有 `/ws/runtime` 运行态推送，并移除扫货页 steady-state `1.5s` 轮询，避免把后台状态刷新误报成“后端卡死”。

**Architecture:** 保留现有 `bootstrap snapshot + /health ready gate`，只把 steady-state runtime 同步改成 `push 主导 + resync 兜底`。Electron 主进程在 embedded backend ready 后把本地 `runtimeWebSocketUrl` 注入 bootstrap config；renderer 只要拿到非空 websocket URL 就接入 `runtime_connection_manager`，不再按 `backendMode === "remote"` 硬门禁。`purchase-system` 页面继续保留首次 bootstrap / 手动动作后的补拉，但删除常态 `setInterval` 轮询；运行中状态改由 runtime store 吃推送更新。

**Tech Stack:** React 19, Electron, FastAPI, WebSocket, Vitest, Python 3.11, pytest

---

## Scope

### In Scope
- 本地 `embedded` 模式注入并消费 `runtimeWebSocketUrl`
- `App.jsx` 顶层 runtime push 接入条件放宽到“有 ws URL 就接”
- `purchase-system` steady-state 从 polling 改为 push + resync
- 保持 draft/UI state 不丢
- 保持启动期 `/health -> ready=true` gate 不变

### Out Of Scope
- 诊断页 `/diagnostics/sidebar` 的单独轮询架构
- query-system 全量 push 改造
- 修改 `/health` 语义
- 全局删除超时错误；本计划只消除 purchase steady-state 对这类超时的常态依赖

## File Map

- Modify: `app_desktop_web/electron-main.cjs`
  - embedded backend ready 后写入本地 `runtimeWebSocketUrl`
- Modify: `app_desktop_web/electron_runtime_mode.cjs`
  - 明确 embedded bootstrap config 的 ws 字段行为
- Modify: `app_desktop_web/src/App.jsx`
  - 放宽 runtime push 接入门槛，不再只限 `remote`
- Modify: `app_desktop_web/src/runtime/runtime_connection_manager.js`
  - 如有必要，补 embedded 断线/resync 测试缺口；原则上复用现有 stale/reconnect/resync 逻辑
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
  - 删除 steady-state `setInterval` 轮询，改为 store/runtime push 驱动
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
  - 如有需要，仅保留手动刷新/错误展示与 push 语义一致的 UI 收口
- Modify: `app_desktop_web/tests/electron/electron_remote_mode.test.js`
  - 扩展 embedded bootstrap config 断言
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
  - 增补 embedded runtime websocket bootstrap 用例
- Modify: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`
  - 补本地 runtime ws 接入 / stale / resync 断言
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
  - 删除对 polling 的依赖，改测 push 驱动与 draft 保活
- Reference: `docs/superpowers/plans/2026-03-31-remote-runtime-thin-client.md`
- Reference: `docs/superpowers/specs/2026-04-02-remote-runtime-state-sync-design.md`

## Chunk 1: Expose Embedded Runtime WebSocket

### Task 1: Add failing coverage for embedded bootstrap runtime websocket

**Files:**
- Modify: `app_desktop_web/electron-main.cjs`
- Modify: `app_desktop_web/electron_runtime_mode.cjs`
- Modify: `app_desktop_web/tests/electron/electron_remote_mode.test.js`
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`

- [ ] **Step 1: Write the failing Electron/bootstrap tests**

```js
it("publishes a local runtimeWebSocketUrl after embedded backend becomes ready", async () => {
  const config = await startDesktopAndGetBootstrapConfig({
    backendMode: "embedded",
    backendBaseUrl: "http://127.0.0.1:8123",
  });
  expect(config.runtimeWebSocketUrl).toBe("ws://127.0.0.1:8123/ws/runtime");
});

it("allows the renderer to keep the embedded runtime websocket url from desktop bootstrap", async () => {
  const payload = desktopHarness.emitReadyBootstrap({
    backendMode: "embedded",
    apiBaseUrl: "http://127.0.0.1:8123",
    runtimeWebSocketUrl: "ws://127.0.0.1:8123/ws/runtime",
  });
  expect(payload.runtimeWebSocketUrl).toContain("/ws/runtime");
});
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run:

```powershell
npm --prefix app_desktop_web test -- `
  tests/electron/electron_remote_mode.test.js `
  tests/renderer/app_remote_bootstrap.test.jsx
```

Expected:
- embedded bootstrap still reports empty `runtimeWebSocketUrl`
- existing assertions only cover `remote` happy path

- [ ] **Step 3: Implement embedded websocket URL injection**

Implementation target:

```js
function buildRuntimeWebSocketUrl(apiBaseUrl) {
  const url = new URL(apiBaseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/runtime";
  url.search = "";
  url.hash = "";
  return url.toString();
}
```

Rules:
- embedded backend ready 后，bootstrap config 必须带上本地 ws URL
- remote mode 现有行为不变
- 失败文案不要重新耦合 `.venv` / `data/app.db` 之外的新逻辑

- [ ] **Step 4: Re-run focused tests and confirm they pass**

Run:

```powershell
npm --prefix app_desktop_web test -- `
  tests/electron/electron_remote_mode.test.js `
  tests/renderer/app_remote_bootstrap.test.jsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/electron-main.cjs app_desktop_web/electron_runtime_mode.cjs app_desktop_web/tests/electron/electron_remote_mode.test.js app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx
git commit -m "feat: expose runtime websocket url for embedded desktop mode"
```

## Chunk 2: Connect Runtime Updates In Embedded Mode

### Task 2: Remove the remote-only gate in `App.jsx`

**Files:**
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- Modify: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`

- [ ] **Step 1: Write the failing renderer test**

```jsx
it("connects runtime updates in embedded mode when runtimeWebSocketUrl is present", async () => {
  renderDesktopAppWithBootstrap({
    backendMode: "embedded",
    backendStatus: "ready",
    apiBaseUrl: "http://127.0.0.1:8123",
    runtimeWebSocketUrl: "ws://127.0.0.1:8123/ws/runtime",
  });
  await openPurchaseSystemTab();
  expect(WebSocket).toHaveBeenCalledWith(expect.stringContaining("/ws/runtime"));
});
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run:

```powershell
npm --prefix app_desktop_web test -- `
  tests/renderer/app_remote_bootstrap.test.jsx `
  tests/renderer/runtime_connection_manager.test.js
```

Expected:
- `App.jsx` still exits early because `backendMode !== "remote"`

- [ ] **Step 3: Implement the minimal gate change**

Rules:
- 运行态 ws 接入条件改成：
  - backend ready
  - 当前页属于 `FULL_BOOTSTRAP_PAGE_IDS`
  - `runtimeWebSocketUrl` 非空
  - full bootstrap ready
- 不再把 `backendMode === "remote"` 作为硬门禁
- embedded / remote 共用同一套 `runtimeConnectionManager.connectRuntimeUpdates()`

- [ ] **Step 4: Re-run focused tests and confirm they pass**

Run:

```powershell
npm --prefix app_desktop_web test -- `
  tests/renderer/app_remote_bootstrap.test.jsx `
  tests/renderer/runtime_connection_manager.test.js `
  tests/renderer/remote_runtime_shell.test.jsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/src/App.jsx app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx app_desktop_web/tests/renderer/runtime_connection_manager.test.js
git commit -m "feat: consume runtime websocket updates in embedded mode"
```

## Chunk 3: Replace Purchase Polling With Push + Resync

### Task 3: Remove the steady-state `1.5s` polling loop from purchase-system

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: Write the failing purchase-system tests**

```jsx
it("does not start the 1.5s purchase runtime polling loop after bootstrap hydrates", async () => {
  vi.spyOn(window, "setInterval");
  renderPurchasePageWithBootstrapAndStore();
  await openPurchaseSystemTab();
  expect(window.setInterval).not.toHaveBeenCalledWith(expect.any(Function), 1500);
});

it("applies purchase runtime websocket updates without calling getPurchaseRuntimeStatus repeatedly", async () => {
  renderPurchasePageWithBootstrapAndStore();
  await openPurchaseSystemTab();
  pushRuntimeEvent({
    event: "purchase_runtime.updated",
    version: 3,
    payload: { running: true, total_purchased_count: 4 },
  });
  expect(screen.getByText("运行中")).toBeInTheDocument();
  expect(client.getPurchaseRuntimeStatus).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run:

```powershell
npm --prefix app_desktop_web test -- tests/renderer/purchase_system_page.test.jsx
```

Expected:
- 现有 hook 仍在 `setInterval(..., 1500)`
- purchase 页面仍把 steady-state status update 建立在 `GET /purchase-runtime/status`

- [ ] **Step 3: Refactor purchase page to use push-driven server state**

Rules:
- 删除无条件 `setInterval`
- 保留以下主动拉取场景：
  - 首次 bootstrap / 首次进入所需快照
  - 用户主动启停/保存后的必要补拉
  - runtime connection manager 触发的 resync
- hidden page 不得自建第二套后台刷新链路
- draft/UI state 继续留在 store / local state，不因 push 覆盖

- [ ] **Step 4: Re-run focused tests and confirm they pass**

Run:

```powershell
npm --prefix app_desktop_web test -- `
  tests/renderer/purchase_system_page.test.jsx `
  tests/renderer/remote_runtime_shell.test.jsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "refactor: drive purchase runtime ui from websocket updates"
```

## Chunk 4: Keep Resync And Failure Behavior Honest

### Task 4: Verify stale/resync fallback instead of reviving polling

**Files:**
- Modify: `app_desktop_web/src/runtime/runtime_connection_manager.js`
- Modify: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: Write the failing stale/resync tests**

```js
it("marks the connection stale and triggers bootstrap resync after embedded runtime websocket closes", async () => {
  const manager = createRuntimeConnectionManager({ client, store });
  const disconnect = manager.connectRuntimeUpdates({
    websocketUrl: "ws://127.0.0.1:8123/ws/runtime",
    WebSocketImpl: FakeWebSocket,
  });
  closeLatestWebSocket();
  await flushPromises();
  expect(store.getSnapshot().connection.stale).toBe(true);
  expect(client.getAppBootstrapFull).toHaveBeenCalled();
  disconnect();
});
```

- [ ] **Step 2: Run focused tests to verify they fail**

Run:

```powershell
npm --prefix app_desktop_web test -- tests/renderer/runtime_connection_manager.test.js
```

Expected:
- embedded-specific stale/resync path still没被覆盖，或 purchase 页面仍依赖旧轮询断言

- [ ] **Step 3: Implement only the minimal fallback behavior needed**

Rules:
- 不恢复 steady-state polling
- ws close/error 后允许：
  - connection 标 `stale`
  - 自动重连
  - 必要时回源 `/app/bootstrap`
- 不能把 draft / hidden-page state 清空

- [ ] **Step 4: Re-run focused tests and confirm they pass**

Run:

```powershell
npm --prefix app_desktop_web test -- `
  tests/renderer/runtime_connection_manager.test.js `
  tests/renderer/purchase_system_page.test.jsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/src/runtime/runtime_connection_manager.js app_desktop_web/tests/renderer/runtime_connection_manager.test.js app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "fix: keep embedded runtime resync as websocket fallback"
```

## Chunk 5: Final Verification

### Task 5: Run final focused verification and document remaining gaps

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run final renderer/electron suite**

Run:

```powershell
npm --prefix app_desktop_web test -- `
  tests/electron/electron_remote_mode.test.js `
  tests/renderer/app_remote_bootstrap.test.jsx `
  tests/renderer/runtime_connection_manager.test.js `
  tests/renderer/purchase_system_page.test.jsx `
  tests/renderer/remote_runtime_shell.test.jsx
```

Expected: PASS

- [ ] **Step 2: Run backend websocket regression if frontend assumptions changed**

Run:

```powershell
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest `
  tests/backend/test_runtime_update_websocket.py -q
```

Expected: PASS

- [ ] **Step 3: Manual smoke in embedded desktop mode**

Manual checklist:
- 启动本地桌面 app，进入 `扫货系统`
- 确认 steady-state 不再每 `1.5s` 拉 `/purchase-runtime/status`
- 模拟一条 `purchase_runtime.updated` / `query_runtime.updated` 后 UI 自动刷新
- 断开 ws 后 UI 进入 `stale` / `resync`，恢复后自动回正
- 不再因为 steady-state runtime refresh 冒出“检查本地后端是否卡死” modal

- [ ] **Step 4: Append verification evidence to session log**

- [ ] **Step 5: Commit**

```bash
git add docs/agent/session-log.md
git commit -m "docs: record embedded runtime push verification"
```

## Notes For Executor

- 当前工作树已存在未提交改动：
  - `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
  - `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- 执行前先读清这些 diff，默认视为用户/前序会话现场，不得无脑覆盖。
- 本计划默认不处理 diagnostics polling；若执行中发现仍会复现同类 modal，只在交付中明确“purchase steady-state 已改为 push，diagnostics 仍属后续范围”，不要悄悄扩大改动面。

Plan complete and saved to `docs/superpowers/plans/2026-04-27-embedded-runtime-push.md`. Ready to execute?
