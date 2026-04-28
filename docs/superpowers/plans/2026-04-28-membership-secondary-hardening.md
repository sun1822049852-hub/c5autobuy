# Membership Secondary Hardening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the membership-management issues that were intentionally left out of the main blocker handoff, so the remaining auth surface, control-plane UI semantics, deployment gate, and key-lifecycle risks can be closed in a separate stream without colliding with the primary membership blocker work.

**Architecture:** Keep this plan strictly separate from the primary blocker stream that is already handling immediate launch blockers such as "clear expiry becomes permanent member", "device revoke does not immediately stop active runtime", and "permission allowlist / non-member entitlement leakage". This plan covers the second ring of hardening: public auth-surface abuse reduction, admin-console truthfulness, signer/key lifecycle safety, proxy boundary tightening, and stronger release verification. Changes should be split by domain so each slice can land and verify independently.

**Tech Stack:** Node.js (`program_admin_console`), Python FastAPI (`app_backend`), pytest, node tests, PowerShell deploy tooling, Markdown docs.

**Must NOT change in this plan:**
- Do not reopen or reimplement the primary blocker chain already handed off: signing-key deployment root leak, clearing expiry turning members permanent, device revoke not instantly stopping active runtime, permission allowlist gaps, non-member entitlement leakage, or the primary runtime revoke path.
- Do not change hardware target, desktop startup `ready=true` gate, or the `查询 -> 命中 -> 购买` mainline.
- Do not regenerate installers or widen validation into full packaging work.
- Do not silently change product behavior outside the specific issues listed below.

**Scope of this plan only:**
- Public auth-surface information leaks and proxy/source-IP robustness
- Admin-console display/count accuracy for secondary membership/session states
- Key rotation and local secret-read failure semantics
- Release/deploy smoke completeness for public/private control-plane exposure
- Focused regression coverage for the above

---

## Chunk 1: Public Auth Surface Hardening

### Task 1: Remove easy account-enumeration signals from public auth endpoints

**Files:**
- Modify: `program_admin_console/src/server.js`
- Modify: `program_admin_console/src/controlPlaneStore.js`
- Test: `program_admin_console/tests/control-plane-server.test.js`
- Test: `tests/backend/test_remote_control_plane_client.py` (only if response-shape expectations propagate to desktop client)

- [ ] **Step 1: Write the failing tests**

Add focused tests that lock the desired public behavior:
- `register/send-code` must not reveal whether an email is already registered through distinct user-visible outcomes
- `password/send-reset-code` must not reveal whether a user exists through distinct user-visible outcomes
- Retry-after behavior must still be preserved when rate limiting applies

- [ ] **Step 2: Run the focused server tests and watch them fail**

Run:

```powershell
npm --prefix program_admin_console run test:server
```

Expected: FAIL because current responses expose different outcomes for registered vs unregistered emails.

- [ ] **Step 3: Implement a narrow response normalization**

Implementation rules:
- Preserve internal auditability and rate-limit enforcement
- Normalize externally visible success/failure text and status where needed so callers cannot reliably distinguish account existence
- Keep registration cooldown and abuse checks intact

- [ ] **Step 4: Re-run the focused server tests**

Run:

```powershell
npm --prefix program_admin_console run test:server
```

Expected: PASS


### Task 2: Tighten trusted-proxy source-IP parsing so callers cannot spoof localhost or arbitrary source IP

**Files:**
- Modify: `program_admin_console/src/server.js`
- Modify: `program_admin_console/tests/control-plane-server-runtime.test.js`
- Modify: `program_admin_console/tests/control-plane-server.test.js`
- Review: `program_admin_console/deploy/nginx-program-access-auth-gateway.example.conf`
- Review: `program_admin_console/deploy/nginx-program-access-auth-gateway-ip.example.conf`

- [ ] **Step 1: Write the failing runtime-option and request-source tests**

Add focused tests for:
- trusted proxy mode only accepting proxy-derived source IP in the expected boundary shape
- forged client-supplied `X-Forwarded-For` not being treated as authoritative source
- `/api/admin/bootstrap` not becoming spoofable as localhost when proxy mode is on

- [ ] **Step 2: Run the focused Node tests and watch them fail**

Run:

```powershell
npm --prefix program_admin_console run test:server-runtime
npm --prefix program_admin_console run test:server
```

Expected: FAIL because current parsing takes the first forwarded value too trustingly.

- [ ] **Step 3: Implement proxy-safe source-IP parsing**

Implementation rules:
- Treat proxy trust as a strict deployment contract, not a convenience flag
- Do not allow public callers to self-declare localhost or arbitrary origin IP through a header
- Keep loopback-only bootstrap semantics intact

- [ ] **Step 4: Re-run the focused tests**

Run:

```powershell
npm --prefix program_admin_console run test:server-runtime
npm --prefix program_admin_console run test:server
```

Expected: PASS

## Chunk 2: Control-Plane Truthfulness Fixes

### Task 3: Stop counting expired device sessions as active devices

**Files:**
- Modify: `program_admin_console/src/controlPlaneStore.js`
- Test: `program_admin_console/tests/control-plane-store.test.js`
- Test: `program_admin_console/tests/control-plane-server.test.js`

- [ ] **Step 1: Write the failing store/server tests**

Add tests that prove:
- naturally expired refresh sessions are not counted in active-device totals
- the device list shown to admins matches real active-session semantics, not just unrevoked rows

- [ ] **Step 2: Run the focused tests and watch them fail**

Run:

```powershell
npm --prefix program_admin_console run test:store
npm --prefix program_admin_console run test:server
```

Expected: FAIL because current counting/listing still treats expired sessions as active.

- [ ] **Step 3: Implement a single active-session truth rule**

Implementation rules:
- Reuse one consistent definition of "active device" everywhere the admin console shows counts or device rows
- Do not silently change refresh-token validation semantics; only align display/count behavior with it

- [ ] **Step 4: Re-run the focused tests**

Run:

```powershell
npm --prefix program_admin_console run test:store
npm --prefix program_admin_console run test:server
```

Expected: PASS


### Task 4: Make disabled-user UI stop implying that displayed permissions are still effectively active

**Files:**
- Modify: `program_admin_console/ui/app.js`
- Modify: `program_admin_console/ui/index.html`
- Test: `program_admin_console/tests/control-plane-ui.test.js`

- [ ] **Step 1: Write the failing UI tests**

Add focused tests that lock:
- disabled users are clearly shown as non-effective regardless of stored overrides
- the detail view distinguishes "stored overrides" from "currently effective permissions"
- admins are not left with a contradictory message + permission-token display

- [ ] **Step 2: Run the UI test and watch it fail**

Run:

```powershell
npm --prefix program_admin_console run test:ui
```

Expected: FAIL because current UI still renders effective-looking permission output for disabled users.

- [ ] **Step 3: Implement the UI wording/state separation**

Implementation rules:
- Keep existing admin workflows intact
- Prefer explicit "stored override" vs "currently effective permission" language over hiding all context
- Do not change backend execution truth in this task; only make the UI stop misrepresenting it

- [ ] **Step 4: Re-run the UI test**

Run:

```powershell
npm --prefix program_admin_console run test:ui
```

Expected: PASS

## Chunk 3: Key Lifecycle And Local Failure Semantics

### Task 5: Add a safe key-rotation path instead of single-key cutover only

**Files:**
- Modify: `program_admin_console/src/server.js`
- Modify: `program_admin_console/src/entitlementSigner.js`
- Modify: `app_backend/infrastructure/program_access/entitlement_verifier.py`
- Modify: `app_backend/infrastructure/program_access/remote_control_plane_client.py`
- Test: `tests/backend/test_remote_control_plane_client.py`
- Test: `program_admin_console/tests/control-plane-server.test.js`
- Docs: `program_admin_console/README.md`

- [ ] **Step 1: Write the failing rotation tests**

Add focused tests for:
- client can continue to verify a still-valid old signature during a staged rotation
- client can fetch and accept the new signer identity before old tokens have naturally aged out
- public key publishing and cache behavior support overlap rather than abrupt cutover

- [ ] **Step 2: Run the focused tests and watch them fail**

Run:

```powershell
C:/Users/18220/Desktop/C5autobug更新接口 - 副本 (2)/.venv/Scripts/python.exe -m pytest -q tests/backend/test_remote_control_plane_client.py
npm --prefix program_admin_console run test:server
```

Expected: FAIL because current behavior assumes a single active key only.

- [ ] **Step 3: Implement an overlap rotation contract**

Implementation rules:
- Keep fail-closed signature verification
- Add overlap/transition support rather than weakening verification
- Do not expand this task into HSM/secret-vault redesign

- [ ] **Step 4: Re-run the focused tests**

Run:

```powershell
C:/Users/18220/Desktop/C5autobug更新接口 - 副本 (2)/.venv/Scripts/python.exe -m pytest -q tests/backend/test_remote_control_plane_client.py
npm --prefix program_admin_console run test:server
```

Expected: PASS


### Task 6: Distinguish "local secret/material read failure" from "user is unauthenticated"

**Files:**
- Modify: `app_backend/infrastructure/program_access/remote_entitlement_gateway.py`
- Modify: `app_backend/application/program_access.py`
- Test: `tests/backend/test_remote_entitlement_gateway.py`
- Test: `tests/backend/test_program_access_refresh_scheduler.py`
- Test: `tests/backend/test_program_auth_routes.py`

- [ ] **Step 1: Write the failing backend tests**

Add focused tests that prove:
- local refresh-token read/decrypt failure does not collapse into plain "please log in" semantics
- the system returns a dedicated recoverable failure code/message for local material read problems
- refresh scheduler and auth routes preserve that distinction

- [ ] **Step 2: Run the focused pytest set and watch it fail**

Run:

```powershell
C:/Users/18220/Desktop/C5autobug更新接口 - 副本 (2)/.venv/Scripts/python.exe -m pytest -q tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_refresh_scheduler.py tests/backend/test_program_auth_routes.py
```

Expected: FAIL because current behavior tends to fold local secret-read failure into unauthenticated state.

- [ ] **Step 3: Implement a dedicated local-material failure path**

Implementation rules:
- Keep remote auth failures and local material failures separate
- Preserve fail-closed behavior
- Do not mutate this into a broad auth-message rewrite

- [ ] **Step 4: Re-run the focused pytest set**

Run:

```powershell
C:/Users/18220/Desktop/C5autobug更新接口 - 副本 (2)/.venv/Scripts/python.exe -m pytest -q tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_refresh_scheduler.py tests/backend/test_program_auth_routes.py
```

Expected: PASS

## Chunk 4: Release Gate Completion

### Task 7: Make deployment smoke verify the real public/private boundary

**Files:**
- Modify: `program_admin_console/tools/deployProgramAdminRemote.ps1`
- Modify: `program_admin_console/tests/deploy-program-admin-remote.test.js`
- Modify: `program_admin_console/README.md`
- Review: `AGENTS.md`

- [ ] **Step 1: Write the failing deploy-smoke tests**

Add focused checks that require:
- public smoke to assert `/api/admin/*` is not exposed, not only `/admin`
- external HTTPS/auth-gateway verification to be explicit rather than silently skipped
- deploy output to make it obvious when only loopback smoke ran vs when public gateway smoke ran

- [ ] **Step 2: Run the deploy-script test and watch it fail**

Run:

```powershell
npm --prefix program_admin_console run test:deploy-script
```

Expected: FAIL because current deploy verification is too weak for the public/private boundary.

- [ ] **Step 3: Implement stricter deploy verification**

Implementation rules:
- Keep loopback-only deployments valid
- Make public-gateway verification explicit and non-ambiguous
- Do not claim full public safety when only local loopback smoke ran

- [ ] **Step 4: Re-run the deploy-script test**

Run:

```powershell
npm --prefix program_admin_console run test:deploy-script
```

Expected: PASS

## Chunk 5: Final Regression And Docs

### Task 8: Re-run secondary hardening regressions and sync docs/logs

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `README.md` (only if user-facing verification instructions must change)
- Modify: `program_admin_console/README.md`

- [ ] **Step 1: Re-run focused Node regressions**

Run:

```powershell
npm --prefix program_admin_console run test:server-runtime
npm --prefix program_admin_console run test:store
npm --prefix program_admin_console run test:server
npm --prefix program_admin_console run test:ui
npm --prefix program_admin_console run test:deploy-script
```

Expected: PASS

- [ ] **Step 2: Re-run focused backend regressions**

Run:

```powershell
C:/Users/18220/Desktop/C5autobug更新接口 - 副本 (2)/.venv/Scripts/python.exe -m pytest -q tests/backend/test_remote_control_plane_client.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_refresh_scheduler.py tests/backend/test_program_auth_routes.py
```

Expected: PASS

- [ ] **Step 3: Review documentation impact**

Check:
- whether root `README.md` launch verification wording must mention the stronger public/private membership gate
- whether `program_admin_console/README.md` needs updated proxy, gateway, or smoke guidance

If no root README changes are needed, record that it was checked and left unchanged.

- [ ] **Step 4: Update session log**

Append what was changed, how it was verified, and what still remains outside this secondary-hardening plan.

- [ ] **Step 5: Commit**

```powershell
git add docs/superpowers/plans/2026-04-28-membership-secondary-hardening.md program_admin_console app_backend tests docs/agent README.md AGENTS.md
git commit -m "fix: harden secondary membership control-plane risks"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-04-28-membership-secondary-hardening.md`. Ready to execute after the primary blocker handoff stream finishes or once a separate worker is assigned.
