# 左侧通用诊断面板设计

日期：2026-03-25

## 1. 目标

为当前桌面端增加一个常驻左侧的通用诊断面板，用统一入口展示：

- 查询运行时状态
- 购买运行时状态
- 登录任务状态

第一阶段的核心目标不是做一套完整日志平台，而是解决当前“系统实际异常但 UI 不可见”的问题，尤其是：

- 新增账号后查询仍在增加 `query_count`
- 某个 API / token 账号实际上已经失效
- 前端界面没有直接暴露 mode 级、账号级、事件级诊断信息

该面板必须在不明显影响“查询 -> 购买”主链路速度的前提下提供可观察性。

## 2. 当前问题

当前系统并不是完全没有诊断信息，而是缺少统一观察面：

1. 查询运行时后端已经有 `recent_events`、`last_error`、`query_count`、`found_count` 等状态快照。
2. 购买运行时后端已经有 `recent_events`、账号状态、库存状态等运行时摘要。
3. 登录任务本身已经有 task state 与 event timeline。
4. 前端查询页目前主要展示配置状态和商品状态文案，没有把后端已有的诊断信号展开到可直接排障的程度。
5. 用户现在无法快速判断：
   - 哪个 mode 在出错
   - 哪个账号已经失效
   - 为什么 `query_count` 仍在上涨
   - 查询命中后是否实际流入购买

因此问题的本质不是“先缺日志文件”，而是“运行时诊断不可见”。

## 3. 已确认的用户决策

以下内容已经在讨论中确认：

- 采用左侧常驻通用诊断面板，而不是单独弹窗或仅后台日志。
- 面板采用统一入口，覆盖：
  - `查询`
  - `购买`
  - `登录任务`
- 第一阶段不做落盘日志，优先做内存态与已有运行时快照的可视化。
- 第一阶段必须避免明显拖慢“查询 -> 购买”链路。
- 第一阶段允许只保留最近一段内存事件，不做历史持久化。
- 第一阶段优先深做查询诊断，购买与登录诊断先做基础版。

## 4. 方案比较

### 方案 A：只做后台文件日志

- 在后端增加查询、购买、登录相关文本日志文件。
- 前端不增加统一诊断展示。

优点：

- 后端实现路径直接。
- 不需要改前端主壳布局。

缺点：

- 仍然需要手动翻日志，排障路径长。
- 用户最缺的是“运行时状态可见性”，不是单纯“有日志文件”。
- 如果把文件写入接到热路径，容易拖慢主链路。

### 方案 B：只做前端面板，不补后端聚合

- 前端从多个现有接口分别拉状态，拼装左侧面板。

优点：

- 后端改动少。

缺点：

- 前端需要并发拉多个接口，数据更新节奏不一致。
- 聚合逻辑散在前端，后续维护成本高。
- 结构难以统一，不利于后续扩展。

### 方案 C：后端结构化诊断聚合 + 前端左侧通用面板

- 后端新增单一聚合接口，汇总查询、购买、登录任务诊断快照。
- 前端新增左侧常驻诊断面板，统一展示结构化结果。

优点：

- 最符合当前“直接查看并快速定位”的目标。
- 前端只轮询一个接口，最容易控制性能与一致性。
- 复用现有运行时快照，避免重新造一套重日志系统。

缺点：

- 需要同时修改前后端。
- 需要对桌面壳布局做一次结构调整。

### 结论

采用方案 C。

第一阶段以“结构化诊断 + 常驻面板”为主，不做文件日志主导方案。

## 5. 第一阶段范围

第一阶段只做以下内容：

1. 左侧常驻三栏布局：
   - 主导航
   - 诊断面板
   - 主内容区
2. 单一诊断聚合接口
3. 三个诊断标签：
   - `查询`
   - `购买`
   - `登录任务`
4. 查询标签深诊断：
   - 运行摘要
   - mode 状态
   - 异常账号
   - 最近事件
5. 购买标签基础诊断：
   - 运行摘要
   - 异常账号
   - 最近事件
6. 登录任务标签基础诊断：
   - 最近任务
   - 当前状态
   - 冲突/失败摘要

第一阶段明确不做：

- 文件落盘日志
- WebSocket 实时推送
- 全文搜索
- 日志导出
- 无限历史
- 新增数据库日志表
- 全账号全事件明细展开

## 6. 总体架构

### 6.1 前端布局

当前桌面壳为两栏结构：

- 左侧主导航
- 右侧主内容

第一阶段改为三栏：

1. 主导航栏
2. 通用诊断面板
3. 页面主内容

诊断面板常驻显示，不使用弹窗或抽屉，原因：

- 诊断信息是高频观察对象，而不是临时查看对象。
- 弹窗会打断当前操作，且不利于边查边改。
- 常驻第二列可以减少对主导航的挤压，也不会侵入页面主工作区。

### 6.2 后端聚合

后端新增统一接口，例如：

`GET /diagnostics/sidebar`

该接口只做轻量聚合，不直接触发业务行为，不主动刷新远程状态，不写磁盘。

数据来源：

1. 查询诊断
   - `query_runtime_service.get_status()`
2. 购买诊断
   - `purchase_runtime_service.get_status()`
3. 登录任务诊断
   - `task_manager` 最近任务快照

### 6.3 事件策略

第一阶段采用“已有状态优先，新增事件最小化”原则：

- 优先复用现有 `recent_events`
- 如果现有数据不足，再补固定长度内存 ring buffer
- 新增事件写入必须是 best-effort
- 写入失败不得影响查询、购买、登录主流程

## 7. 聚合接口设计

### 7.1 顶层结构

接口返回统一诊断快照：

```json
{
  "summary": {},
  "query": {},
  "purchase": {},
  "login_tasks": {},
  "updated_at": "2026-03-25T20:00:00"
}
```

### 7.2 summary

`summary` 用于左侧顶部健康摘要，至少包含：

- `backend_online`
- `query_running`
- `purchase_running`
- `active_query_config_name`
- `last_error`
- `updated_at`

### 7.3 query

`query` 分区建议返回：

- `running`
- `config_id`
- `config_name`
- `message`
- `total_query_count`
- `total_found_count`
- `last_error`
- `updated_at`
- `mode_rows`
- `account_rows`
- `recent_events`

其中：

`mode_rows` 包含：

- `mode_type`
- `enabled`
- `eligible_account_count`
- `active_account_count`
- `query_count`
- `found_count`
- `last_error`

`account_rows` 第一阶段只返回“异常优先”的账号行，至少包含：

- `account_id`
- `display_name`
- `mode_type`
- `active`
- `query_count`
- `found_count`
- `last_error`
- `disabled_reason`
- `last_seen_at`

`recent_events` 默认最多返回最近 20 条。

### 7.4 purchase

`purchase` 分区建议返回：

- `running`
- `message`
- `active_account_count`
- `total_purchased_count`
- `last_error`
- `updated_at`
- `account_rows`
- `recent_events`

`account_rows` 包含：

- `account_id`
- `display_name`
- `purchase_capability_state`
- `purchase_pool_state`
- `purchase_disabled`
- `selected_inventory_name`
- `selected_inventory_remaining_capacity`
- `last_error`

### 7.5 login_tasks

`login_tasks` 分区建议返回：

- `running_count`
- `conflict_count`
- `failed_count`
- `updated_at`
- `recent_tasks`

`recent_tasks` 每项建议包含：

- `task_id`
- `account_id`
- `account_display_name`
- `state`
- `started_at`
- `updated_at`
- `last_message`
- `pending_conflict`
- `events`

第一阶段对 `events` 做裁剪，只保留最近几条。

## 8. 前端面板设计

### 8.1 组件结构

新增 `features/diagnostics/` 模块，建议拆分：

- `diagnostics_panel.jsx`
- `diagnostics_tabs.jsx`
- `diagnostics_summary.jsx`
- `diagnostics_event_list.jsx`
- `query_diagnostics_tab.jsx`
- `purchase_diagnostics_tab.jsx`
- `login_task_diagnostics_tab.jsx`

公共组件尽量复用，避免三个标签各自长成三套 UI。

### 8.2 查询标签

查询标签是第一阶段重点，布局建议为：

1. 运行摘要
   - 当前配置
   - runtime message
   - total query / found
   - 最近错误
2. Mode 状态列表
   - `new_api`
   - `fast_api`
   - `token`
3. 异常账号列表
   - 仅展示异常账号与最近活跃异常账号
4. 最近事件流

目标是让用户直接看到：

- 哪个 mode 还在跑
- 哪个 mode 已经报错
- 哪个账号已经失效
- 为什么 `query_count` 仍然在增长

### 8.3 购买标签

购买标签第一阶段显示：

1. 运行摘要
2. 异常账号列表
3. 最近事件流

重点用于判断：

- 查询命中后有没有实际流入购买
- 是库存问题、鉴权问题还是配置问题

### 8.4 登录任务标签

登录任务标签第一阶段显示：

1. 任务摘要
2. 进行中任务
3. 冲突任务
4. 最近失败任务
5. 选中任务的精简时间线

重点用于判断：

- 登录当前卡在哪一步
- 是否进入冲突
- 为什么失败

## 9. 性能约束

该功能必须遵守以下硬约束：

1. 不得在查询/购买热路径中进行同步文件写入。
2. 不得因诊断写入失败而影响主业务流程。
3. 前端只轮询单一聚合接口，不散拉多个状态接口。
4. 诊断数据优先读现有运行时快照，不重复触发远程查询。
5. 事件列表固定长度，采用 ring buffer 或已有 `recent_events` 裁剪结果。
6. 聚合接口仅做轻量拼装，不做复杂聚合计算。

建议前端轮询频率：

- 前台可见时：`1000ms` 到 `2000ms`
- 页面失焦或应用后台时：可降频到 `5000ms`

## 10. 成功标准

第一阶段完成后，用户应能在左侧 3 到 5 秒内确认：

1. 当前查询运行时是否真正正常运行。
2. 哪个 query mode 在出错。
3. 哪个账号 API 或 token 已失效。
4. 为什么 `query_count` 仍然在增长。
5. 查询命中后是否流入购买。
6. 登录任务当前停在哪一步。

同时满足：

- 开启面板前后，查询 -> 购买链路主观速度无明显下降。

## 11. 风险与控制

### 风险 1：诊断面板拖慢主链路

控制：

- 不写盘
- 不进热路径同步等待
- 只读已有状态

### 风险 2：诊断接口数据过大

控制：

- 最近事件限长
- 账号行异常优先
- 不做第一阶段全量展开

### 风险 3：前端左侧面板挤压主工作区

控制：

- 采用三栏结构而非把诊断面板塞进主导航栏
- 支持折叠诊断面板
- 移动窗口窄宽度时允许自动收起

## 12. 第一阶段实施顺序

1. 新增后端诊断聚合接口，但仅拼现有数据。
2. 改造前端壳层为三栏布局。
3. 新增诊断面板骨架与轮询逻辑。
4. 先做查询标签深诊断。
5. 接入购买标签基础诊断。
6. 接入登录任务标签基础诊断。
7. 最后补折叠、异常态、空态与刷新节奏优化。

## 13. 非目标

以下内容不属于第一阶段目标：

- 完整日志平台
- 历史日志归档
- 文本日志文件下载
- 事件全文搜索
- 复杂筛选系统
- 多用户日志审计
- 独立日志数据库
