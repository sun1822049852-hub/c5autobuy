# 查询统计与账号能力统计持久化设计

日期：2026-03-21

## 1. 文档目的

本文用于冻结当前 `app_desktop_web` 新 UI 所需的统计与偏好持久化方案，覆盖以下三件事：

- 购买页手动选择配置的持久化
- 查询统计页的商品视角统计
- 账号能力统计页的账号性能统计

本文只服务当前正在建设的新 UI。

用户已经明确说明：这套 UI 完成后，其他旧 UI 会被删除；因此本设计不为 legacy 页面、兼容层或旧入口保留额外负担。

若与以下旧文档局部冲突，以本文为准：

- `docs/superpowers/specs/2026-03-19-purchase-system-design.md`
- `docs/superpowers/specs/2026-03-20-purchase-page-ui-freeze-design.md`

## 2. 范围

本文覆盖：

- 购买页所选配置在页面切换、刷新、重启后的持久化规则
- 查询统计页与账号能力统计页的页面职责拆分
- 统计数据的持久化模型
- 统计数据的按天聚合与时间范围筛选
- 不影响 `查询 -> 购买池 -> 分配 -> 执行购买` 主链路延迟的异步统计链路
- 查询与购买两侧 latency 的统计口径
- 面向当前 UI 的读模型与接口边界

本文不覆盖：

- 旧 UI、兼容层、`pyui` 的适配
- 购买执行网关的完整重写
- 统计页的最终视觉稿
- 原始明细事件的长期审计仓库

## 3. 当前问题

结合当前代码状态，存在以下问题：

1. 购买页当前所选配置会被运行态覆盖或清空，无法稳定跨页面、刷新、重启保留。
2. 购买页商品统计主要来自 runtime snapshot，重启后丢失，不具备真正的持久化能力。
3. 现有购买统计聚合器以 `query_item_id` 为主键，而不是以商品真实身份 `external_item_id` 为主键，导致跨配置共用统计时语义错误。
4. 查询命中链路已经带有 `account_id`、`mode_type`、`latency_ms` 等关键字段，但这些信息没有沉淀为可持久化的账号性能统计。
5. 购买执行结果目前缺少结构化的 `create_order_latency_ms` 与 `submit_order_latency_ms`，无法支撑账号能力统计页。
6. 当前统计接口与购买运行态接口耦合过深，不利于后续拆出独立的查询统计页与账号能力统计页。
7. 系统还没有“累计 + 按天”双层统计结构，无法支持“总和 / 某一天 / 某时间段”的筛选需求。

## 4. 已确认的用户决策

以下内容已经在会话中明确拍板：

- 当前只考虑新 UI，其他 UI 不纳入本次设计约束。
- 购买页手动选择的配置必须持久化。
- 该选择在页面切换、刷新、重启后仍然保留。
- 只有“用户手动切换配置”或“所选配置被删除”才允许改变持久化选择。
- 查询统计页只保留商品视角，不展示账号性能。
- 查询统计页的主体信息为：
  - 命中
  - 成功
  - 失败
  - 来源统计
- 商品统计以 `external_item_id` 作为主身份，跨配置共享同一份统计。
- 同一商品不同规则仍保留 `rule_fingerprint` 维度，用于后续下钻。
- `rule_fingerprint` 固定由以下字段组成：
  - `detail_min_wear`
  - `detail_max_wear`
  - `max_price`
- “购买统计页”正式重命名为“账号能力统计页”。
- 账号能力统计页按表格展示，列固定为：
  - 账号名称
  - `new_api` 查询速度
  - `fast_api` 查询速度
  - `browser` 查询速度
  - 订单发送速度
  - 购买速度
- 上述五个速度列显示格式固定为：
  - `平均耗时(ms) + 样本数`
  - 例如：`182ms · 34次`
- 五个速度列的口径固定为：
  - `new_api` / `fast_api` / `browser`：查询耗时
  - 订单发送速度：`create_order_latency_ms`
  - 购买速度：`submit_order_latency_ms`
- 统计支持时间筛选，按“自然日”聚合。
- 统计页右上角允许选择：
  - 总和
  - 某一天
  - 某时间段
- 统计信息要进入数据库持久化。
- 运行时调度状态仍保留在内存。
- 统计绝不能拖慢 `查询 -> 购买池 -> 分配 -> 执行购买` 主链路。
- 允许为了保证主链路延迟而丢失最后一小段尚未 flush 的统计事件。
- 允许在统计队列满时直接丢弃统计事件，而不是阻塞主链路。

## 5. 方案比较

### 方案 A：在主链路中同步更新统计表

优点：

- 架构看起来最直接
- 不需要额外事件队列

缺点：

- 每次 query 命中、创建订单、提交订单都会直接引入数据库写入
- 数据库抖动会直接放大成购买延迟
- 违背“主链路延迟必须最低”的硬要求

### 方案 B：原始事件全量落库，再离线聚合

优点：

- 明细最完整
- 后续审计、追溯能力最强

缺点：

- 首版复杂度高
- 原始事件写入量大
- 即使异步落库，也会引入更多序列化、写放大和清理成本
- 当前需求核心是统计页，不是审计回放页，首版投入与收益不匹配

### 方案 C：主链路 fire-and-forget + 异步聚合落库

优点：

- 主链路最短
- 统计与 runtime 调度彻底解耦
- 可以同时支持累计统计与按天统计
- 可以接受少量统计丢失而保持主链路稳定
- 最符合当前用户优先级

缺点：

- 统计为最终一致，不是瞬时强一致
- 需要单独维护统计队列、聚合器与 flush 机制

## 6. 推荐方案

采用方案 C：

- 主链路只负责把命中商品尽快送入购买池
- 统计通过轻量事件旁路发送到独立 stats pipeline
- stats pipeline 在后台聚合并批量写数据库
- 页面统计一律读取数据库聚合结果，不再从 runtime memory 拼接伪持久化数据

这意味着系统将明确分为两条链：

### 6.1 Fast Path：实时购买主链路

`查询执行 -> 命中 -> 购买池 -> 账号分配 -> 创建订单 -> 提交订单`

要求：

- 不等待统计结果
- 不等待数据库
- 不回读统计表
- 不因为统计缺失而影响购买决策

### 6.2 Slow Path：统计旁路

`事件入队 -> 后台聚合 -> 批量 flush -> 统计页读取`

特点：

- 最终一致
- 可接受短时间延迟
- 可接受少量事件丢失
- 只影响统计页刷新速度，不影响抢购速度

## 7. 持久化模型

### 7.1 `purchase_ui_preferences`

用途：

- 保存购买页的 UI 偏好，目前只要求保存手动选择的配置

建议字段：

- `id`
- `selected_config_id`
- `updated_at`

规则：

- 页面初始化时先读取该表
- 只有手动切换配置时更新
- 若配置被删除，则清空 `selected_config_id`
- `active_query_config` 仅表示当前 runtime 正在跑什么，不允许反向覆盖该偏好

### 7.2 `query_item_stats_total`

用途：

- 保存商品维度的累计统计
- 面向查询统计页和购买页商品行的持久化数据

主键语义：

- `external_item_id`

建议字段：

- `external_item_id`
- `item_name_snapshot`
- `product_url_snapshot`
- `query_execution_count`
- `matched_product_count`
- `purchase_success_count`
- `purchase_failed_count`
- `new_api_hit_count`
- `fast_api_hit_count`
- `browser_hit_count`
- `last_hit_at`
- `last_success_at`
- `last_failure_at`
- `updated_at`

说明：

- 虽然查询统计页首版不展示 `query_execution_count`，但该值仍保留，用于购买页商品行与后续诊断。
- `browser_hit_count` 对应内部 `token` 模式的展示名。

### 7.3 `query_item_stats_daily`

用途：

- 保存商品维度的按天统计
- 用于“某一天 / 某时间段”查询

主键语义：

- `external_item_id + stat_date`

建议字段：

- `external_item_id`
- `stat_date`
- `item_name_snapshot`
- `product_url_snapshot`
- `query_execution_count`
- `matched_product_count`
- `purchase_success_count`
- `purchase_failed_count`
- `new_api_hit_count`
- `fast_api_hit_count`
- `browser_hit_count`
- `updated_at`

### 7.4 `query_item_rule_stats_total`

用途：

- 保存“同一商品 + 不同规则”的累计统计
- 当前页不必首版直接展示，但保留为后续下钻基础

主键语义：

- `external_item_id + rule_fingerprint`

建议字段：

- `external_item_id`
- `rule_fingerprint`
- `detail_min_wear`
- `detail_max_wear`
- `max_price`
- `query_execution_count`
- `matched_product_count`
- `purchase_success_count`
- `purchase_failed_count`
- `updated_at`

### 7.5 `query_item_rule_stats_daily`

用途：

- 保存“同一商品 + 不同规则”的按天统计

主键语义：

- `external_item_id + rule_fingerprint + stat_date`

建议字段：

- `external_item_id`
- `rule_fingerprint`
- `stat_date`
- `detail_min_wear`
- `detail_max_wear`
- `max_price`
- `query_execution_count`
- `matched_product_count`
- `purchase_success_count`
- `purchase_failed_count`
- `updated_at`

### 7.6 `account_capability_stats_total`

用途：

- 保存账号能力统计页所需的累计性能数据

主键语义：

- `account_id + mode_type + phase`

说明：

- `phase` 固定为：
  - `query`
  - `create_order`
  - `submit_order`
- `mode_type` 在查询阶段取：
  - `new_api`
  - `fast_api`
  - `token`
- `create_order` 与 `submit_order` 阶段不依赖 `mode_type` 决策，但仍允许保留统一主键形状；首版可写入固定值 `purchase`

建议字段：

- `account_id`
- `account_display_name_snapshot`
- `mode_type`
- `phase`
- `sample_count`
- `success_count`
- `failure_count`
- `total_latency_ms`
- `max_latency_ms`
- `last_latency_ms`
- `last_error`
- `updated_at`

### 7.7 `account_capability_stats_daily`

用途：

- 保存账号能力统计页所需的按天性能数据

主键语义：

- `account_id + mode_type + phase + stat_date`

建议字段：

- `account_id`
- `account_display_name_snapshot`
- `mode_type`
- `phase`
- `stat_date`
- `sample_count`
- `success_count`
- `failure_count`
- `total_latency_ms`
- `max_latency_ms`
- `last_latency_ms`
- `last_error`
- `updated_at`

## 8. 事件模型

为满足“次数、命中、成功、失败、来源、账号耗时”全部进入统计系统，同时不阻塞主链路，统计旁路接收以下事件。

### 8.1 `query_execution_event`

用途：

- 记录一次实际查询执行完成
- 用于累计 `query_execution_count`

建议字段：

- `timestamp`
- `query_config_id`
- `query_item_id`
- `external_item_id`
- `rule_fingerprint`
- `detail_min_wear`
- `detail_max_wear`
- `max_price`
- `mode_type`
- `account_id`
- `account_display_name`
- `latency_ms`
- `success`
- `error`

说明：

- 该事件即使没有命中商品，也应该发送。
- 它是“查询次数持久化”的来源。
- 该事件只做轻量入队，不能反向阻塞 query scheduler。

### 8.2 `query_hit_event`

用途：

- 记录一次查询命中商品
- 用于累计商品命中、来源统计，以及账号查询 latency 统计

建议字段：

- `timestamp`
- `runtime_session_id`
- `query_config_id`
- `query_item_id`
- `external_item_id`
- `rule_fingerprint`
- `detail_min_wear`
- `detail_max_wear`
- `max_price`
- `mode_type`
- `account_id`
- `account_display_name`
- `product_url`
- `latency_ms`
- `matched_count`
- `product_list`

说明：

- 现有 query 命中链已经具备大部分字段。
- `matched_count` 表示本次命中的具体商品件数。
- `product_list` 仅用于需要时辅助计算成功/失败件数，不要求长期原样落库。

### 8.3 `purchase_create_order_event`

用途：

- 记录一次创建订单行为
- 用于账号能力统计页的“订单发送速度”

建议字段：

- `timestamp`
- `runtime_session_id`
- `query_config_id`
- `query_item_id`
- `external_item_id`
- `rule_fingerprint`
- `account_id`
- `account_display_name`
- `create_order_latency_ms`
- `submitted_count`
- `status`
- `error`

### 8.4 `purchase_submit_order_event`

用途：

- 记录一次提交订单行为
- 用于账号能力统计页的“购买速度”
- 用于累计商品成功/失败件数

建议字段：

- `timestamp`
- `runtime_session_id`
- `query_config_id`
- `query_item_id`
- `external_item_id`
- `rule_fingerprint`
- `account_id`
- `account_display_name`
- `submit_order_latency_ms`
- `submitted_count`
- `success_count`
- `failed_count`
- `status`
- `error`

说明：

- `failed_count = submitted_count - success_count`
- 即使支付响应只返回成功件数，也可以由调用侧推导出失败件数

## 9. 统计聚合规则

### 9.1 商品累计统计

- `query_execution_event` 增加 `query_execution_count`
- `query_hit_event` 增加 `matched_product_count`
- `query_hit_event` 根据 `mode_type` 增加对应来源计数
- `purchase_submit_order_event` 增加：
  - `purchase_success_count`
  - `purchase_failed_count`

### 9.2 商品按天统计

- 以上同样规则按 `stat_date` 写入 daily 表
- `stat_date` 按本地自然日生成，格式为 `YYYY-MM-DD`

### 9.3 规则维度统计

- `query_execution_event`
- `query_hit_event`
- `purchase_submit_order_event`

都按 `external_item_id + rule_fingerprint` 进行同口径累计

### 9.4 账号能力统计

- `query_execution_event` 更新：
  - `phase=query`
  - `mode_type=new_api / fast_api / token`
- `purchase_create_order_event` 更新：
  - `phase=create_order`
  - `mode_type=purchase`
- `purchase_submit_order_event` 更新：
  - `phase=submit_order`
  - `mode_type=purchase`

页面显示时：

- 第二列取 `phase=query, mode_type=new_api`
- 第三列取 `phase=query, mode_type=fast_api`
- 第四列取 `phase=query, mode_type=token`，展示名为 `browser`
- 第五列取 `phase=create_order, mode_type=purchase`
- 第六列取 `phase=submit_order, mode_type=purchase`

每个单元格显示规则为：

- `sample_count <= 0` 时显示 `--`
- 否则显示 `round(total_latency_ms / sample_count)ms · {sample_count}次`

## 10. 统计旁路与性能约束

### 10.1 主链路硬约束

以下行为全部禁止进入主链路阻塞点：

- 同步写统计表
- 等待 stats queue 消费完成
- 等待统计聚合器返回
- 为统计目的增加数据库查询
- 为统计目的增加额外去重逻辑

### 10.2 stats queue

采用内存有界队列：

- 主链路只负责 `enqueue`
- 队列满时直接丢弃统计事件
- 丢弃统计事件只影响统计完整度，不影响主链路

建议同时维护内存指标：

- `dropped_stats_event_count`

用于后续诊断，但不参与购买决策

### 10.3 flush 策略

采用 `batch + short interval flush`：

- 达到批量阈值时 flush
- 达到时间阈值时 flush

要求：

- flush 在后台执行
- flush 失败可以重试
- flush 延迟只影响统计页可见时间，不影响主链路

### 10.4 一致性原则

统计系统采用最终一致：

- 统计页允许短时间落后于 runtime
- 程序异常退出时允许丢失最后一小段尚未 flush 的统计事件
- 用户已经明确接受这一取舍，以换取最低主链路延迟

## 11. 页面职责与读模型

### 11.1 查询统计页

职责：

- 商品视角统计页
- 不承载账号性能

首版显示：

- 商品名称
- 命中
- 成功
- 失败
- 来源统计

数据来源：

- `query_item_stats_total`
- `query_item_stats_daily`

时间模式：

- 总和
- 某一天
- 某时间段

### 11.2 账号能力统计页

职责：

- 账号综合性能页
- 不承载商品主视角统计

表头固定为：

- 账号名称
- `new_api`
- `fast_api`
- `browser`
- 订单发送速度
- 购买速度

列值固定为：

- `平均耗时(ms) + 样本数`

数据来源：

- `account_capability_stats_total`
- `account_capability_stats_daily`

时间模式：

- 总和
- 某一天
- 某时间段

### 11.3 购买页

购买页不再承担“统计 source of truth”职责，但仍读取持久化统计用于展示商品行摘要。

购买页中的“当前所选配置”规则如下：

1. 页面初始化时读取 `purchase_ui_preferences.selected_config_id`
2. 若该配置存在，则直接作为当前页面选择
3. 若该配置已被删除，则清空偏好并回到未选择状态
4. `active_query_config` 只作为运行态展示，不得自动覆盖页面持久化选择

## 12. 接口建议

首版建议将统计读取与 UI 偏好读取拆开：

### 12.1 `GET /purchase-runtime/ui-preferences`

返回：

- `selected_config_id`
- `updated_at`

### 12.2 `PUT /purchase-runtime/ui-preferences`

请求：

- `selected_config_id`

语义：

- 用户在购买页手动切换配置时调用

### 12.3 `GET /stats/query-items`

请求参数建议：

- `range_mode=total|day|range`
- `date=YYYY-MM-DD`
- `start_date=YYYY-MM-DD`
- `end_date=YYYY-MM-DD`

返回：

- 查询统计页商品列表
- 以及购买页商品摘要可复用的持久化统计字段

### 12.4 `GET /stats/account-capability`

请求参数建议：

- `range_mode=total|day|range`
- `date=YYYY-MM-DD`
- `start_date=YYYY-MM-DD`
- `end_date=YYYY-MM-DD`

返回：

- 账号能力统计页表格数据

说明：

- 这两类统计接口不应继续寄生在 `/purchase-runtime/status` 上
- `purchase-runtime/status` 继续服务实时运行态
- 统计页读取数据库聚合结果

## 13. 错误处理与降级

### 13.1 数据库不可用

- 主链路照常运行
- stats ingestor flush 失败后重试
- 若持续失败，允许丢弃统计事件并记录日志
- 页面统计可能过时，但购买流程不得被阻塞

### 13.2 队列满

- 直接丢弃新统计事件
- 累加 `dropped_stats_event_count`
- 不阻塞主链路

### 13.3 配置被删除

- 清空 `purchase_ui_preferences.selected_config_id`
- 购买页显示未选择状态
- 不自动替换为其他配置

## 14. 验收标准

满足以下条件即可认为本设计落地正确：

1. 购买页选择的配置在页面切换、刷新、重启后仍保留。
2. 只有手动切换配置或配置被删除时，购买页选择才变化。
3. 同一 `external_item_id` 在不同配置中共用同一份商品累计统计。
4. 查询统计页可以按：
   - 总和
   - 某一天
   - 某时间段
   查看商品统计。
5. 账号能力统计页可以按：
   - 总和
   - 某一天
   - 某时间段
   查看账号能力统计。
6. 账号能力统计页六列固定为：
   - 账号名称
   - `new_api`
   - `fast_api`
   - `browser`
   - 订单发送速度
   - 购买速度
7. 五个速度列显示格式固定为 `平均耗时 + 样本数`。
8. 统计系统关闭、卡顿、数据库抖动时，不得明显增加查询到购买之间的延迟。
9. 统计队列满时，只允许丢统计，不允许拖慢主链路。

## 15. 后续实现顺序建议

1. 补齐 `purchase_ui_preferences` 持久化与购买页读取逻辑
2. 扩展 query runtime，新增 `query_execution_event`
3. 扩展 purchase execution result，补齐：
   - `create_order_latency_ms`
   - `submit_order_latency_ms`
4. 增加 stats queue、ingestor、aggregate writer
5. 落商品累计/按天统计表
6. 落账号能力累计/按天统计表
7. 新增：
   - `GET /stats/query-items`
   - `GET /stats/account-capability`
8. 将购买页商品行与后续统计页改为读取持久化统计

