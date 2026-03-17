# Inventory Refresh Gateway Replacement Design

## 1. 目标

在不改变购买运行时、库存状态机、快照存储和前后端接口的前提下，把库存刷新链路从 `autobuy.py` 的 legacy 实现中剥离出来，接入新架构自己的库存刷新网关。

本次只替换：

- 库存刷新请求执行
- 库存刷新响应解析

本次明确不替换：

- `PurchaseRuntimeService` 调度逻辑
- `InventoryState` 选仓与本地库存扣减逻辑
- 恢复检查调度机制
- 快照持久化逻辑

## 2. 约束

这次替换必须遵守以下硬约束：

- 不改前端配置项
- 不改后端 API 字段
- 不改 `InventoryRefreshResult`
- 不改 `PurchaseRuntimeService` 调用库存刷新网关的方式
- 不改 `InventoryState.refresh_from_remote(...)`
- 不改“启动时刷新一次仓库、购买成功后本地扣减、无容量再远程刷新”的现有流程
- 不改 `Not login / 403` 在上层表现出来的鉴权失效语义

也就是说：

- 对外合同不变
- 只替换库存刷新内部实现

## 3. 当前问题

当前购买运行时的库存刷新仍依赖：

- 旧库存刷新网关
- `autobuy.py` 中的 preview 仓库查询实现

这带来几个问题：

1. 购买模块仍然没有完全脱离 `autobuy.py`
2. 库存刷新请求构造、签名和响应解析仍然挂在 legacy 依赖上
3. 启动刷新、购买后远程确认、恢复检查三处路径共享同一个 legacy 刷新实现，后续难以单独维护

## 4. 方案比较

### 方案 A：只替换库存刷新网关

- 新增一个新的库存刷新网关
- 网关内部完成 preview 请求构造、签名、发送和响应解析
- `PurchaseRuntimeService`、`InventoryState`、恢复检查和快照逻辑不动

优点：

- 风险最小
- 与当前渐进迁移策略一致
- 最容易做回归验证

缺点：

- 库存刷新内部仍然会有独立的请求构造逻辑，暂时还没和购买请求做统一抽象

### 方案 B：替换库存刷新网关，并把请求构造拆成更多小模块

- 新增库存刷新网关
- 再把 headers/body/response parser 单独拆文件

优点：

- 结构更细

缺点：

- 当前收益不大
- 文件和抽象层会明显增多
- 对这轮目标来说有过度设计风险

### 方案 C：把购买执行和库存刷新合并成统一 C5 客户端

- 新建统一客户端，承接购买和库存刷新两类请求

优点：

- 长期结构更统一

缺点：

- 会重新扰动刚稳定的购买执行链路
- 迁移面太大，不符合本轮“只拆库存刷新”的目标

## 5. 结论

采用方案 A。

原因：

- 风险最小
- 与前两轮“先拆具体执行，再保留运行时上层不动”的迁移方式一致
- 能把购买模块剩余的 legacy 运行时依赖继续缩小

## 6. 新设计

### 6.1 新增库存刷新网关

新增一个只负责库存刷新的新网关。

职责：

- 校验账号基础登录信息
- 从 `RuntimeAccountAdapter` 获取浏览器会话
- 从 cookie 中提取 `NC5_accessToken` 和 `NC5_deviceId`
- 构建 preview 请求体和精确请求头
- 生成 `x-sign`
- 解析 preview 响应中的 `receiveSteamList`
- 返回标准 `InventoryRefreshResult`

它不负责：

- 选仓
- 本地库存扣减
- 恢复定时器
- 账号入池/出池
- GUI / API

### 6.2 `PurchaseRuntimeService`

保持不变：

- 继续通过 `inventory_refresh_gateway_factory` 获取刷新网关
- 继续在 3 个场景下调用同一个 `refresh(account=...)`
  - 启动时初次拉仓库
  - 购买成功但本地容量耗尽后做远程确认
  - 恢复检查定时器触发时再次拉仓库

### 6.3 `InventoryState`

保持不变：

- 继续根据仓库列表筛选可用仓库
- 继续决定 `selected_steam_id`
- 继续在购买成功后本地扣减库存
- 继续在无容量时要求上层触发远程刷新

### 6.4 快照持久化

保持不变：

- 库存刷新结果仍由现有运行时写入 snapshot repository
- `selected_steam_id` 仍然来自 `InventoryState`

## 7. 请求语义

### 7.1 输入来源

库存刷新网关继续只使用：

- `account`

并通过 `RuntimeAccountAdapter` 获取：

- `get_global_session()`
- `get_x_access_token()`
- `get_x_device_id()`
- `get_cookie_header_exact()`

### 7.2 preview 请求语义

必须保持与旧逻辑一致：

- path：`support/trade/product/batch/v1/preview/1380979899390267393`
- URL：`https://www.c5game.com/api/v1/support/trade/product/batch/v1/preview/1380979899390267393`
- body：
  - `{"itemId": "1380979899390267393"}`
- referer：
  - 继续使用旧实现中的固定商品页 URL

headers 继续包含：

- `Cookie`
- `Referer`
- `x-device-id`
- `x-start-req-time`
- `x-sign`
- `x-access-token`

## 8. 输出与错误语义兼容

### 8.1 输出结构

输出必须继续是 `InventoryRefreshResult`：

- `status`
- `inventories`
- `error`

### 8.2 错误语义

第一版只做兼容复刻，不做错误体系升级。

要求：

- 缺少 `access_token / device_id` 时，继续返回 `auth_invalid("Not login")`
- session 取不到时，继续返回 `auth_invalid("Not login")`
- 响应错误含 `Not login` 时，继续映射为 `auth_invalid`
- 响应错误含 `403` 时，也映射为 `auth_invalid`
- `x-sign` 生成失败时，返回 `status="error"`，错误文本为 `x-sign生成失败: ...`
- 超时返回 `status="error"`，错误文本为 `请求超时`
- 请求异常返回 `status="error"`，错误文本为 `请求失败: ...`
- 非法 JSON 返回 `status="error"`，错误文本为 `响应不是有效的JSON格式`
- 普通业务失败返回 `status="error"`，错误文本为 `请求失败: <errorMsg>`

重点是：

- 上层行为不改
- 只是底层实现来源改变

## 9. 测试策略

### 9.1 新库存刷新网关单测

至少覆盖：

1. 成功拿到 `receiveSteamList`
2. cookie 缺 `access_token / device_id`
3. 响应 `Not login`
4. 响应包含 `403`
5. `x-sign生成失败`
6. `请求超时`
7. `请求失败`
8. `响应不是有效的JSON格式`
9. 请求 URL / body / headers 形状兼容旧逻辑

### 9.2 运行时回归

至少覆盖：

1. 启动时远程刷新仍能选出 `selected_steam_id`
2. 购买成功后本地容量耗尽时仍会触发远程刷新
3. 远程刷新后仍由 `InventoryState` 负责重新选仓
4. `auth_invalid` 仍把账号标记为失效
5. 恢复检查仍能把账号重新入池

### 9.3 全量回归

至少覆盖：

1. 购买运行时相关测试继续通过
2. 全项目 pytest 继续通过

## 10. 非目标

本次不做：

- 重构 `PurchaseRuntimeService`
- 重构 `InventoryState`
- 重构恢复检查机制
- 将购买执行和库存刷新进一步合并抽象
- 改造错误体系为结构化错误码

## 11. 结论

本次采用“只替换库存刷新 gateway、上层行为完全不变”的渐进方案：

- 风险最小
- 能把购买模块剩余的 legacy 运行时依赖继续缩小
- 不会破坏当前已经稳定的库存状态机和恢复检查逻辑
