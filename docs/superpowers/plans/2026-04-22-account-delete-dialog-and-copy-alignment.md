# Account Delete Dialog And Copy Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace account-center delete confirmation with an in-app dialog and align obvious user-facing eyebrow copy to the current product style.

**Architecture:** Keep the existing delete API flow in `use_account_center_page.js`, but split it into “request delete” and “confirm delete” phases so the UI can render a local dialog. Apply minimal copy changes only at already-user-facing render points rather than introducing a global localization layer for shell eyebrow text.

**Tech Stack:** React, Testing Library, Vitest, existing `dialog-surface` UI styles.

---

## Chunk 1: Red Tests

### Task 1: Lock the delete-dialog behavior

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`

- [ ] **Step 1: Write the failing test**

Add assertions that opening “删除账号” shows a `role="dialog"` delete modal with the selected account name and `取消` / `确认删除` buttons, and remove the `window.confirm` stub/assertion.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx --run`
Expected: FAIL because the account center still uses `window.confirm`.

### Task 2: Lock the visible copy alignment

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`
- Modify: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] **Step 1: Write the failing tests**

Change expectations so the account center eyebrow expects `账号中心`, the program-access entry/dialog expects `程序账号`, and the diagnostics eyebrow expects `运行诊断`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/diagnostics_sidebar.test.jsx --run`
Expected: FAIL on the old English eyebrow copy.

## Chunk 2: Minimal Implementation

### Task 3: Add the account delete dialog

**Files:**
- Create: `app_desktop_web/src/features/account-center/dialogs/account_delete_dialog.jsx`
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] **Step 1: Add dialog component**

Create a small account-delete dialog component that mirrors existing `dialog-surface` structure, renders only the account name plus `取消` / `确认删除`, and supports overlay-close.

- [ ] **Step 2: Split request vs confirm in the hook**

Replace the inline `window.confirm` branch with state for the pending account, `requestDeleteAccount(account)`, `closeDeleteDialog()`, and `confirmDeleteAccount()` that preserves the existing DELETE + refresh + log flow.

- [ ] **Step 3: Wire the dialog into the page**

Render the new dialog from `AccountCenterPage` and keep the context menu delete action pointing at the request phase.

- [ ] **Step 4: Add minimal styling**

Reuse existing dialog tokens and give the selected account name a compact highlighted card style consistent with the existing delete-config dialog.

### Task 4: Align eyebrow copy

**Files:**
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Modify: `app_desktop_web/src/program_access/program_access_sidebar_card.jsx`
- Modify: `app_desktop_web/src/program_access/program_access_banner.jsx`
- Modify: `app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx`

- [ ] **Step 1: Replace visible English eyebrow copy**

Update only the user-visible eyebrow labels:
- `ACCOUNT CENTER` -> `账号中心`
- `PROGRAM ACCESS` -> `程序账号`
- `Diagnostics` -> `运行诊断`

- [ ] **Step 2: Leave debug-only copy untouched**

Do not change `本地调试模式`, because it is part of the explicit local debug path.

## Chunk 3: Verification And Handoff

### Task 5: Run focused verification

**Files:**
- Test: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`
- Test: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`

- [ ] **Step 1: Run focused suite**

Run: `npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx tests/renderer/account_center_page.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/diagnostics_sidebar.test.jsx --run`
Expected: PASS

- [ ] **Step 2: Update logs**

Append the scope, files, verification, and residual risks to `docs/agent/session-log.md`. If the centralized eyebrow-copy rule becomes stable enough, record it in `docs/agent/memory.md`.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/superpowers/specs/2026-04-22-account-delete-dialog-and-copy-alignment-design.md docs/superpowers/plans/2026-04-22-account-delete-dialog-and-copy-alignment.md app_desktop_web/src/features/account-center/dialogs/account_delete_dialog.jsx app_desktop_web/src/features/account-center/account_center_page.jsx app_desktop_web/src/features/account-center/hooks/use_account_center_page.js app_desktop_web/src/program_access/program_access_sidebar_card.jsx app_desktop_web/src/program_access/program_access_banner.jsx app_desktop_web/src/features/diagnostics/diagnostics_panel.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/account_center_editing.test.jsx app_desktop_web/tests/renderer/account_center_page.test.jsx app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx docs/agent/session-log.md docs/agent/memory.md
git commit -m "feat: align delete dialog and user-facing shell copy"
```

Plan complete and saved to `docs/superpowers/plans/2026-04-22-account-delete-dialog-and-copy-alignment.md`. Ready to execute.
