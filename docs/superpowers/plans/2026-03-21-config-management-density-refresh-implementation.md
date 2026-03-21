# Config Management Density Refresh Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `app_desktop_web` 的查询页落地为已确认的“配置管理”紧凑布局，去掉旧 Hero 和底部保存区，完成左侧删除态、顶部压缩栏、商品表头/数据对齐与标签点击编辑交互。

**Architecture:** 保持现有 `QuerySystemPage -> QueryConfigNav / QueryWorkbenchHeader / QueryItemTable` 的组件边界，不做无关重构。通过少量 UI 状态补充删除态与表头工具栏，把布局重排尽量收敛在现有组件和 `app.css`，并同步更新 renderer 测试断言。

**Tech Stack:** React 19、Vite、Vitest、Testing Library、单文件全局样式 `app.css`

---

## Chunk 1: 页面骨架与左栏配置管理

### Task 1: 改写查询页入口结构

**Files:**
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Test: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: 为删除态补最薄 UI 状态**

在 `use_query_system_page.js` 增加：
- `isConfigDeleteMode`
- `toggleConfigDeleteMode`
- `exitConfigDeleteMode`

要求：
- 仅影响 UI 展示，不改业务删除 API
- 删除成功后自动退出删除态

- [ ] **Step 2: 运行查询页测试确认旧结构断言存在**

Run: `npm test -- query_system_page.test.jsx`
Expected: 至少包含旧标题或旧按钮断言，后续会因布局调整而需要更新

- [ ] **Step 3: 改写 `QuerySystemPage` 组合结构**

落地目标：
- 删除 `query-system-page__hero`
- 保留错误区
- 页面主体只保留 `QueryConfigNav` + `QueryWorkbenchHeader` + `QueryItemTable`
- 移除 `QuerySaveBar` 挂载

- [ ] **Step 4: 运行查询页测试观察新的失败点**

Run: `npm test -- query_system_page.test.jsx`
Expected: 失败集中到文案、按钮与结构断言，而不是运行时异常

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/src/features/query-system/query_system_page.jsx app_desktop_web/src/features/query-system/hooks/use_query_system_page.js app_desktop_web/tests/renderer/query_system_page.test.jsx
git commit -m "refactor: collapse query page into config management shell"
```

### Task 2: 重做左侧配置栏交互

**Files:**
- Modify: `app_desktop_web/src/features/query-system/components/query_config_nav.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: 写出左栏新接口使用方式**

`QueryConfigNav` 需要支持：
- `onToggleDeleteMode`
- `isDeleteMode`
- `onDeleteConfig`

表现要求：
- 标题改为 `配置管理`
- 顶部仅保留 `+ / -`
- 非删除态时配置项右侧不占删除按钮宽度
- 删除态时才显示每项小 `-`

- [ ] **Step 2: 改写 `QueryConfigNav` 组件**

落地内容：
- `+` 复用现有新建配置 dialog
- 顶部 `-` 切换删除态
- 每项状态右对齐
- 删除按钮只在删除态出现

- [ ] **Step 3: 最小实现样式**

在 `app.css` 中同步：
- 缩窄左栏宽度
- 压缩头部 padding
- 顶部按钮做成小图标按钮
- 配置卡 active / hover / delete-mode 状态

- [ ] **Step 4: 运行查询页测试并更新断言**

Run: `npm test -- query_system_page.test.jsx`
Expected: 断言更新到 `配置管理`、`+ / -` 删除态、无常驻删除按钮

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/src/features/query-system/components/query_config_nav.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/query_system_page.test.jsx
git commit -m "feat: add compact config nav delete mode"
```

## Chunk 2: 当前配置头部与保存入口

### Task 3: 压缩当前配置头部

**Files:**
- Modify: `app_desktop_web/src/features/query-system/components/query_workbench_header.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: 改写 `QueryWorkbenchHeader` 的 props 结构**

新增/保留：
- `onSave`
- `isSaving`
- `saveMessage`

移除：
- 旧的第二排大动作区

- [ ] **Step 2: 按确认稿重排头部**

第一行目标：
- 配置名
- `当前配置`
- `new_api / fast_api / token`
- `已停止 / 未运行`
- 最右小号 `保存当前配置`

第二行目标：
- 仅保留紧凑保存提示

注意：
- 不再保留 `添加商品` 文字按钮
- 商品添加/删除入口放到商品表头右侧

- [ ] **Step 3: 落样式**

样式要求：
- 更薄的 header padding
- inline save 按钮尺寸压小
- 运行态胶囊与容量 chip 同排
- 不出现旧副标题与大块说明文案

- [ ] **Step 4: 运行查询页测试并更新头部断言**

Run: `npm test -- query_system_page.test.jsx`
Expected: 新测试检查保存按钮仍存在，但位置与文案从旧卡片切到新头部

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/src/features/query-system/components/query_workbench_header.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/query_system_page.test.jsx
git commit -m "feat: compress config header and inline save action"
```

## Chunk 3: 商品表格化与标签点击编辑

### Task 4: 重做商品表头和工具栏

**Files:**
- Modify: `app_desktop_web/src/features/query-system/components/query_item_table.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/query_system_page.test.jsx`

- [ ] **Step 1: 改写商品区头部结构**

目标：
- 移除 `商品列表` 标题
- 顶部只保留一行：
  - 左边列头 `商品名 / 价格 / 磨损 / new_api / fast_api / token`
  - 右边 `+ / -`

- [ ] **Step 2: 接入商品区删除态**

需要增加：
- `isItemDeleteMode`
- `onToggleItemDeleteMode`
- `onOpenCreateItemDialog`

若当前实现还没有删除商品功能入口，可先只做 UI 删除态占位和按钮结构；若已有删除 dialog，可直接复用。

- [ ] **Step 3: 运行测试确认旧标题断言移除**

Run: `npm test -- query_system_page.test.jsx`
Expected: 测试不再依赖“商品列表”标题

- [ ] **Step 4: Commit**

```bash
git add app_desktop_web/src/features/query-system/components/query_item_table.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/query_system_page.test.jsx
git commit -m "feat: align item table header with inline controls"
```

### Task 5: 把商品行改成表格式并移除“编辑商品”

**Files:**
- Modify: `app_desktop_web/src/features/query-system/components/query_item_row.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`

- [ ] **Step 1: 写出新的商品行交互**

每个商品行应展示：
- 第一列：商品名
- 第二列：价格值
- 第三列：磨损值
- 第四到第六列：`new_api / fast_api / token` 具体状态值

交互要求：
- 去掉 `编辑商品` 独立按钮
- 改为点击价格、磨损、状态值本身触发 `onEditItem`
- 保留 `role` / `aria-label`，确保测试可定位

- [ ] **Step 2: 改写 `QueryItemRow`**

最小实现建议：
- 价格按钮 aria：`修改价格 <商品名>`
- 磨损按钮 aria：`修改磨损 <商品名>`
- 模式按钮 aria：`修改 <mode> <商品名>`
- 所有这些按钮最终调用同一个 `onEditItem(query_item_id)`

- [ ] **Step 3: 重写样式以保证表头和数据列共用网格**

要求：
- 头部与每行使用同一套列宽
- 商品区右侧工具列与删除占位列共用同一常量宽度
- 模式值胶囊定宽，避免字数长短导致不对齐

- [ ] **Step 4: 更新编辑测试**

Run: `npm test -- query_system_editing.test.jsx`
Expected:
- 不再查找 `编辑 <商品名>`
- 改为点击价格/磨损/状态按钮打开编辑 dialog
- 现有保存与容量校验逻辑继续通过

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/src/features/query-system/components/query_item_row.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/query_system_editing.test.jsx
git commit -m "refactor: convert query items into aligned editable grid"
```

## Chunk 4: 收尾验证

### Task 6: 全量验证与文档同步

**Files:**
- Modify: `docs/superpowers/specs/2026-03-21-config-management-density-refresh-design.md`
- Test: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`

- [ ] **Step 1: 回写设计文档**

补充最终确认差异：
- 商品表头与 `+ / -` 同排
- 商品值点击编辑
- 保存入口与运行状态调换位置
- 商品共有字段改为表头合并

- [ ] **Step 2: 运行聚焦测试**

Run: `npm test -- query_system_page.test.jsx query_system_editing.test.jsx`
Expected: PASS

- [ ] **Step 3: 运行构建验证**

Run: `npm run build`
Expected: Vite build 成功，无 JSX/CSS 语法错误

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-03-21-config-management-density-refresh-design.md app_desktop_web/tests/renderer/query_system_page.test.jsx app_desktop_web/tests/renderer/query_system_editing.test.jsx app_desktop_web/src/features/query-system app_desktop_web/src/styles/app.css
git commit -m "feat: finish config management density refresh"
```
