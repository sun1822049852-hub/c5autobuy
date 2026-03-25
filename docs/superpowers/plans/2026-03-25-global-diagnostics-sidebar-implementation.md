# Global Diagnostics Sidebar Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent left-side diagnostics panel backed by one read-only backend aggregate endpoint so query, purchase, and login-task health become visible without slowing the query-to-purchase chain.

**Architecture:** Reuse existing runtime snapshots instead of introducing disk logs. Add `GET /diagnostics/sidebar` in FastAPI to aggregate query runtime, purchase runtime, and recent login tasks into one light payload, then poll that payload from the desktop web shell every `1500ms` in the foreground and `5000ms` when the window is hidden. Render the diagnostics panel as the second shell column so every page sees the same state without duplicating fetch logic.

**Tech Stack:** FastAPI, Pydantic, existing runtime services/task manager, React 19, existing desktop web CSS, pytest + httpx, Vitest + Testing Library.

---

## File Map

### Backend

- Create: `app_backend/api/routes/diagnostics.py`
  Read-only `GET /diagnostics/sidebar` route that pulls app-state services and returns the aggregate response model.
- Create: `app_backend/api/schemas/diagnostics.py`
  Pydantic response models for `summary`, `query`, `purchase`, `login_tasks`, and the nested row/event structures used by the sidebar.
- Create: `app_backend/application/use_cases/get_sidebar_diagnostics.py`
  Pure aggregation and normalization layer. This file should:
  - call `query_runtime_service.get_status()`
  - call `GetPurchaseRuntimeStatusUseCase(purchase_runtime_service, query_runtime_service).execute()`
  - call a new public `task_manager.list_recent_tasks(...)`
  - derive abnormal-first `query.account_rows` from existing `group_rows`
  - derive abnormal-first `purchase.account_rows` from existing `accounts`
  - trim recent events and task timelines to fixed lengths
  - compute top summary fields without triggering any remote refresh
- Modify: `app_backend/workers/manager/task_manager.py`
  Add read-only helpers such as `list_recent_tasks(task_type: str | None = None, limit: int = 10)` that return deep-copied snapshots sorted by `updated_at` descending.
- Modify: `app_backend/main.py`
  Register the diagnostics router.
- Create: `tests/backend/test_diagnostics_routes.py`
  Route contract tests for idle, running, and abnormal states.

### Frontend

- Modify: `app_desktop_web/src/api/account_center_client.js`
  Add `getSidebarDiagnostics()`.
- Create: `app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js`
  Single polling hook for the whole app. It owns loading/error state, visibility-aware polling cadence, and request dedupe/cleanup.
- Create: `app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx`
  Panel container, loading/error/empty states, collapse affordance, top summary, active tab body.
- Create: `app_desktop_web/src/features/diagnostics/diagnostics_tabs.jsx`
  Tab switcher for `查询`, `购买`, `登录任务`.
- Create: `app_desktop_web/src/features/diagnostics/diagnostics_summary.jsx`
  Shared summary cards / compact health strip.
- Create: `app_desktop_web/src/features/diagnostics/diagnostics_event_list.jsx`
  Shared compact event timeline list with capped rows.
- Create: `app_desktop_web/src/features/diagnostics/query_diagnostics_tab.jsx`
  Deep query tab: runtime summary, mode rows, abnormal accounts, recent events.
- Create: `app_desktop_web/src/features/diagnostics/purchase_diagnostics_tab.jsx`
  Basic purchase tab: runtime summary, abnormal accounts, recent events.
- Create: `app_desktop_web/src/features/diagnostics/login_task_diagnostics_tab.jsx`
  Basic login-task tab: task summary, running/conflict/failed tasks, compact timeline preview.
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
  Expand shell from two columns to `nav | diagnostics | content`, with collapsible diagnostics column.
- Modify: `app_desktop_web/src/App.jsx`
  Mount the diagnostics polling hook once, render the diagnostics panel once, and pass it into `AppShell`.
- Modify: `app_desktop_web/src/styles/app.css`
  Three-column shell layout, diagnostics panel visuals, responsive collapse behavior, and shared status color tokens if needed.
- Create: `app_desktop_web/tests/renderer/diagnostics_client.test.js`
  Client-level API contract test for `/diagnostics/sidebar`.
- Create: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`
  Renderer tests for shell placement, polling result rendering, tab switching, abnormal rows, and responsive/collapsed behavior.
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
  Update top-level shell expectations now that the diagnostics column exists on the default page.
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
  Guard that diagnostics stays in the shell while query page content remains config-management-only.
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
  Guard that diagnostics column coexists with the purchase page layout and does not replace page-local runtime controls.

### Existing Read Sources To Reuse

- `app_backend/api/routes/query_runtime.py`
- `app_backend/api/routes/purchase_runtime.py`
- `app_backend/api/schemas/query_runtime.py`
- `app_backend/api/schemas/purchase_runtime.py`
- `app_backend/application/use_cases/get_purchase_runtime_status.py`
- `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- `app_backend/workers/manager/task_manager.py`
- `app_desktop_web/src/App.jsx`
- `app_desktop_web/src/features/shell/app_shell.jsx`
- `app_desktop_web/src/api/account_center_client.js`
- `app_desktop_web/src/styles/app.css`

---

## Chunk 1: Backend Contract First

### Task 1: Add failing route tests for the aggregate diagnostics endpoint

**Files:**
- Create: `tests/backend/test_diagnostics_routes.py`

- [ ] Add an idle snapshot test that expects:
  - `GET /diagnostics/sidebar` returns `200`
  - `summary.backend_online` is `true`
  - `query.running` is `false`
  - `purchase.running` is `false`
  - `login_tasks.recent_tasks` is `[]`
- [ ] Add a populated snapshot test using fake runtime services plus seeded login tasks:

```python
async def test_sidebar_diagnostics_returns_query_purchase_and_login_sections(client, app):
    app.state.query_runtime_service = FakeQueryRuntimeService()
    app.state.purchase_runtime_service = FakePurchaseRuntimeService()
    task = app.state.task_manager.create_task(task_type="login", message="创建任务")
    app.state.task_manager.set_state(task.task_id, "waiting_for_scan", message="等待扫码")

    response = await client.get("/diagnostics/sidebar")

    assert response.status_code == 200
    assert response.json()["summary"]["query_running"] is True
    assert response.json()["query"]["mode_rows"][0]["mode_type"] == "token"
    assert response.json()["purchase"]["account_rows"][0]["last_error"] == "库存刷新失败"
    assert response.json()["login_tasks"]["recent_tasks"][0]["state"] == "waiting_for_scan"
```

- [ ] Add an abnormal-account prioritization test that proves:
  - query abnormal accounts come from `group_rows` with `last_error` or `disabled_reason`
  - purchase abnormal accounts come from `accounts` with `purchase_disabled` or `last_error`
  - long event/task lists are capped

- [ ] Run: `python -m pytest tests/backend/test_diagnostics_routes.py -q`
Expected: FAIL because `/diagnostics/sidebar` does not exist yet.

### Task 2: Add read-only task listing support

**Files:**
- Modify: `app_backend/workers/manager/task_manager.py`
- Test: `tests/backend/test_task_manager.py`

- [ ] Add a failing unit test for `list_recent_tasks()` ordering and deep-copy behavior.
- [ ] Implement `list_recent_tasks()` so it:
  - never mutates internal task storage
  - can filter by `task_type`
  - sorts by `updated_at` descending
  - applies a hard `limit`
- [ ] Run: `python -m pytest tests/backend/test_task_manager.py -q`
Expected: PASS with the new helper covered.

### Task 3: Implement the diagnostics schema and aggregation use case

**Files:**
- Create: `app_backend/api/schemas/diagnostics.py`
- Create: `app_backend/application/use_cases/get_sidebar_diagnostics.py`

- [ ] Add response models for:
  - `SidebarDiagnosticsResponse`
  - `SidebarDiagnosticsSummaryResponse`
  - `SidebarQueryDiagnosticsResponse`
  - `SidebarPurchaseDiagnosticsResponse`
  - `SidebarLoginTasksDiagnosticsResponse`
  - nested row/event/task models used by the route
- [ ] Implement `GetSidebarDiagnosticsUseCase.execute()` so it returns a dict shaped like:

```python
{
    "summary": {
        "backend_online": True,
        "query_running": False,
        "purchase_running": False,
        "active_query_config_name": None,
        "last_error": None,
        "updated_at": "2026-03-25T20:00:00",
    },
    "query": {...},
    "purchase": {...},
    "login_tasks": {...},
    "updated_at": "2026-03-25T20:00:00",
}
```

- [ ] Keep the use case read-only:
  - do not call any refresh method
  - do not write disk logs
  - do not sleep or block on background tasks
- [ ] Derive `query.last_error` from the first non-empty source in:
  - mode `last_error`
  - abnormal group row `last_error`
  - recent event `error`
- [ ] Derive `purchase.last_error` from the first non-empty source in:
  - abnormal account `last_error`
  - recent event failure/error text
- [ ] Limit rows:
  - query recent events: `20`
  - purchase recent events: `20`
  - login recent tasks: `12`
  - login task events per task: `3`
  - abnormal account rows per tab: `8`

### Task 4: Add the route and wire it into the app

**Files:**
- Create: `app_backend/api/routes/diagnostics.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_diagnostics_routes.py`

- [ ] Add `GET /diagnostics/sidebar`.
- [ ] Validate through `SidebarDiagnosticsResponse.model_validate(...)`.
- [ ] Register the router in `create_app()`.
- [ ] Run: `python -m pytest tests/backend/test_diagnostics_routes.py -q`
Expected: PASS.

- [ ] Checkpoint commit:

```bash
git add app_backend/api/routes/diagnostics.py app_backend/api/schemas/diagnostics.py app_backend/application/use_cases/get_sidebar_diagnostics.py app_backend/workers/manager/task_manager.py app_backend/main.py tests/backend/test_diagnostics_routes.py tests/backend/test_task_manager.py
git commit -m "feat: add sidebar diagnostics backend"
```

---

## Chunk 2: Frontend Client and Polling Hook

### Task 5: Add failing client and shell tests

**Files:**
- Create: `app_desktop_web/tests/renderer/diagnostics_client.test.js`
- Create: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] Add a client test that expects:

```js
const client = createAccountCenterClient({
  apiBaseUrl: "http://127.0.0.1:8123",
  fetchImpl,
});

await client.getSidebarDiagnostics();

expect(fetchImpl).toHaveBeenCalledWith(
  "http://127.0.0.1:8123/diagnostics/sidebar",
  expect.objectContaining({ method: "GET" }),
);
```

- [ ] Add a renderer test that mounts `<App />` and expects:
  - diagnostics panel is visible on the left of content
  - top tab labels `查询`, `购买`, `登录任务` exist
  - default query tab shows total query/found and most recent error/event text
  - clicking `购买` and `登录任务` swaps bodies without changing the page route
- [ ] Run:

```bash
npm test -- app_desktop_web/tests/renderer/diagnostics_client.test.js app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx
```

Expected: FAIL because the client method and diagnostics components do not exist yet.

### Task 6: Add the client method

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Test: `app_desktop_web/tests/renderer/diagnostics_client.test.js`

- [ ] Implement `getSidebarDiagnostics()` using `http.getJson("/diagnostics/sidebar", { method: "GET" })`.
- [ ] Run:

```bash
npm test -- app_desktop_web/tests/renderer/diagnostics_client.test.js
```

Expected: PASS.

### Task 7: Add the shared polling hook

**Files:**
- Create: `app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js`
- Test: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] Implement a hook state shape like:

```js
{
  error: "",
  isLoading: true,
  isRefreshing: false,
  snapshot: null,
  refresh: async () => {},
}
```

- [ ] Use one in-flight request at a time.
- [ ] Use `1500ms` while `document.visibilityState === "visible"`.
- [ ] Use `5000ms` when hidden.
- [ ] Ignore polling errors after storing the latest error string; never throw into the shell render path.
- [ ] Keep the hook app-global. Do not fetch separately inside page components.
- [ ] Run:

```bash
npm test -- app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx
```

Expected: still FAIL because the shell and panel are not rendered yet.

---

## Chunk 3: Shell Layout and Diagnostics Panel Skeleton

### Task 8: Add the shell slot and mount the diagnostics panel once

**Files:**
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Create: `app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx`
- Create: `app_desktop_web/src/features/diagnostics/diagnostics_tabs.jsx`
- Create: `app_desktop_web/src/features/diagnostics/diagnostics_summary.jsx`
- Create: `app_desktop_web/src/features/diagnostics/diagnostics_event_list.jsx`

- [ ] Update `App.jsx` to:
  - call `useSidebarDiagnostics(client)`
  - create one diagnostics panel node
  - pass that node into `AppShell`
- [ ] Update `AppShell` props to accept a diagnostics slot:

```jsx
<AppShell
  activeItem={activeItem}
  diagnosticsPanel={diagnosticsPanel}
  onSelect={handleSelectItem}
>
  {page}
</AppShell>
```

- [ ] Render `nav | diagnostics | content` in `AppShell`.
- [ ] Keep page-switching logic unchanged.
- [ ] Add collapse support so narrow windows can hide the middle column without unmounting page content.

### Task 9: Add shared styles for the new middle column

**Files:**
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] Change `.app-shell` from two columns to three columns.
- [ ] Add dedicated classes for:
  - `.app-shell__diagnostics`
  - `.diagnostics-panel`
  - `.diagnostics-panel.is-collapsed`
  - `.diagnostics-summary`
  - `.diagnostics-tabs`
  - `.diagnostics-event-list`
- [ ] Add responsive rules:
  - large screens keep the second column visible
  - medium screens allow manual collapse
  - narrow screens stack to one column and auto-collapse diagnostics by default
- [ ] Preserve existing page layout widths. Do not rewrite query/purchase/account page internals in this chunk.

### Task 10: Make the shell tests pass again

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] Update shell assertions so all pages still render their existing content plus the diagnostics column.
- [ ] Run:

```bash
npm test -- app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx app_desktop_web/tests/renderer/account_center_page.test.jsx app_desktop_web/tests/renderer/query_system_page.test.jsx app_desktop_web/tests/renderer/purchase_system_page.test.jsx
```

Expected: PASS for the shell-level diagnostics skeleton, with tab content still minimal.

- [ ] Checkpoint commit:

```bash
git add app_desktop_web/src/App.jsx app_desktop_web/src/features/shell/app_shell.jsx app_desktop_web/src/features/diagnostics app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/diagnostics_client.test.js app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx app_desktop_web/tests/renderer/account_center_page.test.jsx app_desktop_web/tests/renderer/query_system_page.test.jsx app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat: add diagnostics shell scaffold"
```

---

## Chunk 4: Query Tab Deep Dive

### Task 11: Add failing query-tab assertions

**Files:**
- Modify: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] Add query-tab expectations for:
  - current config name and runtime message
  - `total_query_count` and `total_found_count`
  - mode rows for `new_api`, `fast_api`, `token`
  - abnormal account list built from `account_rows`
  - recent events list with level, account display, mode, and error/message
- [ ] Run:

```bash
npm test -- app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx
```

Expected: FAIL because query-tab deep rendering is not complete yet.

### Task 12: Implement the query diagnostics tab

**Files:**
- Create: `app_desktop_web/src/features/diagnostics/query_diagnostics_tab.jsx`
- Modify: `app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx`
- Modify: `app_desktop_web/src/features/diagnostics/diagnostics_summary.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] Render:
  - runtime summary cards
  - mode status table/list
  - abnormal accounts list
  - shared recent event list
- [ ] Prioritize errors visually:
  - `last_error` and disabled reasons use danger styling
  - inactive but error-free rows stay muted
- [ ] Keep the list sizes capped and scrollable inside the panel, not the whole page.
- [ ] Run:

```bash
npm test -- app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx
```

Expected: PASS for the query tab.

---

## Chunk 5: Purchase and Login Tabs Basic Coverage

### Task 13: Add failing purchase/login tab assertions

**Files:**
- Modify: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] Add purchase-tab expectations for:
  - running state, active accounts, total purchased count
  - abnormal account rows with selected inventory and `last_error`
  - recent purchase events
- [ ] Add login-tab expectations for:
  - `running_count`, `conflict_count`, `failed_count`
  - recent tasks list
  - compact per-task timeline preview capped to three events
- [ ] Run:

```bash
npm test -- app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx
```

Expected: FAIL because those tab bodies are still placeholders.

### Task 14: Implement purchase and login diagnostics tabs

**Files:**
- Create: `app_desktop_web/src/features/diagnostics/purchase_diagnostics_tab.jsx`
- Create: `app_desktop_web/src/features/diagnostics/login_task_diagnostics_tab.jsx`
- Modify: `app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] Purchase tab must show:
  - runtime summary
  - abnormal-first account rows
  - recent events via the shared event list
- [ ] Login tab must show:
  - compact summary chips
  - recent tasks list
  - each task’s latest message plus trimmed event preview
- [ ] Keep the UI read-only in stage 1. No retry buttons, no export, no search.
- [ ] Run:

```bash
npm test -- app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx
```

Expected: PASS.

- [ ] Checkpoint commit:

```bash
git add app_desktop_web/src/features/diagnostics app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx
git commit -m "feat: add query purchase and login diagnostics tabs"
```

---

## Chunk 6: Final Verification and Manual Smoke Check

### Task 15: Run targeted verification

**Files:**
- Verify only

- [ ] Run:

```bash
python -m pytest tests/backend/test_task_manager.py tests/backend/test_diagnostics_routes.py -q
```

Expected: all diagnostics-related backend tests PASS.

- [ ] Run:

```bash
npm test -- app_desktop_web/tests/renderer/diagnostics_client.test.js app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx app_desktop_web/tests/renderer/account_center_page.test.jsx app_desktop_web/tests/renderer/query_system_page.test.jsx app_desktop_web/tests/renderer/purchase_system_page.test.jsx
```

Expected: all diagnostics-related renderer tests PASS.

### Task 16: Run broader regression

**Files:**
- Verify only

- [ ] Run:

```bash
python -m pytest -q
```

Expected: full backend suite PASS and no regression to the existing token-inventory-refresh work.

- [ ] Run:

```bash
npm test
```

Expected: full renderer suite PASS.

### Task 17: Manual smoke check in the desktop shell

**Files:**
- Verify only

- [ ] Start the app with the project’s existing desktop entry command.
- [ ] Confirm:
  - the shell becomes three columns
  - diagnostics stays visible while switching `账号中心 / 配置管理 / 扫货系统`
  - query tab surfaces an invalid API/token account within one poll cycle
  - purchase tab shows hit flow / inventory issues
  - login tab shows new task progress without blocking account creation success
- [ ] If a query account is manually invalidated during runtime, confirm the panel shows the account-level error even if the page body itself still looks superficially healthy.

### Task 18: Final integration commit

**Files:**
- Commit only

- [ ] Run:

```bash
git add app_backend app_desktop_web
git commit -m "feat: add global diagnostics sidebar"
```

- [ ] Do not include unrelated dirty files if they were not part of the implementation.

---

## Notes for the Implementer

- Keep all diagnostics writes best-effort or read-only. Stage 1 should not introduce file logging.
- Do not add WebSocket transport for the sidebar in this phase.
- Do not trigger any inventory refresh, token refresh, login retry, or remote API probe from the diagnostics endpoint.
- Prefer transforming existing runtime payloads inside `GetSidebarDiagnosticsUseCase` over changing runtime engines.
- If tests reveal a missing read-only field that cannot be derived safely, add the smallest possible runtime-service extension and cover it with a backend test before wiring it into the UI.
