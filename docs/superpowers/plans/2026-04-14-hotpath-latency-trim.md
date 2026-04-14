# Hotpath Latency Trim Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trim remaining local overhead on the `query -> hit -> purchase` hot path without changing user-facing behavior.

**Architecture:** Keep the existing fast-path and queue semantics intact, but remove redundant local work in three places: repeated query hit serialization, drain-thread event-loop bridging, and session checks that depend on stats snapshots. Each change stays inside the current runtime boundaries and is guarded by regression tests.

**Tech Stack:** Python, pytest, threaded runtimes, asyncio bridges

---

### Task 1: Query Event Serialization Reuse

**Files:**
- Modify: `tests/backend/test_mode_execution_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run the focused test and confirm it fails for repeated serialization**
- [ ] **Step 3: Reuse one serialized query event payload across hit/event fan-out**
- [ ] **Step 4: Re-run the focused test until it passes**

### Task 2: Drain Worker Loop Bridge Removal

**Files:**
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run the focused test and confirm it fails when `asyncio.run` is forbidden**
- [ ] **Step 3: Move drain-thread dispatching onto a synchronous helper so the thread stops creating event loops**
- [ ] **Step 4: Re-run the focused test until it passes**

### Task 3: Session Check Snapshot Bypass

**Files:**
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run the focused test and confirm it fails when session checks touch stats snapshot**
- [ ] **Step 3: Cache bound query-session identity on the purchase runtime and use it for queue session checks**
- [ ] **Step 4: Re-run the focused test until it passes**

### Task 4: Verification And Session Records

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run focused regressions for the three hot-path changes**
- [ ] **Step 2: Run broader purchase/query hot-path regressions**
- [ ] **Step 3: Update session log with implemented optimizations and verification evidence**
