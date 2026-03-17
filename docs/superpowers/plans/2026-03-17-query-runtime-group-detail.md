# Query Runtime Group Detail Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在查询运行页新增“查询组明细”表，展示每个账号每种查询方式的运行状态，同时保持现有查询控制链路不变。

**Architecture:** 后端在查询运行状态快照中新增 `group_rows`，由 `ModeRunner` 产出单组状态、`QueryTaskRuntime` 负责聚合；前端在查询运行面板中新增只读表格并通过 formatter 输出中文文案。

**Tech Stack:** Python, FastAPI, PySide6, pytest

---

## 文件结构

- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/api/schemas/query_runtime.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Modify: `app_frontend/app/formatters/query_runtime_display.py`
- Modify: `app_frontend/app/widgets/query_runtime_panel.py`
- Modify: `tests/frontend/test_query_runtime_panel.py`

## Task 1: 先写后端失败测试

- [ ] 为 `QueryRuntimeService` 增加 `group_rows` 断言
- [ ] 为 `/query-runtime/status` 路由增加 `group_rows` 断言
- [ ] 运行定向测试，确认因缺字段而失败

## Task 2: 最小实现后端 `group_rows`

- [ ] 在 `ModeRunner.snapshot()` 生成单模式查询组状态
- [ ] 在 `QueryTaskRuntime.snapshot()` 聚合全部模式的 `group_rows`
- [ ] 在 `QueryRuntimeService` 和 schema 中规范化该字段
- [ ] 复跑后端定向测试

## Task 3: 先写前端失败测试

- [ ] 为 `QueryRuntimePanel` 新增查询组明细表渲染测试
- [ ] 运行前端定向测试，确认因表格/文案缺失而失败

## Task 4: 最小实现前端明细表

- [ ] 在 formatter 中新增 `build_group_rows`
- [ ] 在 panel 中新增 `group_table`
- [ ] 加载并渲染 `group_rows`
- [ ] 复跑前端定向测试

## Task 5: 完整验证

- [ ] 运行查询相关后端与前端测试
- [ ] 运行全量测试
- [ ] 按验证结果汇报

注：本计划不包含 git 提交。
