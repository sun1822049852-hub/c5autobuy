# Browser Query Enable Entitlement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require explicit program-access entitlement before turning on account-level browser query, and show a frontend dialog saying the feature is not open when permission is missing.

**Architecture:** Add a narrow backend guard only for the `browser_query_enabled=false -> true` path, backed by a dedicated entitlement key in cached/remote program-access gateways. Keep the frontend account-center toggle flow intact, but intercept that specific guard failure and render a local dialog instead of silently failing.

**Tech Stack:** FastAPI, Python domain/use-case layer, React, Vitest, pytest

---

## Chunk 1: Backend Guard Contract

### Task 1: Lock the route-level denial behavior with failing tests

**Files:**
- Modify: `tests/backend/test_account_routes.py`
- Modify: `tests/backend/test_remote_entitlement_gateway.py`
- Modify: `tests/backend/test_program_access_guard_routes.py`

- [ ] **Step 1: Write the failing backend tests**

Add tests for:
- enabling browser query without entitlement returns `403` with `program_feature_not_enabled`
- disabling browser query still succeeds
- remote entitlement gateway denies `account.browser_query.enable` when the specific permission/flag is absent
- remote entitlement gateway allows `account.browser_query.enable` when the specific permission/flag is present

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_account_routes.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_guard_routes.py -q
```

Expected: FAIL on the new entitlement assertions because the route currently allows browser-query enable without a dedicated guard.

- [ ] **Step 3: Write the minimal backend implementation**

Modify:
- `app_backend/api/routes/accounts.py`
- `app_backend/infrastructure/program_access/remote_entitlement_gateway.py`
- `app_backend/infrastructure/program_access/cached_program_access_gateway.py`

Implementation notes:
- only call the new guard when `browser_query_enabled is True`
- use action string `account.browser_query.enable`
- use message `当前此功能未开放`
- check `permissions=["account.browser_query.enable"]` or `feature_flags.account_browser_query_enable=true`

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_account_routes.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_guard_routes.py -q
```

Expected: PASS

## Chunk 2: Frontend Dialog Contract

### Task 2: Lock the account-center popup behavior with failing tests

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] **Step 1: Write the failing frontend tests**

Add tests for:
- clicking “切换浏览器查询” from disabled -> enabled and receiving `program_feature_not_enabled` for `account.browser_query.enable` opens a dialog with `当前此功能未开放`
- the existing disable flow still sends `{ browser_query_enabled: false, browser_query_disabled_reason: "manual_disabled" }`

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx tests/renderer/account_center_page.test.jsx --run
```

Expected: FAIL because the account-center page currently only logs the error and shows no dedicated popup.

- [ ] **Step 3: Write the minimal frontend implementation**

Modify:
- `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Create: `app_desktop_web/src/features/account-center/dialogs/feature_unavailable_dialog.jsx`

Implementation notes:
- parse the returned program-access error
- only show the popup for `program_feature_not_enabled` + `action=account.browser_query.enable`
- keep other errors on the existing logging path

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx tests/renderer/account_center_page.test.jsx --run
```

Expected: PASS

## Chunk 3: Focused Regression And Docs

### Task 3: Re-run affected verification and sync docs

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if this becomes a stable long-term product rule)

- [ ] **Step 1: Re-run focused regressions**

Run:

```bash
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_account_routes.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_guard_routes.py -q
npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx tests/renderer/account_center_page.test.jsx tests/renderer/program_access_provider.test.jsx --run
```

Expected: PASS

- [ ] **Step 2: Review README impact**

Check whether the new entitlement behavior changes user-facing setup or permission documentation. If not, leave `README.md` unchanged and note that it was checked.

- [ ] **Step 3: Update session log**

Append the new implementation + verification evidence to `docs/agent/session-log.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-04-24-browser-query-enable-entitlement-design.md docs/superpowers/plans/2026-04-24-browser-query-enable-entitlement.md app_backend app_desktop_web tests docs/agent
git commit -m "fix: gate browser query enable behind entitlement"
```
