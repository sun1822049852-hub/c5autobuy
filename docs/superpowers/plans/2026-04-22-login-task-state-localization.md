# Login Task State Localization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace user-facing raw C5 login task state codes with formal Chinese copy across the login drawer, logs, diagnostics, and default placeholders while keeping the backend task protocol unchanged.

**Architecture:** Add one shared renderer-side login-task state mapping module, then route the login drawer, login-task log meta, diagnostics login-task tab, and default account-center seed copy through that module or through updated formal wording. Keep all changes in the display layer so backend task creation, polling, and conflict handling remain untouched.

**Tech Stack:** React 19 + Vitest; existing account-center and diagnostics renderer modules; existing shared app CSS.

---

## Chunk 1: Lock The User-Facing Contract

### Task 1: Add failing login-drawer and log-meta tests for localized state display

**Files:**
- Modify: `app_desktop_web/tests/renderer/login_drawer.test.jsx`

- [ ] **Step 1: Add a failing assertion that the task status card renders Chinese instead of raw `pending` / `idle`**
- [ ] **Step 2: Add a failing assertion that the timeline falls back to Chinese labels when `event.message` is empty**
- [ ] **Step 3: Add a failing assertion that account logs use localized `状态：...` text instead of raw `succeeded`**
- [ ] **Step 4: Run the focused login-drawer test and confirm it fails**

Run: `npm --prefix app_desktop_web test -- tests/renderer/login_drawer.test.jsx --run`

Expected: FAIL because the drawer still renders `task.state` and `event.state` directly.

### Task 2: Add failing diagnostics and seed-copy tests

**Files:**
- Modify: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] **Step 1: Add a failing assertion that diagnostics login-task rows show Chinese localized states**
- [ ] **Step 2: Add a failing assertion that diagnostics timeline entries show Chinese localized states**
- [ ] **Step 3: Add a failing assertion that default account-center login placeholder copy no longer uses `等待接入真实任务流`**
- [ ] **Step 4: Run the focused renderer tests and confirm they fail**

Run: `npm --prefix app_desktop_web test -- tests/renderer/diagnostics_sidebar.test.jsx tests/renderer/account_center_page.test.jsx --run`

Expected: FAIL because diagnostics still render raw states and the default seed copy still contains development wording.

## Chunk 2: Implement Shared Localization

### Task 3: Add a single renderer-side login-task state mapping module

**Files:**
- Create: `app_desktop_web/src/features/account-center/login_task_state_labels.js`

- [ ] **Step 1: Create the single-source mapping table for raw task states**
- [ ] **Step 2: Export helpers for task-state labels and fallback event labels**
- [ ] **Step 3: Keep unknown states on a safe Chinese fallback such as `状态更新中`**

### Task 4: Route the login drawer through the shared mapping

**Files:**
- Modify: `app_desktop_web/src/features/account-center/drawers/login_drawer.jsx`

- [ ] **Step 1: Replace the raw task status card value with the localized label**
- [ ] **Step 2: Replace event fallback text with the localized label helper**
- [ ] **Step 3: Replace the development subtitle with formal user-facing copy**
- [ ] **Step 4: Re-run the focused login-drawer test**

### Task 5: Route diagnostics and seed copy through the same contract

**Files:**
- Modify: `app_desktop_web/src/features/diagnostics/login_task_diagnostics_tab.jsx`
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`

- [ ] **Step 1: Localize diagnostics task-row status text**
- [ ] **Step 2: Localize diagnostics timeline state text**
- [ ] **Step 3: Localize login-task log meta from `状态：raw-code` to `状态：中文状态`**
- [ ] **Step 4: Replace `等待接入真实任务流` with formal default login placeholder copy**
- [ ] **Step 5: Re-run the focused diagnostics and account-center tests**

## Chunk 3: Verification And Project Record

### Task 6: Run the affected renderer verification set

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run focused renderer verification**

Run: `npm --prefix app_desktop_web test -- tests/renderer/login_drawer.test.jsx tests/renderer/diagnostics_sidebar.test.jsx tests/renderer/account_center_page.test.jsx --run`

- [ ] **Step 2: If failures expand beyond the target files, fix only the regressions introduced by the localization change**
- [ ] **Step 3: Update `docs/agent/session-log.md` with scope, changed files, verification results, and next-step notes**

### Task 7: Optional follow-up cleanup only if time remains

**Files:**
- Modify: `app_desktop_web/src/features/account-center/components/status_strip.jsx`

- [ ] **Step 1: If this dead component is still intentionally retained, align its seed wording with the new formal copy**
- [ ] **Step 2: Do not expand into unrelated UI cleanup**
