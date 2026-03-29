# Per-Batch IP Fanout Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add global per-batch IP fanout settings, batch-scoped purchase fanout by idle accounts, and purchase settings UI wiring.

**Architecture:** Keep purchase runtime state centralized in `PurchaseRuntimeService` while extending `PurchaseScheduler` into an atomic claim/release state center. Each accepted hit becomes one independent batch fanout context that claims idle accounts per proxy bucket up to the configured global limit and dispatches account-local single-flight executions on a persistent background loop.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, Python pytest, React 19, Vite, Vitest, Testing Library

---

## Chunk 1: Runtime Settings Foundation

### Task 1: Add runtime settings persistence for purchase fanout limit

**Files:**
- Create: `app_backend/domain/models/runtime_settings.py`
- Create: `app_backend/infrastructure/repositories/runtime_settings_repository.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Modify: `tests/backend/test_desktop_web_backend_bootstrap.py`
- Create: `tests/backend/test_runtime_settings_repository.py`

- [ ] **Step 1: Write failing repository tests for purchase defaults**

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement `RuntimeSettings` model and repository with default `per_batch_ip_fanout_limit = 1`**

- [ ] **Step 4: Wire schema creation**

- [ ] **Step 5: Re-run targeted repository tests**

## Chunk 2: Purchase Runtime Fanout Semantics

### Task 2: Add proxy bucket normalization and scheduler claim/release

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/proxy_bucket.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`
- Modify: `tests/backend/test_purchase_scheduler.py`

- [ ] **Step 1: Write failing scheduler tests for idle account claim per bucket**

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement `proxy_bucket.py` and scheduler busy/bucket claim/release**

- [ ] **Step 4: Re-run scheduler tests**

### Task 3: Fan out each accepted batch across idle accounts

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/runtime_account_adapter.py`
- Modify: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Modify: `app_backend/application/use_cases/get_purchase_runtime_status.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `tests/backend/test_runtime_account_adapter.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`

- [ ] **Step 1: Write failing runtime tests for per-batch bucket fanout and account single-flight**

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Fix `RuntimeAccountAdapter.get_global_session()` to use browser/account proxy**

- [ ] **Step 4: Replace single serial drain semantics with persistent background dispatch tasks using scheduler claims**

- [ ] **Step 5: Extend purchase status read model with `purchase_settings` and `bucket_rows`**

- [ ] **Step 6: Re-run targeted runtime and route tests**

## Chunk 3: Frontend Purchase Settings UI

### Task 4: Add global purchase fanout settings UI

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_settings_panel.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`

- [ ] **Step 1: Write failing frontend tests for loading and saving `per_batch_ip_fanout_limit`**

- [ ] **Step 2: Run frontend tests to verify they fail**

- [ ] **Step 3: Implement purchase settings panel global field and client wiring**

- [ ] **Step 4: Re-run frontend tests**

## Chunk 4: Verification

### Task 5: Run the integrated verification suite

**Files:**
- Test: `tests/backend/test_runtime_settings_repository.py`
- Test: `tests/backend/test_purchase_scheduler.py`
- Test: `tests/backend/test_purchase_runtime_service.py`
- Test: `tests/backend/test_purchase_runtime_routes.py`
- Test: `tests/backend/test_runtime_account_adapter.py`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/purchase_system_client.test.js`

- [ ] **Step 1: Run targeted backend suite**

- [ ] **Step 2: Run targeted frontend suite**

- [ ] **Step 3: Fix regressions until both suites pass**

