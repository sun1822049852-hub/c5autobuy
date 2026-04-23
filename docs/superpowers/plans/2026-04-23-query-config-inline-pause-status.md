# Query Config Inline Pause Status Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move query config item manual pause from an external text control into the item row as an inline icon status cell.

**Architecture:** Keep `manual_paused` as the existing draft source of truth. Update the query item table grid to include a final in-row status cell, render pause/run icons from CSS, and preserve the delete-mode slot replacement in that same cell.

**Tech Stack:** React, CSS, Vitest, Testing Library.

---

## Chunk 1: Inline Status Cell

### Task 1: Add renderer regression coverage

**Files:**
- Modify: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [x] **Step 1: Write the failing test for inline icon state**

In `query_system_editing.test.jsx`, update the manual pause test to assert:

```jsx
const activePauseControl = within(itemOne).getByRole("button", {
  name: "切换手动暂停 AK-47 | Redline",
});
expect(activePauseControl).toHaveClass("query-item-row__status-toggle");
expect(activePauseControl).toHaveClass("is-running");
expect(within(activePauseControl).getByText("运行中")).toHaveClass("query-item-row__status-label");
expect(within(activePauseControl).getByTestId("pause-status-running-icon")).toBeInTheDocument();

const pausedItem = await screen.findByRole("region", { name: "商品 M4A1-S | Blue Phosphor" });
const pausedPauseControl = within(pausedItem).getByRole("button", {
  name: "切换手动暂停 M4A1-S | Blue Phosphor",
});
expect(pausedPauseControl).toHaveClass("query-item-row__status-toggle");
expect(pausedPauseControl).toHaveClass("is-paused");
expect(within(pausedPauseControl).getByText("已暂停")).toHaveClass("query-item-row__status-label");
expect(within(pausedPauseControl).getByTestId("pause-status-paused-icon")).toBeInTheDocument();
```

The visible text labels will later be visually hidden so the UI remains icon-only while tests can still assert semantics.

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
npm --prefix app_desktop_web test -- tests/renderer/query_system_editing.test.jsx --run
```

Expected: FAIL because the current control still uses `query-item-row__control`, contains visible `手动暂停`, and has no icon elements.

- [x] **Step 3: Update readonly regression expectation**

In `query_system_page.test.jsx`, keep the readonly disabled assertion but target the same accessible name and expect the new class:

```jsx
const pauseControl = screen.getByRole("button", { name: "切换手动暂停 AK-47 | Redline" });
expect(pauseControl).toBeDisabled();
expect(pauseControl).toHaveClass("query-item-row__status-toggle");
```

- [x] **Step 4: Run readonly test to verify it fails**

Run:

```powershell
npm --prefix app_desktop_web test -- tests/renderer/query_system_page.test.jsx --run
```

Expected: FAIL on the new class assertion.

### Task 2: Implement row and table structure

**Files:**
- Modify: `app_desktop_web/src/features/query-system/components/query_item_table.jsx`
- Modify: `app_desktop_web/src/features/query-system/components/query_item_row.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [x] **Step 1: Add the status column header**

In `query_item_table.jsx`, add a final `状态` header inside `.query-item-table__column-grid`, after `token`. Keep the existing top-right create/delete toolbar unchanged.

- [x] **Step 2: Move the pause/delete control into row content**

In `query_item_row.jsx`, render the normal pause button or delete button as the last child of `.query-item-row__content`. Remove the separate sibling button after the content grid.

The normal button should be shaped like:

```jsx
const isPaused = Boolean(item.manual_paused);

<button
  aria-label={`切换手动暂停 ${displayName}`}
  aria-pressed={isPaused}
  className={`query-item-row__status-toggle ${isPaused ? "is-paused" : "is-running"}`}
  type="button"
  disabled={readOnly}
  onClick={() => onToggleManualPause(queryItemId)}
>
  <span
    className="query-item-row__status-icon"
    data-testid={isPaused ? "pause-status-paused-icon" : "pause-status-running-icon"}
    aria-hidden="true"
  />
  <span className="query-item-row__status-label">{isPaused ? "已暂停" : "运行中"}</span>
</button>
```

The delete button keeps `aria-label="删除商品 ..."` and visible `-`, but uses the same final grid cell.

- [x] **Step 3: Update CSS grid columns**

In `app.css`, change the query item grid variable to include the final status column:

```css
--query-item-grid-columns: minmax(240px, 1.5fr) 92px 92px 124px 112px 112px 112px 56px;
```

Keep the table toolbar in the header, but remove the item row's outer two-column layout:

```css
.query-item-row {
  display: block;
}
```

Ensure `.query-item-row__content` remains the full row grid.

- [x] **Step 4: Add icon-only state styles**

Replace the old `.query-item-row__control` styles with `.query-item-row__status-toggle` styles:

```css
.query-item-row__delete,
.query-item-row__status-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 32px;
  padding: 0;
  border-radius: 999px;
}
```

Use CSS to draw icons:

```css
.query-item-row__status-icon {
  position: relative;
  display: inline-block;
}

.query-item-row__status-toggle.is-paused .query-item-row__status-icon {
  width: 0;
  height: 0;
  border-top: 7px solid transparent;
  border-bottom: 7px solid transparent;
  border-left: 12px solid var(--danger);
}

.query-item-row__status-toggle.is-running .query-item-row__status-icon {
  width: 14px;
  height: 16px;
}

.query-item-row__status-toggle.is-running .query-item-row__status-icon::before,
.query-item-row__status-toggle.is-running .query-item-row__status-icon::after {
  content: "";
  position: absolute;
  top: 0;
  width: 4px;
  height: 16px;
  border-radius: 999px;
  background: var(--success);
}
```

Visually hide `.query-item-row__status-label` using an existing sr-only pattern if present, otherwise add a local visually-hidden rule.

- [x] **Step 5: Run focused renderer tests**

Run:

```powershell
npm --prefix app_desktop_web test -- tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_page.test.jsx --run
```

Expected: PASS.

### Task 3: Documentation and verification closeout

**Files:**
- Modify: `docs/agent/session-log.md`
- Check: `README.md`

- [x] **Step 1: Run affected renderer suite**

Run:

```powershell
npm --prefix app_desktop_web test -- tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_page.test.jsx tests/renderer/query_system_models.test.js --run
```

Expected: PASS.

- [x] **Step 2: Run build**

Run:

```powershell
npm --prefix app_desktop_web run build
```

Expected: PASS.

- [x] **Step 3: Update session log**

Append a new entry to `docs/agent/session-log.md` with:

- Background: query config manual pause was ambiguous and outside the item row.
- Completed: inline status cell with red triangle / green double-bar icon.
- Verification: exact commands and results.
- Next step: user visual check in the desktop window.

- [x] **Step 4: README check**

Review `README.md`. Expected: no change needed because this is a narrow UI affordance change.
