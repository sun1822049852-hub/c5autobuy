# Program Runtime Revoke Push Stop Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make control-plane revoke of runtime permission stop active query/purchase runtimes immediately, without waiting for the existing `300s` membership summary refresh or an app restart.

**Architecture:** Split "membership summary" from "runtime execution control". Keep the existing signed snapshot + `300s` refresh scheduler for sidebar/auth-state hydration, but add a separate authenticated server-push control channel for runtime execution. When control plane changes `status`, `membership_plan`, or `permission_overrides` in a way that removes effective `runtime.start`, it pushes a revoke event to the desktop backend; the desktop backend immediately stops query runtime (which already cascades purchase stop), publishes normal runtime stop updates to the renderer, and uses a short control-channel grace only to absorb transient jitter rather than to preserve indefinite execution after disconnect.

**Tech Stack:** Node.js HTTP/SSE (`program_admin_console`), Python FastAPI + `httpx` streaming (`app_backend`), existing `RuntimeUpdateHub`, existing query/purchase runtime services, pytest, node tests.

**Non-goals:** Do not replace the existing `300s` `program_access` summary refresh. Do not make sidebar membership status instant in this slice. Do not rework purchase dispatch/performance architecture. Do not re-open already finished control-plane cleanup, HTTPS+CA fail-closed, or register-flow work.

**Semantic Guard:**
- Truth source for "may this desktop keep running query/purchase right now" is control-plane effective entitlements plus an active runtime-control session, not the cached summary snapshot.
- Allowed fallback: cached signed snapshot may continue to backfill UI/auth summary when remote refresh is temporarily unavailable.
- Forbidden downgrade: reusing `program_access.auth_state` or `last_error_code` to imply real-time runtime execution state; runtime-execution revocation must travel on a separate channel and, if surfaced locally, use separate fields/reasons.

---

## Chunk 1: Runtime Control Contract

### Task 1: Add a control-plane push channel for runtime revoke

**Files:**
- Create: `program_admin_console/src/runtimeControlHub.js`
- Modify: `program_admin_console/src/controlPlaneStore.js`
- Modify: `program_admin_console/src/server.js`
- Test: `program_admin_console/tests/control-plane-server.test.js`

- [ ] **Step 1: Write the failing control-plane tests**

Add focused tests that prove all of the following:
- An authenticated runtime-control stream can be opened for a valid refresh session + device.
- `PATCH /api/admin/users/:id` pushes a revoke event when effective runtime execution permission changes from allowed to denied because of:
  - `status: active -> disabled`
  - `membership_plan: member -> inactive`
  - `permission_overrides` removing `runtime.start`
  - `permission_overrides` removing `program_access_enabled`
- Non-runtime-only changes (for example only toggling `account.browser_query.enable`) do **not** emit runtime revoke events.
- Stream emits periodic keepalive events/comments so the desktop backend can distinguish a healthy idle connection from silence.

- [ ] **Step 2: Run the focused control-plane tests and watch them fail**

Run:

```powershell
node program_admin_console/tests/control-plane-server.test.js
```

Expected: FAIL because the runtime-control stream endpoint and revoke broadcast path do not exist yet.

- [ ] **Step 3: Implement `runtimeControlHub.js`**

Build a focused hub responsible only for runtime-control streams:
- Register SSE subscribers keyed by `user_id` and `device_id`
- Send initial `hello` payload with server timestamp + current stream version
- Send periodic keepalive frames on a fixed interval
- Broadcast `runtime.revoke` payloads with explicit revoke reason codes
- Clean up closed sockets and stale subscribers

- [ ] **Step 4: Extract runtime execution truth-source helpers in `controlPlaneStore.js`**

Add helpers that answer:
- Does this user currently have effective runtime execution permission?
- Which concrete rule removed it (`user_disabled`, `membership_inactive`, `runtime_start_disabled`, `program_access_disabled`)?

Do not reuse UI summary-only helpers if they blur execution truth and display truth.

- [ ] **Step 5: Add the authenticated SSE endpoint in `server.js`**

Expose a dedicated stream such as:

```text
GET /api/auth/runtime-control/stream
Authorization: Bearer <refresh_token>
X-C5-Device-Id: <device_id>
```

Implementation rules:
- Authenticate via `resolveRefreshSession(...)`
- Reject mismatched device or invalid refresh token
- Register the subscriber in `runtimeControlHub`
- Keep `/api/auth/runtime-permit` and normal auth routes unchanged for this task

- [ ] **Step 6: Broadcast revoke events on admin-side entitlement changes**

In the admin user update path:
- Read runtime execution state before mutation
- Apply the mutation
- Read runtime execution state after mutation
- If the state changed from allowed to denied, publish a `runtime.revoke` event to all active runtime-control streams for that user

Keep this diff local to runtime execution. Do not broadcast revoke for unrelated permission edits.

- [ ] **Step 7: Re-run the control-plane tests**

Run:

```powershell
node program_admin_console/tests/control-plane-server.test.js
```

Expected: PASS


## Chunk 2: Desktop Backend Enforcement

### Task 2: Add a desktop runtime-control listener service

**Files:**
- Create: `app_backend/infrastructure/program_access/runtime_control_service.py`
- Modify: `app_backend/infrastructure/program_access/remote_control_plane_client.py`
- Modify: `app_backend/startup/build_runtime_full_services.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_program_runtime_control_service.py`

- [ ] **Step 1: Write the failing backend service tests**

Add focused pytest coverage for:
- Receiving `runtime.revoke` triggers the local forced-stop callback exactly once
- Temporary stream jitter inside grace does not stop runtime immediately
- Keepalive silence beyond grace triggers local forced stop
- Transport loss does **not** rewrite `program_access` summary into a fake "revoked membership" state
- A normal stream close after local runtime stop does not emit duplicate stop callbacks

- [ ] **Step 2: Run the backend service tests and watch them fail**

Run:

```powershell
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_program_runtime_control_service.py -q
```

Expected: FAIL because the runtime-control listener service and streaming client helpers do not exist yet.

- [ ] **Step 3: Extend `remote_control_plane_client.py` with SSE streaming support**

Add a focused helper that:
- Opens the authenticated runtime-control stream
- Parses SSE events / keepalive frames
- Yields normalized event dictionaries to the caller
- Keeps refresh tokens out of query strings and logs

Do not widen this into a generic websocket framework; keep it minimal and purpose-built for runtime-control.

- [ ] **Step 4: Implement `runtime_control_service.py`**

Service responsibilities:
- Start only while local runtime execution is active
- Use the current refresh token + device id from existing stores
- Maintain a last-seen keepalive timestamp
- Call back into local runtime enforcement when:
  - a `runtime.revoke` event arrives
  - keepalive silence exceeds the configured grace
  - the stream cannot be re-established inside the allowed reconnect budget

Keep summary refresh cadence separate; this service is only for runtime execution control.

- [ ] **Step 5: Wire lifecycle in `build_runtime_full_services.py` and `main.py`**

Construct the service only after query/purchase runtime services exist, so it can receive stop callbacks without circular imports. Ensure app shutdown cleanly closes the stream and worker thread/task.

- [ ] **Step 6: Re-run the backend service tests**

Run:

```powershell
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_program_runtime_control_service.py -q
```

Expected: PASS


### Task 3: Hook revoke events into query/purchase runtime stop

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/api/schemas/query_runtime.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Test: `tests/backend/test_query_runtime_service.py`
- Test: `tests/backend/test_runtime_update_websocket.py`

- [ ] **Step 1: Write the failing runtime-stop integration tests**

Add focused tests that prove:
- Starting query runtime also arms the runtime-control service
- A revoke callback stops the running query runtime
- Linked purchase runtime also stops through the existing query-stop cascade
- `query_runtime.updated` / `purchase_runtime.updated` still publish normal stop snapshots
- A dedicated stop reason (for example `program_runtime_revoked` or `program_runtime_control_unreachable`) survives in runtime status without overwriting `program_access` summary fields

- [ ] **Step 2: Run the runtime integration tests and watch them fail**

Run:

```powershell
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_query_runtime_service.py tests/backend/test_runtime_update_websocket.py -q
```

Expected: FAIL because runtime-control callbacks are not wired into the running runtime lifecycle yet.

- [ ] **Step 3: Start/stop the runtime-control session with query runtime lifecycle**

In `query_runtime_service.py`:
- Arm the runtime-control service after successful runtime start
- Disarm it on normal stop
- On revoke/timeout callback, schedule a local stop that is safe against existing locks/threads

Use the existing query stop path so purchase stop continues to piggyback on the current cascade.

- [ ] **Step 4: Add a separate forced-stop reason field**

Use a dedicated runtime field/reason for "control plane revoked execution" or "control channel lost" instead of mutating `program_access.auth_state`.

Examples:
- `query_runtime.last_error = "program_runtime_revoked"`
- `purchase_runtime.last_error = "program_runtime_revoked"`

Do **not** overload membership summary fields to carry this state.

- [ ] **Step 5: Re-run the runtime integration tests**

Run:

```powershell
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_query_runtime_service.py tests/backend/test_runtime_update_websocket.py -q
```

Expected: PASS


## Chunk 3: Verification And Rollout

### Task 4: Focused regression sweep and manual acceptance

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run the focused automated regression sweep**

Run:

```powershell
node program_admin_console/tests/control-plane-server.test.js
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_program_runtime_control_service.py tests/backend/test_query_runtime_service.py tests/backend/test_runtime_update_websocket.py tests/backend/test_program_access_guard_routes.py -q
```

Expected: PASS

- [ ] **Step 2: Manually validate the real revoke story**

Manual checklist:
1. Start query/purchase runtime in a logged-in packaged-release desktop session
2. From control plane, revoke effective runtime execution permission
3. Confirm the local runtime stops without waiting for `300s`
4. Confirm restart is denied immediately afterwards
5. Confirm sidebar membership summary is allowed to lag until manual refresh / scheduled refresh

- [ ] **Step 3: Manually validate the network-cut story**

Manual checklist:
1. Start runtime normally
2. Simulate transient control-plane jitter shorter than grace; runtime should stay alive
3. Simulate longer disconnect or deliberate network cut to control plane; runtime should stop after grace
4. Confirm this path reports a control-channel loss reason, not fake membership revocation

- [ ] **Step 4: Update `docs/agent/session-log.md`**

Record separately:
- Existing tests passed / failed
- New revoke-stop guard tests passed / failed
- Whether real desktop revoke and network-cut scenarios were manually verified

