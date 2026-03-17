# Token 查询执行器替换设计

## 1. 目标

在不改变现有前端配置、后端接口、运行时调度语义和命中结果结构的前提下，把 `token` 查询模式从 `autobuy.py` 的 legacy scanner 中拆出来，做成新架构自己的执行模块。

本次只替换：

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
- 只替换 `token` 内部执行实现

## 3. 当前问题

当前查询运行时虽然已经把 `new_api` 和 `fast_api` 从 legacy scanner 中剥离，但 `token` 真正执行查询时仍然依赖：

- `LegacyScannerAdapter`
- `autobuy.py` 中的 `ProductQueryScanner`

这带来几个问题：

1. 查询链路仍然需要 `autobuy.py`
2. `token` 请求构造、签名和结果解析无法在新架构内独立维护
3. `LegacyScannerAdapter` 还没有真正完成“只做分发”的收尾
4. 只要 `token` 还没迁移，查询链路就不能彻底脱离 legacy

## 4. 方案比较

### 方案 A：新增 `TokenQueryExecutor`，保留现有上层对 `"Not login"` 的处理

- `token` -> `TokenQueryExecutor`
- `AccountQueryWorker` 继续按结果字符串处理 `"Not login"` / `HTTP 403`
- 不复刻 legacy scanner 内部的 `_publish_not_login / disabled_time / disabled`

优点：

- 风险最小
- 与当前新架构职责边界一致
- 不把旧 scanner 的内部状态机继续带进来

缺点：

- 需要重新整理 token 请求头和响应解析逻辑

### 方案 B：连 legacy scanner 内部事件系统一起复刻

- 继续在执行器内部维护 `disabled` / `disabled_time`
- 继续模拟 `_publish_not_login`

优点：

- 看起来“更像旧代码”

缺点：

- 把 legacy 内部状态机继续带入新架构
- 与现有上层账号禁用逻辑重复
- 结构明显更脏

## 5. 结论

采用方案 A。

原因：

- 用户已经确认：只保留 `"Not login"` 对外结果兼容，由新架构上层处理账号禁用
- 这样可以保持行为兼容，同时避免复刻旧 scanner 内部状态机
- 是完成查询链路去 legacy 的最小风险方案

## 6. 新设计

### 6.1 新增 `TokenQueryExecutor`

新增一个只服务 `token` 的执行模块。

职责：

- 从 `RuntimeAccountAdapter` 获取浏览器会话
- 从 cookie 中提取 `NC5_accessToken` 和 `NC5_deviceId`
- 构建 token 查询请求体和精确请求头
- 生成 `x-sign`
- 解析 `token` 响应
- 返回标准 `QueryExecutionResult`

它不负责：

- 查询调度
- GUI
- 查询组冷却
- 购买桥接
- 账号禁用状态机
- 发布 legacy 未登录事件

### 6.2 签名依赖

本次不再通过 `autobuy.py` 获取 `GLOBAL_XSIGN_WRAPPER`。

改为直接使用仓库内独立的：

- `xsign.py`
- `test.wasm`

实现方式：

- `TokenQueryExecutor` 默认懒加载 `XSignWrapper`
- 单测中允许注入 fake signer，避免真的启动 Node.js 进程

这意味着：

- 查询链路迁移完成后，不再依赖 `autobuy.py`
- 但 `xsign.py` 仍然是 token 链路的必要依赖

### 6.3 `LegacyScannerAdapter`

改造后：

- `new_api` -> `NewApiQueryExecutor`
- `fast_api` -> `FastApiQueryExecutor`
- `token` -> `TokenQueryExecutor`

这样做的目的仍然是保持：

- `AccountQueryWorker` 调用方式不变
- 上下游不感知替换发生

### 6.4 `AccountQueryWorker`

保持不变：

- 继续只认 `scanner_adapter.execute_query(...)`
- 继续拿到 `QueryExecutionResult`
- 继续按现有错误字符串语义做 `403 / 429 / Not login` 处理

本次不升级错误体系。

## 7. `token` 输入与输出兼容要求

### 7.1 输入来源

`TokenQueryExecutor` 继续使用：

- `RuntimeAccountAdapter.get_global_session()`
- `RuntimeAccountAdapter.get_x_access_token()`
- `RuntimeAccountAdapter.get_x_device_id()`
- `RuntimeAccountAdapter.get_cookie_header_exact()`
- `QueryItem.external_item_id`
- `QueryItem.min_wear`
- `QueryItem.max_wear`
- `QueryItem.max_price`
- `QueryItem.product_url`

### 7.2 请求语义

必须保持与 legacy `ProductQueryScanner` 一致：

- URL：`https://www.c5game.com/api/v1/support/trade/product/batch/v1/sell/query`
- path：`support/trade/product/batch/v1/sell/query`
- body：
  - `itemId: str(query_item.external_item_id)`
  - `maxPrice: str(query_item.max_price)`
  - `delivery: 0`
  - `minWear: float(query_item.min_wear)`
  - `maxWear: float(query_item.max_wear)`
  - `limit: "200"`
  - `giftBuy: ""`

headers 继续包含：

- `Cookie`
- `Referer`
- `x-device-id`
- `x-start-req-time`
- `x-sign`
- `x-access-token`

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

- 403 继续返回 `HTTP 403 Forbidden`
- 响应为纯文本 `Not login` 时，继续返回精确字符串 `Not login`
- session 获取失败继续返回 `无法创建浏览器会话`
- `x-sign` 生成失败继续返回 `x-sign生成失败: ...`
- timeout 继续返回 `请求超时`
- 其他请求异常继续返回 `请求错误: ...`
- 非法 JSON 继续返回 `响应不是有效的JSON格式`

重点是：

- 上层行为不改
- 只是底层实现来源改变

## 9. 测试策略

### 9.1 新执行器单测

至少覆盖：

1. 成功响应解析
2. 403 响应
3. `Not login` 纯文本响应
4. session 不存在
5. `x-sign` 生成失败
6. 非法 JSON
7. timeout
8. 请求异常

### 9.2 适配器路由测试

至少覆盖：

1. `token` 走 `TokenQueryExecutor`
2. `new_api / fast_api` 路由不回归

### 9.3 运行时回归

至少覆盖：

1. `AccountQueryWorker` 仍能消费返回结果
2. `403 / 429 / Not login` 行为不回归
3. 查询命中转购买不回归

## 10. 非目标

本次不做：

- 重构 `AccountQueryWorker`
- 复刻 legacy scanner 的内部事件系统
- 改造错误体系为结构化错误码
- 改造前端或 API 接口
- 改造购买链路

## 11. 结论

本次采用“只替换 `token`、外部合同完全不变”的渐进方案：

- 风险最小
- 可以完成查询链路对 `autobuy.py` 的彻底解耦
- 同时保留你原先最关键的 `"Not login"` / `403` 上层禁用语义
