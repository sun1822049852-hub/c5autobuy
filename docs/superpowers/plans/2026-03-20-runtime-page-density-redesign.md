# Runtime Page Density Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按已确认 spec 重排 desktop web 的账号中心、查询系统、购买系统页面，移除三页 Hero 大标题区，并把购买页改成“紧凑运行栏 + 平铺商品监控行 + 次级辅助区”的结构，同时不改任何运行逻辑。

**Architecture:** 本轮只改 renderer 组件结构、可访问性标记和 CSS，不改 hook 的运行语义，不新增后端字段。先用 Vitest 锁定三页新布局契约，再分别压缩账号中心和查询页头部，最后重排购买页顶部栏、商品行和辅助区，确保悬浮 `开始扫货 / 停止扫货` 继续按原逻辑工作。

**Tech Stack:** React 19, Vitest, Testing Library, CSS

---

## 文件结构

- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/features/query-system/components/query_workbench_header.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Modify: `app_desktop_web/src/styles/app.css`

## Chunk 1: 用前端测试锁定新布局契约

### Task 1: 更新账号中心页面测试，锁定“无 Hero、工具区承载状态与刷新”

**Files:**
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] **Step 1: 写失败断言，移除对 `C5 账号中心` Hero 标题的依赖**
- [ ] **Step 2: 写失败断言，锁定页面直接进入概览卡、工具栏、表格、状态带**
- [ ] **Step 3: 写失败断言，锁定 `后端状态：ready` 与 `刷新` 仍在可见工具区**
- [ ] **Step 4: 运行定向测试，确认 RED**
Run: `cd app_desktop_web && npm test -- tests/renderer/account_center_page.test.jsx`
Expected: FAIL with old hero-based expectations or missing compact toolbar state
- [ ] **Step 5: 提交测试基线**
```bash
git add app_desktop_web/tests/renderer/account_center_page.test.jsx
git commit -m "test(desktop-ui): lock compact account center layout"
```

### Task 2: 更新查询系统页面测试，锁定“无 Hero、工作台直接入场”

**Files:**
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: 写失败断言，移除对 `查询工作台` Hero 标题的依赖**
- [ ] **Step 2: 写失败断言，锁定左侧配置导航和右侧工作台仍是主骨架**
- [ ] **Step 3: 写失败断言，锁定后端状态被并入工作台可见区，而不是独立 Hero**
- [ ] **Step 4: 运行定向测试，确认 RED**
Run: `cd app_desktop_web && npm test -- tests/renderer/query_system_page.test.jsx`
Expected: FAIL because hero text or structure no longer matches new contract
- [ ] **Step 5: 提交测试基线**
```bash
git add app_desktop_web/tests/renderer/query_system_page.test.jsx
git commit -m "test(desktop-ui): lock compact query page layout"
```

### Task 3: 更新购买系统页面测试，锁定紧凑运行栏与平铺商品行

**Files:**
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 写失败断言，移除对 `购买系统` Hero 标题的依赖**
- [ ] **Step 2: 写失败断言，锁定顶部运行栏显示配置名、状态、配置动作、累计购买**
- [ ] **Step 3: 写失败断言，锁定顶部不再显示 `队列中` 与 `run-1` 之类运行代号**
- [ ] **Step 4: 写失败断言，锁定商品区默认直接显示 `名称 / 磨损 / 价格 / 已购 / 命中 / 回执 / 查询次数`，且不再是 accordion**
- [ ] **Step 5: 写失败断言，锁定最近事件与账号监控仍在页面中，右下角悬浮 `开始扫货 / 停止扫货` 继续工作**
- [ ] **Step 6: 运行定向测试，确认 RED**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_page.test.jsx`
Expected: FAIL because current page still渲染 Hero、queue metric、runtime id 和 accordion 商品卡
- [ ] **Step 7: 提交测试基线**
```bash
git add app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "test(desktop-ui): lock compact purchase runtime layout"
```

## Chunk 2: 压缩账号中心与查询页头部

### Task 4: 实现账号中心“去 Hero、不减功能”

**Files:**
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] **Step 1: 删除账号中心 Hero 结构，保留概览卡、工具栏、表格、状态带**
- [ ] **Step 2: 把 `后端状态` 与 `刷新` 合并进现有工具栏，不改按钮行为**
- [ ] **Step 3: 最小调整 CSS，消除 Hero 占位并压缩首屏纵向高度**
- [ ] **Step 4: 复跑账号中心定向测试，确认 GREEN**
Run: `cd app_desktop_web && npm test -- tests/renderer/account_center_page.test.jsx`
Expected: PASS
- [ ] **Step 5: 提交账号中心实现**
```bash
git add app_desktop_web/src/features/account-center/account_center_page.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/account_center_page.test.jsx
git commit -m "feat(desktop-ui): compact account center header"
```

### Task 5: 实现查询系统“去 Hero、保工作台”

**Files:**
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/features/query-system/components/query_workbench_header.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: 删除查询系统 Hero 结构，保留左导航 + 右工作台骨架**
- [ ] **Step 2: 把 `后端状态` 并入 `QueryWorkbenchHeader` 的可见区，避免再占独立横幅**
- [ ] **Step 3: 最小调整 CSS，让工作台在进入页面后直接贴近顶部**
- [ ] **Step 4: 复跑查询页定向测试，确认 GREEN**
Run: `cd app_desktop_web && npm test -- tests/renderer/query_system_page.test.jsx`
Expected: PASS
- [ ] **Step 5: 提交查询页实现**
```bash
git add app_desktop_web/src/features/query-system/query_system_page.jsx app_desktop_web/src/features/query-system/components/query_workbench_header.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/query_system_page.test.jsx
git commit -m "feat(desktop-ui): compact query page header"
```

## Chunk 3: 重排购买页为运行监控布局

### Task 6: 实现购买页紧凑运行栏

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 删除购买页 Hero 结构，只保留错误区、运行栏、主布局和悬浮动作条**
- [ ] **Step 2: 把 `PurchaseRuntimeHeader` 改成紧凑运行栏，显示配置名、状态文案、配置动作、累计购买**
- [ ] **Step 3: 从运行栏中移除 `队列中` 与 `运行代号 / 购买代号`**
- [ ] **Step 4: 协调 `PurchaseRuntimeActions` 的文案与布局，确保右下角悬浮主动作继续可用**
- [ ] **Step 5: 复跑购买页定向测试中与运行栏相关的断言，确认 GREEN**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_page.test.jsx`
Expected: PASS for compact runtime bar assertions
- [ ] **Step 6: 提交运行栏实现**
```bash
git add app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat(desktop-ui): compact purchase runtime header"
```

### Task 7: 把购买商品卡改成平铺监控行

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 移除商品 accordion 交互与展开态文案**
- [ ] **Step 2: 让商品行默认显示 `名称 / 磨损 / 价格` 左侧信息**
- [ ] **Step 3: 让商品行右侧固定显示 `已购 / 命中 / 回执 / 查询次数` 四个统计位**
- [ ] **Step 4: 调整布局和样式，保证桌面横排、窄屏双层，不发生横向溢出**
- [ ] **Step 5: 复跑购买页定向测试，确认 GREEN**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_page.test.jsx`
Expected: PASS for flat item row assertions and preserved runtime action behavior
- [ ] **Step 6: 提交商品区实现**
```bash
git add app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat(desktop-ui): flatten purchase item monitor rows"
```

### Task 8: 降级购买页辅助区权重，不动运行语义

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 调整购买页主区和次级区排布，让商品清单优先于账号监控与最近事件**
- [ ] **Step 2: 压低辅助区标题和容器权重，但不改表格内容和事件内容**
- [ ] **Step 3: 复跑购买页定向测试，确认布局调整不影响功能断言**
Run: `cd app_desktop_web && npm test -- tests/renderer/purchase_system_page.test.jsx`
Expected: PASS
- [ ] **Step 4: 提交辅助区布局实现**
```bash
git add app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat(desktop-ui): de-emphasize purchase support panels"
```

## Chunk 4: 回归验证与收尾

### Task 9: 跑完整相关回归并检查改动边界

**Files:**
- Modify: none

- [ ] **Step 1: 运行三页 renderer 定向回归**
Run: `cd app_desktop_web && npm test -- tests/renderer/account_center_page.test.jsx tests/renderer/query_system_page.test.jsx tests/renderer/purchase_system_page.test.jsx`
Expected: PASS
- [ ] **Step 2: 运行前端全量测试**
Run: `cd app_desktop_web && npm test`
Expected: PASS
- [ ] **Step 3: 检查改动边界**
Run: `git diff --stat`
Expected: only renderer pages, related components, tests, and `app.css`
- [ ] **Step 4: 人工冒烟**
Run: `node main_ui_account_center_desktop.js`
Expected: 三页正常打开，购买页右下角悬浮按钮可用，商品行信息一眼可读
- [ ] **Step 5: 提交最终收尾**
```bash
git add app_desktop_web docs/superpowers/plans/2026-03-20-runtime-page-density-redesign.md
git commit -m "feat(desktop-ui): compact runtime pages"
```
