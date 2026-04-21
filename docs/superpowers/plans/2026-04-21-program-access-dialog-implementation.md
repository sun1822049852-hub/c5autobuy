# Program Access Dialog Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move program-account auth operations out of the left sidebar into a centered dialog while keeping the sidebar as a minimal login-status entry card.

**Architecture:** Extend the existing `program_access` summary with a persisted `username`, then reshape the renderer so the sidebar card becomes a clickable status shell and the auth flows live inside a modal-style dialog. Keep provider wiring and remote auth actions unchanged.

**Tech Stack:** FastAPI + Pydantic + pytest; React 19 + Vitest; existing app CSS dialog surfaces.

---

## Chunk 1: Lock The New Program Access Contract

### Task 1: Add failing backend tests for `program_access.username`

**Files:**
- Modify: `tests/backend/test_app_bootstrap_route.py`
- Modify: `tests/backend/test_remote_entitlement_gateway.py`

- [ ] **Step 1: Write failing assertions for `username` in locked and unlocked summaries**
- [ ] **Step 2: Run focused backend tests and confirm they fail**

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_remote_entitlement_gateway.py -q`

Expected: FAIL because current summary contract lacks `username`.

### Task 2: Add failing renderer tests for sidebar entry + dialog behavior

**Files:**
- Modify: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`

- [ ] **Step 1: Write tests for minimal sidebar state label**
- [ ] **Step 2: Write tests that auth forms only appear after opening the dialog**
- [ ] **Step 3: Write tests that logged-in dialog shows status-only actions**
- [ ] **Step 4: Run the focused renderer test and confirm it fails**

Run: `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`

Expected: FAIL because current component still renders the full auth form directly in the sidebar.

## Chunk 2: Implement The Minimal Behavior Change

### Task 3: Extend the shared summary with `username`

**Files:**
- Modify: `app_backend/application/program_access.py`
- Modify: `app_backend/api/schemas/app_bootstrap.py`
- Modify: `app_backend/infrastructure/program_access/remote_entitlement_gateway.py`
- Modify: `app_backend/infrastructure/program_access/cached_program_access_gateway.py`
- Modify: `app_desktop_web/src/program_access/program_access_runtime.js`

- [ ] **Step 1: Add optional `username` to the shared summary models**
- [ ] **Step 2: Read `username` from verified remote snapshots**
- [ ] **Step 3: Normalize the new field in renderer runtime state**
- [ ] **Step 4: Re-run focused backend tests**

### Task 4: Convert the sidebar card into an entry shell plus centered dialog

**Files:**
- Modify: `app_desktop_web/src/program_access/program_access_sidebar_card.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] **Step 1: Keep the sidebar visible but reduce it to `未登录/用户名` plus open action**
- [ ] **Step 2: Move login/register/reset UI into a dialog**
- [ ] **Step 3: Show only status + refresh/logout when already logged in**
- [ ] **Step 4: Reuse existing dialog surface styling patterns instead of introducing a new layout system**
- [ ] **Step 5: Re-run focused renderer tests**

## Chunk 3: Verification And Handoff

### Task 5: Run the affected verification set and record the result

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if a new stable rule emerges)

- [ ] **Step 1: Run focused backend verification**

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_remote_entitlement_gateway.py -q`

- [ ] **Step 2: Run focused renderer verification**

Run: `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/program_access_provider.test.jsx tests/renderer/app_remote_bootstrap.test.jsx --run`

- [ ] **Step 3: Update session log with scope, implementation, verification, and next-step notes**
