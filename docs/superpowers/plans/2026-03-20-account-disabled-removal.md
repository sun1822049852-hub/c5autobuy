# Account Disabled Removal Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the legacy account-level `disabled` field end-to-end so query flows only use per-queryer flags and purchase flows only use `purchase_disabled`, without breaking current runtime behavior.

**Architecture:** This is a semantic cutover, not a compatibility migration. We first delete `disabled` from runtime eligibility and API contracts, then remove it from domain/repository/frontend compatibility layers, and finally remove the SQLite column through schema bootstrap migration logic plus regression verification.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy + SQLite, PySide6 compatibility UI, React/Vite desktop web, pytest, vitest

---

## Chunk 1: Runtime Eligibility And API Contract Cleanup

### Task 1: Remove `disabled` from query and purchase runtime decisions

**Files:**
- Modify: `app_backend/application/services/query_mode_capacity_service.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/collectors/detail_account_selector.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Test: `tests/backend/test_query_mode_capacity_service.py`
- Test: `tests/backend/test_mode_execution_runner.py`
- Test: `tests/backend/test_detail_account_selector.py`
- Test: `tests/backend/test_purchase_runtime_service.py`
- Test: `tests/backend/test_query_config_routes.py`
- Test: `tests/backend/test_query_runtime_service.py`

- [ ] **Step 1: Write or update failing tests so `disabled` no longer affects eligibility**

```python
def test_query_mode_capacity_service_counts_accounts_without_global_disabled_gate():
    summary = service.get_summary()
    assert summary["modes"]["new_api"]["available_account_count"] == 3


def test_mode_runner_keeps_purchase_disabled_account_query_eligible():
    snapshot = runner.snapshot()
    assert snapshot["eligible_account_count"] == 2


def test_detail_account_selector_ignores_removed_disabled_flag():
    assert [account.account_id for account in selector.build_attempt_order()] == ["a2", "a3", "a4"]
```

- [ ] **Step 2: Run focused backend tests and confirm they fail for legacy `disabled` assumptions**

Run: `pytest tests/backend/test_query_mode_capacity_service.py tests/backend/test_mode_execution_runner.py tests/backend/test_detail_account_selector.py tests/backend/test_purchase_runtime_service.py -q`

Expected: failing assertions or constructor errors still tied to `disabled`

- [ ] **Step 3: Implement the minimal runtime changes**

```python
# query_mode_capacity_service.py
for account in self._account_repository.list_accounts():
    if bool(getattr(account, "api_key", None)) and bool(getattr(account, "new_api_enabled", False)):
        counts[QueryMode.NEW_API] += 1


# mode_runner.py
def _is_eligible_account(self, account: object) -> bool:
    if mode_type == "new_api":
        return bool(getattr(account, "new_api_enabled", False)) and bool(getattr(account, "api_key", None))


# detail_account_selector.py
def _is_eligible(account: object) -> bool:
    cookie_raw = getattr(account, "cookie_raw", None) or ""
    ...
```

- [ ] **Step 4: Remove `disabled` from purchase runtime snapshots and purchase eligibility**

```python
normalized.append(
    {
        "account_id": str(raw_account.get("account_id") or ""),
        "purchase_disabled": bool(raw_account.get("purchase_disabled", False)),
        # no "disabled" key
    }
)
```

- [ ] **Step 5: Re-run focused backend tests**

Run: `pytest tests/backend/test_query_mode_capacity_service.py tests/backend/test_mode_execution_runner.py tests/backend/test_detail_account_selector.py tests/backend/test_purchase_runtime_service.py tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_service.py -q`

Expected: PASS

- [ ] **Step 6: Commit chunk 1**

```bash
git add app_backend/application/services/query_mode_capacity_service.py app_backend/infrastructure/query/runtime/mode_runner.py app_backend/infrastructure/query/collectors/detail_account_selector.py app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py tests/backend/test_query_mode_capacity_service.py tests/backend/test_mode_execution_runner.py tests/backend/test_detail_account_selector.py tests/backend/test_purchase_runtime_service.py tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_service.py
git commit -m "refactor: remove disabled from runtime eligibility"
```

### Task 2: Remove `disabled` from API schemas and request compatibility

**Files:**
- Modify: `app_backend/api/schemas/accounts.py`
- Modify: `app_backend/api/schemas/account_center.py`
- Test: `tests/backend/test_account_center_routes.py`
- Test: `tests/backend/test_purchase_runtime_routes.py`
- Test: `tests/frontend/test_backend_client.py`

- [ ] **Step 1: Write or update failing tests for the public contract**

```python
async def test_update_purchase_config_route_rejects_legacy_disabled_field(client, app):
    response = await client.patch(
        "/accounts/config-target/purchase-config",
        json={"disabled": True, "selected_steam_id": "steam-2"},
    )
    assert response.status_code == 422


async def test_account_center_accounts_route_does_not_return_disabled_field(client, app):
    payload = (await client.get("/account-center/accounts")).json()
    assert "disabled" not in payload[0]
```

- [ ] **Step 2: Run API/contract tests and confirm failure**

Run: `pytest tests/backend/test_account_center_routes.py tests/backend/test_purchase_runtime_routes.py tests/frontend/test_backend_client.py -q`

Expected: FAIL because schemas still expose or accept `disabled`

- [ ] **Step 3: Implement strict schema cleanup**

```python
class AccountCenterAccountResponse(BaseModel):
    purchase_disabled: bool
    # no disabled


class AccountPurchaseConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase_disabled: bool = False
    selected_steam_id: str | None = None
```

- [ ] **Step 4: Re-run API/contract tests**

Run: `pytest tests/backend/test_account_center_routes.py tests/backend/test_purchase_runtime_routes.py tests/frontend/test_backend_client.py -q`

Expected: PASS

- [ ] **Step 5: Commit chunk 1 API contract cleanup**

```bash
git add app_backend/api/schemas/accounts.py app_backend/api/schemas/account_center.py tests/backend/test_account_center_routes.py tests/backend/test_purchase_runtime_routes.py tests/frontend/test_backend_client.py
git commit -m "refactor: drop disabled from account api contract"
```

## Chunk 2: Domain, Repository, Python UI Compatibility Layer, And Web Test Fixtures

### Task 3: Remove `disabled` from domain model, account creation, and repository mapping

**Files:**
- Modify: `app_backend/domain/models/account.py`
- Modify: `app_backend/application/use_cases/create_account.py`
- Modify: `app_backend/infrastructure/repositories/account_repository.py`
- Test: `tests/backend/test_account_domain.py`
- Test: `tests/backend/test_account_repository.py`
- Test: `tests/backend/test_account_query_mode_settings.py`
- Test: `tests/backend/test_account_query_worker.py`
- Test: `tests/backend/test_account_purchase_worker_runtime.py`
- Test: `tests/backend/test_fast_api_query_executor.py`
- Test: `tests/backend/test_inventory_refresh_gateway.py`
- Test: `tests/backend/test_legacy_scanner_real_integration.py`
- Test: `tests/backend/test_new_api_query_executor.py`
- Test: `tests/backend/test_product_detail_fetcher.py`
- Test: `tests/backend/test_purchase_execution_gateway.py`
- Test: `tests/backend/test_query_executor_router.py`
- Test: `tests/backend/test_query_runtime_routes.py`
- Test: `tests/backend/test_query_runtime_service.py`
- Test: `tests/backend/test_token_query_executor.py`

- [ ] **Step 1: Update constructors/fixtures to remove `disabled`**

```python
account = Account(
    account_id="a1",
    ...,
    updated_at="2026-03-20T00:00:00",
    purchase_disabled=False,
    new_api_enabled=True,
    fast_api_enabled=True,
    token_enabled=True,
)
```

- [ ] **Step 2: Run focused backend tests to surface constructor and repository breakage**

Run: `pytest tests/backend/test_account_domain.py tests/backend/test_account_repository.py tests/backend/test_account_query_mode_settings.py tests/backend/test_account_query_worker.py tests/backend/test_account_purchase_worker_runtime.py -q`

Expected: FAIL on removed dataclass field or repository mapping

- [ ] **Step 3: Implement minimal domain/repository cleanup**

```python
@dataclass(slots=True)
class Account:
    ...
    updated_at: str
    purchase_disabled: bool = False


row = AccountRecord(
    ...,
    updated_at=account.updated_at,
    purchase_disabled=int(account.purchase_disabled),
)
```

- [ ] **Step 4: Re-run focused backend tests**

Run: `pytest tests/backend/test_account_domain.py tests/backend/test_account_repository.py tests/backend/test_account_query_mode_settings.py tests/backend/test_account_query_worker.py tests/backend/test_account_purchase_worker_runtime.py tests/backend/test_fast_api_query_executor.py tests/backend/test_inventory_refresh_gateway.py tests/backend/test_legacy_scanner_real_integration.py tests/backend/test_new_api_query_executor.py tests/backend/test_product_detail_fetcher.py tests/backend/test_purchase_execution_gateway.py tests/backend/test_query_executor_router.py tests/backend/test_query_runtime_routes.py tests/backend/test_query_runtime_service.py tests/backend/test_token_query_executor.py -q`

Expected: PASS

- [ ] **Step 5: Commit domain/repository cleanup**

```bash
git add app_backend/domain/models/account.py app_backend/application/use_cases/create_account.py app_backend/infrastructure/repositories/account_repository.py tests/backend/test_account_domain.py tests/backend/test_account_repository.py tests/backend/test_account_query_mode_settings.py tests/backend/test_account_query_worker.py tests/backend/test_account_purchase_worker_runtime.py tests/backend/test_fast_api_query_executor.py tests/backend/test_inventory_refresh_gateway.py tests/backend/test_legacy_scanner_real_integration.py tests/backend/test_new_api_query_executor.py tests/backend/test_product_detail_fetcher.py tests/backend/test_purchase_execution_gateway.py tests/backend/test_query_executor_router.py tests/backend/test_query_runtime_routes.py tests/backend/test_query_runtime_service.py tests/backend/test_token_query_executor.py
git commit -m "refactor: remove disabled from account domain model"
```

### Task 4: Remove `disabled` from Python UI compatibility layer and desktop web fixtures

**Files:**
- Modify: `app_frontend/app/dialogs/purchase_config_dialog.py`
- Test: `tests/frontend/test_account_center_controller.py`
- Test: `tests/frontend/test_account_center_vm.py`
- Test: `tests/frontend/test_account_center_window_status.py`
- Test: `tests/frontend/test_account_dialogs.py`
- Test: `tests/frontend/test_account_detail_panel.py`
- Test: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`
- Test: `app_desktop_web/tests/renderer/login_drawer.test.jsx`
- Test: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: Update failing tests to send and expect only `purchase_disabled`**

```python
controller.update_account_purchase_config(
    "a-1",
    {
        "purchase_disabled": True,
        "selected_steam_id": "steam-2",
    },
)
```

```jsx
expect(harness.calls).toEqual(
  expect.arrayContaining([
    expect.objectContaining({
      body: { purchase_disabled: true, selected_steam_id: "steam-2" },
    }),
  ]),
);
```

- [ ] **Step 2: Run compatibility-layer tests and confirm failure**

Run: `pytest tests/frontend/test_account_center_controller.py tests/frontend/test_account_center_vm.py tests/frontend/test_account_center_window_status.py tests/frontend/test_account_dialogs.py tests/frontend/test_account_detail_panel.py -q`

Run: `npm --prefix app_desktop_web test -- account_center_editing.test.jsx login_drawer.test.jsx purchase_system_client.test.js purchase_system_page.test.jsx`

Expected: FAIL because fixtures or dialog payloads still mention `disabled`

- [ ] **Step 3: Implement minimal UI compatibility cleanup**

```python
self.disabled_checkbox.setChecked(bool(account.get("purchase_disabled", False)))

def build_payload(self) -> dict[str, str | bool | None]:
    return {
        "purchase_disabled": self.disabled_checkbox.isChecked(),
        "selected_steam_id": self._selected_available_steam_id(),
    }
```

- [ ] **Step 4: Re-run compatibility-layer tests**

Run: `pytest tests/frontend/test_account_center_controller.py tests/frontend/test_account_center_vm.py tests/frontend/test_account_center_window_status.py tests/frontend/test_account_dialogs.py tests/frontend/test_account_detail_panel.py -q`

Run: `npm --prefix app_desktop_web test -- account_center_editing.test.jsx login_drawer.test.jsx purchase_system_client.test.js purchase_system_page.test.jsx`

Expected: PASS

- [ ] **Step 5: Commit compatibility cleanup**

```bash
git add app_frontend/app/dialogs/purchase_config_dialog.py tests/frontend/test_account_center_controller.py tests/frontend/test_account_center_vm.py tests/frontend/test_account_center_window_status.py tests/frontend/test_account_dialogs.py tests/frontend/test_account_detail_panel.py app_desktop_web/tests/renderer/account_center_editing.test.jsx app_desktop_web/tests/renderer/login_drawer.test.jsx app_desktop_web/tests/renderer/purchase_system_client.test.js app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "refactor: remove disabled from purchase config clients"
```

## Chunk 3: SQLite Schema Removal And Final Regression Verification

### Task 5: Drop `accounts.disabled` from ORM and bootstrap migration

**Files:**
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Test: `tests/backend/test_account_table_bootstrap.py`
- Test: `tests/backend/test_account_repository.py`

- [ ] **Step 1: Write or update failing migration tests**

```python
def test_create_schema_removes_legacy_accounts_disabled_column(tmp_path):
    create_legacy_accounts_table_with_disabled(tmp_path)
    create_schema(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("accounts")}
    assert "disabled" not in columns
```

- [ ] **Step 2: Run schema tests and confirm failure**

Run: `pytest tests/backend/test_account_table_bootstrap.py tests/backend/test_account_repository.py -q`

Expected: FAIL because ORM/bootstrap still defines `disabled`

- [ ] **Step 3: Implement SQLite table rebuild migration**

```python
def _ensure_account_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_columns = {column["name"] for column in inspector.get_columns("accounts")}
    if "disabled" in existing_columns:
        _rebuild_accounts_table_without_disabled(engine)
```

```sql
CREATE TABLE accounts__new (... purchase_disabled INTEGER NOT NULL DEFAULT 0, ...);
INSERT INTO accounts__new (...) SELECT ... FROM accounts;
DROP TABLE accounts;
ALTER TABLE accounts__new RENAME TO accounts;
```

- [ ] **Step 4: Re-run schema tests**

Run: `pytest tests/backend/test_account_table_bootstrap.py tests/backend/test_account_repository.py -q`

Expected: PASS

- [ ] **Step 5: Commit schema cleanup**

```bash
git add app_backend/infrastructure/db/models.py app_backend/infrastructure/db/base.py tests/backend/test_account_table_bootstrap.py tests/backend/test_account_repository.py
git commit -m "refactor: drop disabled from sqlite accounts schema"
```

### Task 6: Run final regression suite and inspect workspace diff

**Files:**
- Verify only

- [ ] **Step 1: Run consolidated backend regression**

Run: `pytest tests/backend/test_account_center_routes.py tests/backend/test_account_domain.py tests/backend/test_account_query_mode_settings.py tests/backend/test_account_repository.py tests/backend/test_account_table_bootstrap.py tests/backend/test_detail_account_selector.py tests/backend/test_mode_execution_runner.py tests/backend/test_purchase_runtime_service.py tests/backend/test_query_config_routes.py tests/backend/test_query_mode_capacity_service.py tests/backend/test_query_runtime_service.py -q`

Expected: PASS

- [ ] **Step 2: Run consolidated frontend regression**

Run: `pytest tests/frontend/test_backend_client.py tests/frontend/test_account_center_controller.py tests/frontend/test_account_center_vm.py tests/frontend/test_account_center_window_status.py tests/frontend/test_account_dialogs.py tests/frontend/test_account_detail_panel.py -q`

Run: `npm --prefix app_desktop_web test -- account_center_editing.test.jsx login_drawer.test.jsx purchase_system_client.test.js purchase_system_page.test.jsx query_system_client.test.js`

Expected: PASS

- [ ] **Step 3: Inspect final diff and status**

Run: `git status --short`

Expected: only intended source/test/doc changes remain

- [ ] **Step 4: Optional final squash-or-keep decision**

```bash
git log --oneline -n 5
```

Expected: 3-5 clear atomic commits covering runtime, contract/client, and schema cleanup

