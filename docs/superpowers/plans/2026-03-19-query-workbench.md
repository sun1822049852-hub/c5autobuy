# Query Workbench Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为新的桌面化 Web 查询系统落地“左侧配置导航 + 右侧查询工作台 + 商品级专属/共享分配器”，让用户可以保存多个配置、编辑商品参数、查看按模式拆分的运行状态，并让新后端真正承载旧 `autobuy.py` 的 ready 驱动分配语义。

**Architecture:** 先补后端配置真相和运行时分配器，再接桌面 Web 查询页。持久化层负责商品参数、手动暂停和模式分配目标；运行时层负责专属池/共享池的实际分配与状态快照；React 查询页只维护当前配置草稿、动态剩余额度和保存交互，不把调度逻辑搬进前端。

**Tech Stack:** Python, FastAPI, SQLAlchemy, pytest, Electron, React, Vite, JavaScript, Vitest, Testing Library

---

## 文件结构

- Create: `app_backend/application/services/query_mode_capacity_service.py`
- Create: `app_backend/application/services/query_item_settings_service.py`
- Create: `app_backend/application/use_cases/get_query_capacity_summary.py`
- Create: `app_backend/infrastructure/query/runtime/query_mode_allocator.py`
- Create: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Create: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Create: `app_desktop_web/src/features/query-system/components/query_config_nav.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_workbench_header.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_item_table.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_item_row.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_item_create_panel.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_mode_allocation_input.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_save_bar.jsx`
- Create: `app_desktop_web/tests/renderer/query_system_client.test.js`
- Create: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Create: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
- Create: `tests/backend/test_query_mode_capacity_service.py`
- Create: `tests/backend/test_query_mode_allocator.py`
- Modify: `app_backend/domain/models/query_config.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Modify: `app_backend/infrastructure/repositories/query_config_repository.py`
- Modify: `app_backend/application/use_cases/add_query_item.py`
- Modify: `app_backend/application/use_cases/update_query_item.py`
- Modify: `app_backend/api/schemas/query_configs.py`
- Modify: `app_backend/api/schemas/query_runtime.py`
- Modify: `app_backend/api/routes/query_configs.py`
- Modify: `app_backend/infrastructure/query/runtime/query_item_scheduler.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `tests/backend/test_query_config_repository.py`
- Modify: `tests/backend/test_query_config_routes.py`
- Modify: `tests/backend/test_query_item_scheduler.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

注：

- 本计划按 `@superpowers/test-driven-development` 执行，先写失败测试，再写最小实现。
- 遇到运行时偏差，先按 `@superpowers/systematic-debugging` 定位根因，再继续推进。
- 按当前仓库规则，本计划不包含 git 提交、分支或 worktree 操作。

## Chunk 1: 配置真相与保存校验

### Task 1: 先写商品分配真相与容量汇总的失败测试

**Files:**
- Create: `tests/backend/test_query_mode_capacity_service.py`
- Modify: `tests/backend/test_query_config_repository.py`
- Modify: `tests/backend/test_query_config_routes.py`
- Modify: `app_backend/domain/models/query_config.py`

- [ ] 为容量服务写失败测试，锁定三种模式的可用账号统计规则：
  - `new_api` 只统计未禁用且有 `api_key` 且 `new_api_enabled=True` 的账号
  - `fast_api` 只统计未禁用且有 `api_key` 且 `fast_api_enabled=True` 的账号
  - `token` 只统计未禁用、`token_enabled=True` 且 `cookie_raw` 含 `NC5_accessToken=`，并且 `last_error != "Not login"` 的账号
- [ ] 为仓储层写失败测试，锁定 `QueryItem` 新增 `manual_paused` 与按模式分配目标持久化。
- [ ] 为 `/query-configs` 路由写失败测试，锁定配置详情返回：
  - 商品价格与磨损
  - `manual_paused`
  - 三种模式的 `target_dedicated_count`
- [ ] 为容量汇总接口写失败测试，锁定前端可拿到当前三种模式可用账号数。
- [ ] 运行定向后端测试，确认因为缺少字段、缺少容量服务和缺少路由返回结构而失败。

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_query_mode_capacity_service.py" `
  "tests/backend/test_query_config_repository.py" `
  "tests/backend/test_query_config_routes.py" -q
```

Expected:

- 新测试失败
- 失败原因指向 `manual_paused`、模式分配目标或容量汇总接口尚未实现

### Task 2: 最小实现配置真相、容量汇总与保存校验

**Files:**
- Create: `app_backend/application/services/query_mode_capacity_service.py`
- Create: `app_backend/application/services/query_item_settings_service.py`
- Create: `app_backend/application/use_cases/get_query_capacity_summary.py`
- Modify: `app_backend/domain/models/query_config.py`
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Modify: `app_backend/infrastructure/repositories/query_config_repository.py`
- Modify: `app_backend/application/use_cases/add_query_item.py`
- Modify: `app_backend/application/use_cases/update_query_item.py`
- Modify: `app_backend/api/schemas/query_configs.py`
- Modify: `app_backend/api/routes/query_configs.py`

- [ ] 在 `QueryItem` 中补 `manual_paused` 字段，并在同文件中新增商品模式分配模型，例如 `QueryItemModeAllocation`。
- [ ] 在 `app_backend/infrastructure/db/models.py` 中：
  - 为 `query_config_items` 增加 `manual_paused`
  - 新建商品模式分配表，保存 `query_item_id + mode_type + target_dedicated_count`
- [ ] 在 `app_backend/infrastructure/db/base.py` 中增加兼容性建表/补列逻辑，保证本地旧库不会直接炸掉。
- [ ] 在仓储层补齐：
  - 读取商品模式分配目标
  - 新增商品时初始化三种模式目标为 `0`
  - 更新商品时一并写入 `manual_paused` 与模式分配目标
- [ ] 在 `query_item_settings_service.py` 中统一做参数校验：
  - `min_wear / max_wear / detail_max_wear` 关系合法
  - `max_price` 非负
  - 手动暂停商品不占用分配额度
- [ ] 在 `query_mode_capacity_service.py` 中实现三种模式当前可用账号数计算。
- [ ] 新增容量汇总接口，例如 `GET /query-configs/capacity-summary`，供前端动态计算“还可分配 X”。
- [ ] 复跑定向后端测试，确认配置真相与保存校验基础转绿。

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_query_mode_capacity_service.py" `
  "tests/backend/test_query_config_repository.py" `
  "tests/backend/test_query_config_routes.py" -q
```

Expected:

- 配置详情与容量汇总测试通过
- 商品模式分配目标与手动暂停已可持久化

## Chunk 2: 运行时分配器与商品状态快照

### Task 3: 先写专属池 / 共享池分配器的失败测试

**Files:**
- Create: `tests/backend/test_query_mode_allocator.py`
- Modify: `tests/backend/test_query_item_scheduler.py`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`

- [ ] 为 `QueryModeAllocator` 写失败测试，锁定：
  - `target_dedicated_count > 0` 的商品优先获得专属绑定
  - `target_dedicated_count = 0` 的商品默认进入共享池候选
  - 还有至少 1 个专属账号的商品不吃共享池
  - 专属清零后降级到共享池
  - 全局资源重新足够满足目标数时，商品立刻退出共享池回到专属态
- [ ] 为调度器写失败测试，锁定一个商品被多个账号查询时最小可查询时间改成 `0.5 / 当前实际分配账号数量`。
- [ ] 为运行时服务写失败测试，锁定 `/query-runtime/status` 会返回商品级模式状态，而不仅是组状态。
- [ ] 为路由写失败测试，锁定运行中的配置能给前端提供商品级状态标签所需数据。
- [ ] 运行定向后端测试，确认因为缺少分配器和商品级快照而失败。

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_query_mode_allocator.py" `
  "tests/backend/test_query_item_scheduler.py" `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" -q
```

Expected:

- 新增分配器测试失败
- 失败原因指向缺少专属/共享分配、缺少商品级状态或冷却公式未更新

### Task 4: 最小实现分配器、动态冷却与运行时商品状态

**Files:**
- Create: `app_backend/infrastructure/query/runtime/query_mode_allocator.py`
- Modify: `app_backend/infrastructure/query/runtime/query_item_scheduler.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_task_runtime.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/api/schemas/query_runtime.py`

- [ ] 新建 `QueryModeAllocator`，按模式维护：
  - 当前可用 worker 集合
  - 商品专属目标
  - 专属绑定关系
  - 共享池候选商品
  - 商品模式状态快照
- [ ] 让 `ModeRunner` 的 worker loop 不再直接裸调 `QueryItemScheduler.reserve_next()`，改为先向 `QueryModeAllocator` 申请当前 worker 的下一次商品。
- [ ] 对专属 worker：
  - ready 后只取绑定商品
  - 商品仍按最小可查询时间控制调度
- [ ] 对共享 worker：
  - ready 后通过共享池轮转拿商品
  - 跳过手动暂停商品与不在共享候选集里的商品
- [ ] 更新 `QueryItemScheduler`，允许按商品当前实际分配数动态计算冷却时间，默认保留现有 API 兼容。
- [ ] 在 `ModeRunner.snapshot()` 中新增商品级模式状态快照，并在 `QueryTaskRuntime.snapshot()` 中聚合成前端可消费的 `item_rows`。
- [ ] 在 `QueryRuntimeService` 和 `QueryRuntimeStatusResponse` 中规范化 `item_rows`，保持现有 `group_rows` 兼容。
- [ ] 复跑定向运行时测试，确认专属池 / 共享池 / 动态冷却 / 商品级状态全部转绿。

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_query_mode_allocator.py" `
  "tests/backend/test_query_item_scheduler.py" `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" -q
```

Expected:

- 分配器与动态冷却测试通过
- `/query-runtime/status` 能返回商品级模式状态

## Chunk 3: Web 壳导航与查询页骨架

### Task 5: 先写查询页导航与客户端失败测试

**Files:**
- Create: `app_desktop_web/tests/renderer/query_system_client.test.js`
- Create: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Modify: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] 为桌面 Web 客户端写失败测试，锁定新增接口：
  - `listQueryConfigs`
  - `getQueryConfig`
  - `getQueryCapacitySummary`
  - `startQueryRuntime`
  - `stopQueryRuntime`
  - `getQueryRuntimeStatus`
  - `createQueryConfig`
  - `addQueryItem`
  - `updateQueryItem`
- [ ] 为 `App` / `AppShell` 写失败测试，锁定点击左侧 `查询系统` 后会切到真实查询页，而不是 `Soon` 占位。
- [ ] 为查询页骨架写失败测试，覆盖：
  - 左侧配置导航
  - 右侧工作台头部
  - 配置状态标签
  - 底部保存条
- [ ] 运行定向前端测试，确认因为缺少查询页和客户端接口而失败。

Run:

```powershell
npm --prefix "app_desktop_web" test -- `
  query_system_client.test.js `
  query_system_page.test.jsx `
  account_center_page.test.jsx
```

Expected:

- 新测试失败
- 失败原因指向缺少查询页入口或缺少客户端方法

### Task 6: 最小实现导航切换与查询页骨架

**Files:**
- Create: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Create: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Create: `app_desktop_web/src/features/query-system/components/query_config_nav.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_workbench_header.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_save_bar.jsx`
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] 在 `App.jsx` 中引入“当前激活导航项”状态，允许账号中心与查询系统切换。
- [ ] 在 `AppShell` 中把 `查询系统` 从纯占位按钮改成可点击导航项，同时保留 `购买系统` 为占位。
- [ ] 在客户端补齐查询页所需读取接口。
- [ ] 新建 `use_query_system_page.js`，先实现：
  - 加载配置列表
  - 选择当前配置
  - 加载容量汇总
  - 保存条基础状态
- [ ] 新建查询页骨架组件：
  - 左侧配置导航
  - 右侧工作台头部
  - 底部保存条
- [ ] 复跑查询页骨架测试，确认页面结构与导航切换转绿。

Run:

```powershell
npm --prefix "app_desktop_web" test -- `
  query_system_client.test.js `
  query_system_page.test.jsx `
  account_center_page.test.jsx
```

Expected:

- 查询页可从左侧导航进入
- 基础客户端和查询页骨架测试通过

## Chunk 4: 商品列表、行内展开编辑与新增商品面板

### Task 7: 先写商品编辑交互与动态剩余额度的失败测试

**Files:**
- Create: `app_desktop_web/tests/renderer/query_system_editing.test.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`

- [ ] 为商品表格写失败测试，锁定每行直接显示：
  - 商品名
  - 当前设置价格
  - 当前设置磨损
  - `new_api / fast_api / token` 目标分配数
  - 按模式拆分的状态标签
- [ ] 为商品行展开写失败测试，锁定展开区可编辑：
  - `min_wear`
  - `max_wear`
  - `max_price`
  - `manual_paused`
  - 三种模式目标分配数
- [ ] 为分配输入写失败测试，锁定每种模式旁都显示动态“还可分配 X”，并且在修改别的商品后实时刷新。
- [ ] 为新增商品面板写失败测试，锁定：
  - 入口在当前配置右上侧
  - 粘贴 URL 后自动拉取详情回填
  - 三种模式目标分配默认都是 `0`
- [ ] 为保存写失败测试，锁定超配时阻止保存并显示 `校验失败，无法保存`。
- [ ] 运行定向前端测试，确认因为缺少商品编辑组件、动态剩余额度和新增商品面板而失败。

Run:

```powershell
npm --prefix "app_desktop_web" test -- query_system_editing.test.jsx
```

Expected:

- 查询页编辑测试失败
- 失败原因指向缺少商品表格、行内展开区或动态剩余额度计算

### Task 8: 最小实现商品编辑、新增面板与保存交互

**Files:**
- Create: `app_desktop_web/src/features/query-system/components/query_item_table.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_item_row.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_item_create_panel.jsx`
- Create: `app_desktop_web/src/features/query-system/components/query_mode_allocation_input.jsx`
- Modify: `app_desktop_web/src/features/query-system/query_system_page.jsx`
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/styles/app.css`

- [ ] 在 hook 中增加草稿层：
  - 当前配置草稿
  - 展开中的商品 ID
  - 新增商品面板开关
  - 保存前错误状态
- [ ] 实现商品主表格与商品行，直接展示价格、磨损、目标分配数和状态标签。
- [ ] 实现商品行内展开编辑区，支持 `manual_paused` 开关与三种模式目标分配输入。
- [ ] 实现 `query_mode_allocation_input.jsx`，在输入旁显示“还可分配 X / 已超出 Y”。
- [ ] 实现新增商品面板：
  - 输入 URL
  - 调用现有详情解析/抓取接口
  - 回填商品名、默认磨损、价格参考
  - 三种模式分配默认 `0`
- [ ] 保存当前配置时：
  - 先做前端剩余额度校验
  - 再调用后端更新接口
  - 成功后清除 `未保存` 状态
- [ ] 复跑查询页编辑测试，确认商品编辑闭环转绿。

Run:

```powershell
npm --prefix "app_desktop_web" test -- query_system_editing.test.jsx
```

Expected:

- 商品编辑、新增商品与保存校验测试通过
- 查询工作台已经可做真实草稿编辑

## Chunk 5: 运行时状态展示与最终验收

### Task 9: 先写运行态映射与单活动配置失败测试

**Files:**
- Modify: `app_desktop_web/tests/renderer/query_system_page.test.jsx`
- Modify: `tests/backend/test_query_runtime_service.py`
- Modify: `tests/backend/test_query_runtime_routes.py`

- [ ] 为前端写失败测试，锁定商品状态标签按模式展示：
  - `专属中 X/Y`
  - `共享中`
  - `无可用账号 X/Y`
  - `手动暂停`
- [ ] 为前端写失败测试，锁定同一时刻只能启动一个配置，运行中的配置在左侧显示 `运行中`。
- [ ] 为后端写失败测试，锁定当配置切换启动时，前一配置停止、当前配置状态生效。
- [ ] 运行前后端定向测试，确认因为缺少运行态映射和单活动配置显示而失败。

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" -q

npm --prefix "app_desktop_web" test -- query_system_page.test.jsx query_system_editing.test.jsx
```

Expected:

- 前后端测试失败
- 失败原因指向缺少商品状态映射或单活动配置约束未正确表达

### Task 10: 最小实现运行态映射并完成定向验收

**Files:**
- Modify: `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- Modify: `app_desktop_web/src/features/query-system/components/query_item_table.jsx`
- Modify: `app_desktop_web/src/features/query-system/components/query_workbench_header.jsx`
- Modify: `app_desktop_web/src/features/query-system/components/query_save_bar.jsx`
- Modify: `app_desktop_web/src/styles/app.css`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`

- [ ] 在查询页 hook 中增加运行时轮询或刷新逻辑，把 `query-config` 配置真相与 `query-runtime/status` 的 `item_rows` 合并成最终显示模型。
- [ ] 把商品状态标签映射成按模式的小标签，优先级为：
  - `手动暂停`
  - `专属中 X/Y`
  - `共享中`
  - `无可用账号 X/Y`
- [ ] 在左侧配置导航和右侧头部同步表达：
  - `未保存`
  - `运行中`
  - `已停止`
  - `等待账号`
- [ ] 锁定“单活动配置”行为：
  - 查询页只允许一个配置进入运行态
  - 启动后左侧只有一个配置显示 `运行中`
- [ ] 复跑全部定向测试并做一次桌面 Web 手工冒烟：
  - 切换到查询系统
  - 新建配置
  - 新增商品
  - 修改分配
  - 保存
  - 启动查询
  - 检查状态标签

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest `
  "tests/backend/test_query_mode_capacity_service.py" `
  "tests/backend/test_query_mode_allocator.py" `
  "tests/backend/test_query_config_repository.py" `
  "tests/backend/test_query_config_routes.py" `
  "tests/backend/test_query_item_scheduler.py" `
  "tests/backend/test_query_runtime_service.py" `
  "tests/backend/test_query_runtime_routes.py" -q

npm --prefix "app_desktop_web" test -- `
  query_system_client.test.js `
  query_system_page.test.jsx `
  query_system_editing.test.jsx `
  account_center_page.test.jsx
```

Expected:

- 定向后端测试全部通过
- 定向前端测试全部通过
- 查询页完成从配置编辑到运行态展示的闭环

## 结语

实现时务必保持以下顺序：

1. 先做配置真相与保存校验
2. 再做运行时分配器
3. 最后做 Web 查询页

不要先做前端壳再倒逼后端补洞，否则很容易再次出现“界面先行、语义漂移”的老问题。
