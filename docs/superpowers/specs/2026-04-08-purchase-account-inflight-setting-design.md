# 购买设置单账号并发配置设计

日期：2026-04-08

## 1. 目标

在现有 `购买设置` 中新增一个可持久化的全局配置项：

- `max_inflight_per_account`

它用于控制：

- 单个购买账号最多同时承接多少个购买 dispatch job

本次设计同时冻结以下要求：

- 新字段进入现有 `购买设置`，不新开页面
- 新字段默认值为 `1`
- 新字段与现有 `per_batch_ip_fanout_limit` 并列保存
- 保存后若当前没有在途购买，则可立即生效
- 保存后若当前已有在途购买，则等待当前这批购买结束后再生效
- 不改变现有购买命中、去重、队列与账号可用性主语义

## 2. 当前问题

当前系统里和购买分配相关的并发控制实际上分成两层：

1. `per_batch_ip_fanout_limit`
   - 已经进入现有 `购买设置`
   - 它控制“一条命中到来时，每个购买 IP bucket 最多派发多少个当前空闲账号参与购买”
2. `max_inflight_per_account`
   - 目前只存在于后端 `PurchaseRuntimeService` 构造参数中
   - 默认值是 `3`
   - 它控制“单个账号自己最多能同时处理多少个购买任务”

现在的问题不是系统没有这个能力，而是：

- 第二层并发上限是隐藏参数
- 用户无法在 UI 中配置
- 后端默认值 `3` 不符合本次用户新决策
- 很容易把它和 `fanout` 理解成同一件事

## 3. 已确认的用户决策

本次会话已经确认：

- 采用方案 A：把“单账号最大并发购买任务数”并入现有 `购买设置`
- 不拆出新页面
- 不做账号级单独覆盖
- 默认值改为 `1`
- 用户要配置的是“账号所属 worker/并发数”，不是现有的 `单批次单 IP fanout`

## 4. 方案比较

### 方案 A：加入现有购买设置，并支持运行中即时生效

优点：

- 最贴近用户当前心智
- 不需要新入口
- 修改完成后，UI 与后端语义一致
- 没有在途购买时，用户保存后立刻能看到行为变化

缺点：

- 需要补运行时延迟生效同步逻辑

### 方案 B：加入现有购买设置，但只在下次启动购买运行时生效

优点：

- 改动更小
- 风险更低

缺点：

- 用户容易误解为“保存无效”
- 后续大概率还要再补即时生效

### 方案 C：做成账号级覆盖配置

优点：

- 最灵活

缺点：

- 明显超出当前需求
- 会把账号中心、运行时、表单和存储一起复杂化

## 5. 结论

采用方案 A。

冻结后的 `购买设置` 包含两个并列字段：

- `per_batch_ip_fanout_limit`
- `max_inflight_per_account`

它们的职责必须明确分离：

- `per_batch_ip_fanout_limit`
  - 控制单次命中在每个 IP bucket 下最多拉多少个空闲账号一起参与
- `max_inflight_per_account`
  - 控制单个账号最多同时跑多少个购买 dispatch

两者都属于购买运行时设置，但不是同一个层级的并发。

## 6. 领域与持久化设计

### 6.1 `purchase_settings_json`

当前结构从：

```json
{
  "per_batch_ip_fanout_limit": 1
}
```

扩展为：

```json
{
  "per_batch_ip_fanout_limit": 1,
  "max_inflight_per_account": 1
}
```

### 6.2 默认值

默认值冻结为：

- `per_batch_ip_fanout_limit = 1`
- `max_inflight_per_account = 1`

任何 settings 缺省、老数据缺字段、读取失败时，都必须回退到这个默认值。

### 6.3 仓储规则

`RuntimeSettingsRepository` 的购买设置默认值和保存值都要包含新字段。

规则：

- 老库没有新字段时，读取时自动补默认值 `1`
- 保存购买设置时，一次保存完整购买设置快照
- 新旧字段一起返回，不允许前端写一个字段时把另一个字段冲掉

## 7. API 设计

### 7.1 Response

`GET /runtime-settings/purchase` 返回：

```json
{
  "per_batch_ip_fanout_limit": 1,
  "max_inflight_per_account": 1,
  "updated_at": "2026-04-08T18:00:00"
}
```

### 7.2 Update

`PUT /runtime-settings/purchase` 请求体改为：

```json
{
  "per_batch_ip_fanout_limit": 1,
  "max_inflight_per_account": 1
}
```

### 7.3 校验规则

两个字段都必须：

- 是整数
- 大于等于 `1`

错误语义冻结为：

- `per_batch_ip_fanout_limit < 1`
  - 返回对应错误
- `max_inflight_per_account < 1`
  - 返回对应错误

## 8. 运行时语义

### 8.1 命中接入阶段

查询命中进入购买 runtime 时：

1. 命中经过 `PurchaseHitInbox` 去重
2. runtime 调用 `claim_idle_accounts_by_bucket(limit_per_bucket=per_batch_ip_fanout_limit)`
3. 本次命中最多按 bucket fanout 到若干个空闲账号
4. 每个被选中的账号再由自己的 dispatch runner 处理

这一阶段不读取 `max_inflight_per_account` 来决定“本批次要派给多少个账号”；
它只读取 `per_batch_ip_fanout_limit`。

### 8.2 单账号执行阶段

每个账号创建自己的 `_AccountDispatchRunner` 时，`max_concurrent` 来自：

- `max_inflight_per_account`

同时 scheduler 注册账号时，`max_inflight` 也来自：

- `max_inflight_per_account`

因此它决定的是：

- 该账号是否还能继续接新任务
- 该账号内部最多能同时跑几个 dispatch

### 8.3 默认行为变更

当前隐藏默认值是 `3`。

本次设计后，系统默认行为改为：

- 单个账号默认最多同时跑 `1` 个购买任务

这会让默认行为更保守，也更符合用户这次的预期。

## 9. 运行中即时生效

本次设计要求：保存购买设置后，不必停止当前购买 runtime，也不必重启账号 session。
但若当前存在在途购买 dispatch，则不得在购买中途改动并发上限，而是要等当前这批购买结束后再切换。

### 9.1 生效目标

更新完成后，运行中的购买 runtime 需要同步两处：

1. `PurchaseScheduler` 中每个账号状态的 `max_inflight`
2. `_AccountDispatchRunner` 的 `max_concurrent`

### 9.2 生效时机

生效时机冻结为：

- 若当前 `inflight dispatch count == 0`
  - 保存后立即应用到运行时
- 若当前 `inflight dispatch count > 0`
  - 本次保存先落库
  - runtime 记录一份 `pending purchase settings`
  - 等当前在途购买全部结束后，再一次性切换到新值

这里的“当前在途购买全部结束”指：

- 当前已经进入执行阶段的购买任务自然完成
- 不强行取消
- 不在半途中修改账号并发上限

### 9.3 生效方式

新增一个购买 runtime 内部同步入口，例如：

- `apply_runtime_settings(...)`
- 或更明确的 `apply_purchase_settings(...)`

该入口职责固定为：

- 读取最新 `max_inflight_per_account`
- 在允许切换时更新 runtime 内存中的并发上限
- 不重建 runtime
- 不停止 drain worker
- 不关闭 `RuntimeAccountAdapter` session

同时建议补一份 pending 入口，例如：

- `schedule_purchase_settings_apply(...)`

职责固定为：

- 收到保存后的最新设置
- 若当前无在途购买则直接应用
- 若当前有在途购买则挂到 pending
- 在最后一个在途购买结束的 completion 回调中检查并应用 pending 设置

### 9.4 边界规则

- 已经在执行中的 dispatch 不强行取消
- 新上限不在购买中途插入生效
- 若把上限从大值改小，已在跑的任务允许自然结束，结束后再统一切换
- 若把上限从小值改大，也要等当前在途购买结束后再放量
- 设置保存成功不等于 runtime 已立即切换，前端必须展示“待当前购买完成后生效”的状态文案

## 10. 前端设计

### 10.1 设置面板

现有 `PurchaseSettingsPanel` 保留原字段，并新增第二个 number input：

- `单账号最大并发购买任务数`

文案必须明确和现有字段区分：

- `单批次单IP并发购买数`
  - 说明单条命中每个 IP bucket 最多派给多少个空闲账号
- `单账号最大并发购买任务数`
  - 说明单个账号自己最多同时处理多少个购买任务

### 10.2 草稿与保存

前端 `purchaseSettingsDraft` 扩展新字段：

- `per_batch_ip_fanout_limit`
- `max_inflight_per_account`

保存时两者一起提交，不允许只提交一个字段。

### 10.3 WebSocket / 远端状态同步

`runtime_settings.updated` 的 payload 也必须包含新字段。

前端收到该事件后：

- 更新本地 `runtimeSettings`
- 若当前草稿不是 dirty 状态，则一起刷新显示值

若当前保存后进入 pending 生效状态，前端还需要有明确反馈，例如：

- `已保存，等待当前购买完成后生效`

## 11. 测试要求

### 11.1 后端

至少补以下测试：

1. `RuntimeSettingsRepository` 默认购买设置包含：
   - `per_batch_ip_fanout_limit = 1`
   - `max_inflight_per_account = 1`
2. `GET /runtime-settings/purchase` 返回新字段
3. `PUT /runtime-settings/purchase` 可以保存并回读新字段
4. `max_inflight_per_account < 1` 时返回校验错误
5. 购买 runtime 启动时默认按 `1` 创建账号 inflight 上限
6. 运行中更新购买设置后，scheduler 与 dispatch runner 的账号并发上限同步变化
7. 若保存时存在在途购买，则新值不会中途插入生效，而是在当前在途购买结束后才同步到 scheduler 与 dispatch runner
8. 旧测试里依赖 `max_inflight_per_account=3` 的断言需按新默认值或显式传参重写

### 11.2 前端

至少补以下测试：

1. 购买设置初始加载显示两个字段
2. 编辑第二个字段后，保存按钮进入 dirty 状态
3. 保存请求体包含：
   - `per_batch_ip_fanout_limit`
   - `max_inflight_per_account`
4. 保存成功后，新字段回填到草稿
5. 新字段非法时显示对应错误
6. `runtime_settings.updated` 推送后，页面能同步显示新字段
7. 当前存在在途购买时，页面显示“等待当前购买完成后生效”之类的反馈

## 12. 风险

本次改造的主要风险有：

1. 只改了 settings 接口和前端，但没把运行中 runtime 的内存并发上限同步，导致“保存成功但行为没变”。
2. 把 pending 生效做成“保存后立即插入切换”，导致购买半途中并发上限变化，破坏用户要求。
3. 错把 `max_inflight_per_account` 接到 fanout 逻辑里，导致同批次参战账号数语义变化。
4. 老测试仍默认依赖单账号 `3` 并发，导致回归失败。

## 13. 验收标准

本次完成后，必须满足：

1. 用户能在现有 `购买设置` 中看到并修改“单账号最大并发购买任务数”
2. 新字段默认值为 `1`
3. 设置可持久化保存并在刷新后仍保留
4. 若当前无在途购买，保存后立即生效
5. 若当前有在途购买，保存后等待当前这批购买结束后生效
6. `fanout` 与 `per-account inflight` 两层并发语义保持清晰且互不混淆

## 14. 结论

本次设计冻结以下最终真相：

- “单账号最大并发购买任务数”进入现有 `购买设置`
- 它对应后端 `max_inflight_per_account`
- 默认值从隐藏的 `3` 改为显式的 `1`
- 它与 `per_batch_ip_fanout_limit` 并列持久化保存
- 若当前无在途购买则立即应用
- 若当前有在途购买则等待当前这批购买结束后应用

后续实现、测试与验收均以本文为准。
