# Purchase Competition And Proxy Split Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前新 UI 与新后端落地全局 runtime settings、双代理字段切换、按账户代理 bucket 的竞争购买 fanout，以及扫货页左侧的购买设置/查询设置面板。

**Architecture:** 先建立全局 `runtime_settings` 真相源并让 query runtime 完成 `query_settings_json` cutover，再拆账户代理与 API 代理的使用路径，随后在购买 runtime 中引入 `competition planner -> scheduler claim -> dispatch` 的三段式竞争派发，最后把扫货页左侧设置面板接到新的 settings API。统计口径保持现状，不压平同批次的多账号尝试；查询命中仍按原始 hit 计，账号成功/失败按实际尝试计。

**Tech Stack:** FastAPI、SQLAlchemy/SQLite、Python pytest、React 19、Vite、Vitest、Testing Library

---

## File Map

### Backend persistence / settings

- Create: `app_backend/domain/models/runtime_settings.py`
- Create: `app_backend/infrastructure/repositories/runtime_settings_repository.py`
- Create: `app_backend/application/use_cases/get_runtime_settings.py`
- Create: `app_backend/application/use_cases/update_query_runtime_settings.py`
- Create: `app_backend/application/use_cases/update_purchase_runtime_settings.py`
- Create: `app_backend/api/schemas/runtime_settings.py`
- Create: `app_backend/api/routes/runtime_settings.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Modify: `app_backend/main.py`

### Backend query runtime cutover

- Modify: `app_backend/domain/models/query_config.py`
- Modify: `app_backend/infrastructure/query/runtime/query_item_scheduler.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/application/use_cases/prepare_query_runtime.py`
- Modify: `app_backend/api/routes/query_runtime.py`

### Backend account proxy split

- Modify: `app_backend/domain/models/account.py`
- Modify: `app_backend/infrastructure/repositories/account_repository.py`
- Modify: `app_backend/api/schemas/accounts.py`
- Modify: `app_backend/api/schemas/account_center.py`
- Modify: `app_backend/workers/tasks/login_task.py`
- Modify: `app_backend/application/use_cases/resolve_login_conflict.py`
- Modify: `app_backend/api/routes/accounts.py`
- Modify: `app_backend/application/use_cases/create_account.py`
- Modify: `app_backend/application/use_cases/update_account.py`
- Modify: `app_backend/infrastructure/query/runtime/runtime_account_adapter.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

### Backend competition runtime

- Create: `app_backend/infrastructure/purchase/runtime/proxy_bucket.py`
- Create: `app_backend/infrastructure/purchase/runtime/competition_planner.py`
- Modify: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_hit_inbox.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/application/use_cases/get_purchase_runtime_status.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`

### Frontend settings + account UI

- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/account-center/dialogs/account_create_dialog.jsx`
- Modify: `app_desktop_web/src/features/account-center/dialogs/account_proxy_dialog.jsx`
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_settings_panel.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/query_settings_panel.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

### Backend tests

- Create: `tests/backend/test_runtime_settings_repository.py`
- Create: `tests/backend/test_runtime_settings_routes.py`
- Modify: `tests/backend/test_desktop_web_backend_bootstrap.py`
- Modify: `tests/backend/test_query_item_scheduler.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Modify: `tests/backend/test_account_table_bootstrap.py`
- Modify: `tests/backend/test_account_repository.py`
- Modify: `tests/backend/test_account_routes.py`
- Modify: `tests/backend/test_account_center_routes.py`
- Modify: `tests/backend/test_login_task_flow.py`
- Modify: `tests/backend/test_login_conflict_flow.py`
- Modify: `tests/backend/test_account_center_smoke.py`
- Modify: `tests/backend/test_runtime_account_adapter.py`
- Modify: `tests/backend/test_purchase_scheduler.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_query_purchase_bridge.py`

### Frontend tests

- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/account_center_client.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`

## Chunk 1: Runtime Settings Foundation And Query Cutover

### Task 1: Add `runtime_settings` persistence and repository

**Files:**
- Create: `app_backend/domain/models/runtime_settings.py`
- Create: `app_backend/infrastructure/repositories/runtime_settings_repository.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Test: `tests/backend/test_runtime_settings_repository.py`
- Test: `tests/backend/test_desktop_web_backend_bootstrap.py`

- [ ] **Step 1: Write failing repository tests for default row creation and partial saves**

Cover:
- empty database returns a synthesized default settings object
- `save_query_settings()` updates only `query_settings_json`
- `save_purchase_settings()` updates only `purchase_settings_json`
- persisted row key is always `settings_id = "default"`

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_runtime_settings_repository.py" `
  "tests/backend/test_desktop_web_backend_bootstrap.py" -q
```

Expected:

- FAIL because `runtime_settings` table and repository do not exist

- [ ] **Step 2: Add `RuntimeSettings` domain model and `RuntimeSettingsRecord`**

Freeze the model fields to:
- `settings_id`
- `query_settings_json`
- `purchase_settings_json`
- `updated_at`

Use JSON text storage in the DB model to stay consistent with the current SQLite style.

- [ ] **Step 3: Implement `runtime_settings_repository.py` with deterministic defaults**

Required methods:
- `get()`
- `save_query_settings(query_settings)`
- `save_purchase_settings(purchase_settings)`

Default `query_settings_json` must initialize exactly to the spec defaults:
- `new_api.cooldown_min_seconds = 1.0`
- `fast_api.cooldown_min_seconds = 0.2`
- `token.cooldown_min_seconds = 10.0`
- `item_pacing.*.strategy = "fixed_divided_by_actual_allocated_workers"`
- `item_pacing.*.fixed_seconds = 0.5`

Default `purchase_settings_json` must initialize to:

```json
{
  "ip_bucket_limits": {}
}
```

- [ ] **Step 4: Wire schema creation and thin migration in `db/base.py`**

Requirements:
- create `runtime_settings` when missing
- do not backfill from `QueryConfig.mode_settings`
- do not mutate existing business semantics outside the new table

- [ ] **Step 5: Re-run repository and bootstrap tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_runtime_settings_repository.py" `
  "tests/backend/test_desktop_web_backend_bootstrap.py" -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_backend/domain/models/runtime_settings.py app_backend/infrastructure/repositories/runtime_settings_repository.py app_backend/infrastructure/db/models.py app_backend/infrastructure/db/base.py tests/backend/test_runtime_settings_repository.py tests/backend/test_desktop_web_backend_bootstrap.py
git commit -m "feat: add runtime settings persistence"
```

### Task 2: Expose runtime settings API and cut query runtime over to `query_settings_json`

**Files:**
- Create: `app_backend/application/use_cases/get_runtime_settings.py`
- Create: `app_backend/application/use_cases/update_query_runtime_settings.py`
- Create: `app_backend/application/use_cases/update_purchase_runtime_settings.py`
- Create: `app_backend/api/schemas/runtime_settings.py`
- Create: `app_backend/api/routes/runtime_settings.py`
- Modify: `app_backend/main.py`
- Modify: `app_backend/domain/models/query_config.py`
- Modify: `app_backend/infrastructure/query/runtime/query_item_scheduler.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/application/use_cases/prepare_query_runtime.py`
- Test: `tests/backend/test_runtime_settings_routes.py`
- Test: `tests/backend/test_query_item_scheduler.py`
- Test: `tests/backend/test_query_runtime_service.py`
- Test: `tests/backend/test_query_runtime_routes.py`

Note:
- Spec uses `/api/runtime-settings*` as the external contract description.
- This codebase mounts FastAPI routers at root, so backend tests and route definitions must use:
  - `/runtime-settings`
  - `/runtime-settings/query`
  - `/runtime-settings/purchase`
- Frontend still reaches the same endpoints through `apiBaseUrl`, so there is no behavioral mismatch.

- [ ] **Step 1: Write failing route tests for `GET /runtime-settings` and split `PUT` endpoints**

Cover:
- `GET /runtime-settings` returns both `query_settings` and `purchase_settings`
- `PUT /runtime-settings/query` validates min values:
  - `fast_api >= 0.2`
  - `new_api >= 1.0`
  - `token >= 10.0`
- invalid payload returns `422`
- `PUT /runtime-settings/purchase` validates `concurrency_limit` as integer and `>= 1`

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_runtime_settings_routes.py" -q
```

Expected: FAIL because routes and schemas do not exist

- [ ] **Step 2: Write failing query runtime tests that prove runtime now reads global settings instead of `QueryConfig.mode_settings`**

Cover:
- runtime with no saved global settings uses repository defaults
- after `save_query_settings()`, runtime snapshot reflects new mode enable/window/cooldown behavior
- leaving legacy `QueryConfig.mode_settings` unchanged does not affect runtime behavior
- already-running runtime hot-applies updated global query settings without rebuilding account session identity
- pending-resume runtime reuses the new global settings after accounts recover

Also add a failing scheduler test in `tests/backend/test_query_item_scheduler.py` that proves `item_pacing` now comes from global settings rather than the hard-coded `0.5 / actual_assigned_count` only.

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_query_item_scheduler.py" `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" -q
```

Expected: FAIL because query runtime still consumes config-scoped mode settings

- [ ] **Step 3: Implement runtime settings routes, schemas, and use cases**

Freeze API shapes to:
- `GET /runtime-settings`
- `PUT /runtime-settings/query`
- `PUT /runtime-settings/purchase`

Requirements:
- each `PUT` returns the full latest settings snapshot
- query and purchase settings save independently
- `422` is the only validation error shape used here

- [ ] **Step 4: Inject `RuntimeSettingsRepository` into app bootstrap and query runtime service**

Requirements:
- `app.state.runtime_settings_repository`
- query runtime services receive repository access
- no fallback to `QueryConfig.mode_settings` after cutover

- [ ] **Step 5: Replace runtime reads of config-scoped mode settings with global settings**

Keep `QueryConfig.mode_settings` only for config detail compatibility.

Do not delete the field yet.

Required runtime truth:
- enable / disable by global mode settings
- cooldown window rules by global mode settings
- item pacing by `query_settings_json.item_pacing`

Update `query_item_scheduler.py` so the dynamic pacing base is no longer an unchangeable constant. The scheduler must consume the per-mode pacing strategy/value derived from global settings.

- [ ] **Step 6: Freeze and assert the full default `query_settings_json` payload**

Repository defaults must match the spec shape exactly:

```json
{
  "modes": {
    "new_api": {
      "enabled": true,
      "cooldown_min_seconds": 1.0,
      "cooldown_max_seconds": 1.0,
      "random_delay_enabled": false,
      "random_delay_min_seconds": 0.0,
      "random_delay_max_seconds": 0.0,
      "window_enabled": false,
      "start_hour": 0,
      "start_minute": 0,
      "end_hour": 0,
      "end_minute": 0
    },
    "fast_api": {
      "enabled": true,
      "cooldown_min_seconds": 0.2,
      "cooldown_max_seconds": 0.2,
      "random_delay_enabled": false,
      "random_delay_min_seconds": 0.0,
      "random_delay_max_seconds": 0.0,
      "window_enabled": false,
      "start_hour": 0,
      "start_minute": 0,
      "end_hour": 0,
      "end_minute": 0
    },
    "token": {
      "enabled": true,
      "cooldown_min_seconds": 10.0,
      "cooldown_max_seconds": 10.0,
      "random_delay_enabled": false,
      "random_delay_min_seconds": 0.0,
      "random_delay_max_seconds": 0.0,
      "window_enabled": false,
      "start_hour": 0,
      "start_minute": 0,
      "end_hour": 0,
      "end_minute": 0
    }
  },
  "item_pacing": {
    "new_api": {
      "strategy": "fixed_divided_by_actual_allocated_workers",
      "fixed_seconds": 0.5
    },
    "fast_api": {
      "strategy": "fixed_divided_by_actual_allocated_workers",
      "fixed_seconds": 0.5
    },
    "token": {
      "strategy": "fixed_divided_by_actual_allocated_workers",
      "fixed_seconds": 0.5
    }
  }
}
```

- [ ] **Step 7: Re-run route, scheduler, and query runtime tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_runtime_settings_routes.py" `
  "tests/backend/test_query_item_scheduler.py" `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" -q
```

Expected: PASS

- [ ] **Step 8: Explicitly verify hot-apply without session rebuild**

Run a targeted test or assertion added in `tests/backend/test_query_runtime_service.py` that confirms:
- runtime settings update changes runtime scheduling behavior while running
- pending-resume state also reflects the new settings
- account/runtime session identity stays unchanged

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_query_runtime_service.py" -q
```

Expected: PASS with no assertion that sessions were recreated

- [ ] **Step 9: Commit**

```bash
git add app_backend/application/use_cases/get_runtime_settings.py app_backend/application/use_cases/update_query_runtime_settings.py app_backend/application/use_cases/update_purchase_runtime_settings.py app_backend/api/schemas/runtime_settings.py app_backend/api/routes/runtime_settings.py app_backend/main.py app_backend/domain/models/query_config.py app_backend/infrastructure/query/runtime/query_item_scheduler.py app_backend/infrastructure/query/runtime/query_runtime_service.py app_backend/infrastructure/query/runtime/query_task_runtime.py app_backend/infrastructure/query/runtime/mode_runner.py app_backend/application/use_cases/prepare_query_runtime.py tests/backend/test_runtime_settings_routes.py tests/backend/test_query_item_scheduler.py tests/backend/test_query_runtime_service.py tests/backend/test_query_runtime_routes.py
git commit -m "feat: cut query runtime over to global settings"
```

## Chunk 2: Dual Proxy Field Migration

### Task 3: Add dual proxy fields to account persistence and APIs

**Files:**
- Modify: `app_backend/domain/models/account.py`
- Modify: `app_backend/infrastructure/repositories/account_repository.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Modify: `app_backend/api/schemas/accounts.py`
- Modify: `app_backend/api/schemas/account_center.py`
- Modify: `app_backend/workers/tasks/login_task.py`
- Modify: `app_backend/application/use_cases/resolve_login_conflict.py`
- Modify: `app_backend/api/routes/accounts.py`
- Modify: `app_backend/application/use_cases/create_account.py`
- Modify: `app_backend/application/use_cases/update_account.py`
- Test: `tests/backend/test_account_table_bootstrap.py`
- Test: `tests/backend/test_account_repository.py`
- Test: `tests/backend/test_account_routes.py`
- Test: `tests/backend/test_login_task_flow.py`
- Test: `tests/backend/test_login_conflict_flow.py`
- Test: `tests/backend/test_account_domain.py`

- [ ] **Step 1: Write failing backend tests for account proxy split**

Cover:
- repository round-trips:
  - `account_proxy_mode`
  - `account_proxy_url`
  - `api_proxy_mode`
  - `api_proxy_url`
- create/update routes accept both proxy groups
- old rows with only legacy `proxy_mode/proxy_url` migrate to:
  - `account_proxy_* = legacy`
  - `api_proxy_* = legacy`
- login task uses `account_proxy_url` rather than legacy `proxy_url`
- login conflict resolution creates replacement accounts with the new dual-proxy arguments

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_account_table_bootstrap.py" `
  "tests/backend/test_account_repository.py" `
  "tests/backend/test_account_routes.py" `
  "tests/backend/test_login_task_flow.py" `
  "tests/backend/test_login_conflict_flow.py" `
  "tests/backend/test_account_domain.py" -q
```

Expected: FAIL because account model and schema still expose only `proxy_mode/proxy_url`

- [ ] **Step 2: Add the four new account fields without removing legacy columns in the same commit**

Requirements:
- runtime truth becomes the new fields immediately
- legacy columns may remain in DB during transition, but app code must stop reading them as truth
- migration in `db/base.py` must backfill new columns from legacy values when missing

- [ ] **Step 3: Update create/update use cases and route schemas**

Rules:
- if API proxy is omitted, use account proxy as the saved default
- keep existing proxy normalization logic
- do not invent a temporary runtime-only fallback
- update `login_task.py` to pass `account_proxy_url` into the login adapter
- update `resolve_login_conflict.py` so replacement account creation uses the new proxy argument names

- [ ] **Step 4: Re-run account tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_account_table_bootstrap.py" `
  "tests/backend/test_account_repository.py" `
  "tests/backend/test_account_routes.py" `
  "tests/backend/test_login_task_flow.py" `
  "tests/backend/test_login_conflict_flow.py" `
  "tests/backend/test_account_domain.py" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_backend/domain/models/account.py app_backend/infrastructure/repositories/account_repository.py app_backend/infrastructure/db/models.py app_backend/infrastructure/db/base.py app_backend/api/schemas/accounts.py app_backend/api/schemas/account_center.py app_backend/api/routes/accounts.py app_backend/workers/tasks/login_task.py app_backend/application/use_cases/resolve_login_conflict.py app_backend/application/use_cases/create_account.py app_backend/application/use_cases/update_account.py tests/backend/test_account_table_bootstrap.py tests/backend/test_account_repository.py tests/backend/test_account_routes.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py tests/backend/test_account_domain.py
git commit -m "feat: split account and api proxy fields"
```

### Task 4: Cut runtime sessions over to the correct proxy source

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/runtime_account_adapter.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Test: `tests/backend/test_account_center_routes.py`
- Test: `tests/backend/test_account_center_smoke.py`
- Test: `tests/backend/test_runtime_account_adapter.py`
- Test: `tests/backend/test_purchase_runtime_service.py`
- Test: `tests/backend/test_query_purchase_bridge.py`

- [ ] **Step 1: Write failing tests for session proxy routing**

Cover:
- `get_global_session()` uses account proxy
- `get_api_session()` uses API proxy
- purchase runtime status payload exposes the account proxy display, not the API proxy
- account center list/detail payload exposes the new proxy truth without leaking API proxy into purchase-facing proxy display
- purchase/query bridge still works after the account model changes

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_account_center_routes.py" `
  "tests/backend/test_account_center_smoke.py" `
  "tests/backend/test_runtime_account_adapter.py" `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_query_purchase_bridge.py" -q
```

Expected: FAIL because both sessions still share one proxy field

- [ ] **Step 2: Update `RuntimeAccountAdapter` to expose two explicit proxy getters**

Suggested split:
- `get_account_proxy_url()`
- `get_api_proxy_url()`

And then route:
- `get_global_session()` -> account proxy
- `get_api_session()` -> API proxy

- [ ] **Step 3: Update purchase runtime/account center read models to display account proxy only**

Do not leak API proxy into purchase runtime bucket identity or status labels.

- [ ] **Step 4: Re-run proxy routing tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_account_center_routes.py" `
  "tests/backend/test_account_center_smoke.py" `
  "tests/backend/test_runtime_account_adapter.py" `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_query_purchase_bridge.py" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_backend/infrastructure/query/runtime/runtime_account_adapter.py app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py tests/backend/test_account_center_routes.py tests/backend/test_account_center_smoke.py tests/backend/test_runtime_account_adapter.py tests/backend/test_purchase_runtime_service.py tests/backend/test_query_purchase_bridge.py
git commit -m "feat: route runtime sessions through split proxies"
```

## Chunk 3: Competition Planner And Bucket Fanout

### Task 5: Add proxy-bucket normalization and planner unit tests

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/proxy_bucket.py`
- Create: `app_backend/infrastructure/purchase/runtime/competition_planner.py`
- Test: `tests/backend/test_purchase_scheduler.py`
- Test: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: Write failing tests for bucket identity normalization**

Cover:
- direct connection normalizes to `direct`
- case-only hostname differences collapse to one bucket
- same scheme/host/port/username collapses to one bucket
- password changes do not affect the bucket key
- different usernames produce different bucket keys
- different hostnames are not merged, even if they might resolve to the same IP outside the program

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_purchase_runtime_service.py" -q
```

Expected: FAIL because no bucket helper exists

- [ ] **Step 2: Write failing planner tests**

Cover:
- planner returns at most `concurrency_limit` accounts per bucket
- planner only uses currently ready accounts
- planner does not backfill with busy accounts
- planner can fan out to multiple buckets in one hit
- planner returns a full `CompetitionPlan` carrying:
  - `competition_id`
  - `batch`
  - `candidate_account_ids`
- when a bucket has no saved limit, planner behaves as if `concurrency_limit = 1`

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_purchase_scheduler.py" -q
```

Expected: FAIL because no planner contract exists

- [ ] **Step 3: Implement `proxy_bucket.py`**

Required exports:
- `normalize_proxy_bucket_key(proxy_mode, proxy_url)`
- `build_bucket_display_name(proxy_mode, proxy_url)`

Do not do DNS resolution.

- [ ] **Step 4: Implement `competition_planner.py` as a pure planner**

Required inputs:
- batch
- ready account ids
- `account_id -> bucket_key`
- `bucket_key -> concurrency_limit`

Required output:
- `competition_id`
- `batch`
- `candidate_account_ids`

- [ ] **Step 5: Re-run planner and bucket tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_purchase_scheduler.py" `
  "tests/backend/test_purchase_runtime_service.py" -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_backend/infrastructure/purchase/runtime/proxy_bucket.py app_backend/infrastructure/purchase/runtime/competition_planner.py tests/backend/test_purchase_scheduler.py tests/backend/test_purchase_runtime_service.py
git commit -m "feat: add purchase competition planner"
```

### Task 6: Extend scheduler/runtime to claim planned accounts and execute bucket fanout

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_hit_inbox.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/application/use_cases/get_purchase_runtime_status.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Test: `tests/backend/test_purchase_scheduler.py`
- Test: `tests/backend/test_purchase_runtime_service.py`
- Test: `tests/backend/test_purchase_runtime_routes.py`

- [ ] **Step 1: Write failing tests for the planner-to-scheduler contract**

Cover:
- scheduler accepts a planned candidate list and atomically claims only accounts still ready
- claimed accounts transition to busy
- accounts that turned non-ready between snapshot and claim are dropped
- no replacement account is selected after a claim miss
- `claim_planned_accounts(plan)` returns `PurchaseDispatch[]`
- each dispatch preserves:
  - `competition_id`
  - `bucket_key`
  - `batch`
  - `account_id`

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_purchase_scheduler.py" `
  "tests/backend/test_purchase_runtime_service.py" -q
```

Expected: FAIL because scheduler only supports one-batch/one-account dispatch

- [ ] **Step 2: Write failing integration tests for competition fanout in purchase runtime**

Cover:
- one hit can launch multiple account executions
- one bucket with limit `1` dispatches only one account
- one bucket with limit `2` can dispatch two ready accounts
- one unseen bucket with no saved config defaults to exactly one dispatch
- updating saved `purchase_settings_json.ip_bucket_limits` affects the next hit without restarting runtime
- purchase runtime snapshot includes purchase bucket settings / bucket rows needed by the new UI

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_purchase_runtime_routes.py" -q
```

Expected: FAIL because runtime still queues only one dispatch per hit

- [ ] **Step 3: Add explicit dispatch objects and planned-claim methods**

Suggested changes:
- extend `runtime_events.py` with `CompetitionPlan` / `PurchaseDispatch`
- add `claim_planned_accounts(...)` to `PurchaseScheduler`
- keep existing ready/busy lifecycle logic centralized in scheduler

- [ ] **Step 4: Update `PurchaseRuntimeService.accept_query_hit_async()` to use planner + planned claims**

Requirements:
- fast dedupe stays where it is
- if no ready accounts exist, behavior remains `ignored_no_available_accounts`
- stats enqueue stays unchanged
- no waiting for busy accounts
- no extra slow queue for the same hit
- purchase bucket limits are re-read from persisted `purchase_settings_json` on the next hit after save
- changing a saved limit must not require runtime restart

- [ ] **Step 5: Extend purchase runtime status payload for the settings UI**

Add read-model fields for:
- `purchase_settings`
- `bucket_rows`
  - `bucket_key`
  - `display_name`
  - `configured_concurrency_limit`
  - `ready_account_count`
  - `available_account_count`

Freeze `purchase_settings` to mirror persisted shape:

```json
{
  "ip_bucket_limits": {
    "direct": {
      "concurrency_limit": 1
    }
  }
}
```

- [ ] **Step 6: Re-run scheduler/runtime/route tests**

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_purchase_scheduler.py" `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_purchase_runtime_routes.py" -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app_backend/infrastructure/purchase/runtime/runtime_events.py app_backend/infrastructure/purchase/runtime/purchase_scheduler.py app_backend/infrastructure/purchase/runtime/purchase_hit_inbox.py app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py app_backend/application/use_cases/get_purchase_runtime_status.py app_backend/api/schemas/purchase_runtime.py tests/backend/test_purchase_scheduler.py tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py
git commit -m "feat: add bucket-based purchase competition fanout"
```

## Chunk 4: Frontend Account And Purchase Settings UI

### Task 7: Update account dialogs/client for dual proxy editing

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/account-center/dialogs/account_create_dialog.jsx`
- Modify: `app_desktop_web/src/features/account-center/dialogs/account_proxy_dialog.jsx`
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Test: `app_desktop_web/tests/renderer/account_center_client.test.js`
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] **Step 1: Write failing frontend tests for dual proxy payloads**

Cover:
- create account request sends both account and API proxy fields
- editing proxy dialog can preserve account proxy while overriding API proxy
- leaving API proxy blank uses account proxy by default in the submitted payload

Run:

```powershell
& "C:/Program Files/nodejs/node.exe" ".\node_modules\vitest\vitest.mjs" run `
  "app_desktop_web/tests/renderer/account_center_client.test.js" `
  "app_desktop_web/tests/renderer/account_center_page.test.jsx"
```

Expected: FAIL because frontend still only submits one proxy group

- [ ] **Step 2: Expand client request helpers and account dialogs**

Requirements:
- keep current proxy normalization UX
- surface two labeled sections:
  - `账户代理`
  - `API 代理`
- avoid editing unrelated account fields in the same change

- [ ] **Step 3: Re-run frontend account tests**

Run:

```powershell
& "C:/Program Files/nodejs/node.exe" ".\node_modules\vitest\vitest.mjs" run `
  "app_desktop_web/tests/renderer/account_center_client.test.js" `
  "app_desktop_web/tests/renderer/account_center_page.test.jsx"
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app_desktop_web/src/api/account_center_client.js app_desktop_web/src/features/account-center/dialogs/account_create_dialog.jsx app_desktop_web/src/features/account-center/dialogs/account_proxy_dialog.jsx app_desktop_web/src/features/account-center/hooks/use_account_center_page.js app_desktop_web/tests/renderer/account_center_client.test.js app_desktop_web/tests/renderer/account_center_page.test.jsx
git commit -m "feat: support split proxy editing in account ui"
```

### Task 8: Rebuild left-side purchase/query settings on the purchase page

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_settings_panel.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/query_settings_panel.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: Write failing frontend tests for runtime settings fetch/save and left-side panel rendering**

Cover:
- purchase page loads `GET /runtime-settings`
- left side renders `购买设置` and `查询设置` as separate blocks
- `购买设置` shows bucket rows with default `1`
- `查询设置` shows three modes and item pacing controls
- invalid save input blocks submission before request dispatch
- saving `查询设置` preserves the current selected config and does not clear the active runtime config state
- saving `购买设置` preserves the current selected config and leaves the running runtime state intact except for the next-hit bucket limit hot-apply
- when both runtime settings and legacy `QueryConfig.mode_settings` exist, the panel renders values from `runtime_settings.query_settings_json`
- the old per-account checkbox semantics are gone:
  - no account-enable checkbox rows
  - no `purchase_disabled` toggles inside the bucket panel

Run:

```powershell
& "C:/Program Files/nodejs/node.exe" ".\node_modules\vitest\vitest.mjs" run `
  "app_desktop_web/tests/renderer/purchase_system_client.test.js" `
  "app_desktop_web/tests/renderer/purchase_system_page.test.jsx"
```

Expected: FAIL because purchase page has no runtime settings client or left settings layout

- [ ] **Step 2: Add client methods for runtime settings**

Required methods:
- `getRuntimeSettings()`
- `updateQueryRuntimeSettings(payload)`
- `updatePurchaseRuntimeSettings(payload)`

- [ ] **Step 3: Replace the existing purchase settings panel semantics**

Current `purchase_settings_panel.jsx` is an account checkbox panel.

Refactor it into the new bucket-based panel:
- remove account enable/disable semantics from this component
- render bucket rows
- allow integer editing of `concurrency_limit`

Do not move `purchase_disabled` into this panel.

Add explicit negative assertions in the tests that this panel does not render:
- per-account checkboxes
- warehouse selection controls
- account capability toggles

- [ ] **Step 4: Create `query_settings_panel.jsx` for global query settings**

Render:
- `new_api`, `fast_api`, `token`
- cooldown min/max
- random delay toggles/ranges
- window settings
- item pacing strategy / fixed seconds

Validation rules must match backend minima.

- [ ] **Step 5: Update purchase page hook and page layout**

Requirements:
- left column loads and saves runtime settings
- right column keeps current item list and runtime actions
- saving query settings does not clear selected config
- saving purchase settings does not disturb running runtime state beyond hot-applying limits

- [ ] **Step 6: Re-run purchase page frontend tests**

Run:

```powershell
& "C:/Program Files/nodejs/node.exe" ".\node_modules\vitest\vitest.mjs" run `
  "app_desktop_web/tests/renderer/purchase_system_client.test.js" `
  "app_desktop_web/tests/renderer/purchase_system_page.test.jsx"
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app_desktop_web/src/api/account_center_client.js app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/features/purchase-system/components/purchase_settings_panel.jsx app_desktop_web/src/features/purchase-system/components/query_settings_panel.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/purchase_system_client.test.js app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat: add runtime settings panels to purchase page"
```

## Final Verification

- [ ] **Step 1: Run targeted backend suite for settings, account proxies, query cutover, and purchase competition**

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_runtime_settings_repository.py" `
  "tests/backend/test_runtime_settings_routes.py" `
  "tests/backend/test_account_repository.py" `
  "tests/backend/test_account_routes.py" `
  "tests/backend/test_runtime_account_adapter.py" `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" `
  "tests/backend/test_purchase_scheduler.py" `
  "tests/backend/test_purchase_runtime_service.py" `
  "tests/backend/test_purchase_runtime_routes.py" `
  "tests/backend/test_query_purchase_bridge.py" -q
```

Expected:
- PASS
- no regressions in query runtime start/stop
- no regressions in purchase runtime status schema

- [ ] **Step 2: Run targeted frontend suite for account and purchase page flows**

```powershell
& "C:/Program Files/nodejs/node.exe" ".\node_modules\vitest\vitest.mjs" run `
  "app_desktop_web/tests/renderer/account_center_client.test.js" `
  "app_desktop_web/tests/renderer/account_center_page.test.jsx" `
  "app_desktop_web/tests/renderer/purchase_system_client.test.js" `
  "app_desktop_web/tests/renderer/purchase_system_page.test.jsx"
```

Expected:
- PASS
- account dialogs can submit split proxies
- purchase page renders bucket/query settings and preserves the current selected config

- [ ] **Step 3: Manual smoke test**

1. Start the desktop web app.
2. Open account center and create/edit an account with:
   - one account proxy
   - one different API proxy
3. Open the purchase page and verify the left side shows:
   - `购买设置`
   - `查询设置`
4. Save one bucket limit as `2`, refresh the page, verify it persists.
5. Start query + purchase runtime with at least two ready accounts under the same account proxy bucket.
6. Trigger a known hit and verify:
   - runtime status shows multiple attempts for that hit
   - item-level matched count is not inflated
   - account success/failure counts reflect actual attempts

- [ ] **Step 4: Final commit**

```bash
git status --short
git add docs/superpowers/plans/2026-03-23-purchase-competition-and-proxy-split-implementation.md
git commit -m "docs(plan): add purchase competition implementation plan"
```
