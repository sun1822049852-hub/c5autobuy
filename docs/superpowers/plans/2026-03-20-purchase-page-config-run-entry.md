# Purchase Page Config Run Entry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让购买页成为唯一的“选择配置 / 切换配置 / 开始扫货”入口，并强制无配置时不能启动查询与购买。

**Architecture:** 保留查询系统对配置的编辑与保存能力，但移除查询页运行按钮。购买页新增独立配置选择弹窗，启动时通过购买页选中的配置驱动整条查询+购买链路，后端由 `/purchase-runtime/start` 委托 `query_runtime_service.start(config_id)`，从而复用现有 session 复用与联动停止逻辑。前后端都加门禁，避免再出现“未绑定查询配置却运行中”的状态。

**Tech Stack:** FastAPI, Python, pytest, React, Vitest, Testing Library, CSS

---

## 文件结构

- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Modify: `app_backend/application/use_cases/start_purchase_runtime.py`
- Modify: `app_backend/application/use_cases/stop_purchase_runtime.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_config_selector_dialog.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/features/query-system/components/query_save_bar.jsx`
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

## Chunk 1: 后端运行入口改为“带配置启动”

### Task 1: 为购买运行入口加配置门禁并委托查询运行时启动

**Files:**
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Modify: `app_backend/application/use_cases/start_purchase_runtime.py`
- Modify: `app_backend/application/use_cases/stop_purchase_runtime.py`

- [ ] **Step 1: 写失败测试，锁定 `/purchase-runtime/start` 需要 `config_id`**
- [ ] **Step 2: 写失败测试，锁定启动成功后状态里带所选配置**
- [ ] **Step 3: 运行定向 pytest，确认 RED**
- [ ] **Step 4: 最小实现 request schema 与 start/stop use case 委托 `query_runtime_service`**
- [ ] **Step 5: 复跑定向 pytest，确认 GREEN**

## Chunk 2: 购买页承担选择配置与切换配置

### Task 2: 前端测试先锁定购买页配置选择交互

**Files:**
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 写失败测试，锁定 `startPurchaseRuntime(configId)` 发送 `config_id`**
- [ ] **Step 2: 写失败测试，锁定未选配置时开始扫货禁用并显示“选择配置”**
- [ ] **Step 3: 写失败测试，锁定购买页可通过弹窗选择配置后开始扫货**
- [ ] **Step 4: 写失败测试，锁定运行中按钮文案切为“切换配置”**
- [ ] **Step 5: 运行前端定向测试，确认 RED**

### Task 3: 实现购买页配置选择与切换入口

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Create: `app_desktop_web/src/features/purchase-system/components/purchase_config_selector_dialog.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] **Step 1: 最小实现购买页配置列表加载与本地选择状态**
- [ ] **Step 2: 实现中间弹窗“选择配置 / 切换配置”**
- [ ] **Step 3: 实现开始扫货时传入选中 `config_id`**
- [ ] **Step 4: 无配置时禁用开始扫货并给出清晰状态文案**
- [ ] **Step 5: 复跑购买页与 client 定向测试，确认 GREEN**

## Chunk 3: 查询页只保留配置管理

### Task 4: 移除查询页运行按钮

**Files:**
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/features/query-system/components/query_save_bar.jsx`
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: 写失败测试，锁定查询页不再显示启动/停止当前配置按钮**
- [ ] **Step 2: 运行定向 query page 测试，确认 RED**
- [ ] **Step 3: 最小实现移除运行按钮与相关 props**
- [ ] **Step 4: 复跑 query page 定向测试，确认 GREEN**

## Chunk 4: 回归验证

### Task 5: 跑完整相关回归

**Files:**
- Modify: none

- [ ] **Step 1: 运行后端购买运行时定向测试**
- [ ] **Step 2: 运行前端购买页与查询页定向测试**
- [ ] **Step 3: 运行前端全量测试**
- [ ] **Step 4: 检查 `git diff --stat`，确认改动只围绕运行入口与购买页配置选择**
