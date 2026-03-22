# Global Query Settings And Sweep Page Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent global query settings for the three query modes, wire query runtime to consume them, and expose the settings from the renamed sweep page.

**Architecture:** Keep legacy config-level `mode_settings` for compatibility, but introduce a new global `query-settings` resource as the single source of truth for Web UI and runtime execution. The frontend reads and writes one settings document through the existing shared HTTP client, while the backend resolves runtime mode parameters from the new repository before building query runners.

**Tech Stack:** FastAPI, SQLAlchemy, React 19, Vitest, pytest.

---

## Chunk 1: Back-End Global Settings Model

### Task 1: Add failing repository and route tests

**Files:**
- Modify: `tests/backend/test_query_config_repository.py`
- Modify: `tests/backend/test_query_config_routes.py`
- Modify: `tests/backend/test_query_runtime_service.py`

- [ ] Add repository tests for default global settings bootstrap and persistence.
- [ ] Add route tests for `GET /query-settings` and `PUT /query-settings`.
- [ ] Add runtime test proving global settings override legacy config `mode_settings`.
- [ ] Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_repository.py tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_service.py -q`

### Task 2: Implement database and repository support

**Files:**
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Create: `app_backend/domain/models/query_settings.py`
- Create: `app_backend/infrastructure/repositories/query_settings_repository.py`
- Modify: `app_backend/infrastructure/repositories/__init__.py`

- [ ] Add the new `query_settings_modes` table.
- [ ] Ensure schema creation includes the new table.
- [ ] Implement repository bootstrap defaults and read/write behavior.

### Task 3: Add use cases and routes

**Files:**
- Create: `app_backend/application/use_cases/get_query_settings.py`
- Create: `app_backend/application/use_cases/update_query_settings.py`
- Create: `app_backend/api/schemas/query_settings.py`
- Create: `app_backend/api/routes/query_settings.py`
- Modify: `app_backend/api/routes/__init__.py`
- Modify: `app_backend/main.py`

- [ ] Add request/response schemas with warning support.
- [ ] Add hard validation and token warning generation.
- [ ] Register the new router and repository in app bootstrap.

## Chunk 2: Runtime Integration

### Task 4: Make query runtime resolve mode settings from global settings

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py` (only if required by the test)

- [ ] Inject query settings repository into `QueryRuntimeService`.
- [ ] Replace direct runtime reliance on `config.mode_settings` with global settings snapshots.
- [ ] Keep legacy config-level data untouched for compatibility.

- [ ] Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_runtime_service.py tests/backend/test_query_config_routes.py -q`

## Chunk 3: Front-End Sweep Page + Query Settings UI

### Task 5: Add failing renderer tests

**Files:**
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/account_center_client.test.js`

- [ ] Add assertions for `扫货系统` naming, `查询设置` button, modal load/save behavior, minimum cooldown validation, and token warning flow.
- [ ] Run: `npm test -- tests/renderer/purchase_system_page.test.jsx tests/renderer/account_center_client.test.js`

### Task 6: Implement client and hook support

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`

- [ ] Add `getQuerySettings` and `updateQuerySettings`.
- [ ] Load settings when opening the modal.
- [ ] Validate locally before submit.
- [ ] Surface warning-confirm flow for token cooldown below `10s`.

### Task 7: Implement renamed sweep page UI

**Files:**
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/query_settings_modal.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] Rename sidebar label to `扫货系统`.
- [ ] Add the `查询设置` button to the left of config selection.
- [ ] Add a centered modal with three mode cards and save/cancel controls.
- [ ] Reuse existing modal styling patterns where possible.

## Chunk 4: Verification

### Task 8: Run targeted and full verification

**Files:**
- Verify only

- [ ] Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_query_config_repository.py tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_service.py -q`
- [ ] Run: `npm test -- tests/renderer/purchase_system_page.test.jsx tests/renderer/account_center_client.test.js`
- [ ] Run: `npm test`
