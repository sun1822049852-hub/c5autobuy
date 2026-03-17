# 查询系统重写设计

日期：2026-03-16

## 1. 目标

本设计用于指导账号中心之后的下一阶段重构：重写查询系统。

目标如下：

- 保留原项目查询能力与核心业务规则。
- 不继续依赖 legacy 查询运行时作为主实现。
- 用新的分层架构重写查询配置、查询运行时与查询界面。
- 让新 GUI 直接驱动新的后端查询系统。
- 为后续购买系统重写保留清晰边界。

本阶段明确采用以下方向：

- 前端：`PySide6`
- 后端：`FastAPI`
- 存储：`SQLite`
- 旧代码角色：仅作为业务参考，不作为查询主运行时

## 2. 范围与非目标

### 2.1 本阶段范围

本阶段实现“查询系统”，包括：

- 查询配置的新增、编辑、删除、查看
- 商品 URL 录入与自动解析
- 商品信息自动补全与本地缓存
- 三种查询模式的完整重建
- 三种查询模式各自独立的时间窗口
- 三种查询模式各自独立的冷却与随机延迟
- 单任务查询运行控制
- 查询日志、状态、统计展示
- 账号中心中的查询模式全局开关

### 2.2 本阶段非目标

本阶段不包含以下内容：

- 不重写购买系统
- 不实现下单、支付、购买池
- 不支持多个查询任务并行运行
- 不实现“按配置单独维护账号模式开关”
- 不再把查询时间、冷却、随机延迟挂在账号配置上

## 3. 核心约束

### 3.1 单任务约束

同一时间只允许运行一个查询任务。

该任务：

- 只绑定一个查询配置
- 该配置包含多个查询商品
- 该任务内部同时管理三种查询模式

切换配置前，必须先停止当前任务。

### 3.2 三模式约束

查询系统必须保留三种查询模式：

- `new_api`
- `fast_api`
- `token`

其中：

- `new_api` 与 `fast_api` 依赖 `api_key`
- `token` 依赖登录态中的 `token/cookie`

### 3.3 模式参数独立约束

三种查询模式都必须拥有各自独立的：

- 启用状态
- 时间窗口
- 冷却参数
- 随机延迟参数

不能把三种模式混成一套通用查询参数。

### 3.4 账号开关约束

账号中心中需要提供三种查询模式的全局开关。

这些开关：

- 对所有商品配置全局生效
- 不属于某个单独配置
- 表示用户的全局查询偏好
- 由查询运行时在启动时读取

重要说明：

- 账号上的模式开关是“偏好开关”，不是“强制可运行开关”
- 即使账号当前缺少 `api_key` 或 `token/cookie`，也允许保留偏好为开启
- 查询运行时实际是否启用某账号，仍需同时满足：
  - 账号模式偏好已开启
  - 账号能力满足该模式要求

### 3.5 商品录入约束

保留原有录入方式：

1. 用户输入商品 URL
2. 系统自动解析商品标识
3. 系统自动拉取并缓存商品信息
4. 用户补充或确认筛选参数

重点保留：

- `item_id`
- `item_name`
- `market_hash_name`
- 磨损范围
- 价格信息

### 3.6 配置与运行分离约束

查询配置只描述“应该如何查询”。

运行时只描述“当前正在如何运行”。

禁止把以下运行态字段写回查询配置：

- 当前运行状态
- 当前统计
- 当前日志
- 最近错误快照

## 4. 总体架构

采用“本地桌面前后端分离”架构。

### 4.1 前端职责

前端仅负责：

- 展示查询配置
- 编辑查询配置
- 展示三模式参数
- 展示账号查询模式开关
- 启动与停止查询任务
- 展示查询日志与统计

前端不负责：

- 直接发起底层查询请求
- 自己实现调度器
- 自己维护运行状态机

### 4.2 后端职责

后端负责：

- 查询配置管理
- 商品信息采集与缓存
- 三模式运行时管理
- 调度、日志、统计汇总
- 从账号中心读取账号能力与模式开关

### 4.3 分层建议

```text
app_frontend/
  app/
    windows/
    widgets/
    dialogs/
    controllers/
    services/

app_backend/
  api/
    routes/
    schemas/
    websocket/
  application/
    use_cases/
    services/
  domain/
    models/
    enums/
  infrastructure/
    db/
    repositories/
    query/
      collectors/
      executors/
      schedulers/
      runtime/
      clients/
  shared/
    dto/
    errors/
```

## 5. 领域模型

### 5.1 查询配置

`QueryConfig`

字段概念：

- `config_id`
- `name`
- `description`
- `enabled`
- `items`
- `mode_settings`
- `created_at`
- `updated_at`

说明：

- 一个配置对应一次可运行的查询任务定义
- 一个配置下包含多个查询商品
- 一个配置下包含三种模式设置

### 5.2 查询商品

`QueryItem`

字段概念：

- `query_item_id`
- `config_id`
- `product_url`
- `external_item_id`
- `item_name`
- `market_hash_name`
- `min_wear`
- `max_wear`
- `max_price`
- `last_market_price`
- `last_detail_sync_at`
- `sort_order`

规则：

- `product_url` 为用户输入主入口
- `external_item_id` 为系统解析结果
- `min_wear` 默认来自系统采集结果
- `max_wear` 与 `max_price` 为用户主要控制参数

### 5.3 模式配置

`QueryModeSetting`

字段概念：

- `mode_type`
- `enabled`
- `window_enabled`
- `start_hour`
- `start_minute`
- `end_hour`
- `end_minute`
- `base_cooldown_min`
- `base_cooldown_max`
- `random_delay_enabled`
- `random_delay_min`
- `random_delay_max`

说明：

- 每个配置下必须存在三条模式配置
- 三条记录分别对应三种查询模式

### 5.4 账号查询模式设置

`AccountQueryModeSetting`

字段概念：

- `account_id`
- `new_api_enabled`
- `fast_api_enabled`
- `token_enabled`
- `updated_at`

说明：

- 这张表属于账号中心的扩展设置
- 为账号级全局开关
- 对所有查询配置共享生效

### 5.5 查询任务

`QueryTask`

字段概念：

- `task_id`
- `config_id`
- `status`
- `started_at`
- `stopped_at`
- `last_error`

说明：

- 同一时间只存在一个运行中任务
- 第一阶段可用内存态管理任务
- 如有需要可增加运行记录落库

## 6. 存储设计

### 6.1 表：`query_configs`

- `config_id` TEXT PRIMARY KEY
- `name` TEXT NOT NULL UNIQUE
- `description` TEXT NULL
- `enabled` INTEGER NOT NULL DEFAULT 1
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

### 6.2 表：`query_config_items`

- `query_item_id` TEXT PRIMARY KEY
- `config_id` TEXT NOT NULL
- `product_url` TEXT NOT NULL
- `external_item_id` TEXT NOT NULL
- `item_name` TEXT NULL
- `market_hash_name` TEXT NULL
- `min_wear` REAL NULL
- `max_wear` REAL NULL
- `max_price` REAL NULL
- `last_market_price` REAL NULL
- `last_detail_sync_at` TEXT NULL
- `sort_order` INTEGER NOT NULL DEFAULT 0
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

### 6.3 表：`query_mode_settings`

- `mode_setting_id` TEXT PRIMARY KEY
- `config_id` TEXT NOT NULL
- `mode_type` TEXT NOT NULL
- `enabled` INTEGER NOT NULL DEFAULT 1
- `window_enabled` INTEGER NOT NULL DEFAULT 0
- `start_hour` INTEGER NOT NULL DEFAULT 0
- `start_minute` INTEGER NOT NULL DEFAULT 0
- `end_hour` INTEGER NOT NULL DEFAULT 0
- `end_minute` INTEGER NOT NULL DEFAULT 0
- `base_cooldown_min` REAL NOT NULL DEFAULT 0
- `base_cooldown_max` REAL NOT NULL DEFAULT 0
- `random_delay_enabled` INTEGER NOT NULL DEFAULT 0
- `random_delay_min` REAL NOT NULL DEFAULT 0
- `random_delay_max` REAL NOT NULL DEFAULT 0
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

约束建议：

- `config_id + mode_type` 唯一

### 6.4 表：`account_query_mode_settings`

- `account_id` TEXT PRIMARY KEY
- `new_api_enabled` INTEGER NOT NULL DEFAULT 1
- `fast_api_enabled` INTEGER NOT NULL DEFAULT 1
- `token_enabled` INTEGER NOT NULL DEFAULT 1
- `updated_at` TEXT NOT NULL

## 7. 查询运行架构

### 7.1 运行时核心

建议引入一套统一运行时外壳：

- `QueryTaskRuntime`

其职责：

1. 加载指定查询配置
2. 从账号中心读取全部账号
3. 读取账号查询模式全局开关
4. 按能力与开关过滤账号
5. 为三种模式分别创建 runner
6. 管理任务启动、停止、状态汇总
7. 汇总日志与统计

### 7.2 三模式运行器

建议引入三种模式运行器：

- `NewApiModeRunner`
- `FastApiModeRunner`
- `TokenModeRunner`

每个 runner 负责：

- 读取自己模式的参数
- 维护自己的时间窗口
- 维护自己的冷却与随机延迟
- 调度符合条件的账号参与查询
- 调用对应执行器发请求
- 输出本模式日志与统计

### 7.3 模式调度

每个模式独立调度。

不再使用“账号上挂时间窗口”的设计。

调度规则：

- 由模式配置决定当前是否允许运行
- 若在时间窗口外，则模式 runner 休眠等待
- 若在时间窗口内，则按冷却与随机延迟安排下一次查询
- 三种模式各自独立运行，但归属于同一个查询任务

### 7.4 账号过滤规则

某账号能参与某模式，需同时满足：

1. 账号未禁用
2. 账号中心的该模式全局开关为开启
3. 当前模式在配置中为启用
4. 账号能力满足模式要求

模式能力要求：

- `new_api`: 需要 `api_key`
- `fast_api`: 需要 `api_key`
- `token`: 需要 `token/cookie`

## 8. 商品录入与信息采集

### 8.1 录入流程

保留原逻辑：

1. 输入商品 URL
2. 解析 `external_item_id`
3. 查询本地缓存
4. 如缓存缺失或字段不完整，则调用采集器拉取详情
5. 自动补齐商品基础信息
6. 用户填写或确认筛选参数

### 8.2 采集器拆分建议

建议拆成两个边界：

- `ProductIdentityCollector`
  - 负责 URL 解析与商品标识提取
- `ProductDetailCollector`
  - 负责拉取商品详情与市场信息

必要时再加：

- `ProductCacheService`
  - 负责本地缓存读写

## 9. 前后端接口设计

### 9.1 查询配置接口

- `GET /query-configs`
- `POST /query-configs`
- `GET /query-configs/{config_id}`
- `PATCH /query-configs/{config_id}`
- `DELETE /query-configs/{config_id}`

### 9.2 查询商品接口

- `POST /query-configs/{config_id}/items`
- `PATCH /query-configs/{config_id}/items/{query_item_id}`
- `DELETE /query-configs/{config_id}/items/{query_item_id}`
- `POST /query-items/parse-url`
- `POST /query-items/fetch-detail`

### 9.3 模式配置接口

- `GET /query-configs/{config_id}/modes`
- `PATCH /query-configs/{config_id}/modes/{mode_type}`

### 9.4 查询运行接口

- `POST /query-runtime/start`
- `POST /query-runtime/stop`
- `GET /query-runtime/status`
- `GET /query-runtime/logs`

如需实时反馈，可扩展：

- `GET /ws/query-runtime`

## 10. UI 设计

### 10.1 查询系统主界面

建议拆为两个主要工作区：

- 配置管理区
- 任务运行区

### 10.2 配置管理区

包含：

- 配置列表
- 配置基础信息编辑
- 商品列表与商品编辑
- 三模式参数编辑

### 10.3 商品编辑区

字段建议：

- 商品 URL
- 自动解析到的商品标识
- 商品名称
- 市场名称
- 自动采集到的磨损范围
- 用户设置的最大磨损
- 用户设置的最大价格

### 10.4 模式参数编辑区

对三种模式分别展示：

- 是否启用
- 时间窗口
- 冷却范围
- 随机延迟开关
- 随机延迟范围

### 10.5 账号中心联动

账号中心详情区增加：

- `new_api` 开关
- `fast_api` 开关
- `token` 开关

同时展示强约束说明：

- 偏好开关是否开启
- 当前是否满足实际运行条件
- 缺少 `api_key` 时 API 模式不可实际生效
- 缺少 `token/cookie` 时 token 模式不可实际生效

### 10.6 任务运行区

显示：

- 当前运行配置
- 任务状态
- 三模式运行状态
- 各模式当前窗口状态
- 当前参与账号数
- 查询总次数
- 命中总次数
- 实时日志

## 11. 错误处理

常见错误分类：

1. 配置错误
   - 配置不存在
   - 商品列表为空
   - 模式参数非法

2. 商品录入错误
   - URL 无法解析
   - 商品详情采集失败
   - 必要字段缺失

3. 账号能力错误
   - 可参与账号为空
   - 模式启用但无账号具备对应能力

4. 运行时错误
   - 某模式启动失败
   - 某模式请求异常
   - 运行中断

处理原则：

- 后端返回结构化错误
- UI 展示人类可读错误
- 详细异常进入日志
- 单模式异常不应立即拖垮整个任务，除非是全局级故障

## 12. 测试策略

### 12.1 配置管理测试

- 配置 CRUD
- 商品 CRUD
- 三模式参数保存与读取

### 12.2 账号开关测试

- 账号查询模式偏好可持久化保存
- 偏好与能力状态可分离展示
- 缺少 `api_key` 时 API 模式不进入实际运行账号列表
- 缺少 `token/cookie` 时 token 模式不进入实际运行账号列表

### 12.3 商品录入测试

- URL 解析成功
- 商品详情补全成功
- 缓存命中逻辑正确
- 字段缺失时会重新拉取

### 12.4 运行时测试

- 单任务启动成功
- 同时运行第二个任务被拒绝
- 三模式独立时间窗口生效
- 冷却与随机延迟生效
- 账号能力过滤正确
- 任务停止时各 runner 正常清理

### 12.5 API 测试

- 查询配置接口
- 商品接口
- 模式配置接口
- 查询运行接口

## 13. 分阶段实施建议

建议拆成以下顺序：

1. 查询配置数据模型与仓库
2. 商品 URL 解析与详情采集
3. 配置管理 API 与前端编辑页
4. 账号中心接入查询模式全局开关
5. 查询运行时外壳 `QueryTaskRuntime`
6. `new_api` 模式 runner
7. `fast_api` 模式 runner
8. `token` 模式 runner
9. 日志与统计面板
10. 联调与回归测试

## 14. 结论

本设计确认：

- 账号中心之后，下一阶段重写查询系统
- 查询配置管理与查询运行时一起重写
- 保留原业务规则，不复用 legacy 查询主运行时
- 三种查询模式全部保留
- 三种模式各自独立维护时间窗口、冷却、随机延迟
- 查询时间配置属于查询系统，不属于账号中心
- 账号中心提供三种查询模式的全局偏好开关
- 实际是否参与某模式，由查询运行时结合账号能力再判定
- 同一时间只运行一个查询任务，一个任务只绑定一个配置
