# 购买管线架构说明

> ⚠️ **本文档描述的是经过多轮优化后的最终架构。不要回退调度模型。**

## 总览

```
查询命中 → 去重(10s指纹) → 快速路径(优先) / 队列路径(兜底)
                                ↓                    ↓
                          立刻认领空闲账号      hit-intake线程 → drain线程
                          50ms内无账号则丢弃    2s超时丢弃
                                ↓                    ↓
                          ┌─────────────────────────────┐
                          │  _start_account_dispatch     │
                          │  每账号独立线程 + asyncio loop │
                          │  create_order → pay_order    │
                          └─────────────────────────────┘
                                       ↓
                              完成 → 释放账号
                              → 通知快速路径等待者
                              → 唤醒drain线程(若队列非空)
                              → post-process线程(库存/统计)
```

## 第一步：查询端命中

查询运行时 (`query_runtime_service.py`) 轮询商品列表，发现符合条件的商品后产出一个 hit（字典），包含：
- `external_item_id` — 商品ID
- `product_url` — 商品页URL
- `product_list` — 要买的具体 listing
- `total_price` — 总价
- `total_wear_sum` — 磨损指纹（用于去重）

## 第二步：命中递给购买端

查询端通过 `_resolve_hit_sink()` 选择递送方式，优先级：

| 优先级 | 方法 | 行为 |
|--------|------|------|
| 1 | `accept_query_hit_fast_async` | 快速路径，立刻尝试派发 |
| 2 | `accept_query_hit_async` | 异步直接处理 |
| 3 | `accept_query_hit` | 同步直接处理 |
| 4 | `enqueue_query_hit` | 扔进队列，fire-and-forget |

当前实现中，购买端同时提供以上四种方法，所以始终走快速路径。

### 关键：快速路径不阻塞查询循环

查询端的 `mode_runner.py` 中，`_dispatch_hit()` 是同步方法。它调用 `hit_sink(payload)`，由于 `accept_query_hit_fast_async` 是 async 函数，调用返回一个 coroutine。`_dispatch_hit` 检测到返回值是 awaitable 后，用 `asyncio.create_task()` 将其放入后台执行。

所以 50ms 的等待窗口是在后台 task 中跑的，查询主循环立刻继续下一轮查询。

## 第三步：快速路径内部

`_DefaultPurchaseRuntime.accept_query_hit_fast_async()`:

1. `_prepare_fast_query_hit()` — 加锁验证运行状态、去重、创建 `PurchaseHitBatch`
2. 循环尝试 `_try_start_fast_query_hit()` — 认领空闲账号并派发
3. 若无空闲账号，等待 `_fast_path_idle_signal`（`threading.Condition`），最多 50ms
4. 50ms 超时 → `_drop_fast_query_hit_after_grace()` 丢弃

### 为什么是 50ms？

这个窗口刚好够一个刚完成上一单的账号释放自己。太长会积压 hit，太短会白白丢弃。50ms 是实测后的平衡点。

## 第四步：去重机制

`PurchaseHitInbox` 用 `total_wear_sum`（浮点指纹）做 10 秒 TTL 去重。同一组商品在 10 秒内重复命中，第二次直接过滤。

## 第五步：调度器分配账号

`PurchaseScheduler` 按代理/IP 将账号分桶（`bucket_key`）。

`claim_idle_accounts_by_bucket()` 从每个桶取最多 N 个空闲账号，标记为忙碌。账号有 `max_inflight` 设置，未达上限的账号认领后仍留在空闲池。

## 第六步：账号独立购买

每个被分配的账号启动 `_AccountDispatchRunner`（独立线程 + 独立 asyncio 事件循环）：

1. **下单** — `PurchaseExecutionGateway.create_order()` — POST 请求
2. **支付** — `PurchaseExecutionGateway.process_payment()` — POST 请求

两步都是 async HTTP (aiohttp)。账号之间完全并行，互不阻塞。

## 第七步：完成后回收

`_finish_account_dispatch()`:
- 释放账号，重新标记为空闲
- `_notify_fast_path_idle_waiters()` — 唤醒快速路径等待者
- 若调度器队列非空 → `_signal_drain_worker()` 继续派发
- 结果交给 post-process 线程（库存更新、统计记录）

## 队列路径（兜底）

仅在快速路径不可用时使用：

1. `enqueue_query_hit()` → `_hit_intake_queue` (Queue)
2. `_hit_intake_worker_loop` (daemon thread) 取出 → `_accept_query_hit_now()`
3. 有空闲账号 → 立刻派发
4. 无空闲账号 → `_scheduler.submit(batch)` + `_signal_drain_worker()`
5. `_drain_worker_loop` (daemon thread) 等待 `_drain_signal` → `_drain_scheduler_once()`
6. 队列中的 hit 超过 2 秒 → 丢弃

## 线程模型

```
[查询运行时线程]
    │
    ▼
[PurchaseRuntimeService] → _DefaultPurchaseRuntime
    │
    ├── 快速路径: 调用者的 async 上下文，50ms 等待 _fast_path_idle_signal
    │
    ├── hit-intake 线程: _hit_intake_queue → _accept_query_hit_now
    │
    ├── drain 线程: _drain_signal → _drain_scheduler_once → _start_account_dispatch
    │
    ├── 账号线程 ×N: _AccountDispatchRunner (独立 asyncio loop)
    │       → AccountPurchaseWorker.process() [async]
    │           → PurchaseExecutionGateway.execute() [async aiohttp]
    │               → POST create_order
    │               → POST pay_order
    │       → on_complete → _finish_account_dispatch
    │
    ├── post-process 线程: 结果处理、库存更新
    └── diagnostics 线程: 事件日志
```

## 信号协作

| 信号 | 类型 | 作用 |
|------|------|------|
| `_fast_path_idle_signal` | `threading.Condition` | 账号完成后唤醒快速路径等待者 |
| `_drain_signal` | `threading.Event` | 唤醒 drain 线程处理队列中的 hit |
| `_hit_intake_queue` | `Queue` | 队列路径的 hit 传输通道 |

## 历史演变

| 时间 | commit | 变更 |
|------|--------|------|
| 初始 | e7cb877 | `_resolve_hit_sink` 优先选 `enqueue_query_hit`（纯队列模型） |
| 2026-04-14 | bed62c0 | 引入快速路径 `accept_query_hit_fast_async`，优先级提升到最高 |
| 当前 | — | 快速路径为默认且唯一实际使用的路径 |

## ⚠️ 禁止修改事项

1. **不要把 `_resolve_hit_sink` 的优先级改回 `enqueue_query_hit` 优先** — 纯队列模型延迟更高
2. **不要删除快速路径的 50ms grace 窗口** — 这是给刚完成上一单的账号的等待机会
3. **不要把 `_dispatch_hit` 改成 await 模式** — 当前的 `create_task` 后台执行是故意的，保证查询不阻塞
4. **不要合并账号线程** — 每账号独立线程+独立事件循环是隔离性和并行性的保证
