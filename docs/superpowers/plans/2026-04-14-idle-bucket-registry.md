# Idle Bucket Registry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the purchase scheduler's hot-path global available-account scan with per-bucket standing idle queues so matched hits can claim ready accounts directly.

**Architecture:** Keep existing purchase behavior intact: accounts still announce availability, per-bucket fanout limits still apply, and max inflight-per-account still works. The change is only in the ready-account registry: instead of scanning the global available list on each hit, the scheduler will maintain per-bucket idle queues that are updated when accounts become available, recover inventory, release inflight work, or change capacity.

**Tech Stack:** Python, pytest, threaded purchase scheduler/runtime

---

### Task 1: Lock In The New Hot-Path Contract

**Files:**
- Modify: `tests/backend/test_purchase_scheduler.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: Write a failing scheduler test proving bucket claims do not touch the global available-account list**
- [ ] **Step 2: Write a failing runtime test proving the fast purchase path can still claim accounts when the global available-account list is guarded**
- [ ] **Step 3: Run the focused tests and confirm they fail with the current scan-based hot path**

### Task 2: Build The Standing Idle Bucket Registry

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`

- [ ] **Step 1: Add per-bucket idle queues and queue-membership tracking**
- [ ] **Step 2: Update account register / available / unavailable / release / inflight-capacity transitions to maintain the idle queues**
- [ ] **Step 3: Replace bucket claim scanning with direct per-bucket queue pops while preserving per-bucket limits and inflight behavior**
- [ ] **Step 4: Re-run the focused tests until they pass**

### Task 3: Verify And Record

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run targeted scheduler and purchase-runtime regressions**
- [ ] **Step 2: Run broader query-to-purchase hot-path regressions**
- [ ] **Step 3: Update the session log with the idle bucket registry rollout and evidence**
