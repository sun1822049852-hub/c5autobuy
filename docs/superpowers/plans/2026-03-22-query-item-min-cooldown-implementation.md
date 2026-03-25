# Query Item Min Cooldown Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为全局 `query-settings` 增加每个 mode 的“商品最小冷却策略”，替换新后端当前写死的 `0.5 / actual_assigned_count` 逻辑，并在扫货页 `查询设置` modal 中提供可视化配置。

**Architecture:** 扩展全局 `query-settings` 数据模型与数据库表，为每个 mode 持久化 `item_min_cooldown_seconds` 和 `item_min_cooldown_strategy`。运行时继续由 `ModeRunner` 管理查询器自身冷却，`QueryItemScheduler` 改为根据新的商品冷却策略计算商品下次可执行时间，并支持热应用。前端复用现有 `查询设置` modal，增加对应字段与校验。

**Tech Stack:** Python, FastAPI, SQLAlchemy, Vitest, React

---

## Chunk 1: Backend Contract

### Task 1: Add failing backend tests for query settings payload and scheduler strategy

**Files:**
- Modify: `tests/backend/test_query_settings_repository.py`
- Modify: `tests/backend/test_query_settings_routes.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Create: `tests/backend/test_query_item_scheduler.py`

- [ ] Step 1: Add failing assertions for query settings repository defaults and persistence of `item_min_cooldown_seconds` / `item_min_cooldown_strategy`
- [ ] Step 2: Run repository/route/runtime/scheduler tests to verify expected failures
- [ ] Step 3: Add failing scheduler tests for `fixed` and `divide_by_assigned_count`
- [ ] Step 4: Re-run targeted backend tests and confirm failures match missing fields / unsupported strategy

### Task 2: Implement backend query settings field expansion

**Files:**
- Modify: `app_backend/domain/models/query_settings.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/repositories/query_settings_repository.py`
- Modify: `app_backend/api/schemas/query_settings.py`
- Modify: `app_backend/api/routes/query_settings.py`
- Modify: `app_backend/application/use_cases/update_query_settings.py`

- [ ] Step 1: Add the new fields to the domain, DB record, API schema, and repository defaults
- [ ] Step 2: Validate strategy values and `item_min_cooldown_seconds >= 0`
- [ ] Step 3: Expose the new fields through GET/PUT `/query-settings`
- [ ] Step 4: Run targeted backend tests and confirm this contract layer passes

## Chunk 2: Runtime Behavior

### Task 3: Replace hardcoded item cooldown formula with configurable strategy

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/query_item_scheduler.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`

- [ ] Step 1: Thread per-mode query settings into the item scheduler constructor
- [ ] Step 2: Remove the hardcoded `0.5` base and compute cooldown from strategy
- [ ] Step 3: Make `apply_query_settings` refresh the live item scheduler configuration
- [ ] Step 4: Run targeted backend tests and confirm fixed/divide strategies and hot-apply pass

## Chunk 3: Frontend Query Settings UI

### Task 4: Add failing frontend tests for the new modal fields

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_client.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] Step 1: Add failing client expectations for new `query-settings` fields
- [ ] Step 2: Add failing modal interaction tests for strategy selection and item min cooldown save payload
- [ ] Step 3: Run targeted frontend tests to verify failures are caused by missing UI/data wiring

### Task 5: Implement frontend modal fields and save flow

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/query_settings_modal.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] Step 1: Extend draft normalization and save payload with the two new fields
- [ ] Step 2: Add item cooldown value input and strategy select to each mode card
- [ ] Step 3: Keep existing token risk confirm flow and validation intact
- [ ] Step 4: Run targeted frontend tests and confirm they pass

## Chunk 4: Verification

### Task 6: Run focused and full verification

**Files:**
- Modify: none

- [ ] Step 1: Run `python -m pytest tests/backend/test_query_item_scheduler.py tests/backend/test_query_settings_repository.py tests/backend/test_query_settings_routes.py tests/backend/test_query_runtime_service.py -q`
- [ ] Step 2: Run `npm test -- tests/renderer/account_center_client.test.js tests/renderer/purchase_system_page.test.jsx`
- [ ] Step 3: Run full `npm test`
- [ ] Step 4: Review changed files and summarize any residual edge cases around shared-pool multi-item cooldown semantics

Plan complete and saved to `docs/superpowers/plans/2026-03-22-query-item-min-cooldown-implementation.md`. Ready to execute.
