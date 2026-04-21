# Program Membership Master Recovery Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover the approved membership/control-plane implementation back onto `master` without losing the canonical desktop launcher chain or pulling in the side-worktree drift.

**Architecture:** Treat root `master` as the only trusted release line. Recover the shared-workspace Program Access skeleton and readonly-lock UI behavior from `feature/local-program-access-extension`, then recover the remote control plane, SMTP-backed register/reset flow, Python entitlement adapter, and packaging pieces from `feature/program-control-plane-chunk1`. Reject any drift that deletes or bypasses `main_ui_node_desktop.js`, changes the root launcher/naming contract without explicit approval, or reintroduces local multi-tenant ownership.

**Tech Stack:** Python 3.11 + FastAPI + pytest; React 19 + Vitest; Electron + electron-builder; Node.js + `node:http` + `node:sqlite` + `nodemailer`.

---

## Chunk 1: Recover The Shared-Workspace Program Access Base

### Task 1: Pull the backend skeleton and guard path onto `master`

**Files:**
- Create: `app_backend/api/program_access_guard.py`
- Create: `app_backend/api/routes/program_auth.py`
- Create: `app_backend/api/schemas/program_auth.py`
- Create: `app_backend/application/program_access.py`
- Create: `app_backend/infrastructure/program_access/`
- Modify: `app_backend/api/routes/accounts.py`
- Modify: `app_backend/api/routes/query_runtime.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Modify: `app_backend/api/routes/query_settings.py`
- Modify: `app_backend/api/routes/runtime_settings.py`
- Modify: `app_backend/api/routes/app_bootstrap.py`
- Modify: `app_backend/api/schemas/app_bootstrap.py`
- Modify: `app_backend/application/use_cases/get_app_bootstrap.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_app_bootstrap_route.py`
- Test: `tests/backend/test_desktop_web_backend_bootstrap.py`
- Test: `tests/backend/test_program_access_guard_routes.py`

- [ ] **Step 1: Write or restore the backend guard tests on `master`**

Lock in the approved baseline:

```python
async def test_app_bootstrap_route_includes_program_access_snapshot(client):
    payload = (await client.get("/app/bootstrap")).json()
    assert payload["program_access"]["workspace_mode"] == "shared_workspace"

async def test_runtime_start_route_is_guarded(client):
    response = await client.post("/query-runtime/start")
    assert response.status_code in {200, 401, 403}
```

- [ ] **Step 2: Run the focused backend tests and confirm current `master` fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_desktop_web_backend_bootstrap.py tests/backend/test_program_access_guard_routes.py -q`

Expected: FAIL because root `master` still lacks `program_access` wiring and `/program-auth/*`.

- [ ] **Step 3: Recover only the shared-workspace-safe backend files**

Bring back the guard and bootstrap surface from `feature/local-program-access-extension` and `feature/program-control-plane-chunk1`, but keep these boundaries:

```text
- keep one shared local workspace
- keep route-level guard entrypoints
- keep remote auth contract hooks
- do not introduce owner_user_id-based local isolation
```

- [ ] **Step 4: Re-run the focused backend tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_desktop_web_backend_bootstrap.py tests/backend/test_program_access_guard_routes.py -q`

Expected: PASS.

### Task 2: Recover the shared-workspace renderer/provider baseline

**Files:**
- Create: `app_desktop_web/src/api/program_auth_client.js`
- Create: `app_desktop_web/src/program_access/`
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Modify: `app_desktop_web/src/runtime/app_runtime_store.js`
- Modify: `app_desktop_web/src/runtime/runtime_connection_manager.js`
- Modify: `app_desktop_web/src/runtime/use_app_runtime.js`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- Test: `app_desktop_web/tests/renderer/program_access_provider.test.jsx`
- Test: `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`

- [ ] **Step 1: Restore the readonly/shared-workspace renderer tests**

Lock in the copy that the user approved:

```javascript
expect(screen.getByText("共享工作区")).toBeInTheDocument();
expect(screen.getByText("切换程序账号只会改变当前权限，不会切换本地数据。")).toBeInTheDocument();
expect(screen.getByText("只读锁定")).toBeInTheDocument();
```

- [ ] **Step 2: Run the focused renderer tests and confirm current `master` fails**

Run: `npm --prefix app_desktop_web test -- program_access_provider.test.jsx program_access_sidebar_card.test.jsx app_remote_bootstrap.test.jsx --run`

Expected: FAIL because root `master` has no Program Access UI/provider.

- [ ] **Step 3: Recover the Program Access UI without bringing back fake local membership or launcher drift**

Keep:

```text
- sidebar membership card
- provider-level guard error handling
- readonly-disabled UI states
```

Reject:

```text
- fake local member profile storage
- deleting or bypassing main_ui_node_desktop.js
- changing the desktop naming contract away from whatever root master currently carries without explicit approval
```

- [ ] **Step 4: Re-run the focused renderer tests**

Run: `npm --prefix app_desktop_web test -- program_access_provider.test.jsx program_access_sidebar_card.test.jsx app_remote_bootstrap.test.jsx --run`

Expected: PASS.

## Chunk 2: Recover The Remote Control Plane And Register/Reset Chain

### Task 3: Bring the Node control-plane service back onto `master`

**Files:**
- Create: `program_admin_console/`
- Test: `program_admin_console/tests/control-plane-store.test.js`
- Test: `program_admin_console/tests/control-plane-server.test.js`
- Test: `program_admin_console/tests/control-plane-ui.test.js`

- [ ] **Step 1: Restore the control-plane tests**

Lock in:

```javascript
assert.equal(await sendRegisterCode("alice@example.com").message, "注册验证码已发送");
assert.equal(await resetPassword(...).message, "密码已重置");
assert.equal(await runtimePermit("runtime.start").accepted, true);
```

- [ ] **Step 2: Run Node control-plane tests and confirm current `master` fails**

Run: `node program_admin_console/tests/control-plane-store.test.js`

Expected: FAIL because `program_admin_console/` does not yet exist on root `master`.

- [ ] **Step 3: Recover the control-plane service, SMTP wiring, and admin UI**

Source: `feature/program-control-plane-chunk1`

Keep:

```text
- health/auth/admin/runtime-permit endpoints
- register/send-code/login/refresh/logout/password reset
- SMTP config copied from cs2_alchemy-compatible shape
- sender display name C5 交易助手
- deploy docs pointing at http://8.138.39.139:18787
```

Reject:

```text
- unrelated launcher/output artifacts
- release/win-unpacked blobs
- package-lock drift outside program_admin_console itself unless required
```

- [ ] **Step 4: Re-run the Node control-plane test suite**

Run:

```powershell
node program_admin_console/tests/control-plane-store.test.js
node program_admin_console/tests/control-plane-server.test.js
node program_admin_console/tests/control-plane-ui.test.js
```

Expected: PASS.

### Task 4: Recover the Python remote entitlement adapter

**Files:**
- Modify: `pyproject.toml`
- Modify: `app_backend/application/program_access.py`
- Modify: `app_backend/api/routes/program_auth.py`
- Modify: `app_backend/api/schemas/program_auth.py`
- Create: `app_backend/infrastructure/program_access/remote_control_plane_client.py`
- Create: `app_backend/infrastructure/program_access/entitlement_verifier.py`
- Create: `app_backend/infrastructure/program_access/remote_entitlement_gateway.py`
- Create: `app_backend/infrastructure/program_access/refresh_scheduler.py`
- Modify: `app_backend/infrastructure/program_access/__init__.py`
- Test: `tests/backend/test_remote_control_plane_client.py`
- Test: `tests/backend/test_remote_entitlement_gateway.py`
- Test: `tests/backend/test_program_access_refresh_scheduler.py`
- Test: `tests/backend/test_program_auth_routes.py`

- [ ] **Step 1: Restore the remote-adapter tests**

Lock in:

```python
assert gateway.send_register_code("alice@example.com").message == "注册验证码已发送"
assert gateway.register(...).reason == "membership_inactive"
assert client.fetch_public_key_pem().startswith("-----BEGIN PUBLIC KEY-----")
```

- [ ] **Step 2: Run the focused adapter tests and confirm failure on current `master`**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_remote_control_plane_client.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_refresh_scheduler.py tests/backend/test_program_auth_routes.py -q`

Expected: FAIL because root `master` lacks the remote adapter.

- [ ] **Step 3: Recover the remote adapter and reason mapping**

Must keep:

```text
- register/send-code/reset-password local routes
- remote reason -> local status code mapping
- signed entitlement cache verification
- public-key bootstrap/fallback path
- no local data wipe on logout
```

- [ ] **Step 4: Re-run the focused adapter tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/backend/test_remote_control_plane_client.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_refresh_scheduler.py tests/backend/test_program_auth_routes.py -q`

Expected: PASS.

## Chunk 3: Recover Readonly UI Enforcement Across The Existing Desktop

### Task 5: Reapply readonly-disabled states to the existing pages

**Files:**
- Modify: `app_desktop_web/src/features/account-center/`
- Modify: `app_desktop_web/src/features/purchase-system/`
- Modify: `app_desktop_web/src/features/query-system/`
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: Restore the readonly guard tests**

Lock in examples like:

```javascript
expect(screen.getByRole("button", { name: "添加账号" })).toBeDisabled();
expect(screen.getByRole("button", { name: "开始扫货" })).toBeDisabled();
expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();
```

- [ ] **Step 2: Run the focused page tests and confirm failure on current `master`**

Run: `npm --prefix app_desktop_web test -- account_center_page.test.jsx purchase_system_page.test.jsx query_system_page.test.jsx --run`

Expected: FAIL because current `master` has no readonly-lock integration.

- [ ] **Step 3: Recover page-level disabled states while keeping read visibility**

The rule is fixed:

```text
- local data remains visible
- stop actions remain allowed if already running
- state-mutating buttons, dialogs, and saves are blocked
```

- [ ] **Step 4: Re-run the focused page tests**

Run: `npm --prefix app_desktop_web test -- account_center_page.test.jsx purchase_system_page.test.jsx query_system_page.test.jsx --run`

Expected: PASS.

## Chunk 4: Recover Packaging Without Repeating The Launcher Drift

### Task 6: Bring back packaged control-plane config and Windows build support

**Files:**
- Create: `app_desktop_web/program_access_config.cjs`
- Create: `app_desktop_web/electron-builder-paths.cjs`
- Create: `app_desktop_web/electron-builder-preflight.cjs`
- Create: `app_desktop_web/electron-builder.config.cjs`
- Modify: `app_desktop_web/electron-main.cjs`
- Modify: `app_desktop_web/python_backend.js`
- Modify: `app_desktop_web/package.json`
- Modify: `app_desktop_web/tests/electron/python_backend.test.js`
- Modify: `app_desktop_web/tests/electron/desktop_launcher.test.js`
- Create: `app_desktop_web/tests/electron/program_access_packaging.test.js`
- Modify: `README.md`

- [ ] **Step 1: Restore the packaging tests**

Lock in:

```javascript
expect(buildPythonBackendEnv(...).C5_PROGRAM_ACCESS_STAGE).toBe("packaged_release");
expect(launcherPath.endsWith("main_ui_node_desktop.js")).toBe(true);
```

- [ ] **Step 2: Run the focused Electron/package tests and confirm failure on current `master`**

Run: `npm --prefix app_desktop_web test -- tests/electron/python_backend.test.js tests/electron/desktop_launcher.test.js tests/electron/program_access_packaging.test.js --run`

Expected: FAIL because root `master` lacks release config plumbing.

- [ ] **Step 3: Recover the packaged config path but keep the canonical launcher**

Must keep:

```text
- main_ui_node_desktop.js remains the trusted launcher
- packaged backend reads controlPlaneBaseUrl from client_config.release.json / override
- install path can be user-selected and desktop should get a shortcut, not a whole folder
```

Must reject:

```text
- deleting or bypassing main_ui_node_desktop.js as the canonical root launcher
- changing the root packaging/app naming contract without explicit approval
- checking in build/ or release/ artifacts
```

- [ ] **Step 4: Re-run the focused Electron/package tests**

Run: `npm --prefix app_desktop_web test -- tests/electron/python_backend.test.js tests/electron/desktop_launcher.test.js tests/electron/program_access_packaging.test.js --run`

Expected: PASS.

## Chunk 5: End-To-End Verification And Packaging

### Task 7: Verify recovered master and build the Windows package from the right line

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/superpowers/references/2026-04-21-worktree-disposition-reference.md`

- [ ] **Step 1: Run the combined focused verification**

Run:

```powershell
./.venv/Scripts/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_desktop_web_backend_bootstrap.py tests/backend/test_program_access_guard_routes.py tests/backend/test_remote_control_plane_client.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_refresh_scheduler.py tests/backend/test_program_auth_routes.py -q
npm --prefix app_desktop_web test -- program_access_provider.test.jsx program_access_sidebar_card.test.jsx app_remote_bootstrap.test.jsx account_center_page.test.jsx purchase_system_page.test.jsx query_system_page.test.jsx tests/electron/python_backend.test.js tests/electron/desktop_launcher.test.js tests/electron/program_access_packaging.test.js --run
node program_admin_console/tests/control-plane-store.test.js
node program_admin_console/tests/control-plane-server.test.js
node program_admin_console/tests/control-plane-ui.test.js
```

Expected: PASS.

- [ ] **Step 2: Build from root `master` only**

Run: `npm --prefix app_desktop_web run build:win`

Expected: an installer built from root `master`, not from any side worktree.

- [ ] **Step 3: Append handoff evidence**

Record:

```text
- recovered modules and their source worktrees
- verification commands and results
- packaging output path
- which worktrees still remain as archival sources
```
