# Direct IP Resolution Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current single-source public IP lookup with a direct-only multi-source resolver and treat configured proxy values as the authoritative display value.

**Architecture:** Add a focused resolver service that reproduces the legacy fallback sequence for direct connections. Keep Open API binding sync responsible for selecting between direct resolution and proxy passthrough, then writing consistent account fields for backend and frontend display.

**Tech Stack:** Python, urllib, pytest

---

## Chunk 1: Tests

### Task 1: Cover direct fallback resolution and proxy passthrough

**Files:**
- Modify: `tests/backend/test_open_api_binding_sync_service.py`

- [ ] Step 1: Write failing tests for direct multi-source lookup and proxy passthrough semantics
- [ ] Step 2: Run targeted pytest command and verify failures
- [ ] Step 3: Implement the minimal production code to satisfy the tests
- [ ] Step 4: Re-run targeted pytest command and verify passes

## Chunk 2: Implementation

### Task 2: Introduce resolver and wire sync service

**Files:**
- Create: `app_backend/infrastructure/network/public_ip_resolver.py`
- Modify: `app_backend/infrastructure/browser_runtime/open_api_binding_sync_service.py`

- [ ] Step 1: Add a resolver with legacy direct-IP source ordering and public IPv4 validation
- [ ] Step 2: Update sync service to resolve direct IPs only and reuse proxy input for proxy modes
- [ ] Step 3: Keep account write-back and debug logging consistent with the new semantics

## Chunk 3: Verification

### Task 3: Run targeted verification

**Files:**
- Test: `tests/backend/test_open_api_binding_sync_service.py`

- [ ] Step 1: Run targeted pytest coverage for Open API binding sync behavior
- [ ] Step 2: Review any affected display semantics in account center payload construction
