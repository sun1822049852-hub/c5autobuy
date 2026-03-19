# Purchase Query Runtime Linkage Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让查询运行时在没有任何可用购买账号时立即停机并清空积压，在购买账号恢复后自动重新开始查询。

**Architecture:** 购买运行时负责维护“是否存在可用购买账号”的事实，并在状态从有到无、从无到有时通过回调通知查询运行时；查询运行时负责记录因购买池清空而暂停的配置，并在恢复时自动拉起同一配置。购买队列清理由购买调度器承担，避免把积压状态散落在查询侧。

**Tech Stack:** Python, FastAPI, pytest

---

## 文件结构

- Modify: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`

## Task 1: 先写运行时联动失败测试

- [ ] 为 `PurchaseRuntimeService` 增加“最后一个可用购买账号消失时清空队列”的测试
- [ ] 为 `QueryRuntimeService` 增加“购买池归零时停查询并记录待恢复配置”的测试
- [ ] 为 `QueryRuntimeService` 增加“购买账号恢复后自动重启同一配置”的测试
- [ ] 为查询启动路由增加“没有可用购买账号时拒绝启动”的测试
- [ ] 运行定向测试，确认因缺少联动逻辑而失败

## Task 2: 最小实现购买运行时可用性状态机

- [ ] 在 `PurchaseScheduler` 增加队列清理能力
- [ ] 在 `PurchaseRuntimeService` 默认运行时中跟踪可用购买账号数量变化
- [ ] 在可用账号从大于 0 变为 0 时清空积压并发出停机通知
- [ ] 在可用账号从 0 变为大于 0 时发出恢复通知
- [ ] 复跑购买运行时定向测试

## Task 3: 最小实现查询运行时暂停与自动恢复

- [ ] 在 `QueryRuntimeService` 中记录因购买池清空而暂停的配置 ID
- [ ] 区分“用户主动停止查询”与“因购买池清空被动暂停”
- [ ] 在购买账号恢复通知到达时自动重启待恢复配置
- [ ] 在查询启动前增加“必须存在可用购买账号”的门禁
- [ ] 复跑查询运行时与路由定向测试

## Task 4: 完整验证

- [ ] 运行购买/查询运行时相关后端测试
- [ ] 运行 `pytest -q`
- [ ] 按实际结果汇报通过项与剩余风险

注：本计划不包含 git 提交、分支或 worktree。
