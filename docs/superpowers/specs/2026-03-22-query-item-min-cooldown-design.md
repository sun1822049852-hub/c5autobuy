# 查询商品最小冷却策略设计

日期：2026-03-22

## 1. 背景

当前新后端中，商品级最小查询冷却仍由

- `app_backend/infrastructure/query/runtime/query_item_scheduler.py`

内部写死的 `_DYNAMIC_COOLDOWN_BASE_SECONDS = 0.5` 控制，并在有实际分配账号数时按：

- `0.5 / actual_assigned_count`

进行动态均分。

这层语义并不属于“查询器自身冷却”，而属于“某个 mode 下，商品再次被调度前至少要间隔多久”。

## 2. 已确认决策

- 该设置放在全局 `query-settings`
- 每个 mode 独立配置一套
- 同一个 mode 下的所有商品共享同一套策略
- 策略支持两种：
  - 固定值
  - 固定值除以“该商品当前实际分配到的查询器数量”

## 3. 数据模型

每个 `query-settings mode` 新增两个字段：

- `item_min_cooldown_seconds: float`
- `item_min_cooldown_strategy: str`

策略值限定为：

- `fixed`
- `divide_by_assigned_count`

默认值应保持旧动态语义：

- `item_min_cooldown_seconds = 0.5`
- `item_min_cooldown_strategy = divide_by_assigned_count`

## 4. 运行时语义

`ModeRunner` 继续负责查询器自身基础冷却、随机冷却和时间窗口。

`QueryItemScheduler` 改为根据 mode 的商品最小冷却策略决定下次可执行时间：

- `fixed`
  - `cooldown = item_min_cooldown_seconds`
- `divide_by_assigned_count`
  - `cooldown = item_min_cooldown_seconds / max(actual_assigned_count, 1)`

其中 `actual_assigned_count` 的定义为：

- 该商品当前实际分配到的查询器数量

现有分配器中，专属商品与“共享池仅一个商品”的场景已经能给出该值；多共享商品轮转场景仍按当前实现保守退回 `1`。

## 5. UI 语义

在扫货页的 `查询设置` modal 中，每个 mode 增加：

- 商品最小冷却值输入框
- 商品冷却策略选择框

策略文案：

- `固定值`
- `固定值 / 实际分配查询器数`

## 6. 验证重点

- query settings API 能读写新字段
- repository 默认值与持久化正确
- 调度器不再依赖写死 `0.5`
- `fixed` 与 `divide_by_assigned_count` 两种策略行为正确
- 热应用 query settings 后，运行时调度策略同步更新
- 前端 modal 正确展示并保存新字段
