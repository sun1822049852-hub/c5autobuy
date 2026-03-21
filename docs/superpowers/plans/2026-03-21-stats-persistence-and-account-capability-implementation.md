# Stats Persistence And Account Capability Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前新 UI 落地购买页配置持久化、查询统计页商品统计、账号能力统计页账号性能统计，并保证统计旁路绝不拖慢 `查询 -> 购买池 -> 分配 -> 执行购买` 主链路。

**Architecture:** 后端保持“runtime 调度在内存、统计与 UI 偏好在数据库”的二分结构。通过新增 stats pipeline 把 query / purchase 事件旁路入队、后台聚合、批量落库，再用独立的 stats API 与 purchase UI preferences API 供前端读取；前端在现有 `App -> AppShell -> Page + hook` 模式上扩展，不为 legacy UI 做兼容。

**Tech Stack:** FastAPI、SQLAlchemy/SQLite、Python pytest、React 19、Vite、Vitest、Testing Library

---

## File Map

### Backend persistence and migrations

- Modify: `app_backend/infrastructure/db/models.py`
  - 新增持久化表记录：
    - `PurchaseUiPreferenceRecord`
    - `QueryItemStatsTotalRecord`
    - `QueryItemStatsDailyRecord`
    - `QueryItemRuleStatsTotalRecord`
    - `QueryItemRuleStatsDailyRecord`
    - `AccountCapabilityStatsTotalRecord`
    - `AccountCapabilityStatsDailyRecord`
- Modify: `app_backend/infrastructure/db/base.py`
  - 把上述表纳入 `create_schema`
  - 为已有数据库补齐最薄迁移逻辑

### Backend repositories / use cases / routes

- Create: `app_backend/infrastructure/repositories/purchase_ui_preferences_repository.py`
- Create: `app_backend/infrastructure/repositories/stats_repository.py`
- Create: `app_backend/application/use_cases/get_purchase_ui_preferences.py`
- Create: `app_backend/application/use_cases/update_purchase_ui_preferences.py`
- Create: `app_backend/application/use_cases/get_query_item_stats.py`
- Create: `app_backend/application/use_cases/get_account_capability_stats.py`
- Create: `app_backend/api/schemas/stats.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Create: `app_backend/api/routes/stats.py`
- Modify: `app_backend/main.py`

### Backend runtime telemetry

- Create: `app_backend/infrastructure/stats/runtime/stats_events.py`
- Create: `app_backend/infrastructure/stats/runtime/stats_pipeline.py`
- Modify: `app_backend/infrastructure/query/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Modify: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`
- Modify: `app_backend/infrastructure/purchase/runtime/account_purchase_worker.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

### Frontend client / hooks / pages

- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Create: `app_desktop_web/src/features/query-stats/query_stats_page.jsx`
- Create: `app_desktop_web/src/features/query-stats/hooks/use_query_stats_page.js`
- Create: `app_desktop_web/src/features/account-capability-stats/account_capability_stats_page.jsx`
- Create: `app_desktop_web/src/features/account-capability-stats/hooks/use_account_capability_stats_page.js`
- Modify: `app_desktop_web/src/styles/app.css`

### Tests

- Create: `tests/backend/test_purchase_ui_preferences_repository.py`
- Create: `tests/backend/test_stats_repository.py`
- Create: `tests/backend/test_stats_routes.py`
- Create: `tests/backend/test_stats_pipeline.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/backend/test_query_purchase_bridge.py`
- Modify: `tests/backend/test_purchase_execution_gateway.py`
- Modify: `tests/backend/test_desktop_web_backend_bootstrap.py`
- Modify: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Modify: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Create: `app_desktop_web/tests/renderer/query_stats_page.test.jsx`
- Create: `app_desktop_web/tests/renderer/account_capability_stats_page.test.jsx`

## Chunk 1: 数据库存储基础

### Task 1: 为 UI 偏好与统计聚合新增数据库表

**Files:**
- Modify: `app_backend/infrastructure/db/models.py`
- Modify: `app_backend/infrastructure/db/base.py`
- Test: `tests/backend/test_desktop_web_backend_bootstrap.py`

- [ ] **Step 1: 先写 schema 存在性测试**

在 `tests/backend/test_desktop_web_backend_bootstrap.py` 新增断言：
- `create_app()` 后数据库包含：
  - `purchase_ui_preferences`
  - `query_item_stats_total`
  - `query_item_stats_daily`
  - `query_item_rule_stats_total`
  - `query_item_rule_stats_daily`
  - `account_capability_stats_total`
  - `account_capability_stats_daily`

Run: `pytest tests/backend/test_desktop_web_backend_bootstrap.py -q`
Expected: FAIL，缺少新表

- [ ] **Step 2: 在 `models.py` 新增 record 定义**

要求：
- 文本主键继续用 `Text`
- `daily` 表主键显式包含 `stat_date`
- `account capability` 表主键包含 `account_id + mode_type + phase`
- 所有时间字段继续用 ISO 文本，跟现有库风格一致

- [ ] **Step 3: 在 `base.py` 接入建表与最薄迁移**

要求：
- 把新表纳入 `Base.metadata.create_all`
- 若表不存在则创建
- 不做复杂数据回填
- 不修改已有业务表语义

- [ ] **Step 4: 回跑 bootstrap 测试**

Run: `pytest tests/backend/test_desktop_web_backend_bootstrap.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_backend/infrastructure/db/models.py app_backend/infrastructure/db/base.py tests/backend/test_desktop_web_backend_bootstrap.py
git commit -m "feat: add stats and ui preference tables"
```

### Task 2: 建立 UI 偏好与统计聚合 repository

**Files:**
- Create: `app_backend/infrastructure/repositories/purchase_ui_preferences_repository.py`
- Create: `app_backend/infrastructure/repositories/stats_repository.py`
- Test: `tests/backend/test_purchase_ui_preferences_repository.py`
- Test: `tests/backend/test_stats_repository.py`

- [ ] **Step 1: 写 purchase UI preferences repository 测试**

覆盖：
- 默认读取返回空偏好
- 设置 `selected_config_id`
- 再次设置会覆盖旧值
- 删除配置时可清空偏好

Run: `pytest tests/backend/test_purchase_ui_preferences_repository.py -q`
Expected: FAIL，repository 未实现

- [ ] **Step 2: 实现 `purchase_ui_preferences_repository.py`**

接口最小化：
- `get()`
- `set_selected_config(config_id)`
- `clear_selected_config()`

要求：
- 整库只有一行偏好记录
- 读不到时返回默认对象而不是抛异常

- [ ] **Step 3: 写 stats repository 测试**

覆盖：
- `query_execution_event` 可累计 total 与 daily 的 `query_execution_count`
- `query_hit_event` 可累计 `matched_product_count` 与来源计数
- `purchase_submit_order_event` 可累计成功/失败件数
- `account capability` 可累计 `sample_count / total_latency_ms / last_latency_ms`
- `range_mode=day/range/total` 可正确读取

Run: `pytest tests/backend/test_stats_repository.py -q`
Expected: FAIL，stats repository 未实现

- [ ] **Step 4: 实现 `stats_repository.py`**

最小接口：
- `apply_query_execution_event(event)`
- `apply_query_hit_event(event)`
- `apply_purchase_create_order_event(event)`
- `apply_purchase_submit_order_event(event)`
- `list_query_item_stats(range_mode, date, start_date, end_date)`
- `list_account_capability_stats(range_mode, date, start_date, end_date)`

要求：
- total 与 daily 同时维护
- `external_item_id` 作为商品统计主身份
- `rule_fingerprint` 写到 rule stats 表
- `mode_type=token` 读取时映射展示名 `browser`

- [ ] **Step 5: 回跑两个 repository 测试**

Run: `pytest tests/backend/test_purchase_ui_preferences_repository.py tests/backend/test_stats_repository.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_backend/infrastructure/repositories/purchase_ui_preferences_repository.py app_backend/infrastructure/repositories/stats_repository.py tests/backend/test_purchase_ui_preferences_repository.py tests/backend/test_stats_repository.py
git commit -m "feat: add stats and purchase ui preference repositories"
```

## Chunk 2: 统计旁路与 runtime telemetry

### Task 3: 增加独立 stats pipeline，保证主链路只做 fire-and-forget 入队

**Files:**
- Create: `app_backend/infrastructure/stats/runtime/stats_events.py`
- Create: `app_backend/infrastructure/stats/runtime/stats_pipeline.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_stats_pipeline.py`

- [ ] **Step 1: 先写 stats pipeline 行为测试**

覆盖：
- `enqueue` 不需要等待数据库
- 队列满时直接丢事件并累加 `dropped_stats_event_count`
- `flush` 会批量调用 `stats_repository`
- `stop()` 不抛异常，即使仍有未 flush 事件

Run: `pytest tests/backend/test_stats_pipeline.py -q`
Expected: FAIL，pipeline 未实现

- [ ] **Step 2: 新增 `stats_events.py`**

定义 dataclass：
- `QueryExecutionStatsEvent`
- `QueryHitStatsEvent`
- `PurchaseCreateOrderStatsEvent`
- `PurchaseSubmitOrderStatsEvent`

要求：
- 字段与 spec 保持一致
- 不直接依赖 FastAPI schema

- [ ] **Step 3: 实现 `stats_pipeline.py`**

要求：
- 有界内存队列
- `enqueue()` 永不阻塞主链路
- 后台 worker 批量 flush
- flush 异常只记日志/计数，不向主链路冒泡

- [ ] **Step 4: 在 `main.py` 装配 pipeline**

要求：
- 创建 `stats_repository`
- 创建 `stats_pipeline`
- 注入到 `query_runtime_service` 与 `purchase_runtime_service`
- 放到 `app.state.stats_pipeline` / `app.state.stats_repository`

- [ ] **Step 5: 回跑 pipeline 与 bootstrap 测试**

Run: `pytest tests/backend/test_stats_pipeline.py tests/backend/test_desktop_web_backend_bootstrap.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_backend/infrastructure/stats/runtime/stats_events.py app_backend/infrastructure/stats/runtime/stats_pipeline.py app_backend/main.py tests/backend/test_stats_pipeline.py tests/backend/test_desktop_web_backend_bootstrap.py
git commit -m "feat: add non-blocking stats pipeline"
```

### Task 4: 让 query runtime 同时上报查询次数与命中统计事件

**Files:**
- Modify: `app_backend/infrastructure/query/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/query/runtime/mode_runner.py`
- Modify: `app_backend/infrastructure/query/runtime/query_runtime_service.py`
- Test: `tests/backend/test_query_purchase_bridge.py`

- [ ] **Step 1: 先扩展 query bridge 测试**

覆盖：
- 每次 `run_once()` 都会发送 `query_execution_event`
- `match_count > 0` 时额外发送 `query_hit_event`
- 统计事件发送失败不会阻塞 `hit_sink`

Run: `pytest tests/backend/test_query_purchase_bridge.py -q`
Expected: FAIL，现有 runner 只转发购买 hit，不发 stats 事件

- [ ] **Step 2: 在 `query_runtime_service.py` 新增 stats sink 装配**

要求：
- runtime factory 同时接收：
  - `purchase hit sink`
  - `stats event sink`
- 没有 stats pipeline 时保持兼容

- [ ] **Step 3: 在 `mode_runner.py` 发出两类统计事件**

规则：
- 每次 query 完成后发 `QueryExecutionStatsEvent`
- 仅在 `match_count > 0` 时发 `QueryHitStatsEvent`
- 构造事件时携带：
  - `query_config_id`
  - `query_item_id`
  - `external_item_id`
  - `mode_type`
  - `account_id`
  - `account_display_name`
  - `latency_ms`
  - `rule_fingerprint` 所需字段

- [ ] **Step 4: 回跑 query bridge 测试**

Run: `pytest tests/backend/test_query_purchase_bridge.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_backend/infrastructure/query/runtime/runtime_events.py app_backend/infrastructure/query/runtime/mode_runner.py app_backend/infrastructure/query/runtime/query_runtime_service.py tests/backend/test_query_purchase_bridge.py
git commit -m "feat: emit query stats events from runtime"
```

### Task 5: 补齐 purchase latency 并把 create/submit 事件送入 stats pipeline

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/runtime_events.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`
- Modify: `app_backend/infrastructure/purchase/runtime/account_purchase_worker.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Test: `tests/backend/test_purchase_execution_gateway.py`
- Test: `tests/backend/test_purchase_runtime_routes.py`

- [ ] **Step 1: 先为 execution gateway 写 latency 断言**

覆盖：
- 成功路径返回：
  - `create_order_latency_ms`
  - `submit_order_latency_ms`
- 订单创建失败也会保留 `create_order_latency_ms`
- 提交失败时同时保留前一阶段的 `create_order_latency_ms`

Run: `pytest tests/backend/test_purchase_execution_gateway.py -q`
Expected: FAIL，当前 `PurchaseExecutionResult` 还没有 latency 字段

- [ ] **Step 2: 扩展 `PurchaseExecutionResult` 与 `PurchaseWorkerOutcome`**

新增字段：
- `submitted_count`
- `create_order_latency_ms`
- `submit_order_latency_ms`

要求：
- 保持现有 `status/purchased_count/error` 兼容
- `submitted_count` 等于本次 `product_list` 件数

- [ ] **Step 3: 在 `purchase_execution_gateway.py` 记录两段耗时**

要求：
- `create_order()` 前后测时
- `process_payment()` 前后测时
- 不引入额外网络请求
- 原有错误映射行为不变

- [ ] **Step 4: 在 `purchase_runtime_service.py` 发出 purchase stats 事件**

规则：
- `create_order` 事件以 `PurchaseExecutionResult` 为源
- `submit_order` 事件带：
  - `submitted_count`
  - `success_count`
  - `failed_count = submitted_count - purchased_count`
- 事件发送失败不得阻塞 `_apply_worker_outcome`

- [ ] **Step 5: 回跑 execution gateway 与 purchase runtime route 测试**

Run: `pytest tests/backend/test_purchase_execution_gateway.py tests/backend/test_purchase_runtime_routes.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_backend/infrastructure/purchase/runtime/runtime_events.py app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py app_backend/infrastructure/purchase/runtime/account_purchase_worker.py app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py tests/backend/test_purchase_execution_gateway.py tests/backend/test_purchase_runtime_routes.py
git commit -m "feat: record purchase latencies for stats pipeline"
```

## Chunk 3: 后端 API 与读模型

### Task 6: 增加购买页 UI preferences API

**Files:**
- Create: `app_backend/application/use_cases/get_purchase_ui_preferences.py`
- Create: `app_backend/application/use_cases/update_purchase_ui_preferences.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Test: `tests/backend/test_purchase_runtime_routes.py`

- [ ] **Step 1: 为 UI preferences route 补测试**

覆盖：
- `GET /purchase-runtime/ui-preferences` 默认返回空选择
- `PUT /purchase-runtime/ui-preferences` 可保存 `selected_config_id`
- 配置不存在时返回 404 或明确错误
- 配置删除后再次读取会返回空选择

Run: `pytest tests/backend/test_purchase_runtime_routes.py -q`
Expected: FAIL，路由尚不存在

- [ ] **Step 2: 实现 use case**

要求：
- 读取走 `purchase_ui_preferences_repository`
- 更新前验证 config 是否存在
- 若 config 被删，读取 use case 自动清理无效偏好

- [ ] **Step 3: 扩展 schema 与 route**

新增：
- `PurchaseRuntimeUiPreferencesResponse`
- `PurchaseRuntimeUiPreferencesRequest`

新增接口：
- `GET /purchase-runtime/ui-preferences`
- `PUT /purchase-runtime/ui-preferences`

- [ ] **Step 4: 回跑 purchase runtime route 测试**

Run: `pytest tests/backend/test_purchase_runtime_routes.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_backend/application/use_cases/get_purchase_ui_preferences.py app_backend/application/use_cases/update_purchase_ui_preferences.py app_backend/api/schemas/purchase_runtime.py app_backend/api/routes/purchase_runtime.py tests/backend/test_purchase_runtime_routes.py
git commit -m "feat: add purchase ui preference routes"
```

### Task 7: 增加查询统计与账号能力统计 API

**Files:**
- Create: `app_backend/application/use_cases/get_query_item_stats.py`
- Create: `app_backend/application/use_cases/get_account_capability_stats.py`
- Create: `app_backend/api/schemas/stats.py`
- Create: `app_backend/api/routes/stats.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_stats_routes.py`

- [ ] **Step 1: 先写 stats route 测试**

覆盖：
- `GET /stats/query-items?range_mode=total`
- `GET /stats/query-items?range_mode=day&date=2026-03-21`
- `GET /stats/query-items?range_mode=range&start_date=2026-03-20&end_date=2026-03-21`
- `GET /stats/account-capability` 三种 range mode
- 列值包含 `avg_latency_ms` 与 `sample_count`

Run: `pytest tests/backend/test_stats_routes.py -q`
Expected: FAIL，路由与 schema 尚不存在

- [ ] **Step 2: 实现两个 use case**

要求：
- 只读 `stats_repository`
- `range_mode` 统一校验：
  - `total`
  - `day`
  - `range`
- `range` 缺少 `start_date/end_date` 时抛明确错误

- [ ] **Step 3: 实现 schema 与 route**

要求：
- 商品统计响应直接输出：
  - `external_item_id`
  - `item_name`
  - `matched_product_count`
  - `purchase_success_count`
  - `purchase_failed_count`
  - `source_mode_stats`
- 账号能力响应直接输出六列表格所需字段：
  - `account_id`
  - `account_display_name`
  - `new_api`
  - `fast_api`
  - `browser`
  - `create_order`
  - `submit_order`

- [ ] **Step 4: 把 stats router 挂到 `main.py`**

Run: `pytest tests/backend/test_stats_routes.py tests/backend/test_desktop_web_backend_bootstrap.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_backend/application/use_cases/get_query_item_stats.py app_backend/application/use_cases/get_account_capability_stats.py app_backend/api/schemas/stats.py app_backend/api/routes/stats.py app_backend/main.py tests/backend/test_stats_routes.py tests/backend/test_desktop_web_backend_bootstrap.py
git commit -m "feat: add query stats and account capability routes"
```

## Chunk 4: 前端购买页持久化与新统计页

### Task 8: 扩展前端 client，接入 UI preferences 与 stats API

**Files:**
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Test: `app_desktop_web/tests/renderer/purchase_system_client.test.js`

- [ ] **Step 1: 先写 client 测试**

覆盖：
- `getPurchaseUiPreferences()`
- `updatePurchaseUiPreferences(configId)`
- `getQueryItemStats(params)`
- `getAccountCapabilityStats(params)`

Run: `npm test -- purchase_system_client.test.js`
Expected: FAIL，client 方法尚不存在

- [ ] **Step 2: 实现 client 方法**

要求：
- `GET /purchase-runtime/ui-preferences`
- `PUT /purchase-runtime/ui-preferences`
- `GET /stats/query-items`
- `GET /stats/account-capability`
- query string 按 range mode 生成，不拼接空参数

- [ ] **Step 3: 回跑 client 测试**

Run: `npm test -- purchase_system_client.test.js`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app_desktop_web/src/api/account_center_client.js app_desktop_web/tests/renderer/purchase_system_client.test.js
git commit -m "feat: add stats and ui preferences client methods"
```

### Task 9: 修正购买页配置选择逻辑，改为以持久化偏好为 source of truth

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 先写购买页持久化偏好测试**

覆盖：
- 初次加载读取 `ui-preferences.selected_config_id`
- 即使 `active_query_config` 为空，仍保留已保存选择
- 手动切换配置后会调用 `updatePurchaseUiPreferences`
- 配置被删除后自动回到“未选择配置”

Run: `npm test -- purchase_system_page.test.jsx`
Expected: FAIL，当前 hook 仍以 `active_query_config` 为 preferred config

- [ ] **Step 2: 改写初始加载与轮询逻辑**

要求：
- 首次加载并行读取：
  - runtime status
  - config list
  - capacity summary
  - purchase UI preferences
- `active_query_config` 只影响“当前运行状态文案”，不反向覆盖 `selectedConfigId`
- 手动选择配置后：
  - 先更新后端偏好
  - 再更新本地 `selectedConfigId`

- [ ] **Step 3: 保持购买页商品列表可读持久化统计字段**

此步不要求重做购买页 UI，只要求：
- 为后续改接 stats API 留出 merge 点
- 不再把“未运行时必须清空 selectedConfigId”作为逻辑前提

- [ ] **Step 4: 回跑购买页测试**

Run: `npm test -- purchase_system_page.test.jsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js app_desktop_web/src/features/purchase-system/purchase_system_page.jsx app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "fix: persist purchase page selected config"
```

### Task 10: 增加查询统计页与账号能力统计页

**Files:**
- Modify: `app_desktop_web/src/App.jsx`
- Modify: `app_desktop_web/src/features/shell/app_shell.jsx`
- Create: `app_desktop_web/src/features/query-stats/query_stats_page.jsx`
- Create: `app_desktop_web/src/features/query-stats/hooks/use_query_stats_page.js`
- Create: `app_desktop_web/src/features/account-capability-stats/account_capability_stats_page.jsx`
- Create: `app_desktop_web/src/features/account-capability-stats/hooks/use_account_capability_stats_page.js`
- Modify: `app_desktop_web/src/styles/app.css`
- Test: `app_desktop_web/tests/renderer/query_stats_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/account_capability_stats_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`

- [ ] **Step 1: 写查询统计页测试**

覆盖：
- 侧边栏可进入 `查询统计`
- 默认显示商品表
- 右上角有时间筛选：
  - `总和`
  - `某一天`
  - `某时间段`
- 列包含：
  - 商品名
  - 命中
  - 成功
  - 失败
  - 来源统计

Run: `npm test -- query_stats_page.test.jsx`
Expected: FAIL，页面尚不存在

- [ ] **Step 2: 写账号能力统计页测试**

覆盖：
- 侧边栏可进入 `账号能力统计`
- 表头固定六列：
  - 账号名称
  - `new_api`
  - `fast_api`
  - `browser`
  - 订单发送速度
  - 购买速度
- 单元格格式为 `182ms · 34次`

Run: `npm test -- account_capability_stats_page.test.jsx`
Expected: FAIL，页面尚不存在

- [ ] **Step 3: 实现两个页面与各自 hook**

要求：
- 复用现有 page + hook 模式
- 每页各自维护：
  - `rangeMode`
  - `selectedDate`
  - `startDate/endDate`
  - `isLoading`
  - `loadError`
- 页面初版做静态表格布局即可，不叠加额外复杂交互

- [ ] **Step 4: 更新 `App.jsx` 与 `AppShell`**

要求：
- 新增两个 nav item：
  - `query-stats`
  - `account-capability-stats`
- 顺序放在 `购买系统` 后面，作为 purchase 相关页面继续延伸
- 不改动现有 `account-center / 配置管理 / 购买系统` 入口行为

- [ ] **Step 5: 回跑 renderer 测试**

Run: `npm test -- purchase_system_page.test.jsx query_stats_page.test.jsx account_capability_stats_page.test.jsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app_desktop_web/src/App.jsx app_desktop_web/src/features/shell/app_shell.jsx app_desktop_web/src/features/query-stats/query_stats_page.jsx app_desktop_web/src/features/query-stats/hooks/use_query_stats_page.js app_desktop_web/src/features/account-capability-stats/account_capability_stats_page.jsx app_desktop_web/src/features/account-capability-stats/hooks/use_account_capability_stats_page.js app_desktop_web/src/styles/app.css app_desktop_web/tests/renderer/query_stats_page.test.jsx app_desktop_web/tests/renderer/account_capability_stats_page.test.jsx app_desktop_web/tests/renderer/purchase_system_page.test.jsx
git commit -m "feat: add query stats and account capability pages"
```

## Chunk 5: 收尾验证与文档回写

### Task 11: 全链路验证并同步 spec / plan 留痕

**Files:**
- Modify: `docs/superpowers/specs/2026-03-21-stats-persistence-and-account-capability-design.md`
- Modify: `docs/superpowers/plans/2026-03-21-stats-persistence-and-account-capability-implementation.md`
- Test: `tests/backend/test_purchase_ui_preferences_repository.py`
- Test: `tests/backend/test_stats_repository.py`
- Test: `tests/backend/test_stats_pipeline.py`
- Test: `tests/backend/test_query_purchase_bridge.py`
- Test: `tests/backend/test_purchase_execution_gateway.py`
- Test: `tests/backend/test_purchase_runtime_routes.py`
- Test: `tests/backend/test_stats_routes.py`
- Test: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/query_stats_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/account_capability_stats_page.test.jsx`

- [ ] **Step 1: 回写 spec 的实现差异**

只记录真正发生的实现取舍，例如：
- `mode_type=token` 到 `browser` 的映射位置
- `purchase` 虚拟 `mode_type` 的最终落点

- [ ] **Step 2: 运行后端测试集**

Run: `pytest tests/backend/test_purchase_ui_preferences_repository.py tests/backend/test_stats_repository.py tests/backend/test_stats_pipeline.py tests/backend/test_query_purchase_bridge.py tests/backend/test_purchase_execution_gateway.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_stats_routes.py -q`
Expected: PASS

- [ ] **Step 3: 运行前端测试集**

Run: `npm test -- purchase_system_client.test.js purchase_system_page.test.jsx query_stats_page.test.jsx account_capability_stats_page.test.jsx`
Expected: PASS

- [ ] **Step 4: 手动冒烟**

Run:

```bash
node .\main_ui_account_center_desktop.js
```

检查：
- 购买页刷新后保留上次选择的配置
- 侧边栏能进入 `查询统计` 与 `账号能力统计`
- 时间筛选切换会触发正确请求

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-03-21-stats-persistence-and-account-capability-design.md docs/superpowers/plans/2026-03-21-stats-persistence-and-account-capability-implementation.md
git commit -m "docs: sync stats persistence implementation notes"
```

