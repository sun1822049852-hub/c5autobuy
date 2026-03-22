# Query Runtime Manual Allocation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前新 UI 落地“配置期望只参与开局、购买页编辑运行时实际分配、共享池只服务 `actual=0` 商品”的查询运行时手动分配闭环。

**Architecture:** 后端把现有持续按目标补位的 allocator 拆成“开始扫货时的一次性初始分配器 + runtime 内存态实际分配表”，并通过 `query-runtime` 暴露批量提交接口。前端购买页把当前“改数字并保存配置”的流程改为“编辑实际分配草稿、统一提交 runtime、未保存离开保护”，继续通过 `purchase-runtime/status` 渲染购买页主视图。

**Tech Stack:** FastAPI、Python pytest、React 19、Vitest、Testing Library、现有 `account_center_client` HTTP client

---

## File Map

### Backend runtime allocation core

- Modify: `app_backend/infrastructure/query/runtime/query_mode_allocator.py`
  - 从“持续 reconcile 目标值”改成“初始分配 + runtime 实际分配状态”职责
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
  - 让每个 mode runner 按 runtime 实际分配表取任务，而不是持续参考配置目标值
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
  - 挂载并维护 runtime 手动分配表、共享池、商品实际分配快照
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
  - 负责 start 时的初始分配、stop/start 保留、切换配置清空、runtime 提交接口入口

### Backend API / schema / use case surface

- Modify: `app_backend/api/schemas/query_runtime.py`
  - 扩展 query runtime item / queryer 读模型
- Modify: `app_backend/api/schemas/purchase_runtime.py`
  - 扩展购买页可读的实际分配与共享池状态字段
- Modify: `app_backend/api/routes/query_runtime.py`
  - 新增 runtime 手动分配提交接口
- Modify: `app_backend/api/routes/purchase_runtime.py`
  - 保持 `purchase-runtime/status` 输出新的运行时分配读模型

### Frontend client / hook / page / components

- Modify: `app_desktop_web/src/api/account_center_client.js`
  - 增加 runtime 实际分配提交 client
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
  - 去掉“保存配置热应用”逻辑，改为本地草稿、共享池余额限制、统一提交、未保存保护
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
  - 增加底部 `提交更改` 和未保存确认弹窗接线
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
  - 把 mode 数字输入改成“实际分配 / 配置期望 + +/-”
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
  - 为底部动作区预留 `提交更改`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_header.jsx`
  - 只负责展示当前配置与购买运行态，不再承担分配保存反馈
- Modify: `app_desktop_web/src/features/shell/unsaved_changes_dialog.jsx`
  - 复用现有未保存对话框，无需重造
- Modify: `app_desktop_web/src/App.jsx`
  - 让购买页也接入未保存离开保护流程
- Modify: `app_desktop_web/src/styles/app.css`
  - 调整购买页商品行的“实际分配 / 配置期望”紧凑样式

### Tests

- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_query_purchase_bridge.py`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

## Chunk 1: 后端 runtime 实际分配核心

### Task 1: 先用测试锁定“初始分配只跑一次 + 铺开优先 + 运行中不再按目标自动补位”

**Files:**
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_purchase_bridge.py`
- Modify: `app_backend/infrastructure/query/runtime/query_mode_allocator.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`

- [ ] **Step 1: 为初始分配写 failing test**

在 `tests/backend/test_query_runtime_service.py` 新增覆盖：
- 启动查询 runtime 时按 `target_dedicated_count` 做一次初始分配
- 可用查询器不足时按“铺开优先”分配，而不是按商品顺序吃满
- 初始分配完成后，后续 snapshot 不会因为目标值未满足而自动补位

Run: `pytest tests/backend/test_query_runtime_service.py -q`
Expected: FAIL，当前 allocator 仍会持续 reconcile 目标值

- [ ] **Step 2: 为共享池候选规则写 failing test**

在 `tests/backend/test_query_purchase_bridge.py` 或同文件补覆盖：
- 某商品在某 mode 下 `actual > 0` 时不进入共享池
- `actual = 0` 且未暂停时才进入共享池
- 共享池为空时，这类商品在该 mode 下不被查询

Run: `pytest tests/backend/test_query_purchase_bridge.py -q`
Expected: FAIL，当前共享池逻辑仍混着目标值回填

- [ ] **Step 3: 拆分 `query_mode_allocator.py` 的职责**

要求：
- 保留“按配置目标值算初始分配”的能力
- 去掉运行中持续按目标值自动补位的行为
- 输出 runtime 可消费的实际分配结果，而不是每次实时 reconcile 目标值

- [ ] **Step 4: 改 `mode_runner.py` 按 runtime 实际分配表取任务**

要求：
- 查询器有专属绑定时，只查绑定商品
- 查询器在共享池时，轮转共享候选商品
- 共享池为空或共享候选为空时，这次不查

- [ ] **Step 5: 回跑两组测试**

Run: `pytest tests/backend/test_query_runtime_service.py tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/backend/test_query_runtime_service.py tests/backend/test_query_purchase_bridge.py app_backend/infrastructure/query/runtime/query_mode_allocator.py app_backend/infrastructure/query/runtime/mode_runner.py
git commit -m "feat: add initial-only query allocation runtime model"
```

### Task 2: 在 `QueryTaskRuntime` / `QueryRuntimeService` 中挂载 runtime 实际分配状态

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_service.py`

- [ ] **Step 1: 为 runtime 生命周期写 failing test**

在 `tests/backend/test_query_runtime_service.py` 新增覆盖：
- 同配置 stop/start 保留当前实际分配
- 切换到其他配置时清空旧配置 runtime 实际分配
- 再切回旧配置时重新按配置期望值做初始分配

Run: `pytest tests/backend/test_query_runtime_service.py -q`
Expected: FAIL，当前 runtime 还没有独立的实际分配状态

- [ ] **Step 2: 在 `query_task_runtime.py` 增加 runtime 分配状态容器**

要求：
- 按 mode 保存：
  - `queryers_by_id`
  - `item_assignments`
  - `shared_queryers`
  - `shared_items`
  - `shared_pointer`
- `snapshot()` 能基于它输出商品实际分配视图

- [ ] **Step 3: 在 `query_runtime_service.py` 接住保留 / 清空规则**

要求：
- 同配置 stop/start 时保留 runtime 手动分配状态
- 切配置时清空旧配置的 runtime 实际分配
- start 时若没有已有 runtime 分配表，则重新跑初始分配

- [ ] **Step 4: 回跑 runtime service 测试**

Run: `pytest tests/backend/test_query_runtime_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_backend/infrastructure/query/runtime/query_task_runtime.py app_backend/infrastructure/query/runtime/query_runtime_service.py tests/backend/test_query_runtime_service.py
git commit -m "feat: persist runtime query allocation state per active config"
```

## Chunk 2: runtime 手动提交接口与读模型

### Task 3: 为购买页提供“统一提交实际分配草稿”的 runtime API

**Files:**
- Modify: `app_backend/api/routes/query_runtime.py`
- Modify: `app_backend/api/schemas/query_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`

- [ ] **Step 1: 先写 query runtime route failing test**

在 `tests/backend/test_query_runtime_routes.py` 新增覆盖：
- `PUT /query-runtime/configs/{config_id}/manual-assignments` 可提交整页草稿
- 提交后返回新的 runtime snapshot
- 配置不存在时返回 404
- runtime 未运行或配置非当前运行配置时返回 409 或明确错误

Run: `pytest tests/backend/test_query_runtime_routes.py -q`
Expected: FAIL，接口尚不存在

- [ ] **Step 2: 设计最小请求体并加 schema**

建议请求体至少包含：
- `config_id`
- `items`
  - `query_item_id`
  - `mode_type`
  - `target_actual_count`

要求：
- schema 只描述“用户希望这个商品在这个 mode 下最终有多少实际分配”
- 不把配置期望值写回这个接口

- [ ] **Step 3: 在 `query_runtime_service.py` 实现草稿提交逻辑**

要求：
- 对每个 mode 比较“当前实际数量”和“提交后目标数量”
- 差值为正：从共享池拿查询器补到该商品
- 差值为负：从该商品释放任意数量查询器回共享池
- 不自动去满足其他商品的配置期望值

- [ ] **Step 4: 回跑 query runtime route 测试**

Run: `pytest tests/backend/test_query_runtime_routes.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_backend/api/routes/query_runtime.py app_backend/api/schemas/query_runtime.py app_backend/infrastructure/query/runtime/query_runtime_service.py tests/backend/test_query_runtime_routes.py
git commit -m "feat: add batch query runtime manual allocation api"
```

### Task 4: 扩展购买页状态读模型，暴露“实际分配 / 配置期望 / 共享池可用数”

**Files:**
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`

- [ ] **Step 1: 先写 purchase runtime status failing test**

在 `tests/backend/test_purchase_runtime_routes.py` 新增覆盖：
- `item_rows[].modes[mode]` 同时返回：
  - `target_dedicated_count`
  - `actual_dedicated_count`
  - `status`
  - `status_message`
- status 中可区分：
  - 专属中
  - 共享候选
  - 手动暂停
  - 无可用查询器
- 响应包含该 mode 当前共享池可用数量

Run: `pytest tests/backend/test_purchase_runtime_routes.py -q`
Expected: FAIL，当前响应字段不足

- [ ] **Step 2: 扩展 purchase runtime schema**

要求：
- 增加购买页所需的 mode 级共享池可用数
- 保持已有统计与购买字段兼容

- [ ] **Step 3: 在 `query_runtime_service.py` 的 snapshot 中输出新字段**

要求：
- 商品 mode 行基于 runtime 实际分配表生成
- 不再假装“目标未满足就自动补中”
- `status_message` 明确对应当前 runtime 真实状态

- [ ] **Step 4: 回跑 purchase runtime route 测试**

Run: `pytest tests/backend/test_purchase_runtime_routes.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_backend/api/schemas/purchase_runtime.py app_backend/api/routes/purchase_runtime.py app_backend/infrastructure/query/runtime/query_runtime_service.py tests/backend/test_purchase_runtime_routes.py
git commit -m "feat: expose runtime allocation status for purchase page"
```

## Chunk 3: 前端购买页草稿态、统一提交与离开保护

### Task 5: 扩展前端 client，接入 runtime 实际分配提交接口

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`

- [ ] **Step 1: 先写 client failing test**

在 `app_desktop_web/tests/renderer/purchase_system_client.test.js` 新增覆盖：
- `submitQueryRuntimeManualAllocations(configId, payload)` 发 `PUT /query-runtime/configs/{configId}/manual-assignments`
- 请求体只包含 runtime 实际分配草稿，不包含配置保存字段

Run: `npm test -- purchase_system_client.test.js`
Expected: FAIL，client 方法尚不存在

- [ ] **Step 2: 实现 client 方法**

要求：
- 方法名明确区分 runtime 分配与配置保存
- 不复用 `updateQueryItem` / `applyQueryItemRuntime`

- [ ] **Step 3: 回跑 client 测试**

Run: `npm test -- purchase_system_client.test.js`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app_desktop_web/src/api/account_center_client.js app_desktop_web/tests/renderer/purchase_system_client.test.js
git commit -m "feat: add runtime manual allocation client method"
```

### Task 6: 购买页改成“本地草稿 + 提交更改”，移除“保存分配到配置”

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 先写购买页 runtime 草稿 failing test**

在 `app_desktop_web/tests/renderer/purchase_system_page.test.jsx` 新增覆盖：
- 页面展示“实际分配 / 配置期望”
- 点击 `+ / -` 只改本地草稿，不立刻发请求
- 页面底部 `提交更改` 按钮在有草稿时可点
- 点击 `提交更改` 后才调用 runtime 提交接口

Run: `npm test -- purchase_system_page.test.jsx`
Expected: FAIL，当前页面仍是单商品保存配置

- [ ] **Step 2: 改写 `use_purchase_system_page.js` 的数据模型**

要求：
- 维护按商品、按 mode 的 `draftActualCounts`
- 维护按 mode 的共享池本地余额
- `+ / -` 时同步扣减或返还本地余额
- 去掉 `onSaveItemAllocation` 这种“单商品保存 + apply runtime”逻辑

- [ ] **Step 3: 改写 `purchase_item_panel.jsx`**

要求：
- mode 行显示：
  - `实际分配`
  - `配置期望`
  - `+ / -`
- 保留命中、成功、失败、来源等已做 UI
- 不再显示旧的 mode 数字输入框和“保存分配”按钮

- [ ] **Step 4: 在页面底部加 `提交更改`**

要求：
- 放在底部动作区，和开始扫货区域共存
- 提交成功后：
  - 清空草稿
  - 刷新 runtime 状态
  - 按钮回到禁用或同步态

- [ ] **Step 5: 回跑购买页测试**

Run: `npm test -- purchase_system_page.test.jsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/features/purchase-system/components/purchase_item_panel.jsx app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/src/features/purchase-system/components/purchase_runtime_actions.jsx app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat: edit purchase page runtime allocations as local drafts"
```

### Task 7: 让购买页接入未保存离开保护

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/features/shell/unsaved_changes_dialog.jsx`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 为购买页离开保护写 failing test**

在 `app_desktop_web/tests/renderer/purchase_system_page.test.jsx` 新增覆盖：
- 有未提交草稿时切换配置会弹 `未保存修改`
- 选择“保存”会先提交 runtime 再继续切换
- 选择“不保存”会丢弃草稿再继续切换
- 离开购买页切到别的页面时也走同样保护

Run: `npm test -- purchase_system_page.test.jsx`
Expected: FAIL，购买页尚未接入未保存对话框

- [ ] **Step 2: 复用 `UnsavedChangesDialog` 走购买页脏状态**

要求：
- 购买页 hook 暴露：
  - `hasUnsavedRuntimeDrafts`
  - `pendingLeaveAction`
  - `confirmSaveBeforeLeave`
  - `confirmDiscardBeforeLeave`
- 不复制配置管理页逻辑，尽量复用已有模式

- [ ] **Step 3: 在 `App.jsx` 中接入购买页的 leave guard**

要求：
- 购买页与配置管理页都可以注册未保存状态
- 页面切换统一弹同一个 `UnsavedChangesDialog`

- [ ] **Step 4: 回跑购买页测试**

Run: `npm test -- purchase_system_page.test.jsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/App.jsx app_desktop_web/src/features/shell/unsaved_changes_dialog.jsx app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat: guard unsaved purchase runtime allocation drafts"
```

## Chunk 4: 全量回归与文档回写

### Task 8: 全量验证 runtime 分配链路并同步实现笔记

**Files:**
- Modify: `docs/superpowers/specs/2026-03-22-query-runtime-manual-allocation-design.md`
- Modify: `docs/superpowers/plans/2026-03-22-query-runtime-manual-allocation-implementation.md`
- Test: `tests/backend/test_query_runtime_service.py`
- Test: `tests/backend/test_query_runtime_routes.py`
- Test: `tests/backend/test_purchase_runtime_routes.py`
- Test: `tests/backend/test_query_purchase_bridge.py`
- Test: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 回写 spec / plan 的实现差异**

只记录真正发生的实现取舍，例如：
- runtime 提交接口最终请求体格式
- 共享池可用数的返回位置
- `status_message` 的最终措辞

- [ ] **Step 2: 运行后端测试**

Run: `pytest tests/backend/test_query_runtime_service.py tests/backend/test_query_runtime_routes.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 3: 运行前端测试**

Run: `npm test -- purchase_system_client.test.js purchase_system_page.test.jsx`
Expected: PASS

- [ ] **Step 4: 手动冒烟**

Run:

```bash
node .\main_ui_account_center_desktop.js
```

检查：
- 购买页商品 mode 行显示 `实际分配 / 配置期望`
- 点 `+ / -` 只改本地草稿
- 底部 `提交更改` 能统一提交
- 未提交时切配置或离开页面会弹保存 / 不保存

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-03-22-query-runtime-manual-allocation-design.md docs/superpowers/plans/2026-03-22-query-runtime-manual-allocation-implementation.md
git commit -m "docs: sync runtime manual allocation implementation notes"
```
