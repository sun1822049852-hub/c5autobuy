# 扫货单批次 IP Fanout 设计

日期：2026-03-29

## 1. 目标

为当前购买运行时补上“单批次单 IP 并发购买数”的全局设置，并将购买执行从全局串行改为按当前空闲账号做批次 fanout。

本次设计冻结以下产品语义：

- 配置是全局一套，对所有命中批次生效
- 配置默认值固定为 `1`
- 限制单位不是某个长期存在的商品，也不是某个固定账号组
- 每次查询命中形成的一批待购买数据，都是独立的批次 fanout 上下文
- 同一 IP bucket 下，每个批次最多派发 `N` 个当前空闲账号
- 下一批即使命中的是相同数据，也不继承上一批的占用
- 同一账号始终 `single-flight`

## 2. 用户已确认的语义

魔尊已明确拍板：

- `单批次单IP并发购买数` 是全局配置，不针对某个固定商品配置
- “商品”的意思是一次查询命中后形成的一批待购买数据
- 上一批次是否还在购买，不阻塞下一批次对同一数据再次 fanout
- 真正共享的只有账号本身；账号忙时不能重复参与另一批购买
- 不需要人为建立“组”实体；“每四个账号一组”只是帮助理解容量的抽象说法

## 3. 推荐方案

采用以下组合方案：

- 保留当前新架构的中心控制面：
  - 账号可用性
  - 库存恢复
  - `auth_invalid`
  - stats
  - recent events
- 引入全局 purchase runtime settings：
  - `per_batch_ip_fanout_limit`
- 按购买代理归一化为 `IP bucket`
- 每个批次命中到来时，按各 bucket 当前 `idle` 账号数做即时 fanout
- 同一账号继续保持 `single-flight`

该方案拿回了旧实现“多账号并发抢”的吞吐，同时保留了新实现“统一状态收口”的稳定性。

## 4. 核心运行语义

### 4.1 配置

`purchase_settings_json` 新增并冻结：

```json
{
  "per_batch_ip_fanout_limit": 1
}
```

默认值固定为 `1`。

### 4.2 bucket 定义

购买使用“账户代理/浏览器代理”作为 bucket 依据，而不是 API 代理。

原因：

- 登录、token、库存刷新、购买链路都属于账户代理侧
- 购买 fanout 的隔离目标是购买出口 IP，而不是查询 API 出口 IP

### 4.3 fanout 公式

每个 hit 通过 fast dedupe 后，视为一个独立批次。

对每个 `bucket_key`：

```text
dispatch_count = min(current_idle_accounts_in_bucket, per_batch_ip_fanout_limit)
```

然后立刻为这些账号发起购买 dispatch。

### 4.4 不共享上一批的批次占用

本次设计明确不维护 `(bucket, item_scope)` 级别的占用计数。

原因：

- 魔尊要求下一批次即使命中的是相同数据，也应独立计算
- 影响下一批次是否还能并发参与的唯一因素，是“当前还有多少账号空闲”

因此：

- 上一批次还在买，但 bucket 里仍有空闲账号，则下一批次仍可继续 fanout
- 若 bucket 内账号都 busy，则下一批次该 bucket 只能派 0 个

### 4.5 账号 single-flight

尽管批次之间不互相阻塞，但单账号仍然只能同时执行一个购买请求。

也就是说：

- 批次与批次之间不共享占用
- 账号与账号之间并发
- 同一账号不并发

## 5. 数据与状态模型

### 5.1 全局设置

新增全局 runtime settings 真相源，购买侧只读写：

- `purchase_settings_json.per_batch_ip_fanout_limit`

### 5.2 账号运行态

在 `_RuntimeAccountState` 最小新增：

- `busy: bool`
- `last_started_at: str | None`
- `last_finished_at: str | None`

不新增 group 实体，不新增同商品占用表。

### 5.3 调度器状态

`PurchaseScheduler` 最小新增账号状态字段：

- `available`
- `busy`
- `bucket_key`

并新增能力：

- `claim_idle_accounts_by_bucket(limit)`
- `release_account(account_id)`
- `snapshot_bucket_rows()`

claim 与 release 必须在 scheduler 锁内原子完成。

## 6. 组件职责

### 6.1 `proxy_bucket.py`

只做纯归一化：

- 输入账号购买代理
- 输出 `bucket_key`
- 输出 `display_name`

不做调度，不做状态管理。

### 6.2 `PurchaseScheduler`

负责：

- 维护账号 `available/busy/bucket_key`
- 在当前锁内挑出每个 bucket 的 idle 账号
- claim
- release
- 生成 bucket 状态快照

不直接执行购买。

### 6.3 `PurchaseRuntimeService`

负责：

- 接受查询命中
- 调用 planner / scheduler claim
- 为被 claim 的账号创建后台购买 dispatch
- 统一处理 `outcome`
- 更新 stats
- 更新账号状态与恢复逻辑

### 6.4 `AccountPurchaseWorker`

继续只做：

- 单账号单批次购买执行

不感知 bucket，不负责全局并发策略。

## 7. 前端 UI 设计

扫货系统左侧设置区中的 `购买设置` 面板改为两段式：

### 7.1 全局购买配置

新增字段：

- `单批次单IP并发购买数`

帮助文案：

> 每次查询命中形成一批购买任务后，每个购买 IP 下最多会派发多少个当前空闲账号参与本批次购买。不会限制下一批命中的派发。

### 7.2 账号参与设置

保留现有账号启用勾选逻辑。

## 8. API / 状态读模型

购买运行时状态返回中新增：

- `purchase_settings`
  - `per_batch_ip_fanout_limit`
- `bucket_rows`
  - `bucket_key`
  - `display_name`
  - `configured_limit`
  - `idle_account_count`
  - `busy_account_count`
  - `total_account_count`

这些字段用于前端设置面板与运行时可观测性。

## 9. 实施顺序

1. 先补 runtime settings 与 purchase fanout 的后端失败测试
2. 落全局 purchase settings 默认值与读写接口
3. 实现 `proxy_bucket.py`
4. 扩展 `PurchaseScheduler` 的 `busy/bucket/claim/release`
5. 改造 `PurchaseRuntimeService.accept_query_hit_async()` 为单批次多账号 fanout
6. 将购买执行改为多账号后台 dispatch，而非全局串行 drain
7. 补 `bucket_rows` 读模型
8. 接前端购买设置 UI

## 10. 验收标准

必须满足：

1. 默认 `per_batch_ip_fanout_limit = 1`
2. 当配置值为 `4` 且 bucket 账号数为 `2 / 3 / 6 / 8` 时，单批次可派发 `13`
3. 下一批次即使命中同样数据，也只按当前剩余 idle 账号重新计算
4. 同一账号绝不并发执行两次购买
5. 同一 bucket 内部分账号 busy 时，剩余 idle 账号仍可参与下一批
6. `auth_invalid / no_inventory / recovery` 仍由中心 runtime 统一收口

## 11. 非目标

本次不做：

- 按具体商品保存不同 fanout 配置
- 按 bucket 保存不同 limit
- 显式账号组实体
- 忙账号回头补发同一旧批次
- 多机 / 多进程协调

