# Program Admin Browser-Bound Tunnel Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the local `program_admin_console` connection helper so it launches a dedicated browser window for `/admin` and automatically tears down the SSH tunnel when that browser window closes.

**Architecture:** Keep the remote server posture unchanged and only modify the local Windows helper scripts. Replace the current "detached tunnel PowerShell + shell-open default browser" behavior with a supervised flow that starts one SSH child process and one dedicated browser child process, waits for the browser to exit, then stops only the SSH process it created. Use Node-based tests that execute the PowerShell script with fake `ssh` and fake browser wrappers so the lifecycle can be verified without touching the real server.

**Tech Stack:** PowerShell 5.1, Windows OpenSSH client, Node.js CommonJS test runner, batch wrappers

---

## Chunk 1: Lock The New Script Contract With Failing Tests

### Task 1: Add focused script tests before any PowerShell changes

**Files:**
- Modify: `program_admin_console/package.json`
- Create: `program_admin_console/tests/connect-program-admin-console.test.js`

- [ ] **Step 1: Write the failing tests**

Add a new Node test file that covers:

- dry-run now reports a concrete browser executable path and direct browser args instead of only a shell-open URL
- when the script launches a fake browser process that exits, the fake SSH process started by the script is stopped too
- when browser launch fails, the started fake SSH process is cleaned up before the script exits non-zero

Test harness shape:

- create a temp directory per test
- generate a fake `ssh.cmd` wrapper that:
  - parses the incoming `-L <localPort>:127.0.0.1:<remotePort>` argument
  - starts a tiny PowerShell TCP listener on that local port
  - writes a marker file when started
  - stays alive until killed
- generate a fake `browser.cmd` wrapper that:
  - writes a marker file
  - optionally sleeps briefly and exits
- run `connectProgramAdminConsole.ps1` through `powershell.exe -File ...`
- assert on exit code, marker files, and whether the local port is still reachable after browser exit

- [ ] **Step 2: Run the new test file to verify it fails**

Run:

```bash
node program_admin_console/tests/connect-program-admin-console.test.js
```

Expected: FAIL because the current script does not resolve/print a browser executable, does not supervise browser lifetime, and does not own SSH cleanup on browser exit.

## Chunk 2: Implement Browser-Bound Tunnel Lifecycle

### Task 2: Replace detached shell-open behavior with supervised child processes

**Files:**
- Modify: `program_admin_console/tools/connectProgramAdminConsole.ps1`
- Modify: `program_admin_console/tools/connectProgramAdminConsole.cmd`

- [ ] **Step 1: Implement deterministic browser resolution**

Modify `connectProgramAdminConsole.ps1` so it:

- adds `-BrowserPath` as an explicit override
- resolves a concrete browser executable in this order:
  - explicit `-BrowserPath`
  - Edge common install path(s)
  - Chrome common install path(s)
- throws a clear error if no browser executable can be found when browser auto-open is enabled

Implementation notes:

- do not use shell-open URL behavior for the default path
- keep `-NoBrowser` working for tunnel-only mode
- extend `-DryRun` output to include `BROWSER_PATH` and `BROWSER_ARGS`

- [ ] **Step 2: Replace the extra PowerShell holder window with direct SSH process ownership**

Modify `connectProgramAdminConsole.ps1` so it:

- starts `ssh.exe` directly via `Start-Process -PassThru`
- keeps the returned process handle
- waits for the forwarded local port to become reachable before launching the browser
- stops only that SSH process on any later failure

Implementation notes:

- add an optional `-SshPath` override so tests can inject a fake `ssh.cmd`
- keep existing checks for local port conflicts and identity-file existence
- do not kill unrelated `ssh.exe` instances

- [ ] **Step 3: Bind tunnel lifetime to the dedicated browser process**

Continue modifying `connectProgramAdminConsole.ps1` so it:

- launches the resolved browser executable directly with the admin URL
- keeps the returned browser process handle
- waits for that exact browser process to exit
- then stops the SSH process and exits cleanly

Implementation notes:

- the default behavior should now be "one script invocation owns one browser process + one SSH process"
- if browser launch fails after SSH already started, stop SSH before returning non-zero
- `connectProgramAdminConsole.cmd` should remain a thin wrapper around the `.ps1`, not a second lifecycle owner

- [ ] **Step 4: Run the focused test file to verify it passes**

Run:

```bash
node program_admin_console/tests/connect-program-admin-console.test.js
```

Expected: PASS

## Chunk 3: Focused Verification And Docs Sync

### Task 3: Re-run script verification and update docs

**Files:**
- Modify: `program_admin_console/README.md`
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if the new browser-bound behavior becomes a stable long-term operational rule)

- [ ] **Step 1: Re-run script dry-run verification**

Run:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1 -DryRun -NoBrowser
powershell -NoProfile -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -Command "& 'program_admin_console/tools/connectProgramAdminConsole.cmd' -DryRun -NoBrowser"
```

Expected:

- dry-run succeeds in all three commands
- output includes `SSH_PATH`, `SSH_ARGS`, `ADMIN_URL`
- browser-enabled dry-run also includes `BROWSER_PATH` / `BROWSER_ARGS`

- [ ] **Step 2: Update README usage**

Modify `program_admin_console/README.md` so it explicitly says:

- the script now launches a dedicated browser window for the admin console
- closing that window ends the connection
- `-BrowserPath`, `-NoBrowser`, and `-LocalPort` are the main operator-facing switches

- [ ] **Step 3: Update session log**

Append implementation and fresh verification evidence to `docs/agent/session-log.md`.

- [ ] **Step 4: Update memory only if needed**

If the dedicated-browser shutdown behavior becomes the stable recommended operating mode for all future sessions, add one concise memory entry. If it is just a local helper implementation detail, leave `docs/agent/memory.md` unchanged.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-24-program-admin-browser-bound-tunnel-design.md docs/superpowers/plans/2026-04-24-program-admin-browser-bound-tunnel.md program_admin_console/tools/connectProgramAdminConsole.ps1 program_admin_console/tools/connectProgramAdminConsole.cmd program_admin_console/tests/connect-program-admin-console.test.js program_admin_console/package.json program_admin_console/README.md docs/agent/session-log.md docs/agent/memory.md
git commit -m "feat: bind admin tunnel lifetime to browser window"
```
