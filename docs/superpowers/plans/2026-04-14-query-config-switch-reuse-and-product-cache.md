# Query Config Switch Reuse and Product Cache Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse already-loaded query config detail on in-page config switches, gate same-page config switches behind the existing unsaved-changes flow, and persist product detail into the shared product cache as soon as lookup succeeds in the add-item dialog.

**Architecture:** Keep the current single active query-config draft model. Extend the frontend `querySystem.server.configs` cache so once a config has been loaded as detail it can be reused without another `getQueryConfig` call, and thread the existing leave-confirmation callbacks through config navigation so same-page switches obey the same save/discard behavior as page exits. On the backend, make the explicit `/query-items/fetch-detail` success path upsert the shared `query_products` cache, then leave config-item creation semantics unchanged so duplicate items in one config remain valid.

**Tech Stack:** React 19, Testing Library, Vitest, FastAPI, SQLAlchemy, pytest

---

## File Structure

- `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
  - Add renderer regressions proving already-loaded configs reuse cached detail, same-page config switches invoke the existing unsaved-changes flow, and switching only continues after save/discard resolution.
- `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
  - Teach config selection to reuse detailed configs from `queryServer.configs`, expose same-page switch requests through the page-level leave-state contract, and keep the single `currentConfig` draft semantics intact.
- `app_desktop_web/src/features/query-system/query_system_page.jsx`
  - Bridge config-nav clicks into the existing `onLeaveStateChange` save/discard/cancel pathway instead of switching immediately when the current config is dirty.
- `app_desktop_web/src/features/query-system/components/query_config_nav.jsx`
  - Keep the nav dumb: forward selection intent and never own unsaved logic.
- `tests/backend/test_query_config_routes.py`
  - Add backend regression coverage showing `fetch-detail` writes the shared product cache and does not create a config item.
- `app_backend/application/use_cases/fetch_query_item_detail.py`
  - Extend the use case to optionally upsert product cache records after a successful detail fetch.
- `app_backend/api/routes/query_items.py`
  - Wire the product-cache persistence dependency into `/query-items/fetch-detail`.
- `app_backend/infrastructure/repositories/query_config_repository.py`
  - Reuse the existing `upsert_product` API for lookup-time product caching, without adding any config-level uniqueness rule.

## Chunk 1: Frontend Query Config Switching

### Task 1: Add failing renderer coverage for config-detail reuse and same-page switch confirmation

**Files:**
- Modify: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
- Test: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`

- [ ] **Step 1: Write a failing test for reusing already-loaded config detail**

Add a focused test that:
- boots two configs into the nav,
- clicks the second config once and confirms one `GET /query-configs/<id>` detail request,
- switches back to the first config and then back to the second config,
- asserts the second switch reuses cached detail instead of issuing a second detail request for the already-loaded config,
- asserts the UI does not fall back to the repeated `正在加载配置...` state when the detail is already cached in-session.

- [ ] **Step 2: Run the focused renderer test to verify RED**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx`

Expected: FAIL because `selectConfig` currently always calls `loadConfigDetail(configId)` and the harness sees duplicate `GET /query-configs/<id>` requests.

- [ ] **Step 3: Write a failing test for same-page config switches using the existing unsaved-changes flow**

Add a second focused test that:
- edits the current config so the page becomes dirty,
- clicks another config in the left nav,
- asserts the existing `未保存修改` dialog appears before switching,
- verifies `取消` keeps the original config selected,
- verifies `不保存` switches without calling save,
- verifies `保存` calls the existing page save path before the switch completes.

- [ ] **Step 4: Re-run the focused renderer test to keep RED**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx`

Expected: FAIL because nav clicks bypass the leave-state flow today.

### Task 2: Reuse already-loaded config detail inside the query-system hook

**Files:**
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Test: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`

- [ ] **Step 1: Implement a detail-reuse branch before requesting config detail**

Update the config-load path so that:
- summary-only configs still trigger `client.getQueryConfig(configId)`,
- configs already marked with `serverShape === "detail"` are reused directly,
- reusing detail still updates `selectedConfigId`, `currentConfig`, and transient editor state exactly like a freshly loaded detail response,
- cached-detail reuse never toggles the page back into a visible loading state.

- [ ] **Step 2: Keep the single-draft model intact**

Do not introduce per-config drafts. Continue storing only one editable `currentConfig`, but make `applyDraftFromConfig(...)` accept a cached detailed config from `queryServer.configs` so switching can avoid a round-trip.

- [ ] **Step 3: Keep `server.configs` coherent after save and discard**

Explicitly preserve the existing “save success refreshes the corresponding config detail” behavior, and verify discard returns the draft to the currently cached server copy so later detail reuse does not surface stale data.

- [ ] **Step 4: Re-run the focused renderer test to verify GREEN for detail reuse**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx`

Expected: PASS for the detail-reuse assertions, with any remaining failures limited to same-page unsaved switch behavior.

### Task 3: Route same-page config switches through the existing leave-confirmation contract

**Files:**
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Modify: `app_desktop_web/src/features/query-system/components/query_config_nav.jsx`
- Test: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`

- [ ] **Step 1: Add a pending-config-switch flow that reuses the page leave callbacks**

Implement a page-level switch request flow that:
- captures the target config id when a nav click happens,
- if the current config is clean, switches immediately,
- if the current config is dirty, opens the existing `UnsavedChangesDialog` using the same save/discard handlers already used for page exits,
- continues the pending switch only after save/discard succeeds,
- clears the pending target on save failure.

- [ ] **Step 2: Keep config navigation presentation-only**

`QueryConfigNav` should continue emitting “user intends to switch to config X” and should not gain local save/discard logic. The page owns the unsaved state and the confirmation dialog.

- [ ] **Step 3: Re-run the focused renderer test to verify GREEN**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx`

Expected: PASS.

- [ ] **Step 4: Run adjacent frontend regressions**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_page.test.jsx`

Expected: PASS.

## Chunk 2: Backend Product Cache Persistence on Lookup

### Task 4: Add failing backend coverage for lookup-time product-cache persistence

**Files:**
- Modify: `tests/backend/test_query_config_routes.py`
- Test: `tests/backend/test_query_config_routes.py`

- [ ] **Step 1: Write a failing route test for `/query-items/fetch-detail` persisting the product cache**

Add a test that:
- replaces `app.state.product_detail_collector` with a fake collector,
- calls `POST /query-items/fetch-detail`,
- then checks `app.state.query_config_repository.get_product(external_item_id)` returns a cached product with the fetched name, market hash name, wear range, price, and normalized product URL.

- [ ] **Step 2: Add a failing test for cache-upsert failure semantics**

Add a second test that forces the product-cache upsert path to fail after detail collection succeeds, then asserts:
- the route returns an error instead of a success payload,
- the frontend-facing contract would treat the lookup as failed,
- no partial “cache succeeded” state is left behind.

- [ ] **Step 3: Assert lookup-time persistence does not create a config item**

In the same test, or a neighboring one, assert no config item was created as a side effect. The lookup is cache-only until the user actually adds and saves a config item.

- [ ] **Step 4: Run the targeted backend test to verify RED**

Run from repo root: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_routes.py -q`

Expected: FAIL because `/query-items/fetch-detail` currently returns the payload without upserting `query_products`.

### Task 5: Persist successful lookup results into the shared product cache

**Files:**
- Modify: `app_backend/application/use_cases/fetch_query_item_detail.py`
- Modify: `app_backend/api/routes/query_items.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_query_config_routes.py`

- [ ] **Step 1: Inject the query-config repository into the fetch-detail flow**

Extend the fetch-detail use case or route wiring so a successful collector result can call the existing repository `upsert_product(...)` method with:
- `external_item_id`
- `product_url`
- `item_name`
- `market_hash_name`
- `min_wear`
- `max_wear`
- `last_market_price`
- `last_detail_sync_at`

- [ ] **Step 2: Preserve current API response semantics**

The route must still return the fetched detail payload. This change is additive: cache the product and then respond with the same shape the frontend already consumes.

- [ ] **Step 3: Surface cache-upsert failures as lookup failures**

If detail collection succeeds but the product-cache upsert fails, do not return a success payload. Propagate the failure through the route so the frontend keeps the lookup in an error state and does not act as if the product was successfully remembered.

- [ ] **Step 4: Re-run the targeted backend test to verify GREEN**

Run from repo root: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_routes.py -q`

Expected: PASS.

- [ ] **Step 5: Re-run adjacent backend regressions**

Run from repo root: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_item_collectors.py tests/backend/test_query_config_routes.py -q`

Expected: PASS.

## Chunk 3: End-to-End Verification

### Task 6: Verify the full slice before claiming completion

**Files:**
- Verify only

- [ ] **Step 1: Run frontend query-system regressions**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_page.test.jsx`

Expected: PASS.

- [ ] **Step 2: Run backend query-config regressions**

Run from repo root: `./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_routes.py tests/backend/test_query_item_collectors.py -q`

Expected: PASS.

- [ ] **Step 3: Run the combined focused slice**

Run from repo root:
`./.venv/Scripts/python.exe -m pytest tests/backend/test_query_config_routes.py tests/backend/test_query_item_collectors.py -q`

Then run from `app_desktop_web/`:
`npm test -- tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_page.test.jsx`

Expected: both command groups PASS with no new failures.

- [ ] **Step 4: Manual sanity-check requirements against the spec**

Confirm the implementation still satisfies:
- loaded config detail is reused in-page,
- same-page config switches reuse the existing unsaved-changes dialog flow,
- lookup success persists shared product cache only,
- duplicate items inside one config remain allowed.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-14-query-config-switch-reuse-and-product-cache.md`. Ready to execute?
