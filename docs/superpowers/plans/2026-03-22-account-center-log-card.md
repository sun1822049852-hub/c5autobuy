# Account Center Log Card Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the bottom account-center status strip with a top-row log card that shows log count and opens a readable log viewer.

**Architecture:** Reuse the account-center hook as the single source of truth for log entries, expose a new `日志` overview card action that opens a modal, and remove the old bottom status strip from the page layout. Keep account filtering behavior unchanged for the original four cards.

**Tech Stack:** React 19, existing desktop web UI components, Vitest + Testing Library.

---

## Chunk 1: Tests First

### Task 1: Account-center shell expectations

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] Write failing assertions for:
  - no bottom status strip labels
  - top overview includes `日志`
  - log card shows count
  - clicking log opens viewer modal with login/error/modification entries

- [ ] Run: `npm test -- tests/renderer/account_center_page.test.jsx`

### Task 2: Editing flow expectations

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`
- Modify: `app_desktop_web/tests/renderer/login_drawer.test.jsx`

- [ ] Update tests so success/status messages are verified inside the log viewer instead of the removed strip.
- [ ] Run: `npm test -- tests/renderer/account_center_editing.test.jsx tests/renderer/login_drawer.test.jsx`

## Chunk 2: Runtime Log Model + UI

### Task 3: Hook and overview cards

**Files:**
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Modify: `app_desktop_web/src/features/account-center/components/overview_cards.jsx`

- [ ] Add log-entry state in the hook.
- [ ] Seed the initial three visible messages as log entries.
- [ ] Append new entries when login/error/modification state changes.
- [ ] Add a `日志` overview card with count and click action.

### Task 4: Modal and page composition

**Files:**
- Create: `app_desktop_web/src/features/account-center/components/account_logs_modal.jsx`
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] Remove `StatusStrip` from the page.
- [ ] Add centered/draggable log modal wired to the new log card.
- [ ] Style the log viewer to match the existing desktop web surfaces.

## Chunk 3: Verification

### Task 5: Run targeted and full verification

**Files:**
- Verify only

- [ ] Run: `npm test -- tests/renderer/account_center_page.test.jsx tests/renderer/account_center_editing.test.jsx tests/renderer/login_drawer.test.jsx`
- [ ] Run: `npm test`
