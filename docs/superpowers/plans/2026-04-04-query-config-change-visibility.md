# Query Config Change Visibility Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make config changes on a running query setup visibly understandable without changing purchase execution semantics: new config affects future hits only, while already queued or dispatched purchase batches continue to drain.

**Architecture:** Keep backend and purchase execution behavior unchanged. Surface the semantics through two lightweight UI notices: one on query config save success for active runtimes, and one on the purchase page while an active queue or dispatched work may still be draining old batches.

**Tech Stack:** React, Vitest, Testing Library

---

## Chunk 1: Query Page Save Notice

### Task 1: Add a regression test for post-save notice on active query configs

**Files:**
- Modify: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
- Test: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`

- [ ] **Step 1: Write the failing test**

Add a test that saves a running config and expects a visible notice explaining that the new config only affects future hits and old purchase batches may still drain using previous snapshots.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- tests/renderer/query_system_editing.test.jsx`
Expected: FAIL because the notice is not rendered yet.

- [ ] **Step 3: Write minimal implementation**

Store a transient save-success notice in the query page hook when saving an active config succeeds, and render it near the workbench header.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- tests/renderer/query_system_editing.test.jsx`
Expected: PASS

## Chunk 2: Purchase Page Drain Notice

### Task 2: Add a regression test for old-queue drain notice

**Files:**
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: Write the failing test**

Add a test that renders a running purchase runtime with a selected active query config plus `queue_size > 0` or `active_account_count > 0`, and expects a notice explaining that old queued/dispatched batches are still draining under previous snapshots.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- tests/renderer/purchase_system_page.test.jsx`
Expected: FAIL because no drain notice is shown yet.

- [ ] **Step 3: Write minimal implementation**

Derive a boolean/message in the purchase hook and render a small notice in the runtime header when the runtime is active and there is in-flight queue/dispatch work.

- [ ] **Step 4: Run focused tests**

Run: `npm test -- tests/renderer/query_system_editing.test.jsx tests/renderer/purchase_system_page.test.jsx`
Expected: PASS

## Chunk 3: Verification

### Task 3: Run regression and full frontend verification

**Files:**
- Verify only

- [ ] **Step 1: Run related page tests**

Run: `npm test -- tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_page.test.jsx tests/renderer/purchase_system_page.test.jsx`
Expected: PASS

- [ ] **Step 2: Run full frontend suite**

Run: `npm test`
Expected: PASS

- [ ] **Step 3: Dual review**

Dispatch two read-only reviewers, fix any findings, and repeat until both explicitly report `no findings`.
