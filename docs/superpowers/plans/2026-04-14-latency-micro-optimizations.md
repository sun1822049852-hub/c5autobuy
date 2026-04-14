# Latency Micro Optimizations Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce avoidable local overhead on the `query -> hit -> purchase` hot path without changing dedupe semantics, queue semantics, or user-visible purchase outcomes.

**Architecture:** Keep the current fast-path, `10s` dedupe window, and busy-account drop policy intact. The work only trims same-meaning but higher-cost writing patterns: move diagnostics payload shaping fully off the hot path, add a true light snapshot path that does not flush diagnostics buffers, shorten the dedupe lock critical section, and avoid building oversized temporary bucket lists during account claiming.

**Tech Stack:** Python, pytest, asyncio, threaded runtime services

---

### Task 1: Diagnostics Offload And Light Snapshot

**Files:**
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

- [ ] **Step 1: Write failing tests for diagnostics payload shaping and light snapshot behavior**
- [ ] **Step 2: Run focused tests to confirm they fail for the current hot-path behavior**
- [ ] **Step 3: Change the purchase runtime so the hot path only enqueues lightweight diagnostics jobs and status polling can skip diagnostics buffer draining**
- [ ] **Step 4: Re-run the focused tests until they pass**

### Task 2: Dedupe Inbox Lock Shrink

**Files:**
- Modify: `tests/backend/test_purchase_hit_inbox.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_hit_inbox.py`

- [ ] **Step 1: Write a failing test that proves batch object construction should happen after the dedupe lock is released**
- [ ] **Step 2: Run the focused test to confirm it fails with the current lock scope**
- [ ] **Step 3: Keep only dedupe ledger checks and expiry maintenance inside the lock, then build the purchase batch outside**
- [ ] **Step 4: Re-run the focused test until it passes**

### Task 3: Scheduler Bucket Claim Trim

**Files:**
- Modify: `tests/backend/test_purchase_scheduler.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`

- [ ] **Step 1: Write a failing test that guards against collecting more idle accounts per bucket than the limit needs**
- [ ] **Step 2: Run the focused test to confirm it fails with the current temporary-list behavior**
- [ ] **Step 3: Change bucket claiming to keep only the first needed idle accounts per bucket while preserving claim results**
- [ ] **Step 4: Re-run the focused test until it passes**

### Task 4: Verification And Session Records

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run focused regressions for the three micro-optimizations**
- [ ] **Step 2: Run broader purchase/query hot-path regressions**
- [ ] **Step 3: Update session log with the implemented latency trims and verification evidence**
