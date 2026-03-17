# Fast API 查询执行器替换设计

## 1. 目标

在不改变现有前端配置、后端接口、运行时调度语义和命中结果结构的前提下，把 `fast_api` 查询模式从 `autobuy.py` 的 legacy scanner 中拆出来，做成新架构自己的执行模块。

本次只替换：

- `fast_api`

本次明确不替换：

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
- 只替换 `fast_api` 内部执行实现

## 3. 当前问题

当前查询运行时虽然已经把 `new_api` 从 legacy scanner 中剥离，但 `fast_api` 真正执行查询时仍然依赖：

- `LegacyScannerAdapter`
- `autobuy.py` 中的 `C5MarketAPIFastScanner`

这带来几个问题：

1. `fast_api` 仍然依赖超大 legacy 文件
2. `LegacyScannerAdapter` 还不能完全成为新架构的模式分发层
3. `fast_api` 的客户端价格/磨损筛选逻辑无法在新架构内独立维护
4. 后续彻底移除 `autobuy.py` 时，`fast_api` 仍是阻塞项

## 4. 方案比较

### 方案 A：单独新增 `FastApiQueryExecutor` 并渐进接管

- `fast_api` -> `FastApiQueryExecutor`
- `token` -> 继续 legacy
- `LegacyScannerAdapter` 继续保留为分发层

优点：

- 风险最小
- 与 `new_api` 替换方式一致
- 容易写兼容测试

缺点：

- `new_api` 和 `fast_api` 会有少量重复请求代码

### 方案 B：先抽一个 OpenAPI 公共基类，再同时调整 `new_api/fast_api`

优点：

- 结构更“整齐”
- 代码复用更高

缺点：

- 会同时触碰已稳定的 `new_api`
- 回归面扩大，不适合当前阶段

### 方案 C：直接把 `token` 一起重写

优点：

- 一步把查询模式都拆完

缺点：

- 风险最大
- `token` 依赖浏览器会话和签名链路，复杂度明显更高

## 5. 结论

采用方案 A。

原因：

- 当前目标是逐块移除 legacy 依赖，不是一次性重写全部查询
- `fast_api` 与 `new_api` 共享 OpenAPI 会话管理，拆分方式最稳定
- `token` 明显更复杂，应该后置

## 6. 新设计

### 6.1 新增 `FastApiQueryExecutor`

新增一个只服务 `fast_api` 的执行模块。

职责：

- 从 `RuntimeAccountAdapter` 获取 API session
- 使用账号 `api_key`
- 从 `QueryItem` 提取查询条件
- 组装 `fast_api` 请求
- 解析 `fast_api` 响应
- 在客户端执行价格/磨损筛选
- 返回标准 `QueryExecutionResult`

它不负责：

- 查询调度
- GUI
- 查询组冷却
- 购买桥接
- 其他模式的执行

### 6.2 `LegacyScannerAdapter` 角色继续收缩

改造后：

- `new_api` -> `NewApiQueryExecutor`
- `fast_api` -> `FastApiQueryExecutor`
- `token` -> 保持 legacy `ProductQueryScanner`

这样做的目的仍然是保持：

- `AccountQueryWorker` 调用方式不变
- 上下游不感知替换发生

### 6.3 `AccountQueryWorker`

保持不变：

- 继续只认 `scanner_adapter.execute_query(...)`
- 继续拿到 `QueryExecutionResult`
- 继续按现有错误字符串语义做 `403 / 429 / Not login` 处理

本次仍不升级错误体系。

## 7. `fast_api` 输入与输出兼容要求

### 7.1 输入来源

`FastApiQueryExecutor` 继续使用：

- `RuntimeAccountAdapter.get_api_session()`
- `RuntimeAccountAdapter.get_api_key()`
- `QueryItem.market_hash_name`
- `QueryItem.min_wear`
- `QueryItem.max_wear`
- `QueryItem.max_price`

### 7.2 请求语义

必须保持与 legacy `fast_api` 一致：

- URL：`https://openapi.c5game.com/merchant/market/v2/products/list`
- params：`{"app-key": api_key}`
- body：
  - `pageSize: min(page_size, 50)`
  - `pageNum: 1`
  - `appId: 730`
  - `marketHashName: query_item.market_hash_name`
  - `delivery: 1`
  - `assetType: 1`

说明：

- 该接口不直接支持价格和磨损筛选
- `max_price / min_wear / max_wear` 必须继续在客户端筛选

### 7.3 输出结构

输出必须继续是 `QueryExecutionResult`：

- `success`
- `match_count`
- `product_list`
- `total_price`
- `total_wear_sum`
- `error`
- `latency_ms`

## 8. 错误语义兼容

第一版只做兼容复刻，不做错误体系升级。

要求：

- 429 仍返回 `HTTP 429 Too Many Requests`
- 403 仍返回 `HTTP 403 请求失败 (可能IP未加入白名单)`
- 其他非 200 状态码仍返回 `HTTP {status} 请求失败`
- session 获取失败返回兼容错误文本
- 超时继续返回 `请求超时 (8秒)`
- 网络异常 / JSON 解析异常继续返回字符串错误

重点是：

- 上层行为不改
- 只是底层实现来源改变

## 9. 测试策略

### 9.1 新执行器单测

至少覆盖：

1. 成功响应解析并执行客户端筛选
2. 403 响应兼容文本
3. 429 响应
4. session 不存在
5. 非法 JSON
6. 网络异常
7. 超时异常

### 9.2 适配器路由测试

至少覆盖：

1. `fast_api` 走 `FastApiQueryExecutor`
2. `token` 仍走 legacy token scanner
3. `new_api` 路由不回归

### 9.3 运行时回归

至少覆盖：

1. `AccountQueryWorker` 仍能消费返回结果
2. `403 / 429 / Not login` 行为不回归
3. 查询命中转购买不回归

## 10. 非目标

本次不做：

- 替换 `token`
- 重写全部查询适配器
- 同时重构 `new_api` 为公共基类
- 改造错误体系为结构化错误码
- 改造前端或 API 接口
- 优化查询调度器
- 引入新的查询配置项

## 11. 结论

本次采用“只替换 `fast_api`、外部合同完全不变”的渐进方案：

- 风险最小
- 容易回归验证
- 便于继续把查询执行逻辑从 legacy 大文件中剥离
- 为最终只剩 `token` 一条 legacy 查询路径做准备
