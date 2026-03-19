# 购买系统与精确统计设计

日期：2026-03-19

## 1. 目标

为新的 `app_desktop_web` 补齐独立的“购买系统”页面与后端运行时统计闭环，使系统在“当前运行中的查询配置”基础上，完成以下能力：

- 在独立购买页启动和停止扫货
- 展示当前绑定查询配置下的商品购买运行态
- 展示购买账号维度的执行与结果统计
- 保留 legacy `autobuy.py` 的快速去重语义，不增加查询到购买的延迟
- 新增一套独立的精确统计系统，用于 UI 展示真实命中、成功、失败数量

本次设计的关键不是单纯把旧购买页搬到新 UI，而是明确区分：

- 实时购买链路
- 慢速精确统计链路

这两条链路必须并存，但绝不能互相阻塞。

## 2. 当前问题

当前系统已经具备购买运行时基础能力，但仍存在以下缺口：

1. `app_desktop_web` 侧边栏已有 `purchase-system` 入口占位，但页面尚未实现。
2. 现有购买运行态接口只提供：
   - 全局运行摘要
   - 购买账号列表
   - 最近事件
3. 现有购买运行态接口没有表达：
   - 当前绑定的查询配置
   - 配置商品维度的购买统计
   - 商品查询命中真实数
   - 商品购买成功数 / 失败数
4. 现有快速去重只服务购买主链路，没有独立的精确展示统计。
5. 用户已经明确要求：
   - 新增统计系统不能增加“查询到购买”之间的延迟
   - 快速去重要参考 `autobuy.py`
   - 成功 / 失败统计必须按具体商品件数，不按批次

## 3. 已确认的用户决策

以下内容已经在讨论中确认：

- 购买系统只绑定“当前正在运行的查询配置”
- 查询系统只负责查询，购买系统只负责购买
- 查询命中后，将命中批次提交给购买池
- 购买池先做快速去重，再尽快分配给购买账号
- 查询流程不等待购买执行完成
- 没有可用购买账号时，查询运行时暂停；购买账号恢复时，查询运行时恢复
- 当前没有可用购买账号时：
  - 新命中直接忽略，不进入购买队列
  - 若最后一个可用购买账号消失，现有 backlog 立即清空
- 购买系统切换配置时只活在内存中，切换即清空旧统计
- 快速去重必须参考 `autobuy.py`
- `autobuy.py` 的快速去重逻辑为：
  - 使用 `total_wear_sum`
  - 保留 12 位小数
  - 5 秒窗口去重
- 精确统计不能复用快速去重逻辑
- 命中统计必须精确到“具体商品实例”
- 当前购买链路存在两层 ID：
  - `external_item_id`：商品模板 / 品类 ID
  - `product_list[].productId`：具体可购买商品实例 ID
- 精确统计口径为：
  - `query_item_id + product_list[].productId`
- 购买成功数按具体商品件数统计
- 购买失败数按具体商品件数统计
- 当前支付结果只返回成功件数，但购买链路可知道提交商品件数
- 因此失败件数计算规则为：
  - `failed_count = submitted_count - success_count`
- 当前执行结果模型还不能返回 `productId` 级成功 / 失败明细
- 因此第一阶段只保证：
  - 命中商品数按具体 `productId` 去重
  - 成功 / 失败数在“件数”层面精确
  - 不承诺第一阶段提供“哪一个具体 `productId` 成功 / 失败”的实例归因
- 若后续需要实例级成功 / 失败归因，必须扩展执行网关返回契约
- 新增的精确统计系统必须走旁路，不能进入购买主链路阻塞实时分发
- 命中批次若要进入购买与统计闭环，必须全链路保留：
  - `query_config_id`
  - `query_item_id`
  - `runtime_session_id`
- `waiting for purchase recovery` 仍然属于“绑定原查询配置”的状态
- 配置切换后，旧配置尚未完成的购买结果不能污染新配置统计，必须用运行代号隔离
- 现有 `/purchase-runtime/settings` 与 whitelist 语义继续保留

## 4. 方案比较

### 方案 A：把精确统计直接并入购买主链路

优点：

- 数据最集中
- 状态同步看起来简单

缺点：

- 会增加查询命中进入购买池时的处理时间
- 违背“不增加查询到购买延迟”的硬要求
- 一旦统计处理慢，实时购买链路会被拖慢

### 方案 B：实时购买链路 + 旁路精确统计聚合器

优点：

- 购买主链路最短
- 精确统计可以慢速处理，不阻塞购买
- UI 展示所需数据可以独立演进
- 最符合当前“内存态运行配置”原则

缺点：

- 后端需要维护两套语义：
  - 快速去重
  - 精确统计

### 方案 C：实时购买链路 + 落库统计系统

优点：

- 可追溯历史
- 后续报表能力最强

缺点：

- 当前范围过大
- 会引入更多迁移、回放、一致性问题
- 不符合当前“只活在运行内存中”的决策

### 结论

采用方案 B。

原因：

- 它能同时满足“实时购买不变慢”和“展示统计精确”这两个看似冲突的目标。

## 5. 总体架构

购买系统拆成两条并行链路：

1. `purchase fast path`
2. `purchase stats path`

### 5.1 purchase fast path

职责：

- 接收查询命中
- 执行 legacy 口径快速去重
- 提交购买池
- 分配购买账号
- 执行下单与支付

这条链路只追求尽快把命中商品交给购买执行，不负责精确展示统计。

### 5.2 purchase stats path

职责：

- 旁路接收命中批次与购买结果事件
- 按精确主键慢速聚合统计
- 输出商品维度和账号维度统计视图

这条链路只服务购买页展示，不参与是否购买、何时购买、分配给谁。

## 6. 数据流设计

### 6.1 命中进入购买

1. 查询执行器返回命中批次：
   - `query_config_id`
   - `query_item_id`
   - `query_item_name`
   - `external_item_id`
   - `product_url`
   - `product_list`
   - `total_price`
   - `total_wear_sum`
   - `mode_type`
   - `runtime_session_id`
2. 购买运行时接收批次
3. 快速去重检查：
   - 按 `total_wear_sum` 保留 12 位小数
   - 使用 5 秒 TTL
4. 若未命中快速去重：
   - 立刻入购买池
   - 立刻通知后台购买线程分发
5. 同时将原始批次复制给精确统计聚合器

精确统计聚合器的接入点必须明确为：

- 接在购买运行时接收到“原始 query hit”之后
- 接在 fast dedupe 之前
- 接收对象必须是原始命中载荷，而不是压缩后的 `PurchaseHitBatch`

这里的命中批次必须在进入购买批次模型后仍保留：

- `query_config_id`
- `query_item_id`
- `runtime_session_id`

否则商品维度统计、配置归属、切换隔离都无法可靠实现。

这样设计后：

- `matched_product_count` 能看到 fast dedupe 挡掉之前的原始命中真相
- 购买 fast path 仍然可以继续使用压缩后的批次模型
- 统计旁路不会因为复用 `PurchaseHitBatch` 而丢失身份字段

### 6.2 购买结果回流

账户工作者完成购买后，向精确统计聚合器提交结果事件：

- `account_id`
- `query_config_id`
- `query_item_id`
- `runtime_session_id`
- `submitted_count`
- `success_count`
- `failed_count = submitted_count - success_count`
- `product_list`
- `status`

第一阶段结果事件只要求“件数级精确”：

- 可以精确增加成功件数和失败件数
- 不能声称已经知道哪些具体 `productId` 成功、哪些失败

如果未来需要实例级成功 / 失败归因，必须把执行网关契约扩展为返回：

- `succeeded_product_ids`
- `failed_product_ids`

### 6.3 统计与购买解耦

精确统计聚合器只接收事件，不回调购买池，不反向控制调度器。

即使精确统计处理慢：

- 不影响购买池继续分配
- 不影响购买执行继续运行
- 只会影响购买页数据刷新速度

## 7. 快速去重与精确统计的职责边界

### 7.1 快速去重

沿用 `autobuy.py` 口径：

- 去重键：`total_wear_sum`
- 规范化：12 位小数
- 时间窗口：5 秒
- 目的：尽快过滤短时间内的重复命中，避免重复下单

它是近似去重，不代表真实商品数。

### 7.2 精确统计

精确统计只用于展示，主键为：

- `query_item_id + product_list[].productId`

解释：

- `query_item_id` 用于区分不同配置商品
- `product_list[].productId` 用于区分同一模板商品下的具体商品实例

因此：

- 同一个 `external_item_id` 下的不同具体商品必须分开统计
- 同一个 `productId` 在不同 `query_item_id` 下也必须视为不同统计归属

需要注意：

- 这个主键当前只用于“命中商品数”去重
- 第一阶段的成功 / 失败统计只保证件数级精确
- 第一阶段不维护 `productId` 级成功 / 失败生命周期状态

字段口径需要进一步冻结为：

- `matched_product_count`：
  - 以 `(runtime_session_id, query_item_id, productId)` 为唯一键
  - 在当前统计会话内，同一具体商品重复命中只记 1 次
  - 即使该命中后来被 fast dedupe 挡掉，也仍然属于“真实查询命中”
- `purchase_success_count`：
  - 按购买执行结果中的成功件数累计
  - 不做 `productId` 去重
- `purchase_failed_count`：
  - 按购买执行结果中的失败件数累计
  - 不做 `productId` 去重

## 8. 精确统计模型

### 8.1 商品维度视图

为当前运行配置下的每个 `query_item_id` 维护聚合结果：

- `query_item_id`
- `query_item_name`
- `item_name`
- `max_price`
- `detail_min_wear`
- `detail_max_wear`
- `query_execution_count`
- `matched_product_count`
- `purchase_success_count`
- `purchase_failed_count`
- `last_event_at`

其中：

- `query_execution_count` 表示该商品在当前运行配置下实际执行查询的累计次数
- `matched_product_count` 表示真实命中具体商品件数
- `purchase_success_count` / `purchase_failed_count` 均按具体商品件数累计

这里需要明确区分两类不同概念：

- `query_execution_count`：真实执行了多少次查询
- `actual_dedicated_count`：当前被多少个查询账号承接

购买页需要展示前者，不是后者。

这里还要明确区分两种“精确”：

- `matched_product_count`：按 `productId` 去重后的真实命中数
- `purchase_success_count / purchase_failed_count`：按购买结果件数累计的精确数量

第一阶段后者不承诺保留到单个 `productId` 的成功 / 失败归因。

`query_execution_count` 的真相源必须定义为：

- 由 query runtime 扩展自己的 `item_rows`
- 为每个 `query_item_id` 新增 `query_count`
- 其值等于当前活动配置生命周期内，该商品跨所有 mode 的真实查询执行次数总和

购买页不得用以下字段替代：

- `actual_dedicated_count`
- 配置目标分配数
- 全局 `total_query_count`

### 8.2 账号维度视图

为每个购买账号维护：

- `account_id`
- `display_name`
- `purchase_pool_state`
- `purchase_capability_state`
- `selected_steam_id`
- `selected_inventory_remaining_capacity`
- `selected_inventory_max`
- `submitted_product_count`
- `purchase_success_count`
- `purchase_failed_count`
- `total_purchased_count`

说明：

- `total_purchased_count` 继续沿用运行时现有“累计成功购买件数”
- 新增的 `submitted_product_count / purchase_failed_count` 用于购买页完整展示

### 8.3 全局摘要视图

购买页顶部摘要至少包括：

- `running`
- `message`
- `active_query_config_id`
- `active_query_config_name`
- `queue_size`
- `active_account_count`
- `total_account_count`
- `matched_product_count`
- `purchase_success_count`
- `purchase_failed_count`

## 9. UI 页面设计

### 9.1 页面入口

`app_desktop_web` 侧边栏中的 `purchase-system` 从占位态变为可点击页面。

### 9.2 页面骨架

购买页分为三块：

1. 顶部运行摘要区
2. 中部配置商品折叠列表
3. 下部购买账号统计区

右下角固定主操作按钮：

- `开始扫货`
- `停止扫货`

### 9.3 顶部运行摘要区

显示：

- 当前绑定配置名
- 购买运行状态
- 队列数
- 活跃购买账号数
- 真实命中件数
- 购买成功件数
- 购买失败件数

### 9.4 配置商品折叠列表

商品列表来自当前运行中的查询配置。

每个商品折叠项显示：

- 商品名
- 当前价格阈值
- 当前磨损配置
- 被查询次数
- 真实查询命中件数
- 购买成功件数
- 购买失败件数

说明：

- `被查询次数` 指当前配置运行期间，该商品的真实查询执行次数
- 它不等于当前有多少个账号正在承接该商品

展开后可进一步显示：

- 最近事件
- 当前运行状态提示

### 9.5 购买账号统计区

每个账号行显示：

- 账号显示名
- 购买能力状态
- 购买池状态
- 当前仓库
- 当前仓库容量
- 已提交件数
- 购买成功件数
- 购买失败件数
- 已购件数

### 9.6 近期事件区

保留现有 `recent_events`，并继续作为运行态问题定位视图。

事件区可以显示：

- `queued`
- `success`
- `auth_invalid`
- `paused_no_inventory`
- `inventory_recovered`
- `duplicate_filtered`
- `ignored_no_available_accounts`

近期事件主要用于运行排障，不承担精确统计职责。

## 10. 状态接口设计

### 10.1 现有接口

当前已有：

- `GET /purchase-runtime/status`
- `POST /purchase-runtime/start`
- `POST /purchase-runtime/stop`
- `GET /purchase-runtime/settings`
- `PUT /purchase-runtime/settings`

### 10.2 推荐扩展方式

优先扩展现有 `GET /purchase-runtime/status`，补充以下字段：

- `active_query_config`
  - `config_id`
  - `config_name`
  - `state`
- `item_rows`
  - 当前配置商品购买统计列表
- 顶层新增摘要字段
  - `matched_product_count`
  - `purchase_success_count`
  - `purchase_failed_count`

原因：

- desktop web 购买页只需要一个轮询入口
- 避免页面初期加载多个接口拼接

其中 `item_rows.query_execution_count` 的真相源来自查询运行时，而不是购买统计聚合器。

购买运行时在对外返回状态时，应当读取当前活动查询配置对应的查询运行态，再把查询执行次数与购买统计视图合并成购买页所需的商品行。

现有 `accounts` 字段继续保留，并做增量扩展：

- 保持已有字段不删不改语义
- 新增：
  - `submitted_product_count`
  - `purchase_success_count`
  - `purchase_failed_count`

不单独再设计与 `accounts` 竞争真相源的 `account_rows`。

组合方式也必须冻结：

- 只在 route / use case / assembler 层做 purchase status + query status 的组合
- 不让 `PurchaseRuntimeService` 反向依赖 `QueryRuntimeService`
- 不改变当前 `QueryRuntimeService -> PurchaseRuntimeService` 的依赖方向

### 10.3 查询配置联动

购买运行时状态需要知道“当前运行中的查询配置”：

- 若查询运行时有活动配置，则购买页绑定该配置
- 若查询运行时处于“等待购买账号恢复”，仍绑定原配置
- 只有当查询运行时确实不存在活动配置且不存在待恢复配置时，才显示无活动配置

购买运行时不自行选择配置真相源，而是读取查询运行时当前活动配置。

因此 `active_query_config.state` 至少需要表达：

- `running`
- `waiting_purchase_accounts`
- `idle`

## 11. 内存生命周期

### 11.1 创建时机

精确统计聚合器在购买运行时启动时创建。

同时生成新的 `runtime_session_id`，作为当前购买统计会话代号。

### 11.2 清空时机

以下情况必须清空统计：

- 购买运行时停止
- 当前绑定查询配置切换
- 购买运行时重新启动

每次清空统计时，都必须生成新的 `runtime_session_id`。

旧批次如果仍在飞行中：

- 可以继续走完购买执行
- 但其结果事件若 `runtime_session_id` 不匹配当前会话，必须丢弃，不得污染新统计

### 11.3 不落库

本阶段精确统计不落库，不保留历史。

原因：

- 用户已确认运行态切换即清空
- 当前目标是支撑购买页实时展示，不是做历史报表

## 12. 失败件数结算规则

购买结果当前只返回成功件数，但系统已知提交批次包含多少具体商品。

因此统一规则如下：

- `submitted_count = len(product_list)`
- `success_count = payment successCount`
- `failed_count = submitted_count - success_count`

边界情况：

- 若整批执行失败且没有成功件数：
  - `success_count = 0`
  - `failed_count = submitted_count`
- 若部分成功：
  - 同时增加成功件数和失败件数

这套规则适用于：

- 商品维度统计
- 账号维度统计
- 全局摘要统计

但它只解决“件数统计”，不解决“哪一个具体 `productId` 成功 / 失败”的实例归因。

失败件数的适用边界必须明确：

- 会增加 `purchase_failed_count` 的，是已经进入账户购买执行路径的终态失败
- 第一阶段应至少包括：
  - `order_failed`
  - `payment_failed`
  - `invalid_batch`
  - `auth_invalid`
  - `paused_no_inventory`
- 不增加 `purchase_failed_count`、只记运行事件的包括：
  - `ignored_no_available_accounts`
  - `duplicate_filtered`
  - `queued`
  - `inventory_recovered`

## 13. 与现有后端的关系

### 13.1 保留现有能力

以下能力继续复用现有实现：

- 后台购买线程
- 线程安全购买调度器
- 库存刷新与恢复检查
- 购买账号状态同步
- 查询无购买账号时暂停 / 恢复

### 13.2 新增能力

新增的核心只有两类：

1. 购买页状态表达
2. 精确统计聚合器

不重写现有购买执行网关，不改变现有查询到购买的桥接方式。

## 14. 测试重点

后续实现必须覆盖：

1. 购买页可从侧边栏进入并显示真实页面
2. 购买运行时状态能表达当前绑定查询配置
3. 商品维度统计按 `query_item_id + productId` 去重
4. 快速去重继续保持 `total_wear_sum` 5 秒窗口，不回归
5. 精确统计不会阻塞 `accept_query_hit`
6. 成功件数按 `successCount` 累计
7. 失败件数按 `submitted_count - success_count` 累计
8. 当前无可用购买账号时：
   - 新命中被忽略
   - backlog 被清空
9. 停止购买运行时会清空统计
10. 切换活动查询配置时会清空统计并更换 `runtime_session_id`
11. 旧配置飞行中结果不会污染新统计
12. 购买页账号区正确展示成功 / 失败 / 已购件数
13. `/purchase-runtime/settings` 与 whitelist 语义不回归
14. 最近事件仍可用于定位实时问题

## 15. 分阶段实施建议

### 第一阶段

- 扩展购买运行时状态结构
- 引入内存精确统计聚合器
- 打通 desktop web 购买页骨架

### 第二阶段

- 补齐商品折叠详情与近期事件联动
- 优化账号区状态展示

### 第三阶段

- 根据手动测试体验精修页面布局和状态文案

## 16. 结论

本次设计的核心结论是：

- 实时购买与精确统计必须双轨运行
- 快速去重继续遵循 `autobuy.py`
- 命中统计按“具体商品实例”计算
- 成功 / 失败按具体商品件数累计，不按批次
- 统计系统必须是旁路，绝不能增加查询到购买的延迟

只有先把这几条硬边界锁死，新的购买系统页面才不会再次出现“界面做出来了，但后端语义不对”的问题。
