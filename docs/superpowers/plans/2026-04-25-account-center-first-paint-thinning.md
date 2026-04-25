# Account Center First Paint Thinning Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shrink account-center first paint so the desktop home becomes visible and clickable sooner after backend ready, while moving non-first-screen overlays behind first-interaction lazy loading.

**Architecture:** Keep the current shell-only desktop bootstrap and account list fetch path unchanged. Thin the account-center page itself into a small first-screen closure, then lazy-load heavyweight dialogs/drawers/modals/context menus on first use instead of mounting them in the initial page tree.

**Tech Stack:** Electron, React 19, Vite, Vitest, existing desktop startup trace instrumentation.

---

> Risk level: `risky`. This changes renderer startup behavior on the desktop home page. Keep shell-only, `/health ready=true`, browser-actions lazy boundary, login/open-api flow, and `query -> hit -> purchase` mainline unchanged.

## Locked Decisions

- First-screen priority is `更快可见可点`, not “all overlays ready at first paint”.
- Buttons and entry points may appear before their backing overlays are loaded.
- `代理管理 / 购买配置 / 日志 / 登录抽屉 / 右键菜单 / 编辑弹窗` are allowed to pay first-open lazy cost.
- Do not reintroduce startup-blocking `localStorage/sessionStorage` reads into the first render path.

## Non-Goals

- No backend startup changes.
- No `AccountCenterPage` full eager import rollback just to chase chunk time.
- No product behavior changes for login, open-api, program access, or purchase/query runtime.

## File Map

- `app_desktop_web/src/App.jsx`
  Keep the current startup-fix behavior intact; only touch if account-center entry wiring needs adjustment.
- `app_desktop_web/src/features/account-center/account_center_page.jsx`
  Main target. Needs to stop synchronously mounting all overlays in the page tree.
- `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
  Needs boundary cleanup so first-screen state stays small and overlay-specific state/effects can be activated lazily.
- `app_desktop_web/src/features/proxy-pool/use_proxy_pool.js`
  Must remain interaction-triggered only; verify no eager regression.
- `app_desktop_web/tests/renderer/account_center_page.test.jsx`
  Add contract tests for first-screen visibility and overlay lazy behavior.
- `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
  Keep the current startup contract locked.
- `docs/agent/session-log.md`
  Record final trace deltas and remaining risks.

## Chunk 1: Lock The New First-Screen Contract With Tests

### Task 1: Add failing renderer tests for “visible/clickable first, overlays later”

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Reference: `app_desktop_web/src/features/account-center/account_center_page.jsx`

- [ ] **Step 1: Write the failing test**

Add tests that render the account-center home and assert:
- toolbar actions (`代理管理`, `刷新`, `添加账号`) are visible immediately
- first-screen table / search input render without opening any overlay
- heavyweight overlay content is not mounted before the first user action
- opening `代理管理` and `添加账号` still works after the lazy boundary

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
npm --prefix app_desktop_web run test -- tests/renderer/account_center_page.test.jsx --run
```

Expected:
- FAIL because current page mounts overlay components eagerly in the initial tree.

### Task 2: Re-lock desktop bootstrap startup behavior around the new account-center shape

**Files:**
- Modify: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- Reference: `app_desktop_web/src/App.jsx`

- [ ] **Step 1: Add/adjust a focused assertion**

Keep coverage that:
- desktop home still hydrates from shell bootstrap only
- account-center remains the first page
- the page still waits for backend ready before consuming desktop bootstrap

- [ ] **Step 2: Run targeted bootstrap test**

Run:

```powershell
npm --prefix app_desktop_web run test -- tests/renderer/app_remote_bootstrap.test.jsx --run
```

Expected:
- PASS before implementation, or FAIL only if the account-center entry wiring needs explicit adjustment.

## Chunk 2: Thin The Account-Center First Paint

### Task 3: Stop mounting heavyweight overlays in the initial account-center tree

**Files:**
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Optional Create: `app_desktop_web/src/features/account-center/account_center_lazy_surfaces.jsx`
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] **Step 1: Implement the smallest page-tree split**

Refactor the page so:
- hero, toolbar, search, overview, table stay synchronous
- overlay surfaces move behind `React.lazy` or equivalent first-open loading
- first-screen action buttons stay visible and clickable
- loading one overlay does not blank the whole page

- [ ] **Step 2: Run the focused test**

Run:

```powershell
npm --prefix app_desktop_web run test -- tests/renderer/account_center_page.test.jsx --run
```

Expected:
- PASS, with first-screen assertions green and overlay-open flows still working.

### Task 4: Pull overlay-specific state/effects out of the first-screen hot path

**Files:**
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Optional Create: `app_desktop_web/src/features/account-center/hooks/use_account_center_overlays.js`
- Optional Create: `app_desktop_web/src/features/account-center/hooks/use_account_center_primary_state.js`
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] **Step 1: Implement the smallest state split**

Separate:
- first-screen list/search/filter state
- overlay-only open states and side effects

Constraints:
- do not change login/open-api semantics
- do not move proxy-pool fetching back into startup
- keep existing action names and user-visible behavior

- [ ] **Step 2: Re-run the same focused renderer test**

Run:

```powershell
npm --prefix app_desktop_web run test -- tests/renderer/account_center_page.test.jsx --run
```

Expected:
- PASS.

## Chunk 3: Regression Check And Real Startup Evidence

### Task 5: Run nearby renderer and electron regressions

**Files:**
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- Test: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`
- Test: `app_desktop_web/tests/electron/electron_remote_mode.test.js`

- [ ] **Step 1: Run affected tests**

Run:

```powershell
npm --prefix app_desktop_web run test -- tests/renderer/account_center_page.test.jsx tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/electron/electron_remote_mode.test.js --run
```

Expected:
- PASS.

### Task 6: Rebuild frontend and run a real startup trace

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Build the renderer bundle**

Run:

```powershell
npm --prefix app_desktop_web run build
```

Expected:
- PASS.

- [ ] **Step 2: Run real desktop startup trace**

Run:

```powershell
$env:C5_STARTUP_TRACE='1'
$env:C5_LOCAL_DEBUG_REUSE_RENDERER_DIST='1'
node main_ui_node_desktop.js
```

Expected:
- `desktop.window.visible`
- `desktop.backend.ready`
- `renderer.bootstrap.config.consumed`
- `renderer.account.center.chunk.ready`
- `renderer.account.center.first.commit`
- `renderer.account.center.accounts.loaded`

Success criterion:
- `renderer.account.center.chunk.ready -> renderer.account.center.first.commit` is lower than the current `~2.76s` baseline.

### Task 7: Update session log

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Append the execution result**

Record:
- which overlays were moved behind lazy boundaries
- whether hook/state splitting was needed
- focused test commands + results
- final real trace numbers
- any residual slow segment still left after the change

## Suggested Execution Boundary

- Execute `Task 1 -> Task 3` first.
- If first-screen trace improves clearly, continue with `Task 4`.
- If trace barely changes after `Task 3`, stop and re-measure before doing more hook splitting.
