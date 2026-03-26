# Account Query Mode Status Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让账号中心把 API 查询与浏览器查询展示为独立的启用状态，并支持 `IP失效`、`手动禁用` 等禁用原因。

**Architecture:** 后端继续复用现有 `new_api_enabled`、`fast_api_enabled`、`token_enabled` 三个持久化布尔字段，不新增数据库列；账号中心 contract 改为返回派生后的 API/浏览器查询状态与禁用原因。前端账号表新增两个并列状态区，API 一键联动两个 API mode，浏览器查询单独联动 `token_enabled`，同时保留 API Key 编辑入口。

**Tech Stack:** Python, FastAPI, pytest, React, Vitest, Testing Library

---

## Chunk 1: Backend TDD

### Task 1: 先写后端失败测试，锁定状态机与返回 contract

**Files:**
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_account_center_routes.py`
- Modify: `tests/backend/test_account_routes.py`
- Modify: `tests/backend/test_account_query_mode_settings.py`

- [ ] 为 `499103/IP白名单` 补失败测试，锁定命中后同时持久禁用 `new_api_enabled` 与 `fast_api_enabled`，并记录禁用原因。
- [ ] 为手动切换 API 与浏览器查询补失败测试，锁定：
  - API 打开 = `new_api_enabled=True` 且 `fast_api_enabled=True`
  - API 关闭 = 两个 API mode 同时关闭，并写入 `manual_disabled`
  - 浏览器打开/关闭只联动 `token_enabled`，并写入/清除浏览器禁用原因
- [ ] 为账号中心路由补失败测试，锁定返回：
  - API 状态文本：`已启用` / `已禁用`
  - API 禁用原因：`IP失效` / `手动禁用` / `未配置`
  - 浏览器状态文本：`已启用` / `已禁用`
  - 浏览器禁用原因：`手动禁用` / `未登录`
- [ ] 运行聚焦 pytest，确认因为字段或联动缺失而失败。

## Chunk 2: Backend Implementation

### Task 2: 最小实现后端状态派生与查询模式写回

**Files:**
- Modify: `app_backend/api/schemas/account_center.py`
- Modify: `app_backend/api/routes/accounts.py`
- Modify: `app_backend/api/schemas/accounts.py`
- Modify: `app_backend/application/use_cases/update_account_query_modes.py`
- Modify: `app_backend/infrastructure/query/runtime/api_key_status.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

- [ ] 为账号中心新增 API/浏览器查询状态与禁用原因字段。
- [ ] 扩展 `/accounts/{id}/query-modes`，支持显式接收 API 与浏览器的禁用原因，并在 API 开关写入时强制同步两个 API mode。
- [ ] 将 `499103/IP白名单` 改成账号级禁用：自动关闭两个 API mode，并写入 `ip_invalid`。
- [ ] 移除 API 查询成功自动清除 `IP失效` 的行为，改为只允许用户手动重新启用后清理。
- [ ] 复跑聚焦 pytest，让后端 contract 转绿。

## Chunk 3: Frontend TDD

### Task 3: 先写前端失败测试，锁定账号表新布局与交互

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`
- Modify: `app_desktop_web/tests/renderer/account_center_client.test.js`

- [ ] 为账号表补失败测试，锁定 API 与浏览器查询并列显示，且文案为 `已启用` / `已禁用 (原因)`。
- [ ] 为点击 API/浏览器切换补失败测试，锁定请求发送到 `/accounts/{id}/query-modes`，并保留 API Key 编辑入口。
- [ ] 为 client 补失败测试，锁定新的 query mode 请求 payload。
- [ ] 运行聚焦 vitest，确认因为缺少字段或交互而失败。

## Chunk 4: Frontend Implementation

### Task 4: 最小实现 client、hook、table 与样式

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Modify: `app_desktop_web/src/features/account-center/components/account_table.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] 在 client 中新增/更新 query mode 切换接口。
- [ ] 在 hook 中接入 API 与浏览器查询切换，并写入操作日志。
- [ ] 在表格中改成两个并列状态区，API 区保留“编辑 key”入口。
- [ ] 为禁用状态显示原因括号，样式沿用现有 pill 体系。
- [ ] 复跑聚焦 vitest，让前端交互转绿。

## Chunk 5: Verification

### Task 5: 聚焦验收与提交

**Files:**
- Test: `tests/backend/test_query_runtime_service.py`
- Test: `tests/backend/test_account_center_routes.py`
- Test: `tests/backend/test_account_routes.py`
- Test: `tests/backend/test_account_query_mode_settings.py`
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`
- Test: `app_desktop_web/tests/renderer/account_center_client.test.js`

- [ ] 运行聚焦 pytest。
- [ ] 运行聚焦 vitest。
- [ ] 运行 `npm --prefix app_desktop_web run build`。
- [ ] 检查 `git diff --stat`，确认只包含本劫改动后提交。
