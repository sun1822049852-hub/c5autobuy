# Purchase Disable Semantics Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“禁用购买”从全局 `disabled` 语义中拆出，改为只影响购买分配与库存恢复检查，并保留恢复倒计时语义。

**Architecture:** 保留账户全局 `disabled` 作为查询域/全局禁用标记，新增购买域独立字段 `purchase_disabled` 与恢复调度时间戳。`PurchaseRuntimeService` 与 `_DefaultPurchaseRuntime` 负责购买池移除、恢复检查暂停/恢复以及账户中心状态展示；查询链路继续只读取全局 `disabled`。前端购买配置抽屉改为提交 `purchase_disabled`，不再误导为全局禁用。

**Tech Stack:** Python, FastAPI, SQLAlchemy, React, Vitest, pytest

---

## Chunk 1: Data Model And API Contract

### Task 1: Add purchase-only persistence fields

**Files:**
- Modify: `app_backend/domain/models/account.py`
- Modify: `app_backend/application/use_cases/create_account.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Modify: `app_backend/infrastructure/repositories/account_repository.py`
- Test: `tests/backend/test_account_table_bootstrap.py`
- Test: `tests/backend/test_account_repository.py`

- [ ] Add `purchase_disabled` and `purchase_recovery_due_at` to the account model and repository mapping.
- [ ] Extend schema bootstrap to add missing `accounts.purchase_disabled` and `accounts.purchase_recovery_due_at` columns for existing databases.
- [ ] Update account creation defaults so new accounts start with `purchase_disabled=False` and no recovery deadline.
- [ ] Add/adjust repository tests to verify new fields round-trip through SQLite.

### Task 2: Split account-center purchase config payload from global disabled

**Files:**
- Modify: `app_backend/api/schemas/account_center.py`
- Modify: `app_backend/api/routes/accounts.py`
- Modify: `app_backend/application/use_cases/update_account_purchase_config.py`
- Test: `tests/backend/test_account_center_routes.py`
- Test: `tests/frontend/test_backend_client.py`

- [ ] Rename purchase-config request/response usage from `disabled` to `purchase_disabled` while preserving global `disabled` in account payloads.
- [ ] Add response fields needed by the UI for purchase-only status and recovery deadline display.
- [ ] Update route tests and backend client tests to lock the new contract.

## Chunk 2: Purchase Runtime Behavior

### Task 3: Write failing backend tests for purchase-only disable semantics

**Files:**
- Test: `tests/backend/test_purchase_runtime_service.py`
- Test: `tests/backend/test_account_center_routes.py`
- Test: `tests/backend/test_detail_account_selector.py`
- Test: `tests/backend/test_query_mode_capacity_service.py`
- Test: `tests/backend/test_mode_execution_runner.py`

- [ ] Add a test proving purchase disable removes the account from purchase availability without setting global `disabled`.
- [ ] Add a test proving purchase-disabled accounts still participate in detail lookup and query-capacity/runtime eligibility.
- [ ] Add a test proving recovery timers keep a due timestamp when purchase is manually disabled and trigger immediately on resume if already due.

### Task 4: Implement purchase-disable state machine

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`
- Test: `tests/backend/test_purchase_runtime_service.py`

- [ ] Update `PurchaseRuntimeService.update_account_purchase_config()` to persist purchase-only fields, not global `disabled`.
- [ ] Teach account-center row building and purchase status derivation to use `purchase_disabled`.
- [ ] Update runtime account eligibility to reject `purchase_disabled` but leave query systems untouched.
- [ ] Add runtime state needed to store and reuse recovery deadlines while disabled.
- [ ] When purchase is disabled, remove the account from the scheduler immediately and pause recovery execution without resetting the due time.
- [ ] When purchase is re-enabled, resume from the saved deadline: trigger immediate recovery if overdue, otherwise schedule remaining time.

## Chunk 3: Frontend Purchase Drawer

### Task 5: Update the account-center drawer and client wiring

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/account-center/drawers/purchase_config_drawer.jsx`
- Test: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`

- [ ] Update the purchase config submit payload to send `purchase_disabled`.
- [ ] Update drawer state initialization and labels to reflect purchase-only disable semantics.
- [ ] Add renderer coverage for manual purchase disable save behavior.

## Chunk 4: Verification

### Task 6: Run targeted regression coverage

**Files:**
- Test: `tests/backend/test_account_table_bootstrap.py`
- Test: `tests/backend/test_account_repository.py`
- Test: `tests/backend/test_account_center_routes.py`
- Test: `tests/backend/test_purchase_runtime_service.py`
- Test: `tests/backend/test_detail_account_selector.py`
- Test: `tests/backend/test_query_mode_capacity_service.py`
- Test: `tests/backend/test_mode_execution_runner.py`
- Test: `tests/frontend/test_backend_client.py`
- Test: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`

- [ ] Run the focused pytest selection for purchase-disable regression coverage.
- [ ] Run the focused frontend tests for the purchase drawer contract.
- [ ] If frontend code changed, rebuild `app_desktop_web` to refresh Electron `dist`.
