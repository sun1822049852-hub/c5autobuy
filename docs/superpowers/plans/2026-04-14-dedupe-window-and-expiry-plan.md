# Purchase Dedupe Window And Expiry Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the existing wear-result dedupe semantics, extend the dedupe window from 5 seconds to 10 seconds, and reduce hot-path maintenance cost by replacing per-hit full-cache expiry scans with expiry-ordered cleanup.

**Architecture:** Leave the dedupe key untouched and only change how the dedupe ledger ages out. `PurchaseHitInbox` should evict expired entries in expiry order instead of iterating the whole cache on every hit. `PurchaseRuntimeService` should construct the inbox with a 10-second window so all normal and fast-path purchase hit entry points inherit the same rule.

**Tech Stack:** Python 3.11, pytest, existing purchase runtime/inbox code.

---

### Task 1: Red Tests For New Window And Cheap Expiry

**Files:**
- Modify: `tests/backend/test_purchase_hit_inbox.py`
- Test: `tests/backend/test_purchase_hit_inbox.py`

- [ ] **Step 1: Write the failing test for the 10-second dedupe window**

Add a test that uses a controllable clock, accepts one hit, advances to 6 seconds, and asserts the same wear-result is still blocked, then advances beyond 10 seconds and asserts it is accepted again.

- [ ] **Step 2: Run test to verify it fails**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/backend/test_purchase_hit_inbox.py -q -k ten_second`
Expected: FAIL because the inbox still expires entries after 5 seconds.

- [ ] **Step 3: Write the failing test for no full-cache scan on hot accept**

Add a test that seeds one live entry, swaps the internal cache mapping with a guard that raises if `items()` is used, then accepts a different live hit. This should fail on the current implementation because expiry cleanup iterates the full cache.

- [ ] **Step 4: Run test to verify it fails**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/backend/test_purchase_hit_inbox.py -q -k full_cache_scan`
Expected: FAIL because `accept()` still triggers a full-cache iteration.

### Task 2: Minimal Inbox Implementation

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_hit_inbox.py`
- Test: `tests/backend/test_purchase_hit_inbox.py`

- [ ] **Step 1: Implement expiry-ordered cleanup**

Keep the current dedupe key and forget semantics, but store expiry metadata so cleanup can drop only entries whose expiry time has passed.

- [ ] **Step 2: Change the default dedupe window to 10 seconds**

Update the inbox default so new inbox instances block the same wear-result for 10 seconds unless explicitly overridden.

- [ ] **Step 3: Run inbox tests**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/backend/test_purchase_hit_inbox.py -q`
Expected: PASS.

### Task 3: Runtime Regression Check

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py` (only if explicit inbox construction still pins 5 seconds)
- Test: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: Ensure purchase runtime uses the 10-second inbox window**

If runtime construction overrides the inbox window, align it with the new 10-second default.

- [ ] **Step 2: Add or adjust a regression test only if needed**

Prefer reusing existing runtime dedupe tests; only add a runtime-level 10-second assertion if the inbox-level tests do not fully cover the integrated behavior.

- [ ] **Step 3: Run targeted purchase runtime regressions**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/backend/test_purchase_hit_inbox.py tests/backend/test_purchase_runtime_service.py -q -k "duplicate or dedupe or ten_second"`
Expected: PASS.

- [ ] **Step 4: Run final affected suite**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/backend/test_purchase_hit_inbox.py tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_diagnostics_routes.py -q`
Expected: PASS.
