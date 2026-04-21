# Dual Desktop Entrypoints Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one explicit local-pass-through debug entrypoint and keep one explicit simulated-user entrypoint without changing the shared-workspace product semantics.

**Architecture:** Keep `main_ui_node_desktop.js` as the only real user-facing launcher contract for simulated-user testing and release-like auth behavior. Add a second wrapper launcher that only changes startup config selection, so both paths still run the same Electron main process and backend stack. Make the mode switch explicit through config selection, not implicit through missing files.

**Tech Stack:** Node.js launcher scripts, Electron main/bootstrap config, Python wrapper entrypoints, Vitest, pytest, Markdown docs

---

## Chunk 1: Entrypoint Contract

### Task 1: Lock the dual-entrypoint launcher behavior with tests

**Files:**
- Modify: `app_desktop_web/tests/electron/desktop_launcher.test.js`
- Modify: `tests/backend/test_remove_legacy_cli_entry.py`

- [ ] **Step 1: Write the failing tests**

```javascript
it("builds a local debug launcher env that points to the explicit local debug config", () => {
  expect(localDebugLauncher.buildLocalDebugLaunchEnv({
    PATH: "C:/Windows/System32",
  })).toEqual(expect.objectContaining({
    PATH: "C:/Windows/System32",
    CLIENT_CONFIG_FILE: expect.stringMatching(/client_config\.local_debug\.json$/),
    C5_PROGRAM_ACCESS_STAGE: "prepackaging",
  }));
});
```

```python
def test_run_app_local_debug_points_to_local_debug_launcher():
    content = (PROJECT_ROOT / "run_app_local_debug.py").read_text(encoding="utf-8")

    assert "main_ui_node_desktop_local_debug.js" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix app_desktop_web test -- tests/electron/desktop_launcher.test.js --run`
Expected: FAIL because the local debug launcher module/helpers do not exist yet.

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`
Expected: FAIL because `run_app_local_debug.py` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create a dedicated root launcher wrapper plus a matching Python wrapper, with no extra business logic.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix app_desktop_web test -- tests/electron/desktop_launcher.test.js --run`
Expected: PASS

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`
Expected: PASS

## Chunk 2: Explicit Config Split

### Task 2: Lock config selection for user mode vs local debug mode

**Files:**
- Modify: `app_desktop_web/tests/electron/program_access_packaging.test.js`
- Create: `app_desktop_web/build/client_config.local_debug.json`
- Modify: `app_desktop_web/program_access_config.cjs`
- Create: `main_ui_node_desktop_local_debug.js`
- Create: `run_app_local_debug.py`

- [ ] **Step 1: Write the failing tests**

```javascript
it("reads the explicit local debug config file before release config when CLIENT_CONFIG_FILE is provided", () => {
  expect(readProgramAccessConfig(...)).toEqual({
    controlPlaneBaseUrl: "",
  });
});
```

```javascript
it("exports a local debug launcher path that stays on prepackaging even if release config exists", () => {
  expect(localDebugLauncher.LOCAL_DEBUG_CONFIG_PATH).toMatch(/client_config\.local_debug\.json$/);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js tests/electron/desktop_launcher.test.js --run`
Expected: FAIL because the explicit local debug config path does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Keep `main_ui_node_desktop.js` unchanged as the simulated-user entrypoint. Add a local debug wrapper that injects:

```javascript
CLIENT_CONFIG_FILE=<repo>/app_desktop_web/build/client_config.local_debug.json
C5_PROGRAM_ACCESS_STAGE=prepackaging
```

and then delegates into `main_ui_node_desktop.js`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js tests/electron/desktop_launcher.test.js --run`
Expected: PASS

## Chunk 3: Docs and Verification

### Task 3: Update operator docs and persistent project records

**Files:**
- Modify: `README.md`
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md`

- [ ] **Step 1: Update docs**

Document both entrypoints clearly:

- `node main_ui_node_desktop.js` / `python run_app.py`
- `node main_ui_node_desktop_local_debug.js` / `python run_app_local_debug.py`

- [ ] **Step 2: Run focused verification**

Run: `npm --prefix app_desktop_web test -- tests/electron/desktop_launcher.test.js tests/electron/program_access_packaging.test.js tests/electron/python_backend.test.js --run`
Expected: PASS

Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`
Expected: PASS

- [ ] **Step 3: Re-read changed files and record outcome**

Confirm docs, session log, and memory all reflect:

- user/simulated-user entrypoint is explicit
- local debug entrypoint is explicit
- shared workspace semantics remain unchanged
