# Login Success Chain Restore Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the historical login contract so account login success is returned before browser profile persistence runs, preventing locked Chromium files from breaking the login chain.

**Architecture:** Keep the newer dedicated login-session directory and blocking-call safeguards, but move `persist_session()` back out of the login success path and into delayed cleanup after the browser exits. Preserve `profile_root` metadata in the login payload so downstream account/session storage keeps the existing shape.

**Tech Stack:** Python, pytest, managed Edge browser runtime

---

## Chunk 1: Lock the old contract with tests

### Task 1: Reassert deferred persistence

**Files:**
- Modify: `tests/backend/test_managed_edge_cdp_login_runner.py`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run targeted pytest to confirm current code still persists too early**
- [ ] **Step 3: Verify the failure points at immediate persistence inside the login mainline**

## Chunk 2: Restore the login behavior

### Task 2: Move persistence back to delayed cleanup

**Files:**
- Modify: `app_backend/infrastructure/browser_runtime/login_adapter.py`
- Test: `tests/backend/test_managed_edge_cdp_login_runner.py`

- [ ] **Step 1: Reintroduce the deferred persist cleanup callback**
- [ ] **Step 2: Keep `profile_root/profile_directory/profile_kind` in the login payload**
- [ ] **Step 3: Ensure persist callback exceptions are swallowed by cleanup, not surfaced to login callers**

## Chunk 3: Verify and record

### Task 3: Run affected regression coverage and update agent records

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if a new stable rule is learned)

- [ ] **Step 1: Run focused backend pytest for login/profile/open-api interactions**
- [ ] **Step 2: Read results before making any success claim**
- [ ] **Step 3: Append the session log with root cause, code change, verification, and remaining risk**
