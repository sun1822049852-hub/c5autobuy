# Front Page Keepalive And Fetch Dedup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop top-level frontend pages from re-fetching backend data on every sidebar revisit, while preserving the existing self-built runtime sync pattern.

**Architecture:** Reuse the existing lazy keep-alive pattern already used by the query and purchase pages. Extend it to the other top-level pages, then adjust diagnostics activation so cached data is reused on re-entry instead of forcing an immediate fetch.

**Tech Stack:** React 19, Vite, Vitest, self-built AppRuntimeStore, custom HTTP/WebSocket client.

---

## Chunk 1: Lock The Revisit Behavior With Tests

### Task 1: Add failing renderer tests for page revisit fetch counts

**Files:**
- Create: `app_desktop_web/tests/renderer/app_page_keepalive.test.jsx`
- Reference: `app_desktop_web/src/App.jsx`
- Reference: `app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js`

- [ ] **Step 1: Write the failing test**

Add renderer tests that:
- render `<App />` with a fetch harness covering `/app/bootstrap`, `/account-center/accounts`, `/stats/query-items`, `/stats/account-capability`, and `/diagnostics/sidebar`
- switch between `账号中心`, `查询统计`, `账号能力统计`, and `通用诊断`
- assert each page's backing endpoint is only fetched once across a leave-and-return cycle

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx
```

Expected: FAIL because `App.jsx` remounts these pages or diagnostics re-fetches on re-enable.

## Chunk 2: Reuse The Existing Keepalive Pattern

### Task 2: Extend top-level lazy keep-alive mounting

**Files:**
- Modify: `app_desktop_web/src/App.jsx`
- Test: `app_desktop_web/tests/renderer/app_page_keepalive.test.jsx`

- [ ] **Step 1: Write minimal implementation**

Update `App.jsx` so:
- all top-level sidebar pages use the same lazy mount + hidden keep-alive pattern already used by `query-system` and `purchase-system`
- pages are mounted only after first activation, not all at startup
- existing navigation behavior stays unchanged

- [ ] **Step 2: Run targeted test**

Run:

```powershell
npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx
```

Expected: stats/account-center revisit assertions move toward green, diagnostics may still fail.

### Task 3: Stop diagnostics from immediate re-fetch on re-activation

**Files:**
- Modify: `app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js`
- Test: `app_desktop_web/tests/renderer/app_page_keepalive.test.jsx`

- [ ] **Step 1: Write minimal implementation**

Adjust diagnostics loading so:
- first activation still fetches immediately when no snapshot exists
- returning to the page with an existing snapshot does not trigger an immediate fetch caused only by the sidebar click
- polling resumes without discarding cached snapshot

- [ ] **Step 2: Re-run targeted test**

Run:

```powershell
npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx
```

Expected: PASS.

## Chunk 3: Regression Check And Session Records

### Task 4: Run nearby renderer regressions

**Files:**
- Test: `app_desktop_web/tests/renderer/query_stats_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/account_capability_stats_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] **Step 1: Run affected tests**

Run:

```powershell
npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx query_stats_page.test.jsx account_capability_stats_page.test.jsx account_center_page.test.jsx
```

Expected: PASS.

### Task 5: Update session log

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Append session entry**

Record:
- why the keep-alive change was made
- which top-level pages were moved to lazy keep-alive
- diagnostics fetch gating adjustment
- verification commands and results

