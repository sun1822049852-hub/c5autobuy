# Query Hit Readonly Sharing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove one more query-side hit-payload clone when forwarding matched items into the purchase path, without weakening payload isolation for generic sinks.

**Architecture:** Keep `ModeRunner` conservative by default: generic hit sinks still receive a detached copy. Only sinks that explicitly advertise readonly-safe sharing should receive the already-serialized payload object directly. Purchase runtime hit entrypoints will advertise that contract, letting the query-to-purchase bridge skip one clone on the hottest path.

**Tech Stack:** Python, pytest, asyncio, threaded runtime bridge

---

### Task 1: Encode Sharing Contract In Tests

**Files:**
- Modify: `tests/backend/test_mode_execution_runner.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: Write a failing test showing readonly-safe hit sinks receive the original serialized payload**
- [ ] **Step 2: Write a failing test showing ordinary hit sinks still receive a detached copy**
- [ ] **Step 3: Write a failing test showing purchase runtime hit entrypoints advertise readonly-safe sharing**
- [ ] **Step 4: Run the focused tests and confirm they fail with the current clone-always behavior**

### Task 2: Implement Safe Sharing

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

- [ ] **Step 1: Teach the query mode runner to detect readonly-safe hit sinks**
- [ ] **Step 2: Reuse the serialized payload only for those sinks**
- [ ] **Step 3: Mark purchase runtime hit entrypoints as readonly-safe consumers**
- [ ] **Step 4: Re-run the focused tests until they pass**

### Task 3: Verify And Record

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run targeted query/purchase bridge regressions**
- [ ] **Step 2: Run broader hot-path regressions**
- [ ] **Step 3: Update the session log with the readonly-sharing optimization and evidence**
