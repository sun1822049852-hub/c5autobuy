# Remote Runtime Thin Client Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将桌面前端改造成“本地 App 壳 + 远程主服务器状态驱动”的 thin client，杜绝切页丢状态，并用 bootstrap snapshot 与 runtime push 替代页面级反复全量重读。

**Architecture:** 前端启动时只拉一次聚合 bootstrap snapshot，写入 app-level runtime store；`query-system` 与 `purchase-system` 页面常驻挂载，但隐藏页暂停副作用。后端新增 `GET /app/bootstrap` 与 `WS /ws/runtime`，通过 versioned runtime events 推送 query/purchase/ui-preferences/runtime-settings 变化；前端断线后自动重连，发现版本跳变时回源 resync。

**Tech Stack:** React 19, Vitest, Electron, FastAPI, WebSocket, Python 3.11, pytest

---

## File Map

- `app_desktop_web/electron_runtime_mode.cjs`
  新建。定义桌面端运行模式解析：`embedded`（本地 Python backend）或 `remote`（远程主服务器）。
- `app_desktop_web/electron-main.cjs`
  负责主进程启动链；本次必须先支持 remote mode 下跳过 `startPythonBackend()`，否则 thin client 架构不成立。
- `app_desktop_web/src/App.jsx`
  负责应用壳、页面切换与顶层 client/store 装配；本次改为 keep-alive shell。
- `app_desktop_web/src/runtime/app_runtime_store.js`
  新建。保存远程 bootstrap snapshot、runtime slices、连接状态与 resync 元信息。
- `app_desktop_web/src/runtime/app_runtime_provider.jsx`
  新建。给 React 树提供 runtime store 与 selector hook。
- `app_desktop_web/src/runtime/use_app_runtime.js`
  新建。封装 `useSyncExternalStore` 选择器，避免页面直连底层 store。
- `app_desktop_web/src/runtime/runtime_connection_manager.js`
  新建。统一管理 bootstrap、websocket、重连、stale/offline、resync。
- `app_desktop_web/src/features/query-system/query_system_page.jsx`
  接收 `isActive` 与 store-derived props，不再自持完整 server state。
- `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
  从“整页 server state + draft state 混合 hook”重构为“只处理 query UI/draft 行为”的 hook。
- `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
  接收 `isActive` 与 store-derived props，不再依赖挂载重拉。
- `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
  从“轮询驱动的大型 hook”重构为“purchase UI/draft + action dispatcher”。
- `app_desktop_web/src/api/account_center_client.js`
  新增 `getAppBootstrap()`、`watchRuntimeUpdates()` 与 runtime websocket URL override 支持。
- `app_desktop_web/src/desktop/bridge.js`
  扩展桌面 bootstrap config，支持远程 `apiBaseUrl` / `runtimeWebSocketUrl` / `backendMode`。
- `app_backend/api/routes/app_bootstrap.py`
  新建。聚合 query configs、query runtime、purchase runtime、ui preferences、runtime settings、diagnostics 摘要。
- `app_backend/api/websocket/runtime.py`
  新建。提供 `WS /ws/runtime`，持续发送 versioned runtime events。
- `app_backend/api/schemas/app_bootstrap.py`
  新建。定义 bootstrap response schema 与 runtime event schema。
- `app_backend/application/use_cases/get_app_bootstrap.py`
  新建。组合现有 service/repository 的 snapshot 为单个 bootstrap payload。
- `app_backend/infrastructure/events/runtime_update_hub.py`
  新建。统一发布 runtime-related 更新，并维护单调递增 version；同时作为 bootstrap `version` 的唯一来源。
- `app_backend/infrastructure/query/runtime/query_runtime_service.py`
  修改。query runtime 状态改变时发布 runtime events。
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
  修改。purchase runtime 状态改变时发布 runtime events。
- `app_backend/main.py`
  注册 bootstrap route、runtime websocket 与 `app.state.runtime_update_hub`。
- `app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx`
  新建。验证切页后 query/purchase 页面状态保活。
- `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
  新建。验证 `App.jsx` 启动时使用桌面注入的远程地址创建 client。
- `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`
  新建。验证 bootstrap、push、disconnect、resync。
- `app_desktop_web/tests/electron/electron_remote_mode.test.js`
  新建。验证 remote mode 下主进程不会启动本地 Python backend。
- `app_desktop_web/tests/renderer/account_center_client.test.js`
  修改。覆盖 `getAppBootstrap()` 与 `watchRuntimeUpdates()`。
- `app_desktop_web/tests/renderer/query_system_page.test.jsx`
  修改。验证 query 页面不再切页重置。
- `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
  修改。验证 purchase 页面不再依赖 mount-time reload / polling。
- `tests/backend/test_app_bootstrap_route.py`
  新建。验证 bootstrap route 聚合结果。
- `tests/backend/test_runtime_update_websocket.py`
  新建。验证 runtime websocket 推送、version 与订阅。
- `tests/backend/test_query_runtime_service.py`
  修改。验证 query runtime 变更会发 event。
- `tests/backend/test_purchase_runtime_service.py`
  修改。验证 purchase runtime 变更会发 event。

## Chunk 0: Remote Desktop Mode Is A Hard Precondition

### Task 0: Add explicit remote mode support before any state work

**Files:**
- Create: `app_desktop_web/electron_runtime_mode.cjs`
- Modify: `app_desktop_web/electron-main.cjs`
- Modify: `app_desktop_web/src/desktop/bridge.js`
- Create: `app_desktop_web/tests/electron/electron_remote_mode.test.js`
- Create: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`

- [ ] **Step 1: Write the failing main-process and renderer startup tests**

```js
it("skips embedded python backend when backendMode=remote", async () => {
  const mode = resolveDesktopRuntimeMode({
    backendMode: "remote",
    apiBaseUrl: "https://api.example.com",
    runtimeWebSocketUrl: "wss://api.example.com/ws/runtime"
  });
  expect(mode.shouldStartEmbeddedBackend).toBe(false);
});

it("creates the renderer client from injected remote bootstrap config", () => {
  window.desktopApp = {
    getBootstrapConfig() {
      return {
        backendMode: "remote",
        apiBaseUrl: "https://api.example.com",
        runtimeWebSocketUrl: "wss://api.example.com/ws/runtime"
      };
    }
  };
  render(<App />);
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("https://api.example.com"), expect.anything());
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app_desktop_web; npm test -- tests/electron/electron_remote_mode.test.js tests/renderer/app_remote_bootstrap.test.jsx`

Expected: FAIL because the current main process always tries to start local Python before opening the renderer.

- [ ] **Step 3: Add a pure runtime-mode helper and use it in `electron-main.cjs`**

Required bootstrap config shape:

```js
{
  backendMode: "embedded" | "remote",
  apiBaseUrl: "http://127.0.0.1:8000" | "https://api.example.com",
  runtimeWebSocketUrl: "" | "wss://api.example.com/ws/runtime",
  backendStatus: "starting" | "ready" | "failed"
}
```

Required branch:

```js
if (mode.shouldStartEmbeddedBackend) {
  // existing python backend startup path
} else {
  bootstrapConfig = {
    backendMode: "remote",
    apiBaseUrl: mode.apiBaseUrl,
    runtimeWebSocketUrl: mode.runtimeWebSocketUrl,
    backendStatus: "ready"
  };
  createWindow();
}
```

- [ ] **Step 4: Fix failure messaging for remote mode**

Rules:
- remote mode failure copy must not mention `.venv` or `data/app.db`
- embedded mode may keep the current local-backend troubleshooting copy

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd app_desktop_web; npm test -- tests/electron/electron_remote_mode.test.js tests/renderer/app_remote_bootstrap.test.jsx tests/electron/electron_entrypoints.test.js`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/electron_runtime_mode.cjs app_desktop_web/electron-main.cjs app_desktop_web/src/desktop/bridge.js app_desktop_web/tests/electron/electron_remote_mode.test.js app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx
git commit -m "feat: add remote desktop runtime mode"
```

## Chunk 1: Keep-Alive Shell And Shared Runtime Store

### Task 1: Add a failing renderer test for page keep-alive

**Files:**
- Create: `app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx`
- Reuse for patterns: `app_desktop_web/tests/renderer/app_state_persistence.test.jsx`
- Reuse for page helpers: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: Write the failing test**

```jsx
it("keeps query and purchase page state when switching tabs", async () => {
  render(<App />);
  await openQuerySystemTab();
  await editQueryDraftName("alpha");
  await openPurchaseSystemTab();
  await editPurchaseSetting("3");
  await openQuerySystemTab();
  expect(screen.getByDisplayValue("alpha")).toBeInTheDocument();
  await openPurchaseSystemTab();
  expect(screen.getByDisplayValue("3")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app_desktop_web; npm test -- tests/renderer/remote_runtime_shell.test.jsx`

Expected: FAIL because current tab switch unmounts the page and loses draft state.

- [ ] **Step 3: Add a minimal keep-alive shell in `App.jsx`**

Implementation target:

```jsx
<section hidden={activeItem !== "query-system"}>
  <QuerySystemPage isActive={activeItem === "query-system"} ... />
</section>
<section hidden={activeItem !== "purchase-system"}>
  <PurchaseSystemPage isActive={activeItem === "purchase-system"} ... />
</section>
```

- [ ] **Step 4: Thread `isActive` through page components**

Modify:
- `app_desktop_web/src/features/query-system/query_system_page.jsx`
- `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`

Expected behavior: hidden page stays mounted, but child hook knows whether it is foreground.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd app_desktop_web; npm test -- tests/renderer/remote_runtime_shell.test.jsx tests/renderer/app_state_persistence.test.jsx`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/src/App.jsx app_desktop_web/src/features/query-system/query_system_page.jsx app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx
git commit -m "feat: keep query and purchase pages mounted"
```

### Task 2: Introduce app-level runtime store and hooks

**Files:**
- Create: `app_desktop_web/src/runtime/app_runtime_store.js`
- Create: `app_desktop_web/src/runtime/app_runtime_provider.jsx`
- Create: `app_desktop_web/src/runtime/use_app_runtime.js`
- Test: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`

- [ ] **Step 1: Write the failing store test**

```js
it("stores bootstrap server state separately from ui and draft state", () => {
  const store = createAppRuntimeStore();
  store.applyBootstrap({ querySystem: { server: { configs: [{ config_id: "q1" }] } } });
  store.patchQueryUi({ selectedConfigId: "q1" });
  store.patchQueryDraft({ name: "draft-name" });
  expect(store.getSnapshot().querySystem.server.configs).toHaveLength(1);
  expect(store.getSnapshot().querySystem.ui.selectedConfigId).toBe("q1");
  expect(store.getSnapshot().querySystem.draft.name).toBe("draft-name");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app_desktop_web; npm test -- tests/renderer/runtime_connection_manager.test.js`

Expected: FAIL because store modules do not exist.

- [ ] **Step 3: Implement the store with explicit slice boundaries**

Target snapshot shape:

```js
{
  bootstrap: { state: "idle", hydratedAt: null, version: 0 },
  connection: { state: "idle", stale: false, lastSyncAt: null, lastEventVersion: 0, lastError: "" },
  querySystem: {
    server: { configs: [], capacitySummary: { modes: {} }, runtimeStatus: { running: false, item_rows: [] } },
    ui: { selectedConfigId: null },
    draft: { currentConfig: null, hasUnsavedChanges: false }
  },
  purchaseSystem: {
    server: { runtimeStatus: { running: false, accounts: [], item_rows: [] }, uiPreferences: {}, runtimeSettings: {} },
    ui: { selectedConfigId: null, activeModal: "" },
    draft: { purchaseSettingsDraft: {}, querySettingsDraft: null }
  }
}
```

- [ ] **Step 4: Add provider and selector hook using `useSyncExternalStore`**

Rules:
- no new dependency
- expose narrow selectors such as `useQuerySystemServerState()`
- disallow page hooks from mutating raw snapshot directly

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd app_desktop_web; npm test -- tests/renderer/runtime_connection_manager.test.js`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/src/runtime/app_runtime_store.js app_desktop_web/src/runtime/app_runtime_provider.jsx app_desktop_web/src/runtime/use_app_runtime.js app_desktop_web/tests/renderer/runtime_connection_manager.test.js
git commit -m "feat: add shared app runtime store"
```

### Task 3: Refactor query-system to consume store-backed server state

**Files:**
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/App.jsx`
- Test: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: Write a failing query-system test**

```jsx
it("does not refetch full query page payload on tab re-entry when store is hydrated", async () => {
  const client = buildClientMocks();
  renderQueryPageWithStore(client);
  await leaveAndReturnToQueryTab();
  expect(client.listQueryConfigs).toHaveBeenCalledTimes(1);
  expect(client.getQueryRuntimeStatus).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app_desktop_web; npm test -- tests/renderer/query_system_page.test.jsx`

Expected: FAIL because current hook reloads on every mount.

- [ ] **Step 3: Split query hook responsibilities**

Refactor target:
- server state comes from `useAppRuntime(...)`
- hook keeps only query-local UI/draft actions
- hydration path becomes `if (!store.querySystem.serverHydrated) { manager.bootstrap(); }`

- [ ] **Step 4: Remove mount-time full reload as the primary source of truth**

Allowed fallback:
- explicit user refresh
- bootstrap/resync from connection manager

Disallowed:
- `useEffect(() => loadPage(), [client])` as the normal path after hydration

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd app_desktop_web; npm test -- tests/renderer/query_system_page.test.jsx tests/renderer/remote_runtime_shell.test.jsx`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/src/features/query-system/hooks/use_query_system_page.js app_desktop_web/src/features/query-system/query_system_page.jsx app_desktop_web/src/App.jsx app_desktop_web/tests/renderer/query_system_page.test.jsx
git commit -m "refactor: move query page server state into runtime store"
```

### Task 4: Refactor purchase-system to consume store-backed server state and pause hidden-page effects

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: Write a failing purchase-system test**

```jsx
it("stops background polling when purchase page is hidden and preserves drafts", async () => {
  vi.useFakeTimers();
  renderPurchasePageWithStore();
  hidePurchaseTab();
  vi.advanceTimersByTime(5000);
  expect(client.getPurchaseRuntimeStatus).toHaveBeenCalledTimes(1);
  showPurchaseTab();
  expect(screen.getByDisplayValue("3")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app_desktop_web; npm test -- tests/renderer/purchase_system_page.test.jsx`

Expected: FAIL because current hook keeps polling every 1.5s and loses page state on remount.

- [ ] **Step 3: Move purchase server state into the shared store**

Required changes:
- runtime status, ui preferences, runtime settings come from store
- hook owns only modal state, form edits, transient validation
- hidden page does not run `setInterval`

- [ ] **Step 4: Keep manual refresh, but gate automatic refresh behind `isActive`**

Temporary rule for this chunk:
- foreground page may still use fallback timer until websocket exists
- hidden page must not poll

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd app_desktop_web; npm test -- tests/renderer/purchase_system_page.test.jsx tests/renderer/remote_runtime_shell.test.jsx`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "refactor: move purchase page server state into runtime store"
```

## Chunk 2: Remote Bootstrap Snapshot And Client Wiring

### Task 5: Add backend bootstrap schema, route, and use case

**Files:**
- Create: `app_backend/infrastructure/events/runtime_update_hub.py`
- Create: `app_backend/api/schemas/app_bootstrap.py`
- Create: `app_backend/application/use_cases/get_app_bootstrap.py`
- Create: `app_backend/api/routes/app_bootstrap.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_app_bootstrap_route.py`

- [ ] **Step 1: Write the failing backend route test**

```python
import pytest

@pytest.mark.asyncio
async def test_app_bootstrap_returns_query_purchase_and_diagnostics_snapshot(client, app):
    response = await client.get("/app/bootstrap")
    assert response.status_code == 200
    payload = response.json()
    assert "query_system" in payload
    assert "purchase_system" in payload
    assert "diagnostics" in payload
    assert payload["version"] == app.state.runtime_update_hub.current_version()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_app_bootstrap_route.py -q`

Expected: FAIL because route/schema/use case do not exist.

- [ ] **Step 3: Implement runtime update hub first, then build bootstrap from that shared version source**

Required response shape:

```json
{
  "version": 1,
  "generated_at": "2026-03-31T20:00:00",
  "query_system": {
    "configs": [],
    "capacity_summary": { "modes": {} },
    "runtime_status": { "running": false, "item_rows": [] }
  },
  "purchase_system": {
    "runtime_status": { "running": false, "accounts": [], "item_rows": [] },
    "ui_preferences": { "selected_config_id": null, "updated_at": null },
    "runtime_settings": { "per_batch_ip_fanout_limit": 1, "updated_at": null }
  },
  "diagnostics": {
    "summary": { "backend_online": true, "last_error": null }
  }
}
```

- [ ] **Step 4: Register both the hub and the route in `main.py`**

Required `app.state` wiring:
- `app.state.runtime_update_hub = RuntimeUpdateHub()`
- bootstrap use case reads `current_version()` from the same hub the websocket path will later use
- reuse existing `query_runtime_service`, `purchase_runtime_service`, `purchase_ui_preferences_repository`, `runtime_settings_repository`, and diagnostics inputs from `app.state`

- [ ] **Step 5: Implement bootstrap payload with server-owned snapshot slices**

Rules:
- `version` must come from `runtime_update_hub.current_version()`
- do not invent a second bootstrap-only counter
- if no runtime change has happened yet, `version` may legitimately be `0`

- [ ] **Step 6: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_backend_health.py -q`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app_backend/infrastructure/events/runtime_update_hub.py app_backend/api/schemas/app_bootstrap.py app_backend/application/use_cases/get_app_bootstrap.py app_backend/api/routes/app_bootstrap.py app_backend/main.py tests/backend/test_app_bootstrap_route.py
git commit -m "feat: add runtime version source and aggregated bootstrap endpoint"
```

### Task 6: Add frontend bootstrap client and hydration manager

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Create: `app_desktop_web/src/runtime/runtime_connection_manager.js`
- Modify: `app_desktop_web/src/App.jsx`
- Test: `app_desktop_web/tests/renderer/account_center_client.test.js`
- Test: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`

- [ ] **Step 1: Write failing client and manager tests**

```js
it("requests /app/bootstrap once during startup hydration", async () => {
  await manager.bootstrap();
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/app/bootstrap"), expect.anything());
});

it("marks the connection stale after bootstrap failure", async () => {
  fetchMock.mockRejectedValueOnce(new Error("network"));
  await manager.bootstrap().catch(() => {});
  expect(store.getSnapshot().connection.stale).toBe(true);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app_desktop_web; npm test -- tests/renderer/account_center_client.test.js tests/renderer/runtime_connection_manager.test.js`

Expected: FAIL because the methods/manager do not exist.

- [ ] **Step 3: Add `getAppBootstrap()` to the typed client**

Required method:

```js
async getAppBootstrap() {
  return http.getJson("/app/bootstrap", { method: "GET" });
}
```

- [ ] **Step 4: Implement runtime connection manager bootstrap/hydrate flow**

Required manager methods:
- `bootstrap()`
- `markDisconnected(reason)`
- `applyBootstrap(payload)`
- `scheduleResync(reason)`

Rules:
- bootstrap only once at app startup unless forced
- on success, write store snapshot and clear stale/offline
- on failure, preserve prior UI/draft state and expose error banner state

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd app_desktop_web; npm test -- tests/renderer/account_center_client.test.js tests/renderer/runtime_connection_manager.test.js`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/src/api/account_center_client.js app_desktop_web/src/runtime/runtime_connection_manager.js app_desktop_web/src/App.jsx app_desktop_web/tests/renderer/account_center_client.test.js app_desktop_web/tests/renderer/runtime_connection_manager.test.js
git commit -m "feat: hydrate app runtime store from bootstrap snapshot"
```

## Chunk 3: Runtime Push, Resync, And Remote Desktop Delivery

### Task 7: Add versioned runtime update hub and websocket endpoint

**Files:**
- Create: `app_backend/api/websocket/runtime.py`
- Modify: `app_backend/main.py`
- Modify: `app_backend/infrastructure/events/runtime_update_hub.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Test: `tests/backend/test_runtime_update_websocket.py`
- Test: `tests/backend/test_query_runtime_service.py`
- Test: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: Write the failing websocket test**

```python
from fastapi.testclient import TestClient

def test_runtime_websocket_streams_versioned_events(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/runtime") as websocket:
            app.state.runtime_update_hub.publish(
                event="query_runtime.updated",
                payload={"running": True},
            )
            payload = websocket.receive_json()
            assert payload["version"] >= 1
            assert payload["event"] == "query_runtime.updated"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_runtime_update_websocket.py -q`

Expected: FAIL because websocket route and runtime-service publisher wiring do not exist yet.

- [ ] **Step 3: Extend the versioned runtime hub for websocket delivery**

Required event shape:

```json
{
  "version": 12,
  "event": "purchase_runtime.updated",
  "updated_at": "2026-03-31T20:15:00",
  "payload": { "running": true, "queue_size": 2 }
}
```

Rules:
- version must increase monotonically
- publish only semantic changes
- do not send entire bootstrap payload every time
- websocket payload version and bootstrap version must come from the same hub implementation

- [ ] **Step 4: Publish events from query and purchase runtime services**

Minimum events:
- `query_runtime.updated`
- `purchase_runtime.updated`
- `purchase_ui_preferences.updated`
- `runtime_settings.updated`

- [ ] **Step 5: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_runtime_update_websocket.py tests/backend/test_query_runtime_service.py tests/backend/test_purchase_runtime_service.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_backend/infrastructure/events/runtime_update_hub.py app_backend/api/websocket/runtime.py app_backend/main.py app_backend/infrastructure/query/runtime/query_runtime_service.py app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py tests/backend/test_runtime_update_websocket.py tests/backend/test_query_runtime_service.py tests/backend/test_purchase_runtime_service.py
git commit -m "feat: publish versioned runtime updates over websocket"
```

### Task 8: Consume runtime websocket events in the frontend and replace polling

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/runtime/runtime_connection_manager.js`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Test: `app_desktop_web/tests/renderer/account_center_client.test.js`
- Test: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: Write failing push/resync tests**

```js
it("applies purchase runtime websocket updates without polling", async () => {
  pushRuntimeEvent({ event: "purchase_runtime.updated", version: 3, payload: { running: true } });
  expect(store.getSnapshot().purchaseSystem.server.runtimeStatus.running).toBe(true);
  expect(window.setInterval).not.toHaveBeenCalledWith(expect.any(Function), 1500);
});

it("forces bootstrap resync when a websocket version gap is detected", async () => {
  pushRuntimeEvent({ event: "query_runtime.updated", version: 8, payload: {} });
  pushRuntimeEvent({ event: "query_runtime.updated", version: 10, payload: {} });
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/app/bootstrap"), expect.anything());
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app_desktop_web; npm test -- tests/renderer/runtime_connection_manager.test.js tests/renderer/purchase_system_page.test.jsx`

Expected: FAIL because runtime websocket and version-gap resync do not exist.

- [ ] **Step 3: Add `watchRuntimeUpdates()` to the frontend client**

Required behavior:
- use websocket when available
- prefer `bootstrapConfig.runtimeWebSocketUrl` when provided
- otherwise derive websocket URL from `apiBaseUrl`
- emit parsed versioned events
- surface close/error to connection manager

- [ ] **Step 4: Replace purchase polling with push + fallback resync**

Rules:
- remove the unconditional 1.5s polling loop
- only allow manual refresh or manager-triggered bootstrap resync
- hidden page must not establish its own secondary connection

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd app_desktop_web; npm test -- tests/renderer/account_center_client.test.js tests/renderer/runtime_connection_manager.test.js tests/renderer/purchase_system_page.test.jsx`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/src/api/account_center_client.js app_desktop_web/src/runtime/runtime_connection_manager.js app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/tests/renderer/account_center_client.test.js app_desktop_web/tests/renderer/runtime_connection_manager.test.js app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat: drive runtime ui from websocket updates and resync"
```

### Task 9: Deepen remote observability after remote mode is already in place

**Files:**
- Modify: `app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js`
- Modify: `app_desktop_web/tests/electron/electron_remote_mode.test.js`
- Modify: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] **Step 1: Write failing remote-config and diagnostics tests**

```js
it("retains last known diagnostics when the backend is temporarily unreachable", async () => {
  loadDiagnosticsSnapshotOnce();
  failNextDiagnosticsPoll();
  expect(screen.getByText(/诊断数据暂不可用/)).not.toBeInTheDocument();
});

it("surfaces remote runtime connection metadata in diagnostics", async () => {
  seedConnectionState({ lastEventVersion: 8, lastResyncReason: "version_gap", websocketState: "closed" });
  renderDiagnosticsPanel();
  expect(screen.getByText(/version_gap/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd app_desktop_web; npm test -- tests/electron/electron_runtime.test.js tests/renderer/diagnostics_sidebar.test.jsx`

Expected: FAIL because remote delivery and stale diagnostics retention are incomplete.

- [ ] **Step 3: Extend diagnostics with remote connection metadata**

Required fields:

```js
{
  backendMode: "remote",
  apiBaseUrl: "https://api.example.com",
  runtimeWebSocketUrl: "wss://api.example.com/ws/runtime",
  backendStatus: "online",
  websocketState: "open" | "closed",
  lastEventVersion: 8,
  lastResyncReason: "version_gap"
}
```

Rules:
- remote mode itself was completed in Task 0; this task only extends observability and retained diagnostics
- diagnostics must preserve the last successful snapshot during temporary remote outages
- reverse proxy / subpath deployments must still show the explicit websocket override value when present

- [ ] **Step 4: Extend diagnostics retention and connection visibility**

Add/retain:
- last successful bootstrap time
- websocket state / close code
- last event version
- last resync reason

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd app_desktop_web; npm test -- tests/electron/electron_runtime.test.js tests/renderer/diagnostics_sidebar.test.jsx tests/renderer/app_renderer_diagnostics.test.jsx`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js app_desktop_web/tests/electron/electron_remote_mode.test.js app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx
git commit -m "feat: deepen remote runtime diagnostics"
```

## Final Verification

- [ ] **Step 1: Run targeted renderer suite**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/remote_runtime_shell.test.jsx tests/renderer/runtime_connection_manager.test.js tests/renderer/query_system_page.test.jsx tests/renderer/purchase_system_page.test.jsx tests/renderer/diagnostics_sidebar.test.jsx
```

Expected: PASS

- [ ] **Step 2: Run targeted electron suite**

Run:

```bash
cd app_desktop_web
npm test -- tests/electron/electron_remote_mode.test.js tests/electron/electron_entrypoints.test.js tests/electron/python_backend.test.js
```

Expected: PASS

- [ ] **Step 3: Run targeted backend suite**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py tests/backend/test_query_runtime_service.py tests/backend/test_purchase_runtime_service.py tests/backend/test_backend_main_entry.py tests/backend/test_request_diagnostics_middleware.py -q
```

Expected: PASS

- [ ] **Step 4: Run packaged-desktop smoke checklist**

Checklist:
- packaged app opens with remote `apiBaseUrl`
- first paint uses bootstrap snapshot
- switching query/purchase tabs preserves draft state
- temporary server disconnect shows stale/offline instead of blank default view
- websocket reconnect triggers resync and recovers fresh data

- [ ] **Step 5: Final commit**

```bash
git add app_desktop_web app_backend tests
git commit -m "feat: convert desktop frontend to remote runtime thin client"
```
