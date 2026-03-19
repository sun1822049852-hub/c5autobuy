# Remove Legacy Scan Compat Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 彻底移除 `c5_layered` 中仍直接依赖 `autobuy.py` 的 legacy 扫描兼容层，并把入口收口到 `app_frontend/app_backend`。

**Architecture:** 不再给 `LegacyScanRuntime` 续命，也不再把 `c5_layered` Tk GUI 接到新运行时服务上。`run_app.py` 直接委托 `app_frontend.main`，`c5_layered` 中所有直连 `autobuy.py` 的扫描链文件一并删除，测试改为约束“入口不再依赖 c5_layered、仓库内不再残留 legacy 扫描兼容代码”。

**Tech Stack:** Python, PySide6, FastAPI, pytest

---

## Chunk 1: 先锁定删除目标

### Task 1: 写失败测试，约束入口已切到新前后端

**Files:**
- Modify: `tests/backend/test_remove_legacy_cli_entry.py`
- Test: `tests/backend/test_remove_legacy_cli_entry.py`

- [ ] 写失败测试，断言 `run_app.main()` 直接委托 `app_frontend.main.main`
- [ ] 写失败测试，断言 `run_app.py` 源码中不再出现 `c5_layered`
- [ ] 跑 `python -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`
- [ ] 确认当前为 FAIL，且失败原因是入口仍依赖旧链路

### Task 2: 写失败测试，约束 legacy 扫描兼容文件被移除

**Files:**
- Modify: `tests/backend/test_no_legacy_runtime_dependency.py`
- Modify: `tests/backend/test_legacy_scan_runtime.py`
- Modify: `tests/backend/test_c5_layered_query_only_cleanup.py`
- Test: `tests/backend/test_no_legacy_runtime_dependency.py`
- Test: `tests/backend/test_legacy_scan_runtime.py`

- [ ] 扩大 `autobuy` 文本扫描范围到 `c5_layered`
- [ ] 写失败测试，断言 `legacy_scan_runtime.py / legacy_query_pipeline.py / legacy_bridge.py / pipeline.py / bootstrap.py` 已删除
- [ ] 清理仍依赖 `LegacyQueryPipeline` 的旧测试
- [ ] 跑 `python -m pytest tests/backend/test_no_legacy_runtime_dependency.py tests/backend/test_legacy_scan_runtime.py tests/backend/test_c5_layered_query_only_cleanup.py -q`
- [ ] 确认当前为 FAIL，且失败原因是 legacy 文件仍存在

## Chunk 2: 实际删除 legacy 扫描兼容层

### Task 3: 删除 `c5_layered` 中直连 `autobuy.py` 的扫描代码

**Files:**
- Delete: `c5_layered/bootstrap.py`
- Delete: `c5_layered/infrastructure/runtime/legacy_scan_runtime.py`
- Delete: `c5_layered/infrastructure/runtime/legacy_query_pipeline.py`
- Delete: `c5_layered/infrastructure/query/legacy_bridge.py`
- Delete: `c5_layered/infrastructure/query/pipeline.py`
- Modify: `c5_layered/infrastructure/runtime/__init__.py`
- Modify: `c5_layered/infrastructure/query/__init__.py`

- [ ] 删除 legacy 扫描运行时和桥接文件
- [ ] 收口 `__init__.py` 导出，避免再引用已删除模块
- [ ] 跑 `python -m pytest tests/backend/test_no_legacy_runtime_dependency.py tests/backend/test_legacy_scan_runtime.py -q`
- [ ] 确认删除约束变绿

### Task 4: 收口仓库入口到 `app_frontend.main`

**Files:**
- Modify: `run_app.py`
- Modify: `README.md`
- Test: `tests/backend/test_remove_legacy_cli_entry.py`

- [ ] 让 `run_app.main()` 直接调用 `app_frontend.main.main`
- [ ] 更新 README 入口描述，说明 `run_app.py` 只是前端启动包装
- [ ] 跑 `python -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`
- [ ] 确认入口测试变绿

## Chunk 3: 回归验证

### Task 5: 跑组合回归和全量测试

**Files:**
- Verify only

- [ ] 跑 `python -m pytest tests/backend/test_no_legacy_runtime_dependency.py tests/backend/test_remove_legacy_cli_entry.py tests/backend/test_legacy_scan_runtime.py tests/backend/test_c5_layered_query_only_cleanup.py -q`
- [ ] 跑 `python -m pytest -q`
- [ ] 记录剩余 warning，并确认仅为 websockets/uvicorn 弃用提示
