# autobuy.py 与新 backend 语义对账参考

更新时间：2026-03-19

基准提交：`179c5e0`

注：本文中的 `app_backend/infrastructure/selenium/*` 与 `selenium_login_runner.py` 属于当时代码结构。当前仓库里，活跃登录链已迁到 `app_backend/infrastructure/browser_runtime/`，并由 `BrowserLoginAdapter` / `ManagedEdgeCdpLoginRunner` 承接。

## 1. 目的

这份文档不是架构介绍，而是给后续开发排查“为什么旧版 `autobuy.py` 能跑、新版 `app_backend` 出问题”时用的实现级 reference。

重点不是模块有没有迁完，而是：

- 哪些 legacy 语义已经完整迁移
- 哪些地方只是“看起来像”
- 哪些流程已经发生语义漂移
- 后续改动应优先看哪组文件

## 2. 适用场景

出现下面任一情况时，先看本文件再动代码：

- 浏览器扫码登录能进页面，但任务不结束、卡住、或拿不到登录信息
- 旧版可跑的 “query only / API key only” 场景，新版直接不启动
- 新版偶发 `Not login`、`403`、cookie 相关不稳定，而旧版相对稳定
- 手动选择购买仓库后，运行一段时间又被改回别的仓库
- 同一个账号重新扫码后，账号归属、API key、仓库配置、代理配置表现和旧版不同

## 3. 对账范围

### Legacy 参考对象

- `autobuy.py:5218` `SessionManager`
- `autobuy.py:5320` `APISessionManager`
- `autobuy.py:5420` `SeleniumLoginManager`
- `autobuy.py:6425` `AccountManager`
- `autobuy.py:2539` `ProductDetailCollector`
- `autobuy.py:2801` `SteamInventorySelector`
- `autobuy.py:3409` `OrderCreator`
- `autobuy.py:3636` `PaymentProcessor`
- `autobuy.py:3839` `ProductQueryScanner`
- `autobuy.py:4142` `C5MarketAPIFastScanner`
- `autobuy.py:4539` `C5MarketAPIScanner`
- `autobuy.py:4870` `QueryCoordinator`
- `autobuy.py:1052` `RoundRobinScheduler`
- `autobuy.py:1612` `MultiAccountCoordinator`

### 新 backend 对应对象

- `app_backend/infrastructure/selenium/selenium_login_runner.py:76`
- `app_backend/workers/tasks/login_task.py:8`
- `app_backend/infrastructure/query/runtime/runtime_account_adapter.py:16`
- `app_backend/infrastructure/query/runtime/token_query_executor.py:30`
- `app_backend/infrastructure/query/runtime/new_api_query_executor.py:19`
- `app_backend/infrastructure/query/runtime/fast_api_query_executor.py:19`
- `app_backend/infrastructure/query/runtime/query_runtime_service.py:15`
- `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py:19`
- `app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py:19`
- `app_backend/infrastructure/purchase/runtime/inventory_state.py:14`
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py:26`
- `app_backend/infrastructure/repositories/account_repository.py:11`
- `app_backend/infrastructure/repositories/account_inventory_snapshot_repository.py:10`

## 4. 结论总表

| 链路 | legacy -> new | 迁移状态 | 备注 |
|---|---|---|---|
| 登录浏览器链路 | `SeleniumLoginManager` -> `SeleniumLoginRunner` | 部分迁移 + 语义漂移 | “什么时候算登录完成” 已变化 |
| 账号/会话/cookie 链路 | `AccountManager`/`SessionManager` -> `RuntimeAccountAdapter`/repository | 大体迁移 | `_csrf`、登录态判定、账号归属策略有漂移 |
| token 查询链路 | `ProductQueryScanner` -> `TokenQueryExecutor` | 基本迁移 | 错误传播和运行时联动语义变了 |
| OpenAPI 查询链路 | `C5MarketAPIScanner`/`C5MarketAPIFastScanner` -> `NewApiQueryExecutor`/`FastApiQueryExecutor` | 基本迁移 | 但 query runtime 启动条件已变 |
| 下单支付链路 | `OrderCreator`/`PaymentProcessor` -> `PurchaseExecutionGateway` | 基本迁移 | body/header 主体较稳 |
| 仓库刷新与选择 | `SteamInventorySelector` -> `InventoryRefreshGateway`/`InventoryState` | 部分迁移 + 语义漂移 | 手选仓库持久化闭环未完全收口 |
| 查询命中到购买调度 | `RoundRobinScheduler` -> `PurchaseRuntimeService`/`PurchaseScheduler` | 重写 | 新版多了停机、清 backlog、恢复回调 |

## 5. 高风险语义漂移

### 5.1 登录完成条件被改写

legacy 行为：

- 只要检测到登录跳转到 `/user/user/`，就可以先判“登录已完成”
- 之后允许回退用页面内容或 `driver.get_cookies()` 补抓用户信息和 cookie
- 浏览器在 `finally` 中自动关闭

证据：

- `autobuy.py:5697` `wait_for_login_success`
- `autobuy.py:5754`
- `autobuy.py:5785`
- `autobuy.py:6134` `login_with_proxy`
- `autobuy.py:6349`
- `autobuy.py:6372`

新 backend 行为：

- 必须先提取到 `user_info`
- 必须先拿到 `cookie_raw`
- `NC5_deviceId` 缺失会直接报错
- 提取完成后还会发出 `waiting_for_browser_close`
- 用户不手动关闭浏览器，任务不会返回成功
- 退出时仍会在 `finally` 里关闭浏览器

证据：

- `app_backend/infrastructure/selenium/selenium_login_runner.py:76`
- `app_backend/infrastructure/selenium/selenium_login_runner.py:121`
- `app_backend/infrastructure/selenium/selenium_login_runner.py:136`
- `app_backend/infrastructure/selenium/selenium_login_runner.py:138`
- `app_backend/infrastructure/selenium/selenium_login_runner.py:141`
- `app_backend/infrastructure/selenium/selenium_login_runner.py:142`
- `app_backend/infrastructure/selenium/selenium_login_runner.py:163`

后果：

- 这不是单纯“自动关窗改手动关窗”
- 这是把“登录成功判定时机”一起改了
- 会直接影响扫码闭环、日志时序、UI 等待逻辑、任务状态推进

### 5.2 query-only 语义被打断

legacy 行为：

- 只要账号有 API key，就允许只建查询组
- 未登录但有 API key 时，可以只跑 API 查询，不注册购买
- 已登录但没 API key 时，可以跑浏览器查询并参与购买

证据：

- `autobuy.py:9534` `execute_purchase_scan`
- `autobuy.py:9642`
- `autobuy.py:9681`
- `autobuy.py:9683`
- `autobuy.py:9703`
- `autobuy.py:9752`

新 backend 行为：

- `QueryRuntimeService.start()` 会先尝试自动拉起购买运行时
- 如果没有可用购买账号，查询运行时直接拒绝启动
- 当购买账号归零时，查询会暂停
- 购买账号恢复后，查询才会自动恢复

证据：

- `app_backend/infrastructure/query/runtime/query_runtime_service.py:35`
- `app_backend/infrastructure/query/runtime/query_runtime_service.py:44`
- `app_backend/infrastructure/query/runtime/query_runtime_service.py:47`
- `app_backend/infrastructure/query/runtime/query_runtime_service.py:48`
- `app_backend/infrastructure/query/runtime/query_runtime_service.py:353`
- `app_backend/infrastructure/query/runtime/query_runtime_service.py:408`
- `app_backend/infrastructure/query/runtime/query_runtime_service.py:421`
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py:742`
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py:1062`

后果：

- 旧版能跑的“仅查询”场景，新版不一定还能跑
- 这会掩盖查询执行器本身没问题，但运行时 orchestration 已经变了的事实

### 5.3 cookie 与 `_csrf` 语义存在隐患

legacy 行为：

- `set_cookie_string()` 会解析 cookie，并对 `_csrf` 做 URL decode
- 保留原始 cookie 顺序
- 业务请求大多走 `get_cookie_header_exact()`
- 同时保留 `get_cookie_header_with_decoded_csrf()` 作为排障工具

证据：

- `autobuy.py:6857`
- `autobuy.py:6881`
- `autobuy.py:6905`
- `autobuy.py:6966`
- `autobuy.py:6985`

新 backend 行为：

- `RuntimeAccountAdapter` 也保留了 `get_cookie_header_with_decoded_csrf()`
- 但当前查询、详情、仓库刷新、下单支付仍全部走 `get_cookie_header_exact()`

证据：

- `app_backend/infrastructure/query/runtime/runtime_account_adapter.py:61`
- `app_backend/infrastructure/query/runtime/runtime_account_adapter.py:64`
- `app_backend/infrastructure/query/runtime/token_query_executor.py:72`
- `app_backend/infrastructure/query/collectors/product_detail_fetcher.py:211`
- `app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py:132`
- `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py:263`

后果：

- 这里不是已确认 bug
- 但它是最像“旧版能过、新版偶发 403 / Not login”的隐性风险点之一
- 如果后续遇到只在新版复现的鉴权抖动，优先回看这里

### 5.4 手选仓库持久化闭环未完全收口

legacy 行为：

- 本质上是自动选择可用仓库中的第一个
- 不存在真正独立的“用户手选仓库并长期保持”闭环

证据：

- `autobuy.py:2877`
- `autobuy.py:3128`
- `autobuy.py:3266`
- `autobuy.py:3227`

新 backend 行为：

- `PurchaseRuntimeService` 已经支持 `selected_steam_id` 的读取、保存、接口更新
- 但 `InventoryState.load_snapshot()` 会默认把选中仓库重置为第一个可用仓库
- `refresh_from_remote()` 直接调用 `load_snapshot()`
- 运行时初始化时会尝试恢复 snapshot 中的 `selected_steam_id`
- 但远端刷新后仍存在把手选仓库冲掉的风险

证据：

- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py:428`
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py:483`
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py:831`
- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py:833`
- `app_backend/infrastructure/purchase/runtime/inventory_state.py:34`
- `app_backend/infrastructure/purchase/runtime/inventory_state.py:37`
- `app_backend/infrastructure/purchase/runtime/inventory_state.py:75`
- `app_backend/infrastructure/repositories/account_inventory_snapshot_repository.py:21`

后果：

- UI 允许用户手选仓库，不代表运行时一定长期保真
- 这个点非常容易在“启动后正常，跑一阵又变了”时误判成前端 bug

### 5.5 账号归属与覆盖语义变了

legacy 行为：

- 扫码成功后按 C5 `userId` 查本地账号文件
- 找到已存在账号就原地更新
- 保留旧 `api_key`
- 保留 `query_time_config`
- 保留 `steam_inventories`

证据：

- `autobuy.py:6483`
- `autobuy.py:6515`
- `autobuy.py:6536`
- `autobuy.py:6551`
- `autobuy.py:6552`
- `autobuy.py:6553`

新 backend 行为：

- 登录任务先绑定到当前内部 `account_id`
- 如果扫到的 C5 账号与当前账户不一致，会进入 conflict 流
- 由用户决定 `create_new_account / replace_with_new_account / cancel`

证据：

- `app_backend/workers/tasks/login_task.py:22`
- `app_backend/workers/tasks/login_task.py:38`
- `app_backend/workers/tasks/login_task.py:42`
- `app_backend/workers/tasks/login_task.py:50`
- `app_backend/workers/tasks/login_task.py:65`

后果：

- 这项变化可能是有意增强，但它不是 legacy 等价迁移
- 如果 UI 没把 conflict 流处理完整，就会表现成“扫码成功后卡住”

## 6. 已基本保真的实现

下面这些实现主体和 legacy 贴合度较高，出问题时不要先怀疑它们，先查上面的 orchestration 与状态链：

- token 查询请求体 / headers / `x-sign` 主体
  - `autobuy.py:3839`
  - `app_backend/infrastructure/query/runtime/token_query_executor.py:30`
- OpenAPI 新旧两类查询执行器
  - `autobuy.py:4142`
  - `autobuy.py:4539`
  - `app_backend/infrastructure/query/runtime/fast_api_query_executor.py:19`
  - `app_backend/infrastructure/query/runtime/new_api_query_executor.py:19`
- 商品详情抓取主体
  - `autobuy.py:2539`
  - `app_backend/infrastructure/query/collectors/product_detail_fetcher.py:26`
- 下单 / 支付请求体和头部主体
  - `autobuy.py:3409`
  - `autobuy.py:3636`
  - `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py:19`

## 7. 排障时的文件优先级

### 浏览器登录问题

1. `app_backend/infrastructure/selenium/selenium_login_runner.py`
2. `app_backend/workers/tasks/login_task.py`
3. `app_backend/api/routes/accounts.py`
4. 对照 `autobuy.py:5420` 到 `autobuy.py:6372`

### query-only / 运行时联动问题

1. `app_backend/infrastructure/query/runtime/query_runtime_service.py`
2. `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
3. 对照 `autobuy.py:9534` 起的多账号加载与注册逻辑

### 仓库选择 / 购买池状态问题

1. `app_backend/infrastructure/purchase/runtime/inventory_state.py`
2. `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
3. `app_backend/infrastructure/repositories/account_inventory_snapshot_repository.py`
4. 对照 `autobuy.py:2801`

### 鉴权偶发抖动

1. `app_backend/infrastructure/query/runtime/runtime_account_adapter.py`
2. `app_backend/infrastructure/query/runtime/token_query_executor.py`
3. `app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py`
4. `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`
5. 对照 `autobuy.py:6857` 到 `autobuy.py:7002`

## 8. 后续改动前必须补的回归测试

如果后续要继续修登录与运行时漂移，建议先补下面 4 组测试，不然很容易再次“看似优化，实则改语义”：

- 登录成功但监控数据晚到时，任务仍能完成
- 用户手动关闭浏览器前后，登录状态推进与结果回写完整
- 无可用购买账号时，是否允许 query-only 启动，要被测试明确锁定
- `selected_steam_id` 在启动、远端刷新、恢复检查后保持不丢

## 9. 已跑过的验证

2026-03-19 已跑：

```bash
.\.venv\Scripts\python.exe -m pytest tests\backend\test_account_center_routes.py tests\backend\test_purchase_runtime_routes.py tests\backend\test_query_runtime_routes.py tests\backend\test_selenium_login_runner.py tests\backend\test_login_e2e_watch.py -q
```

结果：

- `34 passed in 2.47s`

注意：

- 这些测试只能证明模块内部基本自洽
- 还不能证明它们与 `autobuy.py` 的 legacy 语义完全等价

## 10. 使用原则

- 不要因为新 backend 已分层，就默认它和 legacy 语义一致
- 不要因为旧版是单文件，就低估它内部的真实行为约束
- 后续凡是改登录、查询、购买、仓库状态机，都先把本文件对应章节过一遍
- 如果聊天记录与当前代码冲突，以源码、测试和本 reference 为准
