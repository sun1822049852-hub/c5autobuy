# JS-Only Public Entry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收口项目对外启动口径为 JS-only，移除顶层 Python 启动壳，同时保留 JS 桌面壳内部拉起 Python backend 的既有机制。

**Architecture:** 这次只改“对外入口定义”和文档/测试口径，不改 Electron 主进程、FastAPI backend 装配、登录链、查询链、购买链和本地数据目录。Python backend 继续作为 JS 桌面壳的内部依赖存在，但不再对外宣称为独立应用入口，也不再保留顶层 Python 包装脚本。

**Tech Stack:** Python 3.11, pytest, Electron launcher scripts, FastAPI backend, Markdown docs

---

### Task 1: 锁定 JS-only 入口契约

**Files:**
- Modify: `tests/backend/test_remove_legacy_cli_entry.py`

- [ ] **Step 1: 写失败测试**

写测试锁定三件事：
- 根目录不再保留 `run_app.py` / `run_app_local_debug.py`
- `README.md` 不再把 Python 当成启动入口
- `app_backend/main.py` 不再保留直接脚本启动口

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`
Expected: FAIL，失败点落在 Python 包装入口仍存在、README 仍含 Python 启动文案、backend 仍保留直接执行入口。

### Task 2: 做最小实现

**Files:**
- Delete: `run_app.py`
- Delete: `run_app_local_debug.py`
- Modify: `app_backend/main.py`
- Modify: `README.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: 删除顶层 Python 包装入口**

只删除对外包装壳，不碰 `app_desktop_web/python_backend.js` 内部拉起 backend 的机制。

- [ ] **Step 2: 收口 backend 直接执行路径**

让 `app_backend/main.py` 继续暴露可供内部导入的 `create_app()` / `main()`，但不再作为对外 CLI 入口。

- [ ] **Step 3: 更新文档**

把 `README.md` 与 `docs/superpowers/README.md` 统一为 JS-only 口径，明确：
- 用户/日常入口：`node main_ui_node_desktop.js`
- 本地调试入口：`node main_ui_node_desktop_local_debug.js`
- Python backend 仅为桌面壳内部依赖

### Task 3: 回归与交接

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md`

- [ ] **Step 1: 跑受影响验证**

Run: `python -m pytest tests/backend/test_remove_legacy_cli_entry.py tests/backend/test_backend_main_entry.py -q`
Expected: PASS

- [ ] **Step 2: 更新会话日志与稳定记忆**

把“对外入口 JS-only，Python backend 为内部依赖”写入日志；如确认这是稳定约束，同步提炼到 `docs/agent/memory.md`。

- [ ] **Step 3: 复扫入口残留**

Run: `rg -n "python run_app|run_app.py|run_app_local_debug.py|python -m app_backend.main" README.md docs tests`
Expected: 只允许命中历史计划/历史记录，不允许命中当前主 README、当前有效说明和当前入口测试契约。
