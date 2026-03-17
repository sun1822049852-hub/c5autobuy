# Purchase 执行网关替换设计

## 1. 目标

在不改变现有前端配置、后端接口、购买运行时调度语义和库存状态机行为的前提下，把购买执行链路从 `autobuy.py` 的 legacy 网关中拆出来，做成新架构自己的执行模块。

本次只替换：

- 下单执行
- 支付执行

本次明确不替换：

- 库存刷新链路
- 购买运行时调度器
- 购买库存状态机

## 2. 约束

这次替换必须遵守以下硬约束：

- 不改前端配置项
- 不改后端 API 字段
- 不改 `PurchaseExecutionResult`
- 不改 `AccountPurchaseWorker` 的调用接口
- 不改 `PurchaseRuntimeService` 的调度与库存协调逻辑
- 不改“购买成功后本地扣库存、无容量再远程刷新”的现有流程
- 不改 `Not login / 403` 在上层表现出来的鉴权失效语义

也就是说：

- 对外合同不变
- 只替换购买执行内部实现

## 3. 当前问题

当前购买运行时虽然已经有新的调度、账号池、库存状态和 GUI，但真正执行购买时仍然依赖：

- 旧购买执行网关
- `autobuy.py` 中的 `OrderCreator`
- `autobuy.py` 中的 `PaymentProcessor`

这带来几个问题：

1. 购买执行链路仍然依赖超大 legacy 文件
2. 下单和支付请求构造、签名和结果解析无法在新架构内独立维护
3. 购买执行和库存刷新都挂在 legacy 上，后续很难逐块迁移
4. 只要购买执行还没迁移，购买模块就无法真正脱离 `autobuy.py`

## 4. 方案比较

### 方案 A：只替换购买执行网关

- 新增一个新的购买执行网关
- 网关内部按旧语义完成“创建订单 -> 支付订单”
- `PurchaseRuntimeService`、`AccountPurchaseWorker`、库存刷新和库存状态机不动

优点：

- 风险最小
- 迁移范围与本轮目标完全一致
- 最容易做回归验证

缺点：

- 库存刷新仍然暂时依赖 legacy

### 方案 B：同时替换购买执行和库存刷新

- 一次把购买执行和库存刷新两个旧网关都替掉

优点：

- 购买模块更完整

缺点：

- 回归面明显扩大
- 容易把“购买成功后本地扣库存、无容量再远程刷新”的现有链路一起碰坏

### 方案 C：直接重写整个购买运行时

- 连运行时调度、恢复检查、库存同步一起改

优点：

- 结构最彻底

缺点：

- 风险最大
- 当前阶段完全没必要

## 5. 结论

采用方案 A。

原因：

- 用户已明确要求这轮先拆购买执行，不动库存刷新
- 当前最重要的是逐块移除 legacy 依赖，而不是一次性重写整个购买系统
- 把“执行购买”和“库存刷新”拆开处理，回归风险最低

## 6. 新设计

### 6.1 新增购买执行网关

新增一个只服务购买执行的新网关。

职责：

- 校验购买批次基础字段
- 从 `RuntimeAccountAdapter` 获取浏览器会话
- 从 cookie 中提取 `NC5_accessToken` 和 `NC5_deviceId`
- 构建下单请求体和精确请求头
- 构建支付请求体和精确请求头
- 生成 `x-sign`
- 解析下单和支付响应
- 返回标准 `PurchaseExecutionResult`

它不负责：

- 购买调度
- GUI
- 库存本地扣减
- 远程库存刷新
- 购买运行时恢复检查

### 6.2 网关内部的步骤拆分

新网关内部继续按旧语义拆成两个步骤：

1. `create_order(...)`
2. `process_payment(...)`

目的不是暴露更多对外接口，而是：

- 让“下单”和“支付”边界清楚
- 方便分别写测试
- 方便后续单独维护请求构造和响应解析

### 6.3 `PurchaseRuntimeService`

保持不变：

- 继续通过 `execution_gateway_factory` 获取执行网关
- 继续把命中批次交给 `AccountPurchaseWorker`
- 继续在购买成功后走现有库存协调逻辑

### 6.4 `AccountPurchaseWorker`

保持不变：

- 继续只认 `await execution_gateway.execute(...)`
- 继续根据 `PurchaseExecutionResult` 决定：
  - 成功后本地扣库存
  - 鉴权失效时暂停账号
  - 其他错误按现有分支处理

## 7. 签名依赖

本次不再通过 `autobuy.py` 获取 `GLOBAL_XSIGN_WRAPPER`。

改为直接使用仓库内独立的：

- `xsign.py`
- `test.wasm`

实现方式：

- 新网关默认懒加载 `XSignWrapper`
- 单测中允许注入 fake signer，避免真的启动 Node.js 进程

这意味着：

- 购买执行链路迁移完成后，不再依赖 `autobuy.py`
- 但库存刷新链路仍然暂时依赖 legacy

## 8. 输入与输出兼容要求

### 8.1 输入来源

购买执行网关继续使用：

- `account`
- `batch.external_item_id`
- `batch.product_url`
- `batch.product_list`
- `batch.total_price`
- `selected_steam_id`

并通过 `RuntimeAccountAdapter` 获取：

- `get_global_session()`
- `get_x_access_token()`
- `get_x_device_id()`
- `get_cookie_header_exact()`

### 8.2 下单请求语义

必须保持与 legacy `OrderCreator` 一致：

- URL：`https://www.c5game.com/api/v1/support/trade/order/buy/v2/create`
- path：`support/trade/order/buy/v2/create`
- body：
  - `type: 4`
  - `productId: str(batch.external_item_id)`
  - `price: format(total_price, ".2f")`
  - `delivery: 0`
  - `pageSource: ""`
  - `receiveSteamId: str(selected_steam_id)`
  - `productList: batch.product_list`
  - `actRebateAmount: 0`

headers 继续包含：

- `Cookie`
- `Referer`
- `x-device-id`
- `x-start-req-time`
- `x-sign`
- `x-access-token`

### 8.3 支付请求语义

必须保持与 legacy `PaymentProcessor` 一致：

- URL：`https://www.c5game.com/api/v1/pay/order/v1/pay`
- path：`pay/order/v1/pay`
- body：
  - `bizOrderId: str(order_id)`
  - `orderType: 4`
  - `payAmount: format(total_price, ".2f")`
  - `receiveSteamId: str(selected_steam_id)`

headers 继续包含：

- `Cookie`
- `Referer`
- `x-device-id`
- `x-start-req-time`
- `x-sign`
- `x-access-token`

### 8.4 输出结构

输出必须继续是 `PurchaseExecutionResult`：

- `status`
- `purchased_count`
- `error`

## 9. 错误语义兼容

第一版只做兼容复刻，不做错误体系升级。

要求：

- 缺少 `access_token / device_id` 时，继续返回 `auth_invalid("Not login")`
- 下单失败且错误里含 `Not login` 或 `403`，继续映射为 `auth_invalid`
- 支付失败且错误里含 `Not login` 或 `403`，继续映射为 `auth_invalid`
- 下单普通失败，继续返回 `status="order_failed"`
- 支付普通失败，继续返回 `status="payment_failed"`
- 支付成功但 `successCount <= 0`，继续返回 `status="payment_success_no_items"`
- `x-sign` 生成失败继续返回 `生成x-sign失败: ...`
- 下单超时继续返回 `订单创建请求超时`
- 支付超时继续返回 `请求超时`
- 非法 JSON 继续返回 `响应不是有效的JSON格式`

重点是：

- 上层行为不改
- 只是底层实现来源改变

## 10. 测试策略

### 10.1 新执行网关单测

至少覆盖：

1. 下单成功 + 支付成功
2. 下单返回 `Not login`
3. 支付返回 `Not login`
4. 下单普通失败
5. 支付普通失败
6. 支付成功但 `successCount <= 0`
7. `x-sign` 生成失败
8. 请求超时
9. 请求异常
10. 请求体和请求头形状兼容旧逻辑

### 10.2 运行时回归

至少覆盖：

1. `AccountPurchaseWorker` 仍正确传递 `selected_steam_id`
2. 成功购买后仍然只做本地库存扣减
3. `auth_invalid` 仍然把账号打成失效
4. `PurchaseRuntimeService` 整体行为不回归

### 10.3 烟测兼容

至少覆盖：

1. 下单 URL / body / headers 仍与旧语义一致
2. 支付 URL / body / headers 仍与旧语义一致
3. `x-sign`、`x-access-token`、`Cookie`、`Referer` 继续存在

## 11. 非目标

本次不做：

- 替换库存刷新链路
- 重构 `PurchaseRuntimeService`
- 重构 `AccountPurchaseWorker`
- 改造购买运行时调度
- 改造库存状态机
- 改造错误体系为结构化错误码

## 12. 结论

本次采用“只替换购买执行、外部合同完全不变”的渐进方案：

- 风险最小
- 可以把购买执行链路从 `autobuy.py` 中剥离
- 不会破坏你当前已经稳定的库存与恢复逻辑
- 为下一轮单独拆库存刷新留出清晰边界
