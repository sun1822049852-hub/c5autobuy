# Hit Payload Ownership Trim Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove one avoidable hit-payload clone from the purchase hot path without changing queue semantics or purchase behavior.

**Architecture:** Keep the purchase runtime's ownership boundary explicit. Direct hit handling paths (`query -> hit -> purchase`) should read the caller's hit payload directly because they finish within the same call, while the background queue intake path must still own a detached copy because processing continues after the caller returns.

**Tech Stack:** Python, pytest, threaded purchase runtime, asyncio bridge

---

### Task 1: Encode Ownership Expectations In Tests

**Files:**
- Modify: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: Write a failing test for the direct purchase path reusing the caller payload**
- [ ] **Step 2: Write a failing test for the fast purchase path reusing the caller payload**
- [ ] **Step 3: Write a failing test for the queued intake path keeping its own payload copy**
- [ ] **Step 4: Run the focused tests and confirm they fail with the current clone-everything behavior**

### Task 2: Trim Direct-Path Clones

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Test: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: Keep queued intake cloning for background ownership**
- [ ] **Step 2: Remove the extra payload clone from the direct and fast hit paths**
- [ ] **Step 3: Re-run the focused tests until they pass**

### Task 3: Verify And Record

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run targeted purchase runtime regressions**
- [ ] **Step 2: Run broader query-to-purchase hot-path regressions**
- [ ] **Step 3: Update the session log with the ownership-boundary optimization and test evidence**
