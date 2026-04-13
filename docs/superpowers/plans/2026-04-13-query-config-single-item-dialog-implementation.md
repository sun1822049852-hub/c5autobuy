# Query Config Single-Item Dialog Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the query config item's single large editor with field-scoped centered dialogs plus an inline manual pause control, while keeping the existing page-level save button as the only action that makes changes take effect.

**Architecture:** Keep `currentConfig` as the only source of truth for draft edits. Replace the separate per-item `editItemDraft + applyEditItem` flow with an `editingContext` shaped as `queryItemId + kind + modeType?`, so dialog inputs write directly into the page draft and closing the dialog never rolls values back. Preserve the existing create-item flow and save pipeline, but update the row UI so `market_price` is read-only, the five editable targets open their own single-item dialogs, and the `token`-side control slot switches between inline `手动暂停` and delete mode.

**Tech Stack:** React 19, Testing Library, Vitest, CSS

---

## File Structure

- `app_desktop_web/tests/renderer/query_system_editing.test.jsx`: regression coverage for single-item dialogs, inline manual pause drafting, delete-slot replacement, and page-level save behavior.
- `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`: remove the old staged item editor state, add item-field dialog context, and expose direct draft mutation helpers.
- `app_desktop_web/src/features/query-system/query_system_page.jsx`: pass the new dialog context and direct draft mutation callbacks into the table and dialog components.
- `app_desktop_web/src/features/query-system/components/query_item_table.jsx`: widen the row API from “edit whole item” to “edit specific field / toggle pause”.
- `app_desktop_web/src/features/query-system/components/query_item_row.jsx`: render per-cell click targets, make `market_price` display-only, and place `手动暂停` or `-` in the token-right control slot.
- `app_desktop_web/src/features/query-system/components/query_item_edit_dialog.jsx`: turn the old full-item modal into a centered single-item dialog shell that renders one field at a time and has no per-dialog apply/cancel workflow.
- `app_desktop_web/src/features/query-system/query_system_models.js`: keep draft mutation helpers small and reusable if the hook needs shared field-update logic.
- `app_desktop_web/src/styles/app.css`: adjust row/control-slot styling and single-item dialog layout without disturbing the existing create dialog.

## Chunk 1: Single-Item Query Editing

### Task 1: Add regression tests for field-scoped dialogs and inline pause drafting

**Files:**
- Modify: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
- Test: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`

- [ ] **Step 1: Write the failing tests**

Add focused tests that cover:
- `market_price` is no longer a button and does not open any dialog.
- Clicking `扫货价`, `磨损`, `new_api`, `fast_api`, and `token` opens five different centered dialogs with names such as `修改扫货价`, `修改磨损`, `修改 new_api 分配`, and each dialog shows only its own inputs.
- Changing a dialog input updates the row immediately, closing the dialog keeps the draft value, and the page save button still shows unsaved state.
- The inline `手动暂停` control sits to the right of `token`, toggles only the draft row state, and delete mode replaces that control with the same `-` delete control slot (while accessibility can still expose `删除商品 ...`).

- [ ] **Step 2: Run the focused test to verify RED**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx`
Expected: FAIL because the row still renders a clickable `市场价`, every editable cell still opens the same `编辑商品` dialog, and `手动暂停` still lives inside the old modal.

- [ ] **Step 3: Keep adjacent save-flow assertions that prove page-level save remains the only real submit**

Extend an existing save test, or add a new focused one, so it edits through the new single-item UI, clicks the existing page save button, and asserts the outbound `PATCH` payload still contains the updated draft values only after that page-level save step.

- [ ] **Step 4: Re-run the focused test after implementation**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx`
Expected: PASS

### Task 2: Replace whole-item staged editing with item-field dialog context

**Files:**
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Modify: `app_desktop_web/src/features/query-system/query_system_models.js`
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Test: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`

- [ ] **Step 1: Write the minimal state contract needed by the failing tests**

Define an `editingContext` shape that carries:
- `queryItemId`
- `kind` (`price`, `wear`, `allocation`)
- `modeType` (`new_api`, `fast_api`, `token`) only when `kind === "allocation"`

Keep the current page draft in `currentConfig.items`; do not keep a second item draft copy that can drift.

- [ ] **Step 2: Implement direct draft mutation helpers**

In `use_query_system_page.js`:
- Replace `editingItemId`, `editItemDraft`, `updateEditItemField`, `updateEditItemAllocation`, and `applyEditItem`.
- Add helpers such as `openEditItemDialog({ queryItemId, kind, modeType })`, `closeEditItemDialog()`, `updateDraftItemField(queryItemId, field, value)`, `updateDraftItemAllocation(queryItemId, modeType, value)`, and `toggleDraftItemManualPaused(queryItemId)`.
- Ensure every helper updates `currentConfig` through `updateDraftConfig(...)` so closing the dialog preserves the changed draft.

- [ ] **Step 3: Keep remaining-capacity math scoped to the currently opened item**

Rebuild `editDialogRemainingByMode` from `currentConfig.items` plus the current `editingContext.queryItemId`, so mode dialogs still show accurate `还可分配` / `已超出` counts even though edits now write directly into the shared page draft.

- [ ] **Step 4: Wire the new contract into the page**

In `query_system_page.jsx`, pass the new context object and direct draft mutation callbacks to the row/table and dialog components; remove the old modal submit callback from the page surface.

- [ ] **Step 5: Re-run the focused test**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx`
Expected: PASS or fail only on remaining presentational gaps in the row/dialog components.

### Task 3: Rebuild the item row and dialog UI around single-field editing

**Files:**
- Modify: `app_desktop_web/src/features/query-system/components/query_item_table.jsx`
- Modify: `app_desktop_web/src/features/query-system/components/query_item_row.jsx`
- Modify: `app_desktop_web/src/features/query-system/components/query_item_edit_dialog.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`

- [ ] **Step 1: Make row actions match the approved product behavior**

Update `query_item_row.jsx` so that:
- `market_price` renders as plain text, not a button.
- `扫货价` opens `修改扫货价`.
- `磨损` opens `修改磨损`.
- Each mode cell opens only its own allocation dialog.
- The control slot to the right of `token` shows `手动暂停` in normal mode and the delete button in delete mode.

- [ ] **Step 2: Turn the old full-item modal into a single-item dialog shell**

Update `query_item_edit_dialog.jsx` so that:
- The dialog title changes by field: `修改扫货价`, `修改磨损`, `修改 new_api 分配`, `修改 fast_api 分配`, `修改 token 分配`.
- `扫货价` dialog shows item name, read-only `market_price`, and one `扫货价` input.
- `磨损` dialog shows item name, item-level natural wear range as read-only reference (`--` fallback if missing), `配置最小磨损`, and `配置最大磨损`.
- Mode dialogs show item name, current mode status text, remaining-capacity text, and only one `QueryModeAllocationInput`.
- There is a close button, but no `应用修改` button and no cancel rollback path.

- [ ] **Step 3: Adjust styling for the new dense row contract**

Update `app.css` so the inline control slot aligns with the token column without adding a new table column, and the single-item dialog stays centered and readable on both desktop and narrow widths.

- [ ] **Step 4: Re-run the focused regression**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx`
Expected: PASS

### Task 4: Run query-system verification and guard against page regressions

**Files:**
- Verify only

- [ ] **Step 1: Run focused query-system renderer tests**

Run from `app_desktop_web/`: `npm test -- tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_page.test.jsx`
Expected: PASS

- [ ] **Step 2: Run the full frontend suite**

Run from `app_desktop_web/`: `npm test`
Expected: PASS

- [ ] **Step 3: Review for scope control**

Confirm the change did not alter:
- create-item dialog flow
- page-level save semantics
- `market_price` data source or editability
- unrelated purchase-system files
