# Account Center Purchase Status Resync Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure account-center purchase status rows stop sticking on `运行时未就绪` after startup optimizations and resync promptly once runtime-full data becomes available.

**Architecture:** Keep the startup split intact: account-center may still render from the lightweight snapshot path first, but the renderer must detect when purchase runtime/full bootstrap has hydrated and then refresh stale account-center rows. Do not change the core `查询 -> 命中 -> 购买` waiting semantics in this task.

**Tech Stack:** React, runtime store hydration, Vitest, existing account-center client/routes.

---

### Task 1: Reproduce The Stale Purchase Status

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Reference: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`

- [ ] **Step 1: Write the failing test**

Add a renderer test that:
- first returns `/account-center/accounts` rows with `purchase_status_code="runtime_unavailable"`
- then hydrates purchase runtime/full bootstrap state
- finally expects the account-center table to refresh and replace `运行时未就绪` with the real warehouse/inventory status

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx -t "resyncs stale purchase status after runtime bootstrap hydrates" --run`

Expected: FAIL because the row stays on `运行时未就绪`.

### Task 2: Refresh Stale Rows After Runtime-Full Hydration

**Files:**
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Reference: `app_desktop_web/src/runtime/use_app_runtime.js`

- [ ] **Step 1: Implement the minimal runtime hydration trigger**

When purchase runtime/full bootstrap becomes hydrated:
- detect whether current account-center rows still contain `purchase_status_code="runtime_unavailable"`
- refresh those rows (or the full list if that is the smallest correct path)
- avoid repeated refetch storms once the stale rows have been replaced

- [ ] **Step 2: Keep scope tight**

Do not:
- block the first paint of account-center
- force `/account-center/accounts` to synchronously ensure runtime-full on the critical startup path
- change query runtime start/wait behavior

- [ ] **Step 3: Run the red test to verify it passes**

Run: `npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx -t "resyncs stale purchase status after runtime bootstrap hydrates" --run`

Expected: PASS

### Task 3: Focused Regression

**Files:**
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`
- Test: `app_desktop_web/tests/renderer/app_page_keepalive.test.jsx`

- [ ] **Step 1: Run focused account-center regressions**

Run: `npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx tests/renderer/account_center_editing.test.jsx --run`

Expected: PASS

- [ ] **Step 2: Run startup/warmup regression that could interact with hydration timing**

Run: `npm --prefix app_desktop_web test -- tests/renderer/app_page_keepalive.test.jsx --run`

Expected: PASS, or clearly isolate any unrelated pre-existing failure.

### Task 4: Documentation Hygiene

**Files:**
- Modify: `docs/agent/session-log.md`
- Review: `docs/agent/memory.md`
- Review: `README.md`

- [ ] **Step 1: Append session log**

Record root cause, fix scope, and verification evidence.

- [ ] **Step 2: Review memory / README**

Only update `docs/agent/memory.md` if a new stable rule emerged. Review `README.md` and note if no change is needed.
