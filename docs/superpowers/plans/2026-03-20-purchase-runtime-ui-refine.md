# Purchase Runtime UI Refine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 desktop web 购买系统页面补齐新的运行监控骨架、仓库名称展示与更清晰的商品/账号/事件布局。

**Architecture:** 先扩展购买运行时状态，补出账号当前仓库名称；再用 TDD 重写购买页组件结构，把顶部总览、商品折叠卡、账号监控表和底部事件区按已确认设计落地。整个实现保持购买链路与查询链路语义不变，只改展示与状态表达。

**Tech Stack:** Python, FastAPI, pytest, React, Vitest, Testing Library, CSS

---

## 文件结构

- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_overview.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_account_table.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_recent_events.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

## Chunk 1: 购买状态补齐

### Task 1: 仓库名称进入购买状态快照

**Files:**
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`

- [ ] **Step 1: 写失败测试，锁定 `accounts` 返回 `selected_inventory_name`**
- [ ] **Step 2: 运行定向 pytest，确认因字段缺失失败**
- [ ] **Step 3: 最小实现仓库昵称提取与 schema 扩展**
- [ ] **Step 4: 复跑定向 pytest，确认转绿**

## Chunk 2: 购买页骨架重塑

### Task 2: 用前端失败测试锁定新页面结构

**Files:**
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 写失败测试，锁定顶部运行条显示配置名、状态、runtime session 短码与摘要**
- [ ] **Step 2: 写失败测试，锁定商品区为可展开卡片并显示状态徽标**
- [ ] **Step 3: 写失败测试，锁定账号表显示仓库名称与占用**
- [ ] **Step 4: 写失败测试，锁定事件区与右下角悬浮动作条的新布局**
- [ ] **Step 5: 运行前端定向测试，确认因现有 UI 结构不匹配而失败**

### Task 3: 最小实现购买页新骨架

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_overview.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_account_table.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_recent_events.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] **Step 1: 实现 header 总览条与状态文案映射**
- [ ] **Step 2: 实现商品折叠卡与展开详情**
- [ ] **Step 3: 实现账号表仓库名称/占用/件数展示**
- [ ] **Step 4: 实现事件区与右下角动作条布局**
- [ ] **Step 5: 复跑前端定向测试，确认转绿**

## Chunk 3: 回归验证

### Task 4: 跑全量相关回归

**Files:**
- Modify: none

- [ ] **Step 1: 运行后端定向回归**
- [ ] **Step 2: 运行前端购买页测试**
- [ ] **Step 3: 运行前端全量测试**
- [ ] **Step 4: 检查 `git diff`，确认仅包含购买状态与购买页改动**
