# Remove Legacy CLI Entry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 `c5_layered` 和 `run_app.py` 中彻底移除旧版 `autobuy.py` CLI 启动入口。

**Architecture:** 这次只清理旧版 CLI 启动链路，不改 `LegacyScanRuntime` 扫描兼容层。`run_app.py` 只保留 GUI 入口；`build_container()`、GUI 主窗口和 runtime 包导出都去掉 `LegacyCliRuntime`；相关协议和实现文件一起删除。

**Tech Stack:** Python, tkinter, pytest

---

## Chunk 1: 锁定对外入口删除语义

### Task 1: 先写失败测试，确认 CLI 入口仍在

**Files:**
- Create: `tests/backend/test_remove_legacy_cli_entry.py`
- Modify: `tests/backend/test_no_legacy_runtime_dependency.py`

- [ ] **Step 1: 写失败测试，锁定 `run_app.py` 不再支持 `--mode cli`**
- [ ] **Step 2: 写失败测试，锁定 `c5_layered.bootstrap.build_container()` 不再暴露 `cli_runtime`**
- [ ] **Step 3: 写失败测试，锁定 `c5_layered` runtime 包不再导出 `LegacyCliRuntime`**
- [ ] **Step 4: 运行定向测试，确认按“旧版 CLI 入口仍存在”失败**

## Chunk 2: 最小实现删除旧版 CLI 入口

### Task 2: 删掉 runtime 和 GUI/容器接线

**Files:**
- Delete: `c5_layered/infrastructure/runtime/legacy_cli_runtime.py`
- Modify: `c5_layered/infrastructure/runtime/__init__.py`
- Modify: `c5_layered/bootstrap.py`
- Modify: `c5_layered/presentation/gui/app.py`
- Modify: `c5_layered/application/ports/runtime.py`
- Modify: `c5_layered/application/ports/__init__.py`
- Modify: `c5_layered/application/__init__.py`
- Modify: `run_app.py`
- Modify: `README.md`

- [ ] **Step 1: 删除 `LegacyCliRuntime` 文件**
- [ ] **Step 2: 去掉 runtime 包导出和应用层协议暴露**
- [ ] **Step 3: 去掉 `build_container()` 的 `cli_runtime` 成员**
- [ ] **Step 4: 去掉 GUI 顶栏按钮、构造参数和 `launch_legacy_cli()` 方法**
- [ ] **Step 5: 把 `run_app.py` 收成仅 GUI 入口**
- [ ] **Step 6: 更新 README 中关于 CLI 兼容入口的描述**

## Chunk 3: 验证

### Task 3: 跑删除后的回归

**Files:**
- No file changes required

- [ ] **Step 1: 运行定向测试**
- [ ] **Step 2: 运行全量测试**
- [ ] **Step 3: 汇报删除结果与剩余直接 `autobuy.py` 依赖点**
