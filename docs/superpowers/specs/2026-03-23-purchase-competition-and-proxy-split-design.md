# 扫货竞争模式与双代理拆分设计

日期：2026-03-23

## 1. 文档目的

本文用于冻结当前新 UI 与新后端下一阶段的三项联动改造：

- 为账户拆分“账户代理”和“API 代理”两套独立配置
- 为扫货系统增加按账户代理 IP 分桶的竞争模式
- 为左侧设置区补齐“购买设置”与“查询设置”的职责边界

本文服务对象为当前正在建设的 `app_desktop_web` 新架构，不为 legacy UI、兼容层或已删除的 `pyui` 保留兼容负担。

若与以下文档局部冲突，以本文为准：

- `docs/superpowers/specs/2026-03-18-account-center-desktop-web-frontend-design.md`
- `docs/superpowers/specs/2026-03-18-login-proxy-dialog-design.md`
- `docs/superpowers/specs/2026-03-16-query-runtime-engine-design.md`
- `docs/superpowers/specs/2026-03-17-query-runtime-mode-scoped-item-schedulers-design.md`
- `docs/superpowers/specs/2026-03-19-purchase-system-design.md`
- `docs/superpowers/specs/2026-03-20-purchase-page-ui-freeze-design.md`
- `docs/superpowers/specs/2026-03-19-query-workbench-design.md`
- `docs/superpowers/specs/2026-03-21-stats-persistence-and-account-capability-design.md`

总则补充：

- 任何旧 spec 只要仍把 `QueryConfig.mode_settings` 视为 query runtime 的活动真相源，均被本文覆盖。
- 任何旧 spec 只要仍把单一 `proxy_mode/proxy_url` 视为账户、API、购买共用的活动真相源，均被本文覆盖。

## 2. 范围

本文覆盖：

- 账户代理与 API 代理的领域模型拆分
- 账户创建、编辑、仓储与 runtime session 的代理使用规则
- 扫货竞争模式的运行语义
- 按账户代理分组的 `IP bucket` 并发限制
- `购买设置` 与 `查询设置` 的 UI 与持久化边界
- 竞争模式下成功/失败统计的口径冻结

本文不覆盖：

- 购买执行网关的协议重写
- 查询统计页与账号能力统计页的视觉终稿
- 未来“API IP”和“token IP”进一步拆分后的高级分桶策略
- 多机、多进程购买协调

## 3. 当前问题

结合当前代码状态，存在以下几个关键问题：

1. `accounts.proxy_url` 当前同时承担登录、token 查询、购买请求、`new_api`、`fast_api` 的代理来源，语义混杂。
2. `RuntimeAccountAdapter` 里 `get_global_session()` 和 `get_api_session()` 都复用同一套代理，无法表达“API 走一条线，账户/购买走另一条线”。
3. 当前购买 runtime 虽然已经从“轮询分配”优化为“ready account 直派”，但同一批命中仍然只会发给一个账号，不具备真正的竞争购买能力。
4. 系统没有“按账户代理 IP 分桶”的购买设置，用户无法控制同一 IP 下允许多少账号并发参战。
5. 左侧设置区目前缺少明确的“购买设置”位置，查询频率配置和购买竞争配置还没有被整理为两个独立区域。
6. 当前统计已经按账号成功/失败累计，但还没有正式冻结“同一批货被多个账号同时抢时，失败放大是允许且有价值的”这一产品语义。

## 4. 已确认的用户决策

以下内容已经在会话中明确拍板：

- 代理需要拆成两套：
  - `账户代理`
  - `API 代理`
- 首版两套代理的输入形式保持一致。
- 首版虽然先采用同样的填写方式，但结构上必须分开，便于后续继续拆分。
- 扫货竞争模式按“账户代理所在 IP”分桶。
- 后续若再拆 `API IP` 与 `token IP`，属于下一阶段，不阻塞本次设计。
- 同一批货允许由多个账号同时发起购买请求。
- 同一批货被多个账号同时买时，统计口径不需要特殊压平：
  - 失败数量变高是允许的
  - 这是换取更高购买成功率的代价
  - 同时也能更清楚地判断哪些账号购买能力更强
- `IP bucket` 并发上限做持久化保存。
- `IP bucket` 默认并发值固定为 `1`。
- 用户可以手动修改每个 `IP bucket` 的并发值。
- 左侧设置区要拆成并列的两块：
  - `购买设置`
  - `查询设置`
- `购买设置` 放在左侧，承担 `IP bucket` 并发设置。
- `查询设置` 继续承担三类查询器频率相关配置。

## 5. 方案比较

### 方案 A：继续复用单代理字段，竞争模式只做单队列加速

优点：

- 改动最少
- 不需要数据库迁移

缺点：

- 无法表达 API 与账户流量分离
- 用户后续想拆代理时还得再重构一次
- 同一批命中仍然无法真正多账号并发抢购

### 方案 B：为每个 IP 建完整独立购买池

优点：

- 语义完整
- 未来扩展多机、多池更自然

缺点：

- 首版改动过大
- 会把当前热路径从“直接派发”重新拉回复杂协调模型
- 容易引入新的延迟和额外状态同步成本

### 方案 C：双代理拆分 + 轻量 `IP bucket` fanout

优点：

- 能在当前 runtime 基础上最小改动落地
- 不改变主链路“命中后立刻分发”的方向
- 直接满足“同批次多账号并发购买”的目标
- 为后续代理进一步拆分预留结构

缺点：

- 需要新增数据库字段与全局 settings 表
- 统计中的失败数会更高，需要接受“尝试数”与“真实命中数”不是同一个概念

## 6. 推荐方案

采用方案 C：

- `Account` 模型拆出两套代理字段
- query runtime 的 API 链路读取 API 代理
- token / 登录 / 详情补全 / 库存刷新 / 购买链路继续读取账户代理
- 扫货命中在进入购买执行前，增加一个轻量 `competition planner`
- `competition planner` 只做：
  - 过滤可用购买账号
  - 按账户代理归一化成 `IP bucket`
  - 按 bucket 的并发上限挑选 ready 账号
  - 直接产出多条 dispatch

这个方案保持了当前“主链路只做快动作”的原则：

- 不等待统计
- 不等待慢协调
- 不等待 busy 账号回头补抢同一批货

原因很简单：这类商品一旦命中，等待往往就意味着货已经没有了。首版竞争模式的价值不在“调度更优雅”，而在“让 ready 的账号立刻一起冲”。

## 7. 代理模型拆分

### 7.1 领域模型

当前 `Account` 里只有：

- `proxy_mode`
- `proxy_url`

本次拆分后，建议改为四个真相字段：

- `account_proxy_mode`
- `account_proxy_url`
- `api_proxy_mode`
- `api_proxy_url`

其中：

- `account_proxy_*`
  - 用于登录
  - 用于 token 查询
  - 用于商品详情补全
  - 用于库存刷新
  - 用于购买创建订单与提交订单
- `api_proxy_*`
  - 用于 `new_api`
  - 用于 `fast_api`

### 7.2 兼容策略

首版迁移规则：

- 老字段 `proxy_mode/proxy_url` 迁移为 `account_proxy_mode/account_proxy_url`
- 若数据库中尚不存在 `api_proxy_*`，迁移时默认回填：
  - `api_proxy_mode = account_proxy_mode`
  - `api_proxy_url = account_proxy_url`

这样旧账号不需要手动重填，就能保持原行为不变。

### 7.3 API 与前端表单

账户创建与编辑接口都改成显式双代理输入。

首版 UI 规则：

- 两套代理的输入控件样式一致
- 两套代理都支持：
  - 直连
  - 完整代理串
  - 用户名/密码/主机/端口形式
- 若用户未单独填写 API 代理，则前端默认用账户代理值进行预填或回写

注意：

- 这里的“默认同值”只是首版交互便利
- 领域层仍然必须是两套独立字段
- 不能再回退成运行时临时猜测

## 8. Runtime session 规则

### 8.1 `RuntimeAccountAdapter`

本次设计冻结以下规则：

- `get_global_session()` 读取 `account_proxy_*`
- `get_api_session()` 读取 `api_proxy_*`

这意味着：

- token 查询器走 `global_session`
- `new_api` / `fast_api` 走 `api_session`
- 购买执行网关走 `global_session`
- 库存刷新与详情补全走 `global_session`

### 8.2 后续扩展边界

未来若要进一步拆分：

- `token_proxy`
- `purchase_proxy`
- `detail_proxy`

允许继续演进。

但本次只冻结两层：

- `account_proxy`
- `api_proxy`

避免首版把代理矩阵炸得过细。

## 9. 购买竞争模式

### 9.1 目标

当查询命中一批商品后：

- 不再只派一个 ready 账号去买
- 而是按账户代理 IP 分桶
- 允许多个 bucket 同时参战
- 同一 bucket 内也允许多个账号同时参战，但数量受该 bucket 的 `concurrency_limit` 约束

### 9.2 核心语义

竞争模式下，一个命中批次会经过以下流程：

1. 命中进入购买 runtime
2. 命中先经过原有快速去重 inbox
3. 去重通过后，不再只生成一条单账号 dispatch
4. runtime 读取当前可用购买账号快照
5. 按账户代理归一化为 `IP bucket`
6. 每个 bucket 最多挑选 `concurrency_limit` 个 ready 账号
7. 为每个被选中的账号生成一条 dispatch
8. 各账号并发发起购买请求

### 9.3 为什么不等 busy 账号

本设计明确不做以下行为：

- 不为了同一批货等待 busy 账号恢复
- 不让同一批货在 pending queue 中长时间排队等更多账号到位

原因：

- 这是抢购程序，不是离线吞吐程序
- 等待回头补抢通常只会增加延迟，不能提高成功率
- 用户目标是尽快冲，而不是让调度图看起来整齐

因此首版规则固定为：

- 只使用“命中到达当下已经 ready 的账号”
- 当前没空的账号不补追这同一批货

### 9.4 与当前 scheduler 的关系

当前 scheduler 已经具备：

- ready account 队列
- pending queue
- dispatch queue

但它的核心仍然是“一条 batch -> 一个账号”。

本次设计不直接把 per-IP 语义硬塞进现有单发接口，而是在提交给 scheduler 前增加一层 `competition planner`，将一个原始 hit 展开为多条账号级 dispatch。

也就是说：

- scheduler 继续负责账号 busy / ready 生命周期
- competition planner 负责“这个 hit 应该扇出给哪些账号”

这样边界最清晰，也最不容易污染现有状态机。

### 9.5 `competition planner ↔ scheduler` 契约

本次必须冻结 planner 与 scheduler 的接口边界，避免实现时再次混层。

#### planner 的职责

`competition planner` 是一个纯规划单元，只负责：

- 接收原始 `PurchaseHitBatch`
- 接收某一时刻的 ready account 快照
- 接收 `account_id -> bucket_key` 映射
- 接收 `bucket_key -> concurrency_limit` 映射
- 输出本次命中应该尝试的账号列表

planner 不负责：

- 修改 ready / busy 状态
- 入队等待
- 重试
- 统计

#### scheduler 的职责

`PurchaseScheduler` 继续作为运行态状态机，只负责：

- 维护 ready / busy / unavailable
- 原子化地 claim 指定账号
- 为已 claim 的账号生成可执行 dispatch
- 在账号完成后恢复 ready

#### 契约对象

建议显式引入两个对象：

- `CompetitionPlan`
  - `competition_id`
  - `batch`
  - `candidate_account_ids`
- `PurchaseDispatch`
  - `competition_id`
  - `account_id`
  - `bucket_key`
  - `batch`

#### 调用顺序

固定流程如下：

1. runtime 从 scheduler 读取 ready account 快照
2. runtime 调用 planner 生成 `CompetitionPlan`
3. runtime 将 `candidate_account_ids` 交还 scheduler
4. scheduler 通过 `claim_planned_accounts(plan)` 原子尝试 claim 这些账号
5. scheduler 只返回“此刻仍然 ready 且 claim 成功”的 `PurchaseDispatch[]`
6. runtime 为这些 dispatch 并发创建执行任务

#### 失败回退

若某些候选账号在 snapshot 与 claim 之间变成 non-ready：

- scheduler 直接丢弃这些账号
- 不等待
- 不补挑新的账号
- 不把同一命中回退到慢队列

这条规则是为了守住热路径延迟。

#### 测试边界

- planner 测试：
  - 输入快照与 bucket limit
  - 断言输出的 candidate account 列表
- scheduler 测试：
  - 输入 `CompetitionPlan`
  - 断言 claim 结果、busy/ready 转移与完成后的恢复
- runtime 集成测试：
  - 断言同一命中会生成多个执行任务
  - 断言 claim 失败账号不会阻塞其他账号执行

## 10. `IP bucket` 规则

### 10.1 bucket key

首版 bucket key 不是运行时真实解析出来的公网 IP，也不做 DNS 解析。

首版真相定义为：

- `bucket key = 归一化后的 account proxy endpoint identity`

也就是说，产品文案里继续沿用“IP bucket”这个叫法，但后端真实分桶依据是“账户代理端点身份”。

规则：

- 直连统一归到固定 key，例如 `direct`
- 同一代理的不同书写形式必须规整成同一个稳定 key
- 归一化字段固定为：
  - `scheme`
  - `host`（转小写）
  - `port`
  - `username`
- `password` 不进入 bucket key，也不进入 UI 展示
- 不做 hostname -> IP 的网络解析
- 不合并“不同 hostname 但实际解析到同一 IP”的情况
- 因此首版语义是“同代理端点视为同 bucket”，不是“同公网出口自动探测归并”

本次实现必须新增统一的 bucket key 归一化函数，不能在 UI、runtime、settings 各自拼字符串。

### 10.2 默认值

新出现的 bucket 若没有用户保存过设置：

- 默认 `concurrency_limit = 1`

### 10.3 用户修改

用户可以在左侧 `购买设置` 中手动修改：

- 某个 bucket 的并发上限

校验规则固定为：

- 必填
- 必须是整数
- 最小值为 `1`
- 不限制大于当前 bucket 账号数的输入
- runtime 实际执行时取：
  - `min(configured_limit, ready_account_count_in_bucket)`

这意味着：

- 用户可以提前为未来可能增加的账号数预留更大的 limit
- 当前 bucket 可用账号不够时，不报错，只是实际派发数达不到该上限

错误处理固定为：

- 前端提交空值、非整数、小于 `1` 的值时，本地直接拦截，不发请求
- 后端对同类非法值返回 `422`
- 保存失败时：
  - 已保存设置不变
  - 当前 runtime 不热应用
  - UI 保留用户输入并显示错误文案

保存后要求：

- 写入数据库持久化
- 后续重启后仍然保留
- 当前运行中的扫货 runtime 若支持热读，则下一个命中立即生效
- 若当前首版实现不做热读，则至少要在下次启动扫货时生效

推荐首版直接支持热读，因为这只是 settings 快照替换，不需要重建 session。

## 11. 左侧设置区设计

### 11.1 区域拆分

左侧固定拆成两个并列设置区：

- `购买设置`
- `查询设置`

### 11.2 `购买设置`

职责固定为：

- 展示当前系统识别到的 `IP bucket` 列表
- 为每个 bucket 展示：
  - 代理名称或显示文案
  - bucket 标识
  - 当前可用账号数
  - 并发上限输入框
- 提供保存入口

本区不接管以下已有能力：

- 单账号 `purchase_disabled`
- 单账号库存/仓库选择
- 单账号可购买能力状态

这些能力继续留在：

- 账号中心
- 账号详情 modal
- 购买 runtime 账号状态视图

也就是说：

- `购买设置` 只管理“全局 bucket 并发”
- `purchase_disabled` 仍然是 per-account 开关，不迁入这里

### 11.3 `查询设置`

职责继续为：

- 三种查询器的全局 cooldown 设置
- 随机冷却设置
- 时间窗口开关与时间点
- 商品最小可查询时间的全局策略

本次设计特意把 `IP 并发` 从 `查询设置` 中剥离出来，避免继续把“查询频率”和“购买竞争”混成一团。

## 12. 持久化模型

当前仓库里没有现成的通用 settings repository，因此本次需要新增一份全局 settings 落库模型。

### 12.1 `runtime_settings`

本次不再保留“键值表还是单行表”的备选态，直接冻结为单行表：

- 表名：`runtime_settings`
- 主键：`settings_id`
- 固定只维护一行：
  - `settings_id = 'default'`

首版至少包含：

- `query_settings_json`
- `purchase_settings_json`
- `updated_at`

新增仓储固定为：

- `RuntimeSettingsRepository.get() -> RuntimeSettings`
- `RuntimeSettingsRepository.save_query_settings(query_settings)`
- `RuntimeSettingsRepository.save_purchase_settings(purchase_settings)`

新增接口固定为：

- `GET /api/runtime-settings`
- `PUT /api/runtime-settings/query`
- `PUT /api/runtime-settings/purchase`

接口规则：

- `GET` 返回两块完整设置
- 两个 `PUT` 分开保存，互不覆盖另一块
- 任一 `PUT` 校验失败时返回 `422`
- 保存成功后返回完整最新 settings 快照

### 12.2 `purchase_settings_json`

建议结构：

```json
{
  "ip_bucket_limits": {
    "direct": {
      "concurrency_limit": 1
    },
    "proxy://example-bucket-key": {
      "concurrency_limit": 2
    }
  }
}
```

### 12.3 `query_settings_json`

查询设置继续承载以下全局配置：

- `new_api` cooldown
- `fast_api` cooldown
- `token` cooldown
- 随机冷却开关与范围
- 时间窗口
- 商品最小可查询时间策略

本次不再把它留在“后面再细化”的状态，首版结构冻结为：

```json
{
  "modes": {
    "new_api": {
      "enabled": true,
      "cooldown_min_seconds": 1.0,
      "cooldown_max_seconds": 1.0,
      "random_delay_enabled": false,
      "random_delay_min_seconds": 0.0,
      "random_delay_max_seconds": 0.0,
      "window_enabled": false,
      "start_hour": 0,
      "start_minute": 0,
      "end_hour": 0,
      "end_minute": 0
    },
    "fast_api": {
      "enabled": true,
      "cooldown_min_seconds": 0.2,
      "cooldown_max_seconds": 0.2,
      "random_delay_enabled": false,
      "random_delay_min_seconds": 0.0,
      "random_delay_max_seconds": 0.0,
      "window_enabled": false,
      "start_hour": 0,
      "start_minute": 0,
      "end_hour": 0,
      "end_minute": 0
    },
    "token": {
      "enabled": true,
      "cooldown_min_seconds": 10.0,
      "cooldown_max_seconds": 10.0,
      "random_delay_enabled": false,
      "random_delay_min_seconds": 0.0,
      "random_delay_max_seconds": 0.0,
      "window_enabled": false,
      "start_hour": 0,
      "start_minute": 0,
      "end_hour": 0,
      "end_minute": 0
    }
  },
  "item_pacing": {
    "new_api": {
      "strategy": "fixed_divided_by_actual_allocated_workers",
      "fixed_seconds": 0.5
    },
    "fast_api": {
      "strategy": "fixed_divided_by_actual_allocated_workers",
      "fixed_seconds": 0.5
    },
    "token": {
      "strategy": "fixed_divided_by_actual_allocated_workers",
      "fixed_seconds": 0.5
    }
  }
}
```

首版优先级冻结为：

- `runtime_settings.query_settings_json` 是查询频率与时间窗口的唯一真相源
- 现有 `QueryConfig.mode_settings` 不再作为 runtime 真相源
- `QueryConfig.mode_settings` 在首版只作为 legacy 数据保留

迁移规则：

- 若数据库里没有 `runtime_settings.default`：
  - 先创建默认行
  - 再以系统默认值写入 `query_settings_json`
- 首版不尝试自动吸收旧 `QueryConfig.mode_settings` 的历史值
- 旧 `QueryConfig.mode_settings` 保留在数据库中，但仅作为 legacy 数据存在
- cutover 之后，runtime 一律只读 `query_settings_json`
- 新 UI 不再编辑 `QueryConfig.mode_settings`
- `QueryConfig.mode_settings` 后续可在独立任务中移除，但不属于本次范围

这样做的理由是：

- 迁移行为完全确定，可重复，可测试
- 不依赖“当前前端选择态”这类运行时上下文
- 不会因为旧库里存在多份互相冲突的 mode 配置而产生随机结果

代价也明确接受：

- 首版全局查询设置以上述默认值起步
- 若用户历史上在某个旧配置里改过 mode cooldown，需要在新 `查询设置` 中重新保存一次

### 12.4 全局 query settings cutover

为了避免 query settings 成为“半新半旧”的灰色真相，本次 cutover 规则冻结为：

- 新 UI 的 `查询设置` 只读写 `runtime_settings.query_settings_json`
- query runtime 在启动、恢复、热应用时只读取 `query_settings_json`
- `QueryConfig.mode_settings` 继续保留在读取旧配置详情时的兼容返回里，但不参与 runtime 调度
- 若旧接口仍返回 `QueryConfig.mode_settings`，前端只将其当作 legacy 数据，不再作为保存目标
- 当 `GET /api/runtime-settings` 成功后，前端优先展示全局 query settings，不回退到 `QueryConfig.mode_settings`

对应接口验收：

- `GET /api/runtime-settings` 必须返回完整 `query_settings_json`
- `PUT /api/runtime-settings/query` 后再次 `GET`，值必须一致
- query runtime 重启前后读取到的 cooldown / window 配置一致
- 修改 query settings 不重建账号 session，只影响后续调度节奏

## 13. 统计口径冻结

### 13.1 不变的部分

以下统计口径保持不变：

- 查询命中数仍按原始命中商品计算
- 命中来源统计仍按查询侧来源计算
- 商品维度的命中数不因 fanout 被放大

### 13.2 会变化的部分

竞争模式开启后，以下账号统计会自然放大：

- `submitted_product_count`
- `purchase_success_count`
- `purchase_failed_count`

原因：

- 这些值描述的是“账号尝试了多少次、成了多少次、失败了多少次”
- 不是“这个商品真实被市场返回了多少次”

这正是用户要的语义：

- 失败可以更多
- 但成功率机会更高
- 账号能力画像也更真实

### 13.3 不新增额外压平层

本次设计明确不新增“同批次多账号尝试后，再额外压平成一条商品级尝试”的统计补丁。

因为这样会：

- 混淆账号能力统计
- 增加主链路外的额外聚合复杂度
- 让“这个账号到底有没有抢到”变得不直观

## 14. 迁移与兼容

### 14.1 数据库迁移

需要为 `accounts` 新增：

- `account_proxy_mode`
- `account_proxy_url`
- `api_proxy_mode`
- `api_proxy_url`

迁移策略：

- 从旧 `proxy_mode/proxy_url` 回填到 `account_proxy_*`
- 再把 `api_proxy_*` 初始化为同值
- 旧列是否立即删除，取决于本轮代码改造范围

推荐首版：

- 先新增新列
- 读新列，迁移时回填
- 若旧列仍存在，只作为一次性迁移来源，不再作为运行真相源

### 14.2 代码兼容

运行期所有以下模块都应改读新字段：

- 账户创建与更新 use case
- 账户 repository
- account center 读模型
- `RuntimeAccountAdapter`
- query executors
- purchase execution gateway 入口包装

## 15. 测试与验收

至少应补以下验证：

### 15.1 代理拆分

- 新建账户时可分别保存账户代理与 API 代理
- 未单独填写 API 代理时，默认继承账户代理
- `get_global_session()` 使用账户代理
- `get_api_session()` 使用 API 代理

### 15.2 竞争模式

- 同一个命中批次可派发到多个 bucket
- 同一个 bucket 在并发上限大于 `1` 时，可同时派发多个账号
- 同一个 bucket 在并发上限为 `1` 时，只允许一个 ready 账号参战
- bucket 新出现且无配置时，默认并发为 `1`

### 15.3 统计

- 商品命中数不因 fanout 被放大
- 账号提交/成功/失败数按实际尝试次数增长

### 15.4 设置持久化

- `购买设置` 中修改某个 bucket 的并发值后，刷新与重启仍然保留

### 15.5 全局 query settings

- `GET /api/runtime-settings` 能返回默认 query settings
- `PUT /api/runtime-settings/query` 能保存并回读三种 mode 设置
- query runtime 在 cutover 后不再读取 `QueryConfig.mode_settings`
- 修改 query settings 后，当前 query runtime 能按新节奏热应用，但不重建 session
- 旧 `QueryConfig.mode_settings` 即使保留在数据库中，也不会改变 runtime 实际行为

## 16. 实施顺序建议

建议按以下顺序落地：

1. 拆账户代理字段并完成数据库迁移
2. 新增全局 `runtime_settings` 表、repository 与 `GET/PUT` 接口
3. 完成 `query_settings_json` cutover，让 query runtime 只读全局 settings
4. 改 `RuntimeAccountAdapter` 与 query / purchase session 读取逻辑
5. 补左侧 `购买设置` UI 与接口
6. 引入 `competition planner`，实现按 bucket fanout
7. 补测试并联调 UI

这个顺序的好处是：

- 先把全局 settings 真相源立住
- 再切 query runtime 的读取路径
- 再拆代理与竞争模式
- 避免“代理拆一半、query settings 还在旧配置里”的双真相状态

## 17. 风险

本次改造的主要风险有：

1. bucket key 归一化不稳定，导致同一代理被拆成多个 bucket。
2. 老数据迁移不完整，导致 API 查询或购买链路走错代理。
3. 若实现时让竞争模式重新依赖慢队列或等待 busy 账号，会抵消本次“降低热路径延迟”的全部收益。
4. 若前端直接把 bucket 配置写死为当前列表，而不考虑新出现 bucket 的默认值，后续新增代理账号时会出现无配置空洞。

## 18. 结论

本次设计冻结以下最终真相：

- 代理拆成 `账户代理` 与 `API 代理` 两套字段
- token / 登录 / 购买链路走账户代理
- `new_api` / `fast_api` 走 API 代理
- 扫货竞争模式按账户代理 IP 分桶
- 同一 bucket 默认并发为 `1`
- 并发设置进入左侧 `购买设置` 并持久化保存
- 统计不压平多账号竞争尝试，失败放大是允许且有价值的

后续实现、测试与 UI 联调均以本文为准。
