# 购买运行页抽屉分配与热应用设计

日期：2026-03-20

## 1. 目标

在新的 `app_desktop_web` 购买系统页上，同时完成三件事：

- 把 `最近事件` 与 `查看账号详情` 从常驻侧栏改为独立 modal
- 把商品级分配编辑移到购买页商品抽屉中管理
- 让分配保存后立即热应用到当前运行中的查询配置，但不重建账号 session

这次设计既包含 UI 重排，也包含查询运行时的最小热更新通道。

## 2. 当前问题

当前购买页虽然已经具备基础运行态展示，但仍有几个关键问题：

1. `最近事件` 与 `账号监控` 常驻页面，抢占了购买商品主视区。
2. 商品行虽然已经在做紧凑化，但还不能在商品下方直接展开管理分配与命中来源。
3. 商品分配主要停留在查询配置页，和“实际扫货运行态”割裂。
4. 当前配置保存与运行时调度之间没有“热应用”桥接，修改分配后只能依赖后续重启或额外处理。
5. 用户已经明确要求：
   - 分配本质上只是“查询者下一轮查询哪个商品”
   - 当前轮任务可以跑完
   - 下一轮重新向调度器取任务时按新分配生效
   - 切换配置或修改分配时，账号 session 必须复用，不能重登、不能重建 HTTP session

## 3. 已确认的用户决策

以下内容已经确认：

- 购买页主区保留商品运行列表，不保留常驻右侧 `最近事件 / 账号监控`
- 页面底部保留三个并列悬浮动作：
  - `最近事件`
  - `查看账号详情`
  - `开始扫货 / 停止扫货`
- `最近事件` 与 `查看账号详情` 分别打开各自独立的居中 modal
- 两个 modal 都必须支持：
  - 拖动
  - 改变大小
  - 运行期间记住当前位置和尺寸
- 商品行指标文案调整为：
  - `成功`（原 `已购`）
  - `失败`（原 `回执`）
- 每个商品行支持展开抽屉
- 抽屉承担两类功能：
  - 查看命中来源
  - 编辑查询分配
- 分配编辑不再作为查询配置页里的主要操作入口，而迁移到购买页抽屉
- 分配结果仍然保存回配置，下次重新使用同一配置时沿用该分配
- 保存策略采用手动保存：
  - 用户在抽屉里调整
  - 点击 `保存分配`
  - 不做自动保存
- 保存后如果当前正在运行的就是这个配置，则立即热应用
- 热应用的真实语义已经冻结为：
  - 不打断当前查询中的 worker
  - 当前轮跑完
  - worker 下一轮重新向 allocator 取任务时按新分配生效
  - 不关闭账号 session
  - 不关闭查询 runtime

## 4. 查询者与分配语义冻结

本次设计必须先冻结“分配”到底在分什么。

### 4.1 查询者定义

购买页里说的“分配账号”不再解释成 UI 直接点名某个账号去查某个商品。

在新架构里，真正被分配的是查询运行时中的 `query worker`：

- 每个可运行的 mode 都会产生活跃 worker
- worker 完成当前轮查询后，再向 allocator 请求下一件商品
- 商品分配本质上就是控制“某类 worker 下一轮优先拿哪件商品”

因此：

- 配置层继续保存 `mode_allocations`
- UI 编辑的是每个 mode 的目标专属数量
- 运行时再把这些目标数量折算到当前活跃 worker 上

这保持了现有后端 `QueryModeAllocator` 的心智，不引入新的“显式账号绑定表”。

### 4.2 专属态与共享态

沿用现有设计，但把运行语义写清楚：

- 若某商品在某个 mode 下有目标专属数量，且当前活跃 worker 足够满足，则该商品进入 `dedicated`
- 若目标专属数量存在，但当前不足以满足，且该商品当前没有任何专属 worker，则进入 `shared`
- 进入 `shared` 后，未被专属占用的 worker 继续轮转查询这些共享商品
- 只要后续又有多出来的可用 worker，且已满足该商品目标专属数量，它就必须立刻退出共享池，回到“只吃专属查询者”的专属态

显示语义继续保留：

- `目标分配数`
- `当前状态`

其中 `当前状态` 至少包含：

- 当前实际分配数
- `专属中`
- `共享中`
- `无可用账号`
- `手动暂停`

### 4.3 动态冷却

当前 `QueryItemScheduler` 已经按 `0.5 / 实际分配账号数` 计算动态最小冷却。

本次不改这个基本公式，只要求在热应用后继续保持：

- 专属数变化后，商品下一轮查询开始使用新的实际分配数
- 因此动态冷却也随之自然变化

## 5. 方案比较

### 方案 A：继续只在查询配置页编辑分配，购买页只读展示

优点：

- 前端改动少
- 不需要购买页新增抽屉编辑器

缺点：

- 与当前运行态脱节
- 用户扫货时还得来回切页面
- 不符合已经确认的使用路径

### 方案 B：购买页编辑分配，保存配置，再通过轻量热应用接口更新当前运行时

优点：

- 配置持久化和运行时更新职责清晰
- 不需要重启查询 runtime
- 可以明确处理“配置已保存，但热应用失败”的部分成功场景
- 与当前 `mode_allocations` 数据结构兼容

缺点：

- 需要新增一个运行时热应用通道
- 前端保存动作变成两步：保存配置 + 请求热应用

### 方案 C：购买页编辑后直接停止并重启查询 runtime

优点：

- 实现概念简单

缺点：

- 破坏 session 复用目标
- 会打断正在运行中的查询
- 很容易重现此前浏览器登录链路被误伤的问题

### 结论

采用方案 B。

原因：

- 它最符合用户已经明确冻结的运行语义：当前轮不停，下一轮按新分配生效，session 不动。

## 6. 页面设计

### 6.1 页面骨架

购买页主结构调整为三层：

1. 顶部紧凑运行栏
2. 商品运行列表
3. 底部悬浮动作条

不再在主页面常驻渲染：

- `最近事件`
- `账号监控`

这两块改由 modal 承载。

### 6.2 顶部紧凑运行栏

顶部继续保留：

- 当前配置
- `选择配置 / 切换配置`
- 累积购买汇总

不在此处新增新的复杂控制。

### 6.3 商品行

每个商品行主视图显示：

- 商品名称
- `detail_min_wear ~ detail_max_wear`
- `价格 <= max_price`
- `成功`
- `命中`
- `失败`
- `查询次数`

不显示：

- 购买代号
- 运行代号
- 队列中

商品主行仍然是平铺监控行，不恢复旧式 accordion。

本次新增的是“轻量 inline drawer”：

- 默认收起
- 只承载二级管理内容
- 不是查看主指标的前置条件
- 不改变“商品关键指标默认一眼可见”的页面原则

### 6.4 商品抽屉

点击商品行后展开抽屉，抽屉分两块：

1. 命中来源区
2. 分配编辑区

#### 命中来源区

用于回答“这件商品最近是由谁提交的”。

这里的“谁”按查询运行语义展示为：

- `mode_type`
- 该 mode 下最近贡献命中的 query worker 摘要

第一阶段不要求把“分配编辑”精确到具体账号 ID。

第一阶段展示以 mode 维度为主，允许附带最近贡献者摘要，例如：

- `new_api`
- `fast_api`
- `token`

若当前运行时能稳定拿到 account display name，则可作为附加展示，但不是分配真相源。

#### 分配编辑区

按 mode 渲染一组输入项：

- `new_api`
- `fast_api`
- `token`

每项显示：

- 目标专属数量输入框
- 当前剩余可分配数量
- 超配提示
- 当前运行状态摘要

抽屉底部显示：

- `保存分配`

若当前商品被手动暂停，也在抽屉中提供切换。

`当前剩余可分配数量` 与 `超配提示` 的计算口径冻结为：

- 真相源来自 `GET /query-configs/capacity-summary`
- 以“配置可用容量”计算，不以当前活跃 worker 数计算
- `remainingCount = mode_capacity - other_items_assigned - current_draft_value`
- 若 `remainingCount < 0`，则显示超配数量 `overflowCount = abs(remainingCount)`

这样 UI 只表达“这个 mode 还允许配置多少目标专属数”，不表达“当前具体哪个账号已经被绑上”。

## 7. Modal 设计

### 7.1 最近事件 modal

由底部悬浮按钮唤起，居中打开。

要求：

- 可拖动
- 可缩放
- 运行期间记住用户调过的位置与大小
- 承载原 `PurchaseRecentEvents` 内容

### 7.2 查看账号详情 modal

同样由底部悬浮按钮唤起，居中打开。

要求：

- 可拖动
- 可缩放
- 运行期间记住用户调过的位置与大小
- 承载原 `PurchaseAccountTable` 与其补充监控信息

两个 modal 相互独立，不做共享内容容器。

## 8. 后端运行时设计

### 8.1 持久化真相源

配置真相源继续是 `QueryConfig.items[].mode_allocations`。

购买页抽屉保存分配时，仍然复用现有配置更新链路：

- `PATCH /query-configs/{config_id}/items/{query_item_id}`

不新增第二套“购买页专用配置表”。

### 8.2 热应用通道

在配置保存成功后，新增一个轻量 runtime 更新通道。

职责只有一个：

- 把某个 `query_item_id` 的最新运行配置，从配置仓库同步到当前活动 query runtime

这里的“最新运行配置”同时包含：

- `mode_allocations`
- `manual_paused`

该通道的服务边界冻结为：

- 输入：`config_id + query_item_id`
- 行为：若当前活动配置就是该 `config_id`，则刷新运行时该商品的 allocator 视图
- 行为：若当前处于 `waiting_purchase_accounts` 且绑定的仍是该配置，则不做 live mutate，但返回“已应用到待恢复配置”
- 行为：若当前没有运行该配置，则跳过热应用，只保留配置保存结果

实现层不要求重建整个 runtime，也不要求重建 mode runner。

HTTP contract 冻结为：

- `POST /query-configs/{config_id}/items/{query_item_id}/apply-runtime`
- request body：空
- response body：
  - `status`
  - `message`
  - `config_id`
  - `query_item_id`

`status` 枚举冻结为：

- `applied`
  - 当前有 live runtime，且已把最新配置推入运行时
- `applied_waiting_resume`
  - 当前没有 live query loop，但该配置正处于 `waiting_purchase_accounts`
  - 下次恢复时自动按最新保存配置启动
- `skipped_inactive`
  - 当前没有绑定该配置的运行态，只保存配置，不做运行时同步
- `failed_after_save`
  - 配置已保存，但 live runtime 同步失败

返回语义冻结为：

- route 总是返回 `200`
- 只有配置或商品不存在时才返回 `404`
- `failed_after_save` 通过响应体表达，而不是通过回滚保存结果表达

该接口必须是幂等的：

- 对同一份最新已保存配置重复调用，不会造成重复副作用

### 8.3 热应用语义

热应用必须满足：

1. 不关闭 `RuntimeAccountAdapter` 持有的 session
2. 不调用 `QueryRuntimeService.stop()`
3. 不重建 `QueryTaskRuntime`
4. 不中断当前已经取到手的 `QueryItemReservation`
5. 只影响 worker 下一次调用 allocator 时拿到的商品

这意味着运行时只需要支持：

- 更新内存中的 `query_item.mode_allocations`
- 更新内存中的 `query_item.manual_paused`
- 触发 allocator 重新 reconcile dedicated/shared 绑定

### 8.4 运行时落点与线程边界

本次热应用的主要落点应当在：

- `QueryRuntimeService`
- `QueryTaskRuntime`
- `ModeRunner`
- `QueryModeAllocator`

职责边界冻结为：

- `QueryRuntimeService`
  - 判断当前是否存在活动配置
  - 判断活动配置是否匹配
  - 从 repository 读取最新 `QueryItem`
  - 把“刷新某个 query item”命令下发到 runtime
  - 对外返回 `applied / applied_waiting_resume / skipped_inactive / failed_after_save`
- `QueryTaskRuntime`
  - 持有唯一的 live runtime 更新入口
  - 通过 `asyncio.run_coroutine_threadsafe(...)` 把刷新命令投递到自己的后台 event loop
  - 不允许主线程直接改 `ModeRunner` live object
- `ModeRunner`
  - 若自身 mode 受影响，则更新内部 `query_items`
  - 在 runtime event loop 线程内串行执行刷新
  - 让 allocator 在下一轮取任务前看到新配置
- `QueryModeAllocator`
  - 基于最新 `mode_allocations` 与活跃 worker 重算 dedicated/shared 绑定

安全约束冻结为：

- 所有 live runtime 配置变更都只能在 `QueryTaskRuntime` 的后台 event loop 线程执行
- 主线程只允许：
  - 读 repository
  - 发送“应用某个 query item 更新”命令
  - 等待命令结果
- `snapshot()` 继续保持现有 best-effort 读语义，本次不借题扩成全面线程模型重写

### 8.5 命中来源统计

购买页商品抽屉需要看到命中来源，因此购买状态接口需要补充每个商品的来源摘要。

真相源冻结为：

- 不新增新的旁路状态器
- 直接扩展现有 `PurchaseStatsAggregator`
- 它已经是购买页展示统计的旁路聚合器
- 命中来源也从这里统一产出
- 输入事件仍然来自 purchase runtime 接收到的原始 query hit
- 接入点仍然在 fast dedupe 之前，不影响购买主链路

第一阶段为每个商品返回：

- `source_mode_stats`
  - `mode_type`
  - `hit_count`
  - `last_hit_at`
- `recent_hit_sources`
  - 最近若干条命中事件
  - 至少包含：
    - `timestamp`
    - `mode_type`
    - `match_count`
    - `account_display_name`（若可用）

最终字段挂在 `GET /purchase-runtime/status` 的 `item_rows[]` 下。

推荐结构冻结为：

- `item_rows[].source_mode_stats[]`
- `item_rows[].recent_hit_sources[]`

`recent_hit_sources[]` 最少字段冻结为：

- `timestamp`
- `mode_type`
- `match_count`
- `account_id`
- `account_display_name`

这部分只服务展示，不参与分配或购买。

## 9. 前端数据流

### 9.1 页面轮询

购买页的数据模型拆成两块：

1. `selected config detail`
2. `runtime overlay`

#### selected config detail

真相源为：

- `GET /query-configs/{config_id}`

职责：

- 提供商品基础信息
- 提供当前保存的 `mode_allocations`
- 提供 `manual_paused`
- 在“已选择配置但未运行”时，仍能渲染可编辑商品列表

#### runtime overlay

真相源为：

- `GET /purchase-runtime/status`

职责：

- 提供当前运行统计
- 提供命中来源摘要
- 提供 mode 当前状态

合并规则冻结为：

- 若 `selectedConfigId == active_query_config.config_id`
  - 用 runtime overlay 覆盖对应商品的统计字段与当前状态
- 若 `selectedConfigId` 对应的配置当前未运行
  - 仍显示 `selected config detail`
  - 统计字段显示为 0 或空
  - 不展示 live runtime 状态文案

因此 `item_rows` 需要扩展，至少让抽屉可拿到：

- 当前商品统计
- mode 状态
- 命中来源摘要

### 9.2 保存分配

购买页点击 `保存分配` 后按以下顺序执行：

1. 调用现有 `PATCH /query-configs/{config_id}/items/{query_item_id}` 保存配置
2. 调用 `POST /query-configs/{config_id}/items/{query_item_id}/apply-runtime`
3. 成功后刷新页面状态

前端必须区分四种结果：

- 配置保存成功，热应用成功
- 配置保存成功，当前处于 waiting 恢复态，恢复后自动生效
- 配置保存成功，但当前没有运行该配置，因此无需热应用
- 配置保存成功，但热应用失败

第三种场景不能回滚已保存配置，而应提示“已保存，需下次运行或手动重试应用”。

前端展示文案建议冻结为：

- `applied`：已保存，并已应用到当前运行配置
- `applied_waiting_resume`：已保存，待查询恢复时自动生效
- `skipped_inactive`：已保存；当前未运行该配置，将在下次启动时生效
- `failed_after_save`：已保存，但当前运行时未同步成功，请重试应用

## 10. 错误处理

### 10.1 保存配置失败

- 不进入热应用
- 抽屉保留用户草稿
- 直接显示错误

### 10.2 热应用失败

- 配置保存结果保留
- 当前运行态继续用旧分配
- 前端提示部分成功
- 允许用户再次点击保存或重试应用

### 10.3 运行中账号变化

若账号失效、恢复、或 mode 可用数变化：

- 仍由现有 allocator 逻辑自行 reconcile
- 某商品若因不足以满足专属目标而失去专属 worker，则按既有规则进入共享池
- 一旦又有足够 worker，多出来的 worker 应让该商品退出共享池，恢复专属态

热应用不覆盖这套动态恢复逻辑，只与其共存。

## 11. 非目标

本次明确不做：

- 不把分配编辑改成“手选具体账号 ID”
- 不做跨应用重启的位置与尺寸持久化
- 不重写查询 runtime 主循环
- 不引入新的数据库表保存购买页局部状态
- 不改变查询命中进入购买池的 fast path

## 12. 测试重点

后续实现至少需要覆盖：

1. 购买页底部显示三个悬浮动作：
   - `最近事件`
   - `查看账号详情`
   - `开始扫货 / 停止扫货`
2. `最近事件` 与 `查看账号详情` 分别打开独立 modal
3. 两个 modal 均支持拖动与缩放
4. 页面主区不再常驻渲染事件区和账号区
5. 商品行文案已切换为 `成功 / 命中 / 失败 / 查询次数`
6. 商品行可展开抽屉
7. 抽屉中能看到 mode 维度的命中来源摘要
8. 抽屉中能编辑 `mode_allocations`
9. 点击 `保存分配` 会先保存配置，再尝试热应用
10. 当前轮查询不会因热应用被中断
11. worker 下一轮取任务时按新分配生效
12. 热应用过程中不关闭账号 session
13. 若活动配置不匹配，则只保存配置，不报错
14. 若配置处于 `waiting_purchase_accounts`，返回 `applied_waiting_resume`
15. 若热应用失败，前端显示部分成功提示，且数据库配置不回滚

## 13. 结论

这次改动的关键不是“把分配 UI 挪个地方”，而是把三件事重新接上：

- 购买页成为真正的运行管理页
- 配置保存继续以 `QueryConfig` 为真相源
- 查询分配修改可以在不打断 runtime 的情况下，下一轮立即生效

只有把“分配 = 查询者下一轮拿什么商品”这个语义钉死，后续实现才不会再走回“保存一次配置就重启一大片运行时”的歪路。
