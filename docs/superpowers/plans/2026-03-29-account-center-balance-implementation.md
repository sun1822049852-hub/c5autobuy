# Account Center Balance Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cached account-balance display to the account center, using OpenAPI `moneyAmount` first and browser-session `balance` as a fallback after login.

**Architecture:** Keep balance refresh logic entirely in the backend. Account-center rows expose cached balance fields, while a dedicated balance service handles OpenAPI calls, browser-session fallback, proxy separation, post-login first refresh, and randomized 8-10 minute refresh windows.

**Tech Stack:** FastAPI, SQLAlchemy, aiohttp, React, pytest, pytest-asyncio

---

## Chunk 1: Backend Balance Model And Service

### Task 1: Add failing persistence coverage for balance fields

**Files:**
- Modify: `tests/backend/test_account_repository.py`
- Modify: `tests/backend/test_account_table_bootstrap.py`
- Modify: `app_backend/domain/models/account.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Modify: `app_backend/infrastructure/repositories/account_repository.py`

- [ ] Add a failing repository test covering `balance_amount`, `balance_source`, `balance_updated_at`, `balance_refresh_after_at`, and `balance_last_error`
- [ ] Run the targeted pytest case and confirm it fails for missing fields
- [ ] Add the new account model fields and SQLite columns with migration fallback
- [ ] Re-run the targeted pytest case and confirm it passes

### Task 2: Add failing tests for balance refresh behavior

**Files:**
- Create: `tests/backend/test_account_balance_service.py`
- Create: `app_backend/application/services/account_balance_service.py`

- [ ] Write a failing test for OpenAPI balance success using `moneyAmount`
- [ ] Write a failing test for browser-session fallback success using `balance`
- [ ] Write a failing test proving browser-session fallback uses browser proxy rather than API proxy
- [ ] Write a failing test proving browser-session fallback failure is not retried
- [ ] Write a failing test proving refresh windows are randomized between 8 and 10 minutes
- [ ] Run the new test module and confirm failure
- [ ] Implement the minimal balance service to make the tests pass
- [ ] Re-run the new test module and confirm success

## Chunk 2: Account-Center Integration

### Task 3: Add failing tests for account-center row exposure

**Files:**
- Modify: `tests/backend/test_account_center_routes.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/api/schemas/account_center.py`

- [ ] Add a failing route test asserting balance fields are returned by `/account-center/accounts`
- [ ] Run the targeted route test and confirm it fails
- [ ] Extend account-center row building and schema serialization with cached balance fields
- [ ] Re-run the targeted route test and confirm it passes

### Task 4: Add failing tests for post-login first refresh

**Files:**
- Modify: `tests/backend/test_login_task_open_api_watch.py`
- Modify: `tests/backend/test_login_task_flow.py`
- Modify: `app_backend/workers/tasks/login_task.py`
- Modify: `app_backend/application/use_cases/start_login_task.py`

- [ ] Add a failing test covering “wait up to 10 seconds for `api_key`, then fallback once”
- [ ] Run the targeted login-task test and confirm it fails
- [ ] Inject the balance service into the login task flow and trigger post-login balance refresh
- [ ] Re-run the targeted login-task test and confirm it passes

## Chunk 3: Frontend Display

### Task 5: Add failing UI tests or focused component assertions for balance rendering

**Files:**
- Modify: `app_desktop_web/src/features/account-center/components/account_table.jsx`
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] Add a focused test or component assertion for balance-cell rendering if existing UI test coverage supports it; otherwise add a narrow normalization/unit test around the row model
- [ ] Run the targeted frontend test and confirm it fails
- [ ] Add the balance column on the right side and render cached values safely
- [ ] Re-run the targeted frontend test and confirm it passes

## Chunk 4: Verification

### Task 6: Run focused verification

**Files:**
- Modify: `tests/backend/test_account_balance_service.py`
- Modify: `tests/backend/test_account_center_routes.py`
- Modify: `tests/backend/test_login_task_open_api_watch.py`

- [ ] Run focused backend tests for repository, balance service, account-center routes, and login-task integration
- [ ] Fix any regressions surfaced by the focused run
- [ ] Run the final focused command set again and record the passing output
