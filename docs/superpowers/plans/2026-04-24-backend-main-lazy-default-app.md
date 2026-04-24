# Backend Main Lazy Default App Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 去掉 `app_backend.main` 在模块导入阶段的默认 app 立即构建，避免桌面 embedded backend 冷启动重复建 app。

**Architecture:** 保留 `create_app()` 与 `main()` 现有外部契约，但把默认 `app` 从模块顶层实例改成懒加载访问。这样桌面入口导入 `app_backend.main` 时不再先做一次完整装配，只有显式访问 `backend_main.app` 或 ASGI server 取 `app` 时才构建默认实例。

**Tech Stack:** Python 3.11、FastAPI、pytest、Vitest

---

## Chunk 1: Lazy App Contract

### Task 1: 锁定 backend main 的懒加载契约

**Files:**
- Modify: `tests/backend/test_backend_main_entry.py`
- Modify: `app_backend/main.py`

- [ ] **Step 1: 写 failing test，证明导入 `app_backend.main` 后访问 `backend_main.app` 才触发 `create_app()`**
- [ ] **Step 2: 跑 focused pytest，确认当前顶层 `app = create_app()` 让测试失败**
  Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_backend_main_entry.py -q`
- [ ] **Step 3: 最小实现 lazy default app（保留 `create_app()` / `main()` 现有入口）**
- [ ] **Step 4: 重跑 focused pytest，确认转绿**

## Chunk 2: Regression Verification

### Task 2: 校准桌面 backend 启动验证

**Files:**
- Modify: `app_desktop_web/tests/electron/python_backend.test.js`（如需补契约）
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: 跑 backend 受影响回归**
  Run: `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_backend_main_entry.py tests/backend/test_desktop_web_backend_bootstrap.py -q`
- [ ] **Step 2: 跑 electron 受影响回归**
  Run: `npm --prefix app_desktop_web test -- tests/electron/python_backend.test.js --run`
- [ ] **Step 3: 如测试需要，补最小契约断言并重跑**
- [ ] **Step 4: 更新 `docs/agent/session-log.md` 记录本轮改动与验证结果**
