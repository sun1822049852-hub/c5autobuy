# 查询运行页查询组明细设计

## 1. 目标

在查询运行页中新增“查询组明细”表，直接展示每个独立查询组的实时状态。

这里的查询组定义为：

- 一个账号
- 一种查询方式

也就是 `账号 × 查询方式`。

本次改动的目标是让用户在运行中能直接看到：

- 哪个账号的哪种查询方式在跑
- 哪个在窗口外等待
- 哪个在冷却中
- 哪个因为 429 处于退避
- 哪个因为 403 / 未登录已经失效

## 2. 放置位置

查询运行页现有结构是：

1. 运行状态摘要
2. 模式统计
3. 最近事件
4. 命中详情

本次改成：

1. 运行状态摘要
2. 模式统计
3. 查询组明细
4. 最近事件
5. 命中详情

这样保留原有“模式级总览”，同时新增“账号级执行视图”。

## 3. 后端输出

在查询运行状态快照中新增 `group_rows`，每一行代表一个查询组。

字段最小集合：

- `account_id`
- `account_display_name`
- `mode_type`
- `active`
- `in_window`
- `cooldown_until`
- `last_query_at`
- `last_success_at`
- `query_count`
- `found_count`
- `disabled_reason`
- `last_error`
- `rate_limit_increment`

其中：

- `cooldown_until` 用于表示该组下一次可运行时间
- 如果是 429 退避，则优先体现退避截止时间
- `in_window` 来自该模式当前时间窗状态

## 4. 前端显示

查询组明细表首版显示 8 列：

- 账号
- 模式
- 状态
- 时间窗
- 冷却
- 查询/命中
- 最近成功
- 最近错误

展示原则：

- `备注名 > 默认名`
- 状态文案使用中文
- 时间使用易读格式
- 不做编辑交互，只做只读监控

## 5. 状态文案

优先级从高到低：

1. `已禁用`
   - 有 `disabled_reason`
2. `限流退避`
   - 存在未来时间的 `cooldown_until`
   - 且 `rate_limit_increment > 0`
3. `冷却中`
   - 存在未来时间的 `cooldown_until`
4. `窗口外等待`
   - `in_window == False`
5. `运行中`
   - `active == True`
6. `未启动`
   - 其他情况

## 6. 实现边界

后端最小改动路径：

- `ModeRunner.snapshot()` 输出本模式下各 worker 的查询组状态
- `QueryTaskRuntime.snapshot()` 聚合全部模式的 `group_rows`
- `QueryRuntimeService.get_status()` 正常透传并规范化
- API schema 增加 `group_rows`

前端最小改动路径：

- `query_runtime_display.py` 新增 `build_group_rows`
- `query_runtime_panel.py` 增加 `group_table`
- 先不增加筛选、折叠、排序交互

## 7. 测试

本次至少补这些测试：

1. 后端状态快照包含 `group_rows`
2. API 路由返回 `group_rows`
3. 查询运行面板能渲染查询组明细表
4. 状态文案和时间文案正确

注：本次只写文档，不做 git 提交。
