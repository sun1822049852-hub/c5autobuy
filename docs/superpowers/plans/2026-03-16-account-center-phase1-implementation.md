# Account Center Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new standalone account center with `PySide6 + FastAPI + SQLite`, covering account CRUD and Selenium login capability binding without touching the current scan/purchase entry flow.

**Architecture:** Add a parallel frontend/backend stack beside the current `run_app.py -> c5_layered` flow. The frontend only handles presentation and API calls; the backend owns account persistence, Selenium login orchestration, conflict resolution, and task status streaming. Phase 1 keeps legacy query/purchase code isolated and does not wire new accounts into the old engine yet.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, SQLAlchemy, Pydantic, PySide6, aiohttp-compatible Selenium login adapter reuse, SQLite, pytest, pytest-asyncio, httpx, pytest-qt

**Historical Naming Note:** 本计划阶段的登录链仍以 `selenium` 作为目录与能力命名。当前仓库中，相关活跃模块已迁到 `app_backend/infrastructure/browser_runtime/`，并由 `BrowserLoginAdapter` 承接原 `SeleniumLoginAdapter` 的职责。

---

## Scope

This plan only covers Phase 1 from the approved spec:

- New account center backend
- New account center desktop frontend
- SQLite account storage
- Selenium login task flow
- Login conflict resolution
- Purchase capability clearing
- Account deletion

Out of scope for this plan:

- Wiring new accounts into legacy scan/purchase
- Reusing `account/*.json`
- Replacing `run_app.py`
- Migrating current Tkinter GUI features

## Existing Context

- Current entrypoint stays at [run_app.py](C:/Users/18220/Desktop/C5autobug更新接口%20-%20副本%20(2)/run_app.py:10).
- Current GUI is Tkinter-based and tightly bound to current use cases at [c5_layered/presentation/gui/app.py](C:/Users/18220/Desktop/C5autobug更新接口%20-%20副本%20(2)/c5_layered/presentation/gui/app.py:11).
- Selenium login, proxy plugin fallback, and account creation logic currently live inside `autobuy.py` and should be wrapped, not rewritten blind in the first pass.
- The repository now exists, but user instruction forbids planning git commits unless explicitly requested, so this plan omits commit steps.

## File Structure Map

### New backend files

- Create: `app_backend/main.py`
  - FastAPI app bootstrap and local dev entrypoint.
- Create: `app_backend/api/routes/accounts.py`
  - Account CRUD HTTP routes.
- Create: `app_backend/api/routes/tasks.py`
  - Task query route.
- Create: `app_backend/api/websocket/tasks.py`
  - WebSocket task status route.
- Create: `app_backend/api/schemas/accounts.py`
  - Pydantic request/response models for accounts.
- Create: `app_backend/api/schemas/tasks.py`
  - Pydantic task payloads.
- Create: `app_backend/application/use_cases/create_account.py`
  - New account creation use case.
- Create: `app_backend/application/use_cases/update_account.py`
  - Account editing use case.
- Create: `app_backend/application/use_cases/delete_account.py`
  - Account deletion use case.
- Create: `app_backend/application/use_cases/clear_purchase_capability.py`
  - Purchase capability clearing use case.
- Create: `app_backend/application/use_cases/start_login_task.py`
  - Selenium login task startup and conflict signaling.
- Create: `app_backend/application/use_cases/resolve_login_conflict.py`
  - Replace-or-create-new conflict resolution use case.
- Create: `app_backend/application/services/account_name_service.py`
  - Default name generation and display-name logic.
- Create: `app_backend/domain/models/account.py`
  - Account domain model.
- Create: `app_backend/domain/enums/account_states.py`
  - Purchase capability and pool state enums.
- Create: `app_backend/infrastructure/db/base.py`
  - SQLAlchemy base and engine/session bootstrap.
- Create: `app_backend/infrastructure/db/models.py`
  - SQLAlchemy `accounts` table model.
- Create: `app_backend/infrastructure/repositories/account_repository.py`
  - Repository implementation for SQLite.
- Create: `app_backend/infrastructure/selenium/login_adapter.py`
  - Wrapper around the existing Selenium login flow and proxy behavior.
- Create: `app_backend/infrastructure/proxy/value_objects.py`
  - Proxy parsing/normalization helpers.
- Create: `app_backend/workers/manager/task_manager.py`
  - In-memory task registry and event fan-out.
- Create: `app_backend/workers/tasks/login_task.py`
  - Async login task implementation.

### New frontend files

- Create: `app_frontend/main.py`
  - PySide6 app bootstrap and local dev entrypoint.
- Create: `app_frontend/app/windows/account_center_window.py`
  - Main account center window.
- Create: `app_frontend/app/widgets/account_table.py`
  - Left-side account list table.
- Create: `app_frontend/app/widgets/account_detail_panel.py`
  - Right-side readonly detail panel.
- Create: `app_frontend/app/dialogs/create_account_dialog.py`
  - New account dialog.
- Create: `app_frontend/app/dialogs/edit_account_dialog.py`
  - Edit dialog.
- Create: `app_frontend/app/dialogs/login_task_dialog.py`
  - Login progress/status dialog and conflict prompt.
- Create: `app_frontend/app/services/backend_client.py`
  - HTTP + WebSocket API client wrapper.
- Create: `app_frontend/app/viewmodels/account_center_vm.py`
  - Presentation state and command coordination.

### Shared/testing/support files

- Create: `pyproject.toml`
  - Project dependencies and test tooling config.
- Create: `.gitignore`
  - Ignore `.venv`, `__pycache__`, `data/app.db`, Qt caches, test artifacts.
- Create: `tests/backend/conftest.py`
  - Backend app/session fixtures.
- Create: `tests/backend/test_account_routes.py`
  - CRUD and capability route tests.
- Create: `tests/backend/test_login_conflict_flow.py`
  - Login conflict tests.
- Create: `tests/backend/test_proxy_normalization.py`
  - Proxy parsing tests.
- Create: `tests/frontend/test_account_center_vm.py`
  - ViewModel behavior tests.
- Create: `tests/frontend/test_account_detail_panel.py`
  - Readonly panel rendering tests.

### Existing files to leave untouched in Phase 1

- Do not modify: `run_app.py`
- Do not modify: `c5_layered/**`
- Do not modify: legacy scan/purchase logic in `autobuy.py` except for extracting a safe adapter boundary if absolutely required by implementation

## Chunk 1: Tooling And Backend Skeleton

### Task 1: Create project tooling baseline

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Test: `python -m pytest --version`

- [ ] **Step 1: Write `pyproject.toml` with runtime and test dependencies**

Include:
- runtime: `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `pyside6`, `httpx`
- test: `pytest`, `pytest-asyncio`, `pytest-qt`

- [ ] **Step 2: Add `.gitignore`**

Ignore:
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `data/app.db`
- `*.pyc`
- Qt-generated caches

- [ ] **Step 3: Verify pytest is available through the chosen environment**

Run: `python -m pytest --version`
Expected: version output, no import error

### Task 2: Create backend package skeleton

**Files:**
- Create: `app_backend/main.py`
- Create: `app_backend/api/routes/__init__.py`
- Create: `app_backend/api/routes/accounts.py`
- Create: `app_backend/api/routes/tasks.py`
- Create: `app_backend/api/websocket/tasks.py`
- Create: `app_backend/api/schemas/accounts.py`
- Create: `app_backend/api/schemas/tasks.py`
- Create: `app_backend/application/__init__.py`
- Create: `app_backend/domain/__init__.py`
- Create: `app_backend/infrastructure/__init__.py`
- Create: `app_backend/workers/__init__.py`
- Test: `tests/backend/test_backend_health.py`

- [ ] **Step 1: Write the failing backend smoke test**

```python
from httpx import AsyncClient

from app_backend.main import create_app


async def test_health_endpoint():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the backend smoke test to verify it fails**

Run: `python -m pytest tests/backend/test_backend_health.py -v`
Expected: FAIL because backend app does not exist yet

- [ ] **Step 3: Implement minimal backend app factory and `/health` route**

Implement `create_app()` in `app_backend/main.py` and register a simple health route.

- [ ] **Step 4: Run the backend smoke test again**

Run: `python -m pytest tests/backend/test_backend_health.py -v`
Expected: PASS

### Task 3: Create SQLite bootstrap and account table

**Files:**
- Create: `app_backend/infrastructure/db/base.py`
- Create: `app_backend/infrastructure/db/models.py`
- Test: `tests/backend/test_account_table_bootstrap.py`

- [ ] **Step 1: Write the failing database bootstrap test**

```python
from sqlalchemy import inspect

from app_backend.infrastructure.db.base import build_engine, create_schema


def test_create_schema_builds_accounts_table(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    inspector = inspect(engine)
    assert "accounts" in inspector.get_table_names()
```

- [ ] **Step 2: Run the database bootstrap test to verify it fails**

Run: `python -m pytest tests/backend/test_account_table_bootstrap.py -v`
Expected: FAIL because DB bootstrap files do not exist

- [ ] **Step 3: Implement engine/session bootstrap and SQLAlchemy `accounts` model**

Model fields must match the approved spec:
- `account_id`
- `default_name`
- `remark_name`
- `proxy_mode`
- `proxy_url`
- `api_key`
- `c5_user_id`
- `c5_nick_name`
- `cookie_raw`
- `purchase_capability_state`
- `purchase_pool_state`
- `last_login_at`
- `last_error`
- `created_at`
- `updated_at`
- `disabled`

- [ ] **Step 4: Run the database bootstrap test again**

Run: `python -m pytest tests/backend/test_account_table_bootstrap.py -v`
Expected: PASS

## Chunk 2: Backend Domain, Repository, And Account CRUD

### Task 4: Create account domain model and state enums

**Files:**
- Create: `app_backend/domain/models/account.py`
- Create: `app_backend/domain/enums/account_states.py`
- Test: `tests/backend/test_account_domain.py`

- [ ] **Step 1: Write the failing domain model test**

```python
from app_backend.domain.models.account import Account


def test_display_name_prefers_remark_then_platform_then_default():
    account = Account(
        account_id="a1",
        default_name="默认账号",
        remark_name="备注名",
        c5_nick_name="平台昵称",
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
        c5_user_id=None,
        cookie_raw=None,
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
    )
    assert account.display_name == "备注名"
```

- [ ] **Step 2: Run the domain model test to verify it fails**

Run: `python -m pytest tests/backend/test_account_domain.py -v`
Expected: FAIL because model is missing

- [ ] **Step 3: Implement the domain model and enum constants**

Ensure:
- display-name priority is `remark_name > c5_nick_name > default_name`
- `purchase_pool_state` defaults to `not_connected` in Phase 1

- [ ] **Step 4: Run the domain model test again**

Run: `python -m pytest tests/backend/test_account_domain.py -v`
Expected: PASS

### Task 5: Create proxy normalization helper

**Files:**
- Create: `app_backend/infrastructure/proxy/value_objects.py`
- Test: `tests/backend/test_proxy_normalization.py`

- [ ] **Step 1: Write failing proxy normalization tests**

Cases:
- empty input -> `direct` / `None`
- full URL with auth stays intact
- split fields can render into full URL

- [ ] **Step 2: Run the proxy normalization tests to verify they fail**

Run: `python -m pytest tests/backend/test_proxy_normalization.py -v`
Expected: FAIL because helper is missing

- [ ] **Step 3: Implement proxy normalization helpers**

Rules:
- empty proxy equals direct connection
- valid stored form uses a single normalized URL string or `None`
- preserve auth credentials when present

- [ ] **Step 4: Run the proxy normalization tests again**

Run: `python -m pytest tests/backend/test_proxy_normalization.py -v`
Expected: PASS

### Task 6: Create account repository

**Files:**
- Create: `app_backend/infrastructure/repositories/account_repository.py`
- Test: `tests/backend/test_account_repository.py`

- [ ] **Step 1: Write failing repository tests**

Cover:
- create account
- list accounts in stable order
- update account fields
- clear purchase capability without touching `api_key`
- delete account

- [ ] **Step 2: Run the repository tests to verify they fail**

Run: `python -m pytest tests/backend/test_account_repository.py -v`
Expected: FAIL because repository does not exist

- [ ] **Step 3: Implement repository methods**

Minimum methods:
- `list_accounts`
- `get_account`
- `create_account`
- `update_account`
- `clear_purchase_capability`
- `delete_account`

- [ ] **Step 4: Run the repository tests again**

Run: `python -m pytest tests/backend/test_account_repository.py -v`
Expected: PASS

### Task 7: Implement account CRUD use cases and routes

**Files:**
- Create: `app_backend/application/services/account_name_service.py`
- Create: `app_backend/application/use_cases/create_account.py`
- Create: `app_backend/application/use_cases/update_account.py`
- Create: `app_backend/application/use_cases/delete_account.py`
- Create: `app_backend/application/use_cases/clear_purchase_capability.py`
- Modify: `app_backend/api/schemas/accounts.py`
- Modify: `app_backend/api/routes/accounts.py`
- Test: `tests/backend/test_account_routes.py`

- [ ] **Step 1: Write failing route tests for account CRUD**

Cover:
- `POST /accounts`
- `GET /accounts`
- `GET /accounts/{id}`
- `PATCH /accounts/{id}`
- `POST /accounts/{id}/purchase-capability/clear`
- `DELETE /accounts/{id}`

- [ ] **Step 2: Run the route tests to verify they fail**

Run: `python -m pytest tests/backend/test_account_routes.py -v`
Expected: FAIL because routes and use cases are incomplete

- [ ] **Step 3: Implement use cases and route wiring**

Behavior requirements:
- backend generates `account_id`
- backend generates `default_name`
- `api_key` is saved without validation
- clearing purchase capability does not modify `api_key`, `remark_name`, or proxy settings

- [ ] **Step 4: Run the route tests again**

Run: `python -m pytest tests/backend/test_account_routes.py -v`
Expected: PASS

## Chunk 3: Selenium Login Task And Conflict Resolution

### Task 8: Create task manager and task schema

**Files:**
- Create: `app_backend/workers/manager/task_manager.py`
- Modify: `app_backend/api/schemas/tasks.py`
- Modify: `app_backend/api/routes/tasks.py`
- Modify: `app_backend/api/websocket/tasks.py`
- Test: `tests/backend/test_task_manager.py`

- [ ] **Step 1: Write failing task manager tests**

Cover:
- create task id
- push ordered state updates
- read current state over HTTP

- [ ] **Step 2: Run the task manager tests to verify they fail**

Run: `python -m pytest tests/backend/test_task_manager.py -v`
Expected: FAIL because task manager does not exist

- [ ] **Step 3: Implement in-memory task manager**

Minimum features:
- `create_task`
- `set_state`
- `set_result`
- `set_error`
- `get_task`
- subscriber fan-out for WebSocket clients

- [ ] **Step 4: Run the task manager tests again**

Run: `python -m pytest tests/backend/test_task_manager.py -v`
Expected: PASS

### Task 9: Wrap the existing Selenium login flow behind a backend adapter

**Files:**
- Create: `app_backend/infrastructure/selenium/login_adapter.py`
- Test: `tests/backend/test_login_adapter_contract.py`

- [ ] **Step 1: Write failing adapter contract tests**

Mock the underlying login implementation and assert the adapter returns:
- `c5_user_id`
- `c5_nick_name`
- `cookie_raw`

- [ ] **Step 2: Run the adapter tests to verify they fail**

Run: `python -m pytest tests/backend/test_login_adapter_contract.py -v`
Expected: FAIL because adapter does not exist

- [ ] **Step 3: Implement the adapter**

Requirements:
- preserve proxy behavior from current Selenium logic
- preserve proxy-auth-plugin-first strategy
- preserve fallback to `--proxy-server`
- treat login completion as “user manually closed browser after capture”
- do not leak direct `autobuy.py` imports into API layer; keep them inside the adapter

- [ ] **Step 4: Run the adapter tests again**

Run: `python -m pytest tests/backend/test_login_adapter_contract.py -v`
Expected: PASS

### Task 10: Implement login task use case

**Files:**
- Create: `app_backend/workers/tasks/login_task.py`
- Create: `app_backend/application/use_cases/start_login_task.py`
- Modify: `app_backend/api/routes/accounts.py`
- Test: `tests/backend/test_login_task_flow.py`

- [ ] **Step 1: Write failing login task tests**

Cover state sequence:
- `starting_browser`
- `waiting_for_scan`
- `captured_login_info`
- `waiting_for_browser_close`
- `saving_account`
- `succeeded`

- [ ] **Step 2: Run the login task tests to verify they fail**

Run: `python -m pytest tests/backend/test_login_task_flow.py -v`
Expected: FAIL because login task flow is not implemented

- [ ] **Step 3: Implement login task orchestration**

Behavior:
- read current account proxy config
- launch Selenium adapter
- store result on success
- update `purchase_capability_state` to `bound`
- keep `purchase_pool_state` as `not_connected` in Phase 1

- [ ] **Step 4: Run the login task tests again**

Run: `python -m pytest tests/backend/test_login_task_flow.py -v`
Expected: PASS

### Task 11: Implement login conflict resolution

**Files:**
- Create: `app_backend/application/use_cases/resolve_login_conflict.py`
- Modify: `app_backend/api/routes/accounts.py`
- Test: `tests/backend/test_login_conflict_flow.py`

- [ ] **Step 1: Write failing login conflict tests**

Cover:
- same `c5_user_id` -> update same account
- different `c5_user_id` -> task enters conflict state
- resolve with `create_new_account`
- resolve with `replace_with_new_account`

- [ ] **Step 2: Run the login conflict tests to verify they fail**

Run: `python -m pytest tests/backend/test_login_conflict_flow.py -v`
Expected: FAIL because conflict flow is not implemented

- [ ] **Step 3: Implement conflict resolution behavior**

Rules:
- `create_new_account`: keep current account, create a separate new one from login payload
- `replace_with_new_account`: delete current account, then create a new one from login payload
- do not merge old `proxy`, `api_key`, or `remark_name` into the new account

- [ ] **Step 4: Run the login conflict tests again**

Run: `python -m pytest tests/backend/test_login_conflict_flow.py -v`
Expected: PASS

## Chunk 4: PySide6 Account Center Frontend

### Task 12: Create backend client and frontend bootstrap

**Files:**
- Create: `app_frontend/main.py`
- Create: `app_frontend/app/services/backend_client.py`
- Test: `tests/frontend/test_backend_client.py`

- [ ] **Step 1: Write failing frontend client tests**

Cover:
- fetch account list
- create account request
- subscribe to task status

- [ ] **Step 2: Run the frontend client tests to verify they fail**

Run: `python -m pytest tests/frontend/test_backend_client.py -v`
Expected: FAIL because client does not exist

- [ ] **Step 3: Implement backend client wrapper**

It must expose:
- `list_accounts()`
- `get_account(account_id)`
- `create_account(payload)`
- `update_account(account_id, payload)`
- `delete_account(account_id)`
- `clear_purchase_capability(account_id)`
- `start_login(account_id)`
- `watch_task(task_id)`

- [ ] **Step 4: Run the frontend client tests again**

Run: `python -m pytest tests/frontend/test_backend_client.py -v`
Expected: PASS

### Task 13: Build account center window shell

**Files:**
- Create: `app_frontend/app/viewmodels/account_center_vm.py`
- Create: `app_frontend/app/windows/account_center_window.py`
- Create: `app_frontend/app/widgets/account_table.py`
- Create: `app_frontend/app/widgets/account_detail_panel.py`
- Test: `tests/frontend/test_account_center_vm.py`
- Test: `tests/frontend/test_account_detail_panel.py`

- [ ] **Step 1: Write failing ViewModel and detail-panel tests**

Cover:
- selected row does not auto-open detail
- clicking “查看详情” loads the detail panel
- detail panel stays readonly
- display-name priority is reflected in the table

- [ ] **Step 2: Run the frontend shell tests to verify they fail**

Run: `python -m pytest tests/frontend/test_account_center_vm.py tests/frontend/test_account_detail_panel.py -v`
Expected: FAIL because frontend shell is missing

- [ ] **Step 3: Implement the account center shell**

Requirements:
- left table columns: display name, query capability, purchase capability, purchase pool state, proxy
- single click only selects
- right panel is readonly
- “查看详情” controls detail loading

- [ ] **Step 4: Run the frontend shell tests again**

Run: `python -m pytest tests/frontend/test_account_center_vm.py tests/frontend/test_account_detail_panel.py -v`
Expected: PASS

### Task 14: Add create/edit dialogs

**Files:**
- Create: `app_frontend/app/dialogs/create_account_dialog.py`
- Create: `app_frontend/app/dialogs/edit_account_dialog.py`
- Modify: `app_frontend/app/windows/account_center_window.py`
- Test: `tests/frontend/test_account_dialogs.py`

- [ ] **Step 1: Write failing dialog tests**

Cover:
- create dialog accepts empty proxy as direct
- edit dialog updates `remark_name`, `proxy`, `api_key`
- dialogs do not expose purchase capability editing

- [ ] **Step 2: Run the dialog tests to verify they fail**

Run: `python -m pytest tests/frontend/test_account_dialogs.py -v`
Expected: FAIL because dialogs do not exist

- [ ] **Step 3: Implement dialogs and window integration**

Requirements:
- create dialog fields: `remark_name`, proxy mode/input, `api_key`
- edit dialog modifies only allowed fields
- API key shown as configured/unconfigured in main detail panel

- [ ] **Step 4: Run the dialog tests again**

Run: `python -m pytest tests/frontend/test_account_dialogs.py -v`
Expected: PASS

### Task 15: Add login task dialog and conflict handling UX

**Files:**
- Create: `app_frontend/app/dialogs/login_task_dialog.py`
- Modify: `app_frontend/app/windows/account_center_window.py`
- Modify: `app_frontend/app/viewmodels/account_center_vm.py`
- Test: `tests/frontend/test_login_task_dialog.py`

- [ ] **Step 1: Write failing login task dialog tests**

Cover:
- dialog shows ordered states
- conflict prompt offers:
  - delete current and create new
  - create new only
  - cancel

- [ ] **Step 2: Run the login task dialog tests to verify they fail**

Run: `python -m pytest tests/frontend/test_login_task_dialog.py -v`
Expected: FAIL because login dialog does not exist

- [ ] **Step 3: Implement login task dialog and conflict UX**

Requirements:
- show task states from backend
- block manual cookie editing
- on conflict, call backend resolution endpoint
- on success, refresh list and detail state

- [ ] **Step 4: Run the login task dialog tests again**

Run: `python -m pytest tests/frontend/test_login_task_dialog.py -v`
Expected: PASS

## Chunk 5: End-To-End Verification And Handoff

### Task 16: Add local integration smoke tests

**Files:**
- Create: `tests/backend/test_account_center_smoke.py`

- [ ] **Step 1: Write failing smoke tests**

Cover:
- create account
- edit account
- clear purchase capability
- delete account

- [ ] **Step 2: Run the smoke tests to verify they fail**

Run: `python -m pytest tests/backend/test_account_center_smoke.py -v`
Expected: FAIL until full route wiring is complete

- [ ] **Step 3: Implement any missing backend glue uncovered by smoke tests**

Use smoke failures to close gaps only; do not expand scope.

- [ ] **Step 4: Run the smoke tests again**

Run: `python -m pytest tests/backend/test_account_center_smoke.py -v`
Expected: PASS

### Task 17: Run final verification suite

**Files:**
- No file changes expected

- [ ] **Step 1: Run backend tests**

Run: `python -m pytest tests/backend -v`
Expected: PASS

- [ ] **Step 2: Run frontend tests**

Run: `python -m pytest tests/frontend -v`
Expected: PASS

- [ ] **Step 3: Run Python syntax verification**

Run: `python -m py_compile $(rg --files -g "*.py")`
Expected: no output, exit code 0

- [ ] **Step 4: Smoke-run backend app startup**

Run: `python -m app_backend.main`
Expected: local backend starts without import errors

- [ ] **Step 5: Smoke-run frontend app startup**

Run: `python -m app_frontend.main`
Expected: window opens without import errors

## Notes For The Implementer

- Do not wire this new frontend into `run_app.py` in Phase 1.
- Do not modify legacy `account/*.json` reading/writing in Phase 1.
- Keep all legacy imports inside backend adapter boundaries.
- Preserve the current Selenium proxy strategy:
  - proxy-auth extension first
  - fallback to `--proxy-server`
- Treat user-closed browser as the true completion event for login, even if credentials were already captured.
- Do not add git commit steps; the repository owner has explicitly not requested commit planning.

## Plan Review Notes

- This harness does not expose the plan-document-reviewer subagent described by the skill, so the plan was self-reviewed against the approved spec and current codebase instead.

Plan complete and saved to `docs/superpowers/plans/2026-03-16-account-center-phase1-implementation.md`. Ready to execute?
