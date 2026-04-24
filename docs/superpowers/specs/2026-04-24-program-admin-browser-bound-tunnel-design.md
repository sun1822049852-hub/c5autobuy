# Program Admin Browser-Bound Tunnel Design

**Goal:** Make the local `program_admin_console` connection script automatically tear down the SSH tunnel when the dedicated admin browser window is closed.

**Status:** Draft approved in chat, written spec pending user review before implementation.

## Context

Current production access posture for the remote program admin console is:

- Remote service binds only to `127.0.0.1:18787` on `8.138.39.139`
- The operator reaches `/admin` through a local SSH tunnel
- The current helper script opens the tunnel in a new PowerShell window, then launches the admin URL in the default browser

That last behavior is convenient but not lifecycle-safe. On Windows, opening a URL through the default browser often reuses an already-running browser process or existing tab/session. That means the script cannot reliably know when "this admin session is over", so it also cannot safely auto-close the SSH tunnel when the operator closes the page.

## Problem Statement

The user wants a single local action with this lifecycle:

1. Start SSH tunnel
2. Open the admin console
3. Work in the admin console
4. Close the browser window
5. SSH tunnel automatically disconnects

The unsafe part is step 4. If the script does not own the browser process, browser close events are ambiguous. Closing one tab does not mean the browser exited. Closing the visible window may still leave background processes alive. Reusing an existing browser instance makes process ownership impossible.

## Approaches Considered

### Option A: Keep default browser open behavior, guess when the page is closed

Use `Start-Process $adminUrl` as today, then poll browser processes or local port activity and try to infer whether the admin page is still open.

**Pros**

- Minimal change
- Preserves current "use whatever browser is default" behavior

**Cons**

- Unreliable on Windows
- Fails when the default browser reuses an existing process
- Can accidentally kill a tunnel that is still needed
- Hard to explain and hard to test

**Decision:** Reject.

### Option B: Launch a dedicated browser process for the admin console and bind tunnel lifetime to that process

The script explicitly launches one browser executable for this session, waits for that process to exit, and then tears down the SSH tunnel it started.

**Pros**

- Reliable ownership model
- "Close this window -> close this tunnel" maps to one actual process
- Easy to explain to the user
- Testable in dry-run and process-lifecycle focused checks

**Cons**

- Requires choosing a browser executable instead of blindly using the system default
- Slightly changes behavior if the user expected the existing browser window/session to be reused

**Decision:** Recommended.

### Option C: Launch a dedicated browser process with an isolated temporary profile

Same as option B, but also force a temporary user-data directory so the admin window is fully isolated from the user's normal browsing session.

**Pros**

- Strongest isolation
- Avoids interference from existing extensions, tabs, and session reuse

**Cons**

- More setup and cleanup logic
- More moving parts for a simple daily-use helper
- Higher chance of Windows path/cleanup edge cases

**Decision:** Not needed for the first cut.

## Chosen Design

Implement option B.

The connection script will stop treating the browser as a detached side effect. Instead, it will own two child processes:

- one SSH process for the tunnel
- one dedicated browser process for the admin window

The script will:

1. Validate local port, SSH executable, identity file, and browser executable
2. Start the SSH tunnel process
3. Wait until the local forwarded port is reachable
4. Start one dedicated browser process with the admin URL
5. Wait for that browser process to exit
6. Stop the SSH tunnel process
7. Exit cleanly

This changes the interaction model from "launch and forget" to "launch and supervise". That is required if tunnel lifetime must follow browser lifetime.

## Browser Selection Rules

Default behavior should prefer a deterministic executable, not "whatever the OS default browser does".

Initial fallback order:

1. Microsoft Edge if found
2. Google Chrome if found
3. User-supplied browser path parameter

The script should expose explicit parameters so the operator can override:

- browser executable path
- whether the browser should auto-open at all

For the first implementation, we do not require a temporary browser profile. We only require a dedicated process launch.

## Process Ownership Rules

To make shutdown reliable, the script must only kill the SSH process it started itself. It must not kill arbitrary `ssh.exe` processes.

Likewise, it should only wait on the specific browser process it launched for this admin session. It must not attach to or interfere with unrelated browser instances.

## Failure Handling

### SSH start failure

- Do not open the browser
- Print a clear error
- Exit non-zero

### Local forwarded port never becomes reachable

- Kill the started SSH process
- Print a clear error
- Exit non-zero

### Browser launch failure

- Kill the started SSH process
- Print a clear error
- Exit non-zero

### Browser exits normally

- Kill the started SSH process
- Return success

### Browser already-running reuse risk

The implementation must avoid shell-open URL behavior for the default path. It should launch the browser executable directly with the admin URL as an argument so there is a concrete process handle to supervise.

## Script UX

The user-facing behavior should be:

- Double-click `.cmd`
- Dedicated browser window opens for the admin console
- Closing that browser window ends the connection

The script should also keep a CLI mode for advanced usage:

- `-DryRun`
- `-LocalPort`
- `-NoBrowser`
- `-BrowserPath`

## Testing Strategy

This behavior change must use TDD.

Minimum test targets:

1. Failing test: direct browser launch arguments are built without using detached shell-open behavior
2. Failing test: browser process exit triggers SSH process cleanup
3. Failing test: browser launch failure triggers SSH process cleanup
4. Focused dry-run / helper verification after implementation

Given the current repository structure, the cleanest path is to extract the PowerShell script generation or lifecycle logic into testable helpers only if needed. If direct script testing is simpler, keep the implementation small and avoid over-abstracting.

## Out of Scope

These are explicitly not part of this change:

- changing the remote server binding or deployment posture
- changing `/admin` authentication logic
- changing SSH key paths on the server
- adding tray icons, installers, or Windows services
- adding temporary browser profile isolation in the first cut

## Success Criteria

The design is considered successful when:

- the user can start the admin console from one local script
- a dedicated browser window is used for that session
- closing that window causes the SSH tunnel started by the script to stop
- no remote server behavior needs to change
