# Remote Runtime State Sync Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让桌面前端在 remote 模式下严格遵循“`/app/bootstrap` 一次启动 + `/ws/runtime` 持续推送 + 共享 runtime store + authoritative settle”模型，彻底移除切页掉状态、页面级重拉与 HTTP success 直接清草稿的旧路径。

**Architecture:** 现有 backend 的 `/app/bootstrap`、`/ws/runtime`、`RuntimeUpdateHub` 视为本轮 verify-first 契约；只有在契约测试失败时才回头补后端。前端以 `App.jsx` 为唯一启动入口，由 `runtime_connection_manager` 负责 `bootstrap + websocket + resync + generation gate`，`app_runtime_store` 负责 server-owned slice、selection 收敛、draft 基线与 terminal signals，`query-system` / `purchase-system` 页面只保留本地 UI 流程与显式命令。

**Tech Stack:** React 19, Vitest, Electron, FastAPI, WebSocket, Python 3.11, pytest

---

> This plan supersedes `docs/superpowers/plans/2026-03-31-remote-runtime-thin-client.md` for the authoritative-settle round described in `docs/superpowers/specs/2026-04-02-remote-runtime-state-sync-design.md`.
>
> Hard requirement: execute this plan in a dedicated worktree with no unrelated changes. Do not implement it in the current dirty workspace. If a clean worktree is unavailable, stop before Task 1 instead of relying on file-level staging.

> All commit commands below assume that dedicated-worktree precondition has already been satisfied.

## File Map

- `docs/superpowers/specs/2026-04-02-remote-runtime-state-sync-design.md`
  Authoritative spec. Every task in this plan is anchored to this file.
- `app_desktop_web/src/runtime/app_runtime_store.js`
  Shared runtime reducer/store. Must become the single owner of server-owned slices, selection convergence, draft baseline metadata, conflict/orphan flags, and reducer-emitted terminal signals.
- `app_desktop_web/src/runtime/runtime_connection_manager.js`
  Single startup/resync pipeline. Must own `connectionGeneration`, `since_version`, websocket lifecycle, disconnect handling, and `runtime.resync_required`.
- `app_desktop_web/src/runtime/use_app_runtime.js`
  Selector and patch hook boundary. Keep page hooks from reaching into raw snapshots.
- `app_desktop_web/src/runtime/runtime_draft_comparators.js`
  New shared helper module. Centralize canonical normalizer/comparator logic for:
  - query config draft
  - purchase settings draft
  - manual allocation draft
  - purchase-page local `querySettingsDraft`
- `app_desktop_web/src/App.jsx`
  Top-level bootstrap and runtime-stream startup. Must stay the only place that starts remote runtime sync.
- `app_desktop_web/src/api/account_center_client.js`
  HTTP and websocket client surface. Must expose `/app/bootstrap` and `/ws/runtime` with explicit `since_version` handling.
- `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
  Query page local workflow only. Must stop owning primary server truth.
- `app_desktop_web/src/features/query-system/query_system_page.jsx`
  Query page composition and view wiring.
- `app_desktop_web/src/features/query-system/query_system_persistence.js`
  Query config save transport boundary. Any plan that changes query save semantics must include this file and its tests.
- `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
  Purchase page local controller. Must become the only owner of `pendingSelectedConfigId` and local `querySettingsDraft`.
- `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
  Purchase page composition and rendering. Must stop using preview fallback as a primary data source.
- `app_desktop_web/src/features/purchase-system/components/query_settings_modal.jsx`
  Purchase-page local query settings editor UI. Its save/close/conflict UX must follow the local modal controller, not the global store.
- `app_desktop_web/src/features/purchase-system/components/purchase_settings_panel.jsx`
  Purchase settings editor UI. Reads store-backed draft only.
- `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`
  Primary reducer/manager regression suite for generation gates, resync, and store event application.
- `app_desktop_web/tests/renderer/account_center_client.test.js`
  Client contract tests for `/app/bootstrap` and `/ws/runtime`.
- `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
  App startup test for remote bootstrap once + runtime stream startup.
- `app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx`
  Keep-alive shell and blank-page regression tests.
- `app_desktop_web/tests/renderer/query_system_page.test.jsx`
  Query page integration tests for no remount refetch and explicit refresh semantics.
- `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
  Query config editor authoritative-settle tests.
- `app_desktop_web/tests/renderer/query_system_persistence.test.js`
  Query config save transport and persistence helper tests.
- `app_desktop_web/tests/renderer/query_system_client.test.js`
  Query config client contract tests.
- `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
  Purchase page integration tests for no polling, no preview fallback truth, save-and-switch, and local modal flows.
- `app_desktop_web/tests/renderer/purchase_system_client.test.js`
  Purchase-side transport contract tests for purchase settings, manual allocation, and query-settings modal save paths.
- `tests/backend/test_app_bootstrap_route.py`
  Verify bootstrap version/source contract.
- `tests/backend/test_runtime_update_websocket.py`
  Verify websocket version domain, `since_version`, and `runtime.resync_required`.
- `tests/backend/test_query_runtime_service.py`
  Verify `query_runtime.updated` / `query_configs.updated` publishing still satisfies the contract.
- `tests/backend/test_purchase_runtime_service.py`
  Verify `purchase_runtime.updated` / `runtime_settings.updated` publishing still satisfies the contract.
- `tests/backend/test_query_config_routes.py`
  Query-config route contract tests, including config-scoped query settings writes.
- `tests/backend/test_query_runtime_routes.py`
  Manual allocation write contract tests, including conflict token handling.
- `tests/backend/test_purchase_runtime_routes.py`
  Purchase UI preference route contract tests, including authoritative event emission.
- `tests/backend/test_runtime_settings_routes.py`
  Purchase settings route contract tests, including conflict token handling.
- `app_backend/api/routes/app_bootstrap.py`
- `app_backend/api/routes/query_configs.py`
- `app_backend/api/routes/query_runtime.py`
- `app_backend/api/routes/purchase_runtime.py`
- `app_backend/api/routes/runtime_settings.py`
- `app_backend/application/use_cases/get_app_bootstrap.py`
- `app_backend/api/schemas/query_configs.py`
- `app_backend/api/schemas/query_runtime.py`
- `app_backend/api/schemas/runtime_settings.py`
- `app_backend/application/use_cases/update_query_config.py`
- `app_backend/application/use_cases/update_query_mode_setting.py`
- `app_backend/application/use_cases/update_purchase_runtime_settings.py`
- `app_backend/infrastructure/repositories/query_config_repository.py`
- `app_backend/infrastructure/repositories/runtime_settings_repository.py`
- `app_backend/api/websocket/runtime.py`
- `app_backend/infrastructure/events/runtime_update_hub.py`
  Verify-first backend files. Only modify them if the contract tests in Task 1 fail.
- `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
  Runtime event publisher implementations. If route/service contract tests fail, fix the implementation instead of relaxing tests.

## Chunk 0: Preflight The Workspace Before Any Code Changes

### Task 0: Refuse to run in the current dirty workspace

**Files:**
- Verify only: `git rev-parse --show-toplevel`
- Verify only: `git worktree list`
- Verify only: `git status --short`

- [ ] **Step 1: Verify the current shell is not the original dirty workspace**

Run:

```bash
git rev-parse --show-toplevel
```

Expected:
- returned path is not `C:\Users\18220\Desktop\C5autobug更新接口 - 副本 (2)`

- [ ] **Step 2: Verify a dedicated worktree exists and is the current working directory**

Run:

```bash
git worktree list
```

Expected:
- the current path is a dedicated worktree for this implementation
- it is not the original dirty workspace path

- [ ] **Step 3: Verify the worktree is clean before Task 1**

Run:

```bash
git status --short
```

Expected:
- no unrelated modified/untracked files

- [ ] **Step 4: Stop immediately if any preflight check fails**

Rules:
- do not continue to Task 1 in the original workspace
- do not rely on file-level staging as a substitute for a clean worktree
- if needed, create a dedicated worktree first, then restart the plan from Task 0

## Chunk 1: Lock The Runtime Transport And Store Contract

### Task 1: Verify and tighten the bootstrap/websocket contract before deeper frontend refactors

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_client.test.js`
- Modify: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`
- Modify: `tests/backend/test_app_bootstrap_route.py`
- Modify: `tests/backend/test_runtime_update_websocket.py`
- Modify only if tests fail: `app_desktop_web/src/api/account_center_client.js`
- Modify only if tests fail: `app_backend/api/routes/app_bootstrap.py`
- Modify only if tests fail: `app_backend/application/use_cases/get_app_bootstrap.py`
- Modify only if tests fail: `app_backend/api/websocket/runtime.py`
- Modify only if tests fail: `app_backend/infrastructure/events/runtime_update_hub.py`

- [ ] **Step 1: Write the failing transport-contract tests**

```js
it("connects runtime updates with an exclusive since_version cursor", async () => {
  const client = createAccountCenterClient({ apiBaseUrl: "https://api.example.com" });
  const events = [];
  const unsubscribe = await client.watchRuntimeUpdates({
    sinceVersion: 7,
    onEvent(event) {
      events.push(event);
    },
  });
  pushServerMessage({ version: 7, event: "query_runtime.updated", payload: {} });
  pushServerMessage({ version: 8, event: "query_runtime.updated", payload: { running: true } });
  expect(events.map((event) => event.version)).toEqual([8]);
  unsubscribe();
});

it("drops stale bootstrap and event results from an older generation", async () => {
  const store = createAppRuntimeStore();
  const manager = createRuntimeConnectionManager({ client, store });
  await manager.handleResyncRequired({ version: 12 });
  manager.applyBootstrapResult({ connectionGeneration: 1, version: 11, query_system: {} });
  expect(store.getSnapshot().connection.lastEventVersion).not.toBe(11);
});
```

```python
def test_runtime_websocket_uses_same_version_domain_as_bootstrap(app_client):
    bootstrap = app_client.get("/app/bootstrap").json()
    with app_client.websocket_connect(f"/ws/runtime?since_version={bootstrap['version']}") as websocket:
        publish_query_runtime_update()
        event = websocket.receive_json()
    assert event["version"] > bootstrap["version"]


def test_runtime_resync_required_event_carries_hub_version(app_client):
    with app_client.websocket_connect("/ws/runtime?since_version=0") as websocket:
        trigger_resync_required()
        event = websocket.receive_json()
    assert event["event"] == "runtime.resync_required"
    assert isinstance(event["version"], int)


def test_bootstrap_snapshot_covers_every_bootstrap_owned_slice_up_to_reported_version(app_client):
    config_id = create_query_config("bootstrap-visible-config")
    set_query_runtime_status(config_id=config_id, message="query-before-bootstrap")
    seed_capacity_summary({"new_api": {"available_account_count": 9}})
    set_purchase_ui_selected_config(config_id)
    set_purchase_runtime_settings_limit(4)
    set_purchase_runtime_message("purchase-before-bootstrap")
    bootstrap = app_client.get("/app/bootstrap").json()
    assert any(config["name"] == "bootstrap-visible-config" for config in bootstrap["query_system"]["configs"])
    assert bootstrap["query_system"]["runtime_status"]["config_id"] == config_id
    assert bootstrap["query_system"]["capacity_summary"]["modes"]["new_api"]["available_account_count"] == 9
    assert bootstrap["purchase_system"]["ui_preferences"]["selected_config_id"] == config_id
    assert bootstrap["purchase_system"]["runtime_settings"]["per_batch_ip_fanout_limit"] == 4
    assert bootstrap["purchase_system"]["runtime_status"]["message"] == "purchase-before-bootstrap"
```

- [ ] **Step 2: Run the transport-contract tests and confirm current gaps**

Run renderer tests:

```bash
cd app_desktop_web
npm test -- tests/renderer/account_center_client.test.js tests/renderer/runtime_connection_manager.test.js
```

Expected: FAIL if `watchRuntimeUpdates()` does not enforce exclusive `since_version`, or if the manager/store still accepts stale generation results.

Run backend tests:

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py -q
```

Expected: FAIL only if backend contract still diverges from the spec.

- [ ] **Step 3: Implement only the minimal transport fixes required by the failing tests**

Frontend client target:

```js
await client.watchRuntimeUpdates({
  sinceVersion: snapshot.connection.lastEventVersion,
  onEvent,
  onClose,
  onError,
});
```

Backend contract target:

```python
assert bootstrap_version == runtime_update_hub.current_version()
assert event["version"] > requested_since_version
assert snapshot_covers_every_server_owned_slice_up_to(bootstrap_version)
```

Rules:
- do not expand backend scope if all backend tests are already green
- keep bootstrap and websocket on the same version domain
- keep `since_version` semantics exclusive
- keep the bootstrap snapshot barrier: `bootstrap.version` must cover every `version <= bootstrap.version` server-owned state change

- [ ] **Step 4: Re-run the same transport-contract tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/account_center_client.test.js tests/renderer/runtime_connection_manager.test.js
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py -q
```

Expected: PASS

- [ ] **Step 5: Commit only the contract-tightening files**

```bash
git add app_desktop_web/tests/renderer/account_center_client.test.js app_desktop_web/tests/renderer/runtime_connection_manager.test.js tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py app_desktop_web/src/api/account_center_client.js app_backend/api/routes/app_bootstrap.py app_backend/application/use_cases/get_app_bootstrap.py app_backend/api/websocket/runtime.py app_backend/infrastructure/events/runtime_update_hub.py
git commit -m "test: lock runtime bootstrap and websocket contract"
```

### Task 2: Add canonical comparator helpers and reshape the runtime store around authoritative slices

**Files:**
- Create: `app_desktop_web/src/runtime/runtime_draft_comparators.js`
- Create: `app_desktop_web/tests/renderer/runtime_draft_comparators.test.js`
- Modify: `app_desktop_web/src/runtime/app_runtime_store.js`
- Modify: `app_desktop_web/src/runtime/use_app_runtime.js`
- Modify: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`

- [ ] **Step 1: Write the failing comparator and reducer tests**

```js
it("normalizes query config payloads through one canonical helper", () => {
  expect(normalizeQueryConfigDraft({ name: "A", items: [{ sort_order: 2 }, { sort_order: 1 }] })).toEqual({
    name: "A",
    items: [{ sort_order: 1 }, { sort_order: 2 }],
  });
});

it("does not let query_configs.updated overwrite a dirty draft payload", () => {
  const store = createAppRuntimeStore();
  store.applyBootstrap(seedBootstrapPayload());
  store.actions.queryDraftEdited({ configId: "cfg-1", patch: { name: "本地草稿" } });
  store.applyRuntimeEvent({
    connectionGeneration: 1,
    version: 8,
    event: "query_configs.updated",
    payload: remoteConfigListWithName("服务器名称"),
  });
  expect(store.getSnapshot().querySystem.draft.currentConfig.name).toBe("本地草稿");
  expect(store.getSnapshot().querySystem.draft.currentConfig.hasRemoteChange).toBe(true);
});

it("treats capacitySummary as advisory data updated only by bootstrap or resync", () => {
  const store = createAppRuntimeStore();
  store.applyBootstrap(seedBootstrapPayload({ capacitySummary: { modes: { new_api: { available_account_count: 2 } } } }));
  store.applyRuntimeEvent({
    connectionGeneration: 1,
    version: 8,
    event: "query_configs.updated",
    payload: remoteConfigListWithName("服务器名称"),
  });
  expect(store.getSnapshot().querySystem.capacitySummary.modes.new_api.available_account_count).toBe(2);
});
```

- [ ] **Step 2: Run the new reducer/comparator tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/runtime_draft_comparators.test.js tests/renderer/runtime_connection_manager.test.js
```

Expected: FAIL because canonical helpers and spec-level draft metadata do not exist yet.

- [ ] **Step 3: Implement one shared canonical helper module for all four draft/editor types**

Required surface:

```js
export function normalizeQueryConfigDraft(value) {}
export function normalizePurchaseSettingsDraft(value) {}
export function normalizeManualAllocationDraft(value) {}
export function normalizeQuerySettingsDraft(value) {}
export function draftsSemanticallyEqual(left, right) {}
```

Rules:
- no per-page ad-hoc deep compare
- no inline JSON stringify compare in hooks or reducers
- helper output must be stable enough for authoritative-settle decisions

- [ ] **Step 4: Extend `app_runtime_store.js` to match the spec-owned state shape**

Required state additions:

```js
connection: {
  state,
  stale,
  lastSyncAt,
  lastEventVersion,
  lastError,
  currentGeneration,
  triggeringResyncVersion,
}

querySystem: {
  configsById,
  configOrder,
  capacitySummary,
  runtimeStatus,
  ui: { selectedConfigId },
  draft: {
    currentConfig,
    hasUnsavedChanges,
    baseConfigVersion,
    baseConfigUpdatedAt,
    hasRemoteChange,
    hasConflict,
    isOrphaned,
  },
}

purchaseSystem: {
  runtimeStatus,
  uiPreferences,
  runtimeSettings,
  ui: { selectedConfigId },
  draft: {
    purchaseSettingsDraft,
    manualAllocationDrafts,
    terminalSignal,
  },
}
```

Rules:
- bootstrap and runtime events may update server-owned slices and draft metadata only
- dirty payload overwrite is forbidden except for `pristine refresh` and matching authoritative settle
- reducer may emit `settle-ready`, `conflict`, or `orphan`, but must not own `pendingSelectedConfigId`
- `capacitySummary` is advisory-only: only bootstrap/resync may update it; runtime events and explicit refresh HTTP responses must not write it

- [ ] **Step 5: Re-run the reducer/comparator tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/runtime_draft_comparators.test.js tests/renderer/runtime_connection_manager.test.js
```

Expected: PASS

- [ ] **Step 6: Commit the store/comparator slice**

```bash
git add app_desktop_web/src/runtime/runtime_draft_comparators.js app_desktop_web/tests/renderer/runtime_draft_comparators.test.js app_desktop_web/src/runtime/app_runtime_store.js app_desktop_web/src/runtime/use_app_runtime.js app_desktop_web/tests/renderer/runtime_connection_manager.test.js
git commit -m "feat: add canonical runtime draft comparators"
```

### Task 3: Wire `App.jsx` and the connection manager to bootstrap once and keep the websocket alive

**Files:**
- Modify: `app_desktop_web/src/runtime/runtime_connection_manager.js`
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- Modify: `app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx`
- Modify: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`

- [ ] **Step 1: Write the failing startup/resync tests**

```jsx
it("bootstraps once and then starts one shared runtime stream in remote mode", async () => {
  render(<App runtimeStore={createAppRuntimeStore()} />);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/app/bootstrap"), expect.anything()));
  expect(openRuntimeSocket).toHaveBeenCalledTimes(1);
});

it("keeps the last good snapshot on disconnect and resyncs without clearing the page", async () => {
  const store = createAppRuntimeStore();
  render(<App runtimeStore={store} />);
  seedConnectedSnapshot(store);
  closeRuntimeSocketWithError("boom");
  expect(store.getSnapshot().connection.stale).toBe(true);
  expect(screen.getByText("白天配置")).toBeInTheDocument();
});

it("accepts an equal-version reconnect bootstrap and leaves stale mode", async () => {
  const store = seedHydratedStore({ lastEventVersion: 9, connectionState: "stale" });
  await manager.applyBootstrapResult({
    connectionGeneration: store.getSnapshot().connection.currentGeneration,
    version: 9,
    query_system: seedQuerySystemPayload(),
  });
  expect(store.getSnapshot().connection.state).toBe("connected");
  expect(store.getSnapshot().connection.stale).toBe(false);
});
```

- [ ] **Step 2: Run the startup/resync tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/remote_runtime_shell.test.jsx tests/renderer/runtime_connection_manager.test.js
```

Expected: FAIL because `App.jsx` still only bootstraps and does not own the full bootstrap-plus-stream lifecycle.

- [ ] **Step 3: Implement the one-owner startup flow in `runtime_connection_manager.js` and `App.jsx`**

Required manager surface:

```js
await manager.start();
manager.stop();
manager.handleRuntimeEvent(event);
manager.handleResyncRequired(event);
```

Required behavior:
- `App.jsx` starts the manager once in remote mode
- bootstrap and websocket share the same `connectionGeneration`
- late results from older generations are discarded
- ordinary reconnect must allow `bootstrap.version === lastEventVersion`
- disconnect marks the connection stale/error but preserves rendered business data

- [ ] **Step 4: Re-run the startup/resync tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/remote_runtime_shell.test.jsx tests/renderer/runtime_connection_manager.test.js
```

Expected: PASS

- [ ] **Step 5: Commit the startup/runtime-stream wiring**

```bash
git add app_desktop_web/src/runtime/runtime_connection_manager.js app_desktop_web/src/App.jsx app_desktop_web/src/api/account_center_client.js app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx app_desktop_web/tests/renderer/runtime_connection_manager.test.js
git commit -m "feat: start shared runtime stream from app shell"
```

## Chunk 2: Move Query Editing To Authoritative Settle

### Task 4: Convert the query page to store-owned server truth and authoritative draft settle

**Files:**
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/features/query-system/query_system_persistence.js`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/runtime/app_runtime_store.js`
- Modify: `app_desktop_web/src/runtime/runtime_draft_comparators.js`
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
- Modify: `app_desktop_web/tests/renderer/query_system_persistence.test.js`
- Modify: `app_desktop_web/tests/renderer/query_system_client.test.js`
- Modify: `app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx`
- Modify: `app_backend/api/routes/query_configs.py`
- Modify: `app_backend/api/schemas/query_configs.py`
- Modify: `app_backend/application/use_cases/update_query_config.py`
- Modify: `app_backend/infrastructure/repositories/query_config_repository.py`
- Modify: `tests/backend/test_query_config_routes.py`
- Modify: `tests/backend/test_query_config_repository.py`

- [ ] **Step 1: Write the failing query-page regression tests**

```jsx
it("does not fetch query page truth on initial entry or tab re-entry after bootstrap hydration", async () => {
  render(<App />);
  await openQuerySystemTab();
  await openPurchaseSystemTab();
  await openQuerySystemTab();
  expect(client.listQueryConfigs).toHaveBeenCalledTimes(0);
  expect(client.getQueryRuntimeStatus).toHaveBeenCalledTimes(0);
  expect(client.getQueryConfig).toHaveBeenCalledTimes(0);
});

it("does not clear dirty query draft on HTTP 200 before authoritative echo arrives", async () => {
  render(<App />);
  await renameCurrentConfig("改名中");
  await clickSave();
  expect(screen.getByText("有未保存更改")).toBeInTheDocument();
});

it("settles a query draft clean only after matching query_configs.updated arrives", async () => {
  render(<App />);
  await renameCurrentConfig("同步后的名字");
  await clickSave();
  pushRuntimeEvent(queryConfigsUpdated("cfg-1", { name: "同步后的名字", version: 9 }));
  expect(screen.queryByText("有未保存更改")).not.toBeInTheDocument();
  expect(readQueryDraftConflict("cfg-1")).toBe(false);
});

it("marks conflict instead of silently clearing when query_configs.updated mismatches the dirty draft", async () => {
  seedDirtyQueryDraft("cfg-1", { name: "本地版本" });
  pushRuntimeEvent(queryConfigsUpdated("cfg-1", { name: "远端版本", version: 9 }));
  expect(screen.getByText(/远端已变化/)).toBeInTheDocument();
});

it("sends query config saves through the persistence layer with baseConfigVersion", async () => {
  await persistQueryConfigDraft({
    client,
    sourceConfig: buildSourceConfig("cfg-1"),
    draftConfig: buildDraftConfig("cfg-1", { baseConfigVersion: 7 }),
  });
  expect(client.updateQueryConfig).toHaveBeenCalledWith(
    "cfg-1",
    expect.objectContaining({ baseConfigVersion: 7 }),
  );
});

it("serializes baseConfigVersion into the real query-config HTTP request", async () => {
  await client.updateQueryConfig("cfg-1", {
    name: "新名字",
    baseConfigVersion: 7,
  });
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/query-configs/cfg-1"),
    expect.objectContaining({ body: expect.stringContaining("\"baseConfigVersion\":7") }),
  );
});

it("does not patch capacitySummary from explicit refresh HTTP responses", async () => {
  seedCapacitySummary({ new_api: { available_account_count: 2 } });
  mockExplicitRefreshResponse({ capacity_summary: { modes: { new_api: { available_account_count: 99 } } } });
  await clickRefreshDetail();
  expect(readCapacitySummary("new_api").available_account_count).toBe(2);
});

def test_query_config_route_rejects_stale_base_config_version(app_client):
    response = app_client.put(
        "/query-configs/cfg-1",
        json={"name": "新名字", "baseConfigVersion": 1},
    )
    assert response.status_code == 409


def test_query_config_repository_rejects_stale_base_config_version(tmp_path):
    repository = build_query_config_repository(tmp_path)
    config = repository.create_config(name="原配置", description="原描述")
    repository.update_config(
        config.config_id,
        name="服务端已更新",
        description="新描述",
        base_config_version=1,
    )
    with pytest.raises(ValueError, match="baseConfigVersion"):
        repository.update_config(
            config.config_id,
            name="客户端旧提交",
            description="过期描述",
            base_config_version=1,
        )
```

- [ ] **Step 2: Run the query-page regression tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/query_system_page.test.jsx tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_persistence.test.js tests/renderer/query_system_client.test.js tests/renderer/remote_runtime_shell.test.jsx
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_routes.py -q
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_repository.py -q
```

Expected: FAIL because the query page still mixes direct fetch truth with local draft truth, and backend stale-base rejection is not yet locked at both route and repository boundaries.

- [ ] **Step 3: Refactor `use_query_system_page.js` and `query_system_persistence.js` so server truth and save transport both follow the spec**

Required rules:
- `configsById`, `configOrder`, `runtimeStatus`, `selectedConfigId` come from store selectors only
- mount-time `listQueryConfigs()` / `getQueryRuntimeStatus()` / `getQueryConfig()` cannot remain the normal truth path
- explicit refresh may trigger the backend command, but the final UI must still wait for `query_configs.updated` or resync bootstrap
- explicit refresh or `GET /query-configs/capacity-summary` response must not patch `capacitySummary`
- config metadata save must flow through the real persistence/client boundary, not an imaginary helper path
- `account_center_client.js`, `query_system_client.test.js`, `query_system_persistence.js`, and `query_system_persistence.test.js` must be updated together
- `query_system_client.test.js` must explicitly fail if `account_center_client.updateQueryConfig()` drops `baseConfigVersion` from the HTTP body
- backend schema/use-case/repository are in scope here; do not try to force a token contract through route-only changes

- [ ] **Step 4: Implement query draft settle/conflict/orphan behavior**

Required save contract:

```js
await persistQueryConfigDraft({
  client,
  sourceConfig,
  draftConfig: {
    ...draftConfig,
    baseConfigVersion: draftConfig.baseConfigVersion,
  },
});
```

Required reducer outcomes:
- match via canonical comparator => settle clean
- stale base or mismatch => stay dirty and mark `hasConflict`
- deleted config => mark `isOrphaned` and block silent rebind
- `query_configs.py` route contract must reject stale `baseConfigVersion` with a conflict response instead of silently accepting it
- `query_config_repository.py` and `update_query_config.py` must participate in stale-base validation, not just the route layer

- [ ] **Step 5: Re-run the query-page regression tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/query_system_page.test.jsx tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_persistence.test.js tests/renderer/query_system_client.test.js tests/renderer/remote_runtime_shell.test.jsx
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_routes.py -q
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_repository.py -q
```

Expected: PASS

- [ ] **Step 6: Commit the query-page authoritative-settle refactor**

```bash
git add app_desktop_web/src/features/query-system/hooks/use_query_system_page.js app_desktop_web/src/features/query-system/query_system_page.jsx app_desktop_web/src/features/query-system/query_system_persistence.js app_desktop_web/src/api/account_center_client.js app_desktop_web/src/runtime/app_runtime_store.js app_desktop_web/src/runtime/runtime_draft_comparators.js app_desktop_web/tests/renderer/query_system_page.test.jsx app_desktop_web/tests/renderer/query_system_editing.test.jsx app_desktop_web/tests/renderer/query_system_persistence.test.js app_desktop_web/tests/renderer/query_system_client.test.js app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx app_backend/api/routes/query_configs.py app_backend/api/schemas/query_configs.py app_backend/application/use_cases/update_query_config.py app_backend/infrastructure/repositories/query_config_repository.py tests/backend/test_query_config_routes.py tests/backend/test_query_config_repository.py
git commit -m "refactor: move query editing to authoritative runtime settle"
```

## Chunk 3: Move Purchase Editing To Authoritative Settle

### Task 5: Lock purchase-side transport tokens and shared-store semantics before touching page-level flow control

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/runtime/app_runtime_store.js`
- Modify: `app_desktop_web/src/runtime/runtime_draft_comparators.js`
- Modify: `app_desktop_web/src/runtime/use_app_runtime.js`
- Modify: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Modify: `app_backend/api/routes/query_runtime.py`
- Modify: `app_backend/api/routes/runtime_settings.py`
- Modify: `app_backend/api/schemas/query_runtime.py`
- Modify: `app_backend/api/schemas/runtime_settings.py`
- Modify: `app_backend/application/use_cases/update_purchase_runtime_settings.py`
- Modify: `app_backend/infrastructure/repositories/runtime_settings_repository.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_runtime_settings_routes.py`
- Modify: `tests/backend/test_runtime_settings_repository.py`

- [ ] **Step 1: Write the failing purchase transport and store tests**

```js
it("sends purchase settings saves with baseRuntimeSettingsVersion", async () => {
  await client.updatePurchaseRuntimeSettings({
    baseRuntimeSettingsVersion: 5,
    per_batch_ip_fanout_limit: 3,
  });
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/runtime-settings"),
    expect.objectContaining({ body: expect.stringContaining("\"baseRuntimeSettingsVersion\":5") }),
  );
});

it("sends manual allocation saves with editing and base tokens", async () => {
  await client.submitQueryRuntimeManualAllocations("cfg-1", {
    editingConfigId: "cfg-1",
    baseConfigId: "cfg-1",
    baseConfigVersion: 8,
    baseRuntimeVersion: 13,
    items: [],
  });
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/query-runtime"),
    expect.objectContaining({ body: expect.stringContaining("\"baseRuntimeVersion\":13") }),
  );
});

it("does not settle an ordinary manual-allocation draft when the command is accepted before purchase_runtime.updated", () => {
  const store = seedDirtyManualAllocationDraft();
  markManualAllocationCommandAccepted(store);
  expect(readManualAllocationDirty(store)).toBe(true);
  expect(store.getSnapshot().purchaseSystem.draft.terminalSignal).toBe(null);
});

it("does not settle purchase settings when the command is accepted before runtime_settings.updated", () => {
  const store = seedDirtyPurchaseSettingsDraft({ per_batch_ip_fanout_limit: 3 });
  markPurchaseSettingsCommandAccepted(store);
  expect(readPurchaseSettingsDirty(store)).toBe(true);
});

it("only lets purchase_runtime.updated settle manual-allocation save-and-switch", () => {
  const store = seedDirtyManualAllocationDraft();
  store.applyRuntimeEvent(queryConfigsUpdatedDifferentVersion());
  expect(store.getSnapshot().purchaseSystem.draft.terminalSignal).toBe(null);
  store.applyRuntimeEvent(purchaseRuntimeUpdatedMatchingDraft());
  expect(store.getSnapshot().purchaseSystem.draft.terminalSignal?.type).toBe("settle-ready");
});

it("marks purchase settings conflict instead of clearing dirty state on mismatch", () => {
  const store = seedDirtyPurchaseSettingsDraft();
  store.applyRuntimeEvent(runtimeSettingsUpdatedMismatch());
  expect(store.getSnapshot().purchaseSystem.draft.purchaseSettingsDraft.hasConflict).toBe(true);
});

it("settles purchase settings clean only after matching runtime_settings.updated arrives", () => {
  const store = seedDirtyPurchaseSettingsDraft({ per_batch_ip_fanout_limit: 3 });
  store.applyRuntimeEvent(runtimeSettingsUpdatedMatchingDraft({ per_batch_ip_fanout_limit: 3, version: 6 }));
  expect(readPurchaseSettingsDirty(store)).toBe(false);
  expect(store.getSnapshot().purchaseSystem.draft.purchaseSettingsDraft.hasConflict).toBe(false);
  expect(store.getSnapshot().purchaseSystem.draft.purchaseSettingsDraft.hasRemoteChange).toBe(false);
});
```

```python
async def test_put_purchase_runtime_settings_rejects_stale_base_runtime_settings_version(client):
    await client.put(
        "/runtime-settings/purchase",
        json={"baseRuntimeSettingsVersion": 1, "per_batch_ip_fanout_limit": 2},
    )
    response = await client.put(
        "/runtime-settings/purchase",
        json={"baseRuntimeSettingsVersion": 1, "per_batch_ip_fanout_limit": 3},
    )
    assert response.status_code == 409


def test_runtime_settings_repository_rejects_stale_base_runtime_settings_version(tmp_path):
    repository = build_runtime_settings_repository(tmp_path)
    repository.save_purchase_settings(
        {"per_batch_ip_fanout_limit": 2},
        base_runtime_settings_version=1,
    )
    with pytest.raises(ValueError, match="baseRuntimeSettingsVersion"):
        repository.save_purchase_settings(
            {"per_batch_ip_fanout_limit": 3},
            base_runtime_settings_version=1,
        )


async def test_update_query_runtime_manual_allocations_rejects_stale_base_tokens(client):
    response = await client.put(
        "/query-runtime/configs/cfg-1/manual-assignments",
        json={
            "editingConfigId": "cfg-1",
            "baseConfigId": "cfg-1",
            "baseConfigVersion": 1,
            "baseRuntimeVersion": 1,
            "items": [],
        },
    )
    assert response.status_code == 409


def test_query_runtime_service_rejects_stale_manual_allocation_base_versions():
    service = build_query_runtime_service_with_versions(config_version=2, runtime_version=5)
    with pytest.raises(ValueError, match="base(Config|Runtime)Version"):
        service.apply_manual_allocations(
            config_id="cfg-1",
            editing_config_id="cfg-1",
            base_config_id="cfg-1",
            base_config_version=1,
            base_runtime_version=4,
            items=[],
        )
```

- [ ] **Step 2: Run the purchase transport and store tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/runtime_connection_manager.test.js tests/renderer/purchase_system_client.test.js
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_routes.py tests/backend/test_query_runtime_service.py tests/backend/test_runtime_settings_routes.py tests/backend/test_runtime_settings_repository.py -q
```

Expected: FAIL because the store does not yet encode the spec-level purchase draft semantics, and backend stale-base rejection is not yet enforced across route plus lower-layer repository/service gates.

- [ ] **Step 3: Implement conflict-token transport and store-backed purchase draft semantics**

Required fields:

```js
purchaseSettingsDraft: {
  baseRuntimeSettingsVersion,
  hasRemoteChange,
  hasConflict,
}

manualAllocationDrafts: {
  editingConfigId,
  baseConfigId,
  baseConfigVersion,
  baseRuntimeVersion,
  hasRemoteChange,
  hasConflict,
  isOrphaned,
}
```

Required rules:
- `runtime_settings.py` must reject stale `baseRuntimeSettingsVersion` with a conflict response
- `query_runtime.py` must reject stale `editingConfigId/baseConfigId/baseConfigVersion/baseRuntimeVersion` combinations with a conflict response
- the schema layer must define these fields explicitly before route validation can pass them through
- lower-layer validation lives in `runtime_settings_repository.py` / `query_runtime_service.py`, not only in route code
- manual allocation currently has no dedicated use-case/repository boundary; `query_runtime_service.py` is the intended lower-layer contract gate and must be protected by direct backend tests
- Task 5 stays transport/store-only: do not pull `use_purchase_system_page.js` or page-only UI orchestration fixes into this task
- if a failing assertion still depends on HTTP 200 page patching, polling, or local save-and-switch flow ownership, carry that failure forward to Task 6 instead of widening Task 5
- `query_configs.updated` may update manual-allocation baseline metadata, but must not settle save-and-switch
- `purchase_runtime.updated` or resync bootstrap is the only settle path for manual allocation
- reducer emits terminal signals only; it never owns `pendingSelectedConfigId`
- `purchase_system_client.test.js` must fail if the client drops any required base token from the request body
- ordinary manual-allocation save and purchase settings save must keep old store values until authoritative event/resync arrives; HTTP success cannot settle them

- [ ] **Step 4: Re-run the purchase-store tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/runtime_connection_manager.test.js tests/renderer/purchase_system_client.test.js
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_routes.py tests/backend/test_query_runtime_service.py tests/backend/test_runtime_settings_routes.py tests/backend/test_runtime_settings_repository.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the purchase-store semantics**

```bash
git add app_desktop_web/src/api/account_center_client.js app_desktop_web/src/runtime/app_runtime_store.js app_desktop_web/src/runtime/runtime_draft_comparators.js app_desktop_web/src/runtime/use_app_runtime.js app_desktop_web/tests/renderer/runtime_connection_manager.test.js app_desktop_web/tests/renderer/purchase_system_client.test.js app_backend/api/routes/query_runtime.py app_backend/api/routes/runtime_settings.py app_backend/api/schemas/query_runtime.py app_backend/api/schemas/runtime_settings.py app_backend/application/use_cases/update_purchase_runtime_settings.py app_backend/infrastructure/repositories/runtime_settings_repository.py app_backend/infrastructure/query/runtime/query_runtime_service.py tests/backend/test_query_runtime_routes.py tests/backend/test_query_runtime_service.py tests/backend/test_runtime_settings_routes.py tests/backend/test_runtime_settings_repository.py
git commit -m "feat: encode purchase draft settle semantics in runtime store"
```

### Task 6: Refactor the purchase page into a local workflow controller with no polling and no preview-truth fallback

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/tests/renderer/account_center_client.test.js`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/query_settings_modal.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_settings_panel.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx`
- Modify: `app_backend/api/routes/query_configs.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Modify: `app_backend/api/schemas/query_configs.py`
- Modify: `app_backend/application/use_cases/update_query_mode_setting.py`
- Modify: `app_backend/application/use_cases/update_purchase_ui_preferences.py`
- Modify: `app_backend/infrastructure/repositories/query_config_repository.py`
- Modify: `tests/backend/test_query_config_routes.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`

- [ ] **Step 1: Write the failing purchase-page integration tests**

```jsx
it("does not keep a 1.5s polling loop once runtime websocket is active", async () => {
  vi.useFakeTimers();
  render(<App />);
  await openPurchaseSystemTab();
  vi.advanceTimersByTime(5000);
  expect(client.getPurchaseRuntimeStatus).toHaveBeenCalledTimes(0);
});

it("keeps pendingSelectedConfigId local until purchase_runtime.updated settles the old draft", async () => {
  await openPurchaseSystemTab();
  await editManualAllocation("item-1", "new_api", "2");
  await chooseSaveAndSwitch("cfg-2");
  expect(readSelectedConfig()).toBe("cfg-1");
  pushRuntimeEvent(queryConfigsUpdatedForCfg2Only());
  expect(readSelectedConfig()).toBe("cfg-1");
  pushRuntimeEvent(purchaseRuntimeUpdatedMatchingOldDraft());
  expect(readSelectedConfig()).toBe("cfg-2");
});

it("does not clear an ordinary manual-allocation draft on HTTP 200 before purchase_runtime.updated", async () => {
  await openPurchaseSystemTab();
  await editManualAllocation("item-1", "new_api", "2");
  await saveManualAllocation();
  expect(screen.getByText(/有未保存更改/)).toBeInTheDocument();
});

it("treats purchase-page querySettingsDraft as local modal state with baseConfigVersion freeze", async () => {
  await openQuerySettingsModal("cfg-1");
  await changeModeCooldown("token", "12");
  pushRuntimeEvent(queryConfigsUpdatedSameConfigDifferentPayload());
  expect(screen.getByText(/远端已变化/)).toBeInTheDocument();
  expect(screen.getByDisplayValue("12")).toBeInTheDocument();
});

it("sends query settings modal saves to the config-scoped target with frozen base tokens", async () => {
  await openQuerySettingsModal("cfg-1");
  await submitQuerySettingsModal();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/query-configs/cfg-1"),
    expect.objectContaining({ body: expect.stringContaining("\"baseConfigVersion\":") }),
  );
  expect(fetchMock).not.toHaveBeenCalledWith(
    expect.stringContaining("/query-settings"),
    expect.anything(),
  );
});

it("does not use the global /query-settings endpoint when opening the purchase-page query settings modal", async () => {
  await openQuerySettingsModal("cfg-1");
  expect(fetchMock).not.toHaveBeenCalledWith(
    expect.stringContaining("/query-settings"),
    expect.objectContaining({ method: "GET" }),
  );
});

it("seeds the purchase-page query settings modal from store without any config/query-settings fetch", async () => {
  await openQuerySettingsModal("cfg-1");
  expect(fetchMock).not.toHaveBeenCalledWith(
    expect.stringContaining("/query-configs/"),
    expect.objectContaining({ method: "GET" }),
  );
  expect(fetchMock).not.toHaveBeenCalledWith(
    expect.stringContaining("/query-settings"),
    expect.objectContaining({ method: "GET" }),
  );
});

it("account center client rejects any purchase-page query-settings transport that falls back to /query-settings", async () => {
  await client.updateConfigScopedQuerySettings("cfg-1", {
    baseConfigId: "cfg-1",
    baseConfigVersion: 7,
    modes: [],
  });
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/query-configs/cfg-1"),
    expect.objectContaining({ body: expect.stringContaining("\"baseConfigVersion\":7") }),
  );
  expect(fetchMock).not.toHaveBeenCalledWith(
    expect.stringContaining("/query-settings"),
    expect.anything(),
  );
});

it.each(["conflict", "orphan", "submit-failure", "cancel", "discard", "success"])(
  "clears pendingSelectedConfigId on %s",
  async (terminalCase) => {
    await startSaveAndSwitchFlow();
    await driveTerminalCase(terminalCase);
    expect(readPendingSelectedConfigId()).toBe(null);
  },
);

it("uses purchase_ui_preferences.updated as the ordinary config-switch settle path", async () => {
  await openPurchaseSystemTab();
  await chooseConfigWithoutDirtyDraft("cfg-2");
  expect(readSelectedConfig()).toBe("cfg-1");
  pushRuntimeEvent(purchaseUiPreferencesUpdated("cfg-2"));
  expect(readSelectedConfig()).toBe("cfg-2");
});

it("does not patch runtime status on start or stop HTTP success before purchase_runtime.updated", async () => {
  await clickRuntimeStart();
  expect(readRuntimeRunning()).toBe(false);
  pushRuntimeEvent(purchaseRuntimeUpdatedRunning());
  expect(readRuntimeRunning()).toBe(true);
});

it("does not settle purchase settings on HTTP 200 before runtime_settings.updated", async () => {
  await editPurchaseSettingsLimit("3");
  await savePurchaseSettings();
  expect(screen.getByText(/有未保存更改/)).toBeInTheDocument();
});

it("does not close the query settings modal on HTTP 200 before authoritative echo", async () => {
  await openQuerySettingsModal("cfg-1");
  await submitQuerySettingsModal();
  expect(screen.getByRole("dialog", { name: /查询设置/ })).toBeInTheDocument();
});

it("settles the query settings modal clean and closes only after matching query_configs.updated arrives", async () => {
  await openQuerySettingsModal("cfg-1");
  await changeModeCooldown("token", "12");
  await submitQuerySettingsModal();
  pushRuntimeEvent(queryConfigsUpdatedMatchingModalDraft("cfg-1", { token: { item_min_cooldown_seconds: 12 } }));
  expect(screen.queryByRole("dialog", { name: /查询设置/ })).not.toBeInTheDocument();
  expect(readQuerySettingsModalConflict()).toBe(false);
});

it("treats resync bootstrap like query_configs.updated for querySettingsDraft settle and orphan paths", async () => {
  await openQuerySettingsModal("cfg-1");
  await changeModeCooldown("token", "12");
  pushResyncBootstrapWithoutConfig("cfg-1");
  expect(screen.getByText(/配置已不存在/)).toBeInTheDocument();
});

it("rebuilds the next manual-allocation draft from authoritative slices after save-and-switch settles", async () => {
  await openPurchaseSystemTab();
  await editManualAllocation("item-1", "new_api", "2");
  await chooseSaveAndSwitch("cfg-2");
  pushRuntimeEvent(purchaseRuntimeUpdatedMatchingOldDraft());
  pushRuntimeEvent(purchaseUiPreferencesUpdated("cfg-2"));
  expect(readSelectedConfig()).toBe("cfg-2");
  expect(readManualAllocationEditorDraft()).toEqual(
    buildManualAllocationDraftFromAuthoritativeSlices("cfg-2"),
  );
});

async def test_patch_query_mode_setting_rejects_stale_base_config_version(client):
    created = await client.post(
        "/query-configs",
        json={"name": "夜间配置", "description": "晚上跑"},
    )
    config_id = created.json()["config_id"]
    await client.patch(
        f"/query-configs/{config_id}/modes/new_api",
        json={"baseConfigVersion": 1, "enabled": True, "base_cooldown_min": 1.0, "base_cooldown_max": 1.0},
    )
    response = await client.patch(
        f"/query-configs/{config_id}/modes/new_api",
        json={"baseConfigVersion": 1, "enabled": False, "base_cooldown_min": 2.0, "base_cooldown_max": 2.0},
    )
    assert response.status_code == 409
```

- [ ] **Step 2: Run the purchase-page integration tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/account_center_client.test.js tests/renderer/purchase_system_client.test.js tests/renderer/purchase_system_page.test.jsx tests/renderer/remote_runtime_shell.test.jsx
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_routes.py tests/backend/test_purchase_runtime_routes.py -q
```

Expected: FAIL because the purchase page still owns polling, preview fallback truth, and mixed local/server draft logic.

- [ ] **Step 3: Refactor `use_purchase_system_page.js` into a pure local workflow controller**

Required ownership:
- local `pendingSelectedConfigId`
- local `querySettingsDraft`
- leave-prompt orchestration
- submit pending flags and toast/error copy

Forbidden ownership:
- authoritative runtime status
- authoritative config list
- authoritative purchase settings payload
- any shadow object used as primary page render truth

Additional required transport boundary:
- replace purchase-page usage of the global `/query-settings` save path with the config-scoped `query_configs.py` path
- remove global `/query-settings` GET/PUT fallback from the purchase-page modal path and lock that with negative client/page tests
- modal open must seed from `querySystem.configsById[purchaseSystem.ui.selectedConfigId]`, not any transport fetch
- freeze `baseConfigId` and `baseConfigVersion` inside the local modal controller
- ordinary config switches must wait for `purchase_ui_preferences.updated`; HTTP response must not directly patch `purchaseSystem.ui.selectedConfigId`
- `account_center_client.test.js` must fail if the modal transport ever reintroduces `/query-settings` GET/PUT fallback
- `query_configs.py` schema/use-case/repository path is in scope here; stale-base validation cannot be implemented in route-only code
- `purchase_runtime.py` / `update_purchase_ui_preferences.py` are in scope for ordinary config-switch authoritative echo behavior

- [ ] **Step 4: Remove polling and preview fallback as primary truth**

Required behavior:
- no unconditional `setInterval(..., 1500)`
- no `PREVIEW_ITEM_ROWS` path when server-owned runtime slices are absent
- disconnected state keeps the last good runtime snapshot and surfaces connection status instead of blank default data
- `querySettingsDraft` stays open after HTTP 200 until authoritative echo/resync says match
- matching `query_configs.updated` or matching resync snapshot is the only path that settles `querySettingsDraft` clean and closes the modal
- `pendingSelectedConfigId` is cleared on conflict, orphan, submit failure, user cancel, discard, and successful consume
- once save-and-switch finishes settling and selection really changes, the new manual-allocation editor payload must be rebuilt from authoritative `querySystem + purchaseSystem.runtimeStatus` slices instead of copying the old dirty payload
- purchase settings save, runtime start/stop, and ordinary config switch must all keep old store values until authoritative runtime event arrives

- [ ] **Step 5: Re-run the purchase-page integration tests**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/account_center_client.test.js tests/renderer/purchase_system_client.test.js tests/renderer/purchase_system_page.test.jsx tests/renderer/remote_runtime_shell.test.jsx
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_routes.py tests/backend/test_purchase_runtime_routes.py -q
```

Expected: PASS

- [ ] **Step 6: Commit the purchase-page controller refactor**

```bash
git add app_desktop_web/src/api/account_center_client.js app_desktop_web/tests/renderer/account_center_client.test.js app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/src/features/purchase-system/components/query_settings_modal.jsx app_desktop_web/src/features/purchase-system/components/purchase_settings_panel.jsx app_desktop_web/tests/renderer/purchase_system_client.test.js app_desktop_web/tests/renderer/purchase_system_page.test.jsx app_desktop_web/tests/renderer/remote_runtime_shell.test.jsx app_backend/api/routes/query_configs.py app_backend/api/routes/purchase_runtime.py app_backend/api/schemas/query_configs.py app_backend/application/use_cases/update_query_mode_setting.py app_backend/application/use_cases/update_purchase_ui_preferences.py app_backend/infrastructure/repositories/query_config_repository.py tests/backend/test_query_config_routes.py tests/backend/test_purchase_runtime_routes.py
git commit -m "refactor: make purchase page follow authoritative runtime state"
```

## Chunk 4: Remove Legacy Paths And Verify The Whole Flow

### Task 7: Delete dead fallback paths and run the full targeted regression gate

**Files:**
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/runtime/app_runtime_store.js`
- Modify: `app_desktop_web/src/runtime/runtime_draft_comparators.js`
- Modify: `app_desktop_web/src/runtime/runtime_connection_manager.js`
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Modify: `app_desktop_web/src/features/query-system/query_system_persistence.js`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- Modify: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`
- Modify: `app_desktop_web/tests/renderer/runtime_draft_comparators.test.js`
- Modify: `app_desktop_web/tests/renderer/query_system_persistence.test.js`
- Modify: `app_desktop_web/tests/renderer/query_system_client.test.js`
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify if contract regressions appear: `app_backend/api/routes/query_configs.py`
- Modify if contract regressions appear: `app_backend/api/routes/query_runtime.py`
- Modify if contract regressions appear: `app_backend/api/routes/purchase_runtime.py`
- Modify if contract regressions appear: `app_backend/api/routes/runtime_settings.py`
- Modify if contract regressions appear: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify if contract regressions appear: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify if contract regressions appear: `tests/backend/test_query_config_routes.py`
- Modify if contract regressions appear: `tests/backend/test_query_runtime_routes.py`
- Modify if contract regressions appear: `tests/backend/test_purchase_runtime_routes.py`
- Modify if contract regressions appear: `tests/backend/test_runtime_settings_routes.py`
- Modify if contract regressions appear: `tests/backend/test_query_runtime_service.py`
- Modify if contract regressions appear: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: Write or update the final blank-state and disconnect regressions**

```jsx
it("shows stale connection state without reverting pages to default placeholders", async () => {
  seedHydratedRemoteRuntime();
  closeRuntimeSocketWithError("network");
  expect(screen.queryByText(/未加载/)).not.toBeInTheDocument();
  expect(screen.getByText(/连接已过期/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Remove only the legacy paths that the passing tests have made obsolete**

Delete or collapse:
- page-level bootstrap reload effects
- direct HTTP-response patching of `querySystem.*` / `purchaseSystem.*`
- polling-only refresh branches
- preview-truth fallback branches
- dead helper code no longer referenced after store migration
- any explicit refresh path that still writes `capacitySummary` outside bootstrap/resync

- [ ] **Step 3: Run the targeted renderer suite**

Run:

```bash
cd app_desktop_web
npm test -- tests/renderer/account_center_client.test.js tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/remote_runtime_shell.test.jsx tests/renderer/runtime_connection_manager.test.js tests/renderer/runtime_draft_comparators.test.js tests/renderer/query_system_client.test.js tests/renderer/query_system_persistence.test.js tests/renderer/query_system_page.test.jsx tests/renderer/query_system_editing.test.jsx tests/renderer/purchase_system_client.test.js tests/renderer/purchase_system_page.test.jsx
```

Expected: PASS

- [ ] **Step 4: Run the targeted backend contract suite**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_routes.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_runtime_settings_routes.py tests/backend/test_query_runtime_service.py tests/backend/test_purchase_runtime_service.py -q
```

```bash
.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_repository.py tests/backend/test_runtime_settings_repository.py -q
```

Expected: PASS

- [ ] **Step 5: Run the targeted electron safety suite**

Run:

```bash
cd app_desktop_web
npm test -- tests/electron/electron_remote_mode.test.js tests/electron/electron_entrypoints.test.js tests/electron/python_backend.test.js
```

Expected: PASS

- [ ] **Step 6: Complete the manual smoke checklist**

Checklist:
- remote mode first paint comes from `/app/bootstrap`
- query and purchase page switching does not blank back to default view
- disconnect leaves the last good business state on screen
- reconnect or `runtime.resync_required` recovers state without duplicate streams
- query save, purchase settings save, manual allocation save-and-switch, and purchase-page query settings save all wait for authoritative echo/resync before settling clean
- purchase-page query settings modal only closes after matching authoritative echo/resync
- save-and-switch lands on the new config with a draft rebuilt from current authoritative slices, not from stale local payload

- [ ] **Step 7: Commit the cleanup and final regression gate**

```bash
git add app_desktop_web/src/App.jsx app_desktop_web/src/api/account_center_client.js app_desktop_web/src/runtime/app_runtime_store.js app_desktop_web/src/runtime/runtime_draft_comparators.js app_desktop_web/src/runtime/runtime_connection_manager.js app_desktop_web/src/features/query-system/hooks/use_query_system_page.js app_desktop_web/src/features/query-system/query_system_persistence.js app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx app_desktop_web/tests/renderer/runtime_connection_manager.test.js app_desktop_web/tests/renderer/runtime_draft_comparators.test.js app_desktop_web/tests/renderer/query_system_client.test.js app_desktop_web/tests/renderer/query_system_persistence.test.js app_desktop_web/tests/renderer/query_system_page.test.jsx app_desktop_web/tests/renderer/query_system_editing.test.jsx app_desktop_web/tests/renderer/purchase_system_client.test.js app_desktop_web/tests/renderer/purchase_system_page.test.jsx app_backend/api/routes/query_configs.py app_backend/api/routes/query_runtime.py app_backend/api/routes/purchase_runtime.py app_backend/api/routes/runtime_settings.py app_backend/infrastructure/query/runtime/query_runtime_service.py app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_routes.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_runtime_settings_routes.py tests/backend/test_query_runtime_service.py tests/backend/test_purchase_runtime_service.py
git commit -m "feat: finish remote runtime authoritative state sync"
```

## Final Handoff

- [ ] **Step 1: Verify the implementation against the spec**

Spec to re-read before declaring done:

```text
docs/superpowers/specs/2026-04-02-remote-runtime-state-sync-design.md
```

Focus points:
- bootstrap-once + shared websocket
- no page-owned server truth
- no HTTP success direct settle
- canonical comparator only
- `pendingSelectedConfigId` and local `querySettingsDraft` owned only by the purchase-page controller

- [ ] **Step 2: Request final code review before merge**

Required review mode:
- one worker result per task
- two read-only reviewers
- fix findings
- re-review until both reviewers explicitly return `no findings`

- [ ] **Step 3: Prepare the merge diff**

Only after all tests pass:

```bash
git status --short
git log --oneline --decorate -5
```

Expected:
- only task-owned files are staged/committed
- no unrelated dirty files are accidentally folded into the implementation branch
