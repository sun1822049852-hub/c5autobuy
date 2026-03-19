# Purchase Config Inventory Refresh Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让账号中心的购买配置抽屉支持手动刷新仓库、显示自动刷新剩余时间，并显式展示当前选中仓库的占用情况。

**Architecture:** 保持购买 runtime 现有恢复计时逻辑不变，只把 `recovery_due_at` 通过库存详情接口暴露给前端，并新增一个按账号触发的手动库存刷新入口。React 抽屉继续通过库存详情接口驱动显示，新增刷新按钮和倒计时文本，不把刷新逻辑搬到前端本地。

**Tech Stack:** Python, FastAPI, pytest, React, Vitest, Testing Library

---

## Chunk 1: Backend Contract

### Task 1: 先写购买库存详情扩展与手动刷新路由的失败测试

**Files:**
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`

- [ ] 为库存详情路由补失败测试，锁定返回：
  - `auto_refresh_due_at`
  - `auto_refresh_remaining_seconds`
  - 当前仓库行仍保留 `inventory_num/inventory_max`
- [ ] 为手动刷新路由补失败测试，锁定：
  - `POST /purchase-runtime/accounts/{account_id}/inventory/refresh`
  - 成功后返回最新库存详情
  - 刷新后会更新 `refreshed_at` 与仓库占用数据
- [ ] 运行定向 pytest，确认因为缺少字段或缺少刷新路由而失败。

## Chunk 2: Backend Implementation

### Task 2: 最小实现 runtime/detail/route

**Files:**
- Create: `app_backend/application/use_cases/refresh_purchase_runtime_inventory_detail.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

- [ ] 在库存详情 schema 中补 `auto_refresh_due_at` 与 `auto_refresh_remaining_seconds`。
- [ ] 在 runtime service 中统一构建库存详情时补充自动刷新时间线。
- [ ] 新增按账号手动刷新库存的方法，优先复用现有网关与 snapshot 持久化逻辑。
- [ ] 新增手动刷新路由并返回刷新后的库存详情。
- [ ] 复跑定向 pytest，让后端 contract 转绿。

## Chunk 3: Frontend TDD

### Task 3: 先写抽屉失败测试

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`

- [ ] 为购买配置抽屉补失败测试，锁定：
  - 展示当前仓库占用 `900/1000`
  - 展示自动刷新剩余时间
  - 点击“手动刷新仓库”会请求新接口并刷新抽屉内容
- [ ] 运行定向 vitest，确认因为按钮/文案/请求缺失而失败。

## Chunk 4: Frontend Implementation

### Task 4: 最小实现 client 与 drawer

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/account-center/drawers/purchase_config_drawer.jsx`
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`

- [ ] 在 client 中新增手动刷新库存接口。
- [ ] 在页面层把购买配置抽屉的手动刷新动作接到现有详情加载状态。
- [ ] 在 drawer 中新增：
  - 手动刷新按钮
  - 自动刷新剩余时间文本
  - 当前仓库占用展示
- [ ] 复跑 renderer 测试，让前端交互转绿。

## Chunk 5: Verification

### Task 5: 聚焦验收

**Files:**
- Test: `tests/backend/test_purchase_runtime_routes.py`
- Test: `tests/backend/test_purchase_runtime_service.py`
- Test: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`

- [ ] 运行聚焦 pytest。
- [ ] 运行聚焦 vitest。
- [ ] 运行 `npm --prefix app_desktop_web run build` 确认桌面 renderer 构建成功。
