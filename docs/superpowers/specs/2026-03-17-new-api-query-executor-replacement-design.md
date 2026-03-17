# New API 查询执行器替换设计

## 1. 目标

在不改变现有前端配置、后端接口、运行时调度语义和命中结果结构的前提下，把 `new_api` 查询模式从 `autobuy.py` 的 legacy scanner 中拆出来，做成新架构自己的执行模块。

本次只替换：

- `new_api`

本次明确不替换：

- `fast_api`
- `token`

## 2. 约束

这次替换必须遵守以下硬约束：

- 不改前端配置项
- 不改后端 API 字段
- 不改查询运行页展示含义
- 不改调度器输入输出协议
- 不改 `QueryExecutionResult`
- 不改查询命中转购买链路输入结构
- 不改 `403 / 429 / Not login` 在上层表现出来的错误语义

也就是说：

- 对外合同不变
- 只替换 `new_api` 内部执行实现

## 3. 当前问题

当前查询运行时虽然已经有新的调度、状态和 GUI，但 `new_api` 真正执行查询时仍然依赖：

- `LegacyScannerAdapter`
- `autobuy.py` 中的 `C5MarketAPIScanner`

这带来几个问题：

1. `new_api / fast_api / token` 三种查询仍混在同一个 legacy 适配器里
2. 新架构仍需动态导入超大旧文件 `autobuy.py`
3. `new_api` 不能独立维护和独立替换
4. 测试上很难只针对 `new_api` 做新旧切换验证

## 4. 新设计

### 4.1 新增 `NewApiQueryExecutor`

新增一个只服务 `new_api` 的执行模块。

职责：

- 从 `RuntimeAccountAdapter` 获取 API session
- 使用账号 `api_key`
- 从 `QueryItem` 提取查询条件
- 组装 `new_api` 请求
- 解析 `new_api` 响应
- 返回标准 `QueryExecutionResult`

它不负责：

- 查询调度
- GUI
- 查询组冷却
- 购买桥接
- 其他模式的执行

### 4.2 `LegacyScannerAdapter` 角色变化

`LegacyScannerAdapter` 不再亲自承担所有模式的实现细节，而是先变成模式分发层：

- `new_api` -> `NewApiQueryExecutor`
- `fast_api` -> 保持 legacy `C5MarketAPIFastScanner`
- `token` -> 保持 legacy `ProductQueryScanner`

这样做的目的不是长期保留这个名字，而是先保持：

- `AccountQueryWorker` 调用方式不变
- 上下游不感知替换发生

### 4.3 `AccountQueryWorker`

保持不变：

- 继续只认 `scanner_adapter.execute_query(...)`
- 继续拿到 `QueryExecutionResult`
- 继续按现有错误字符串语义做 `403 / 429 / Not login` 处理

本次不把错误字符串体系升级成错误码体系。

## 5. `new_api` 输入与输出兼容要求

### 5.1 输入来源

`NewApiQueryExecutor` 仍然使用：

- `RuntimeAccountAdapter.get_api_session()`
- `RuntimeAccountAdapter.get_api_key()`
- `QueryItem.external_item_id`
- `QueryItem.min_wear`
- `QueryItem.max_wear`
- `QueryItem.max_price`

### 5.2 输出结构

输出必须继续是 `QueryExecutionResult`：

- `success`
- `match_count`
- `product_list`
- `total_price`
- `total_wear_sum`
- `error`
- `latency_ms`

## 6. 错误语义兼容

第一版只做兼容复刻，不做错误体系升级。

要求：

- 403 仍返回兼容字符串，供上层禁用查询组
- 429 仍返回兼容字符串，供上层触发退避
- session 获取失败返回兼容错误文本
- 网络异常 / JSON 解析异常返回字符串错误

重点是：

- 上层行为不改
- 只是底层实现来源改变

## 7. 测试策略

### 7.1 新执行器单测

至少覆盖：

1. 成功响应解析
2. 403 响应
3. 429 响应
4. session 不存在
5. 非法 JSON
6. 网络异常

### 7.2 适配器路由测试

至少覆盖：

1. `new_api` 走 `NewApiQueryExecutor`
2. `fast_api` 仍走 legacy fast scanner
3. `token` 仍走 legacy token scanner

### 7.3 运行时回归

至少覆盖：

1. `AccountQueryWorker` 仍能消费返回结果
2. `403 / 429 / Not login` 行为不回归
3. 查询命中转购买不回归

## 8. 非目标

本次不做：

- 替换 `fast_api`
- 替换 `token`
- 重写全部查询适配器
- 改造错误体系为结构化错误码
- 改造前端或 API 接口
- 优化查询调度器
- 引入新的查询配置项

## 9. 结论

本次采用“只替换 `new_api`、外部合同完全不变”的渐进方案：

- 风险最小
- 容易回归验证
- 便于把查询执行逻辑逐步从 legacy 大文件中剥离
- 不会破坏当前已经稳定的 GUI、调度和购买桥接

注：当前会话不执行 git 提交；spec 经用户确认后再写实现计划并进入实现。
