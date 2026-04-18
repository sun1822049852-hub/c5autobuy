# Open API Cookie Local Expiry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the native `open-api` browser session logged in by extending local C5 cookie expiry inside the cloned temporary profile before launch.

**Architecture:** The change stays inside the browser-profile reuse path. `AccountBrowserProfileStore` will prepare the cloned session's Chromium cookie DB, and `OpenApiBindingPageLauncher` will invoke that preparation after cloning and before starting Edge. Failures degrade back to the current behavior.

**Tech Stack:** Python, SQLite, pytest, existing managed Edge runtime

---

## Chunk 1: Red-Green Tests

### Task 1: Lock the cloned-session cookie refresh behavior

**Files:**
- Modify: `tests/backend/test_account_browser_profile_store.py`
- Test: `tests/backend/test_account_browser_profile_store.py`

- [ ] **Step 1: Write the failing test**

Add a test that creates a minimal Chromium-style `Default/Network/Cookies` sqlite DB with both `c5game.com` and non-`c5game.com` rows, runs the new session-preparation method, and asserts only the C5 rows get a newer local expiry.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_account_browser_profile_store.py::test_account_browser_profile_store_prepares_open_api_binding_session_by_refreshing_c5_cookie_expiry -q`
Expected: FAIL because the preparation method does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add the new store method and sqlite helper code needed to refresh local expiry metadata in the cloned cookie DB.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_account_browser_profile_store.py::test_account_browser_profile_store_prepares_open_api_binding_session_by_refreshing_c5_cookie_expiry -q`
Expected: PASS

### Task 2: Lock the launcher call site

**Files:**
- Modify: `tests/backend/test_open_api_binding_page_launcher.py`
- Test: `tests/backend/test_open_api_binding_page_launcher.py`

- [ ] **Step 1: Write the failing test**

Add a launcher test that uses a fake profile store exposing `prepare_open_api_binding_session()` and asserts the launcher calls it on the cloned session root before Edge starts.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_open_api_binding_page_launcher.py::test_open_api_binding_page_launcher_prepares_cloned_session_before_launch -q`
Expected: FAIL because the launcher does not call the preparation method yet.

- [ ] **Step 3: Write minimal implementation**

Update the launcher to invoke the preparation hook after `clone_session()` and before building the Edge command. Log preparation success or failure without turning failure into a hard launch error.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_open_api_binding_page_launcher.py::test_open_api_binding_page_launcher_prepares_cloned_session_before_launch -q`
Expected: PASS

## Chunk 2: Focused Verification and Handoff

### Task 3: Run the affected regression slice

**Files:**
- Modify: `app_backend/infrastructure/browser_runtime/account_browser_profile_store.py`
- Modify: `app_backend/infrastructure/browser_runtime/open_api_binding_page_launcher.py`
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run focused backend tests**

Run: `pytest tests/backend/test_account_browser_profile_store.py tests/backend/test_open_api_binding_page_launcher.py -q`
Expected: PASS

- [ ] **Step 2: Update session log**

Append the goal, changed behavior, and verification evidence to `docs/agent/session-log.md`.

- [ ] **Step 3: Re-read changed files**

Check the modified backend files and confirm the change stays limited to the `open-api` cloned-session path.
