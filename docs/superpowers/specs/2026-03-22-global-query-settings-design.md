# 全局查询设置设计

日期：2026-03-22

## 1. 文档目的

本文用于把“查询器冷却 / 随机冷却 / 每日运行时间窗”从旧的配置级 `mode_settings` 中剥离出来，改为一套全局、持久化、独立于配置管理的 `query settings`。

本文优先服务当前新后端与 `app_desktop_web`。旧 PySide UI 与 legacy 数据结构仅保留兼容，不再作为新设计约束来源。

## 2. 背景与问题

当前后端与旧 UI 延续了“每个查询配置附带三条 `mode_settings`”的设计：

- 配置创建时自动写入 `new_api / fast_api / token` 三条模式设置
- 查询运行时直接读取 `config.mode_settings`
- 旧 PySide 配置页直接把“模式设置”当成配置详情的一部分

这带来四个问题：

1. 查询器运行参数的所有权错误，配置管理与运行策略混在一起。
2. 同一套查询器理论上可以在不同配置里拥有不同冷却值，语义不稳定。
3. 当前后端没有全局最小冷却校验，也没有浏览器模式低冷却风险提示。
4. 新 Web UI 若继续沿用配置级 `mode_settings`，会把旧混乱继续放大。

## 3. 范围

本文覆盖：

- 新增全局 `query settings` 的数据模型、API、仓储与运行时读取
- 扫货系统页面中的“查询设置”入口与编辑弹窗
- 三种查询器的冷却、随机冷却、运行时间窗配置
- 最小冷却校验与浏览器风险提示
- 对旧配置级 `mode_settings` 的兼容策略

本文不覆盖：

- 旧 PySide 界面的同步改造
- 旧 `query_mode_settings` 表的立即删除
- 查询器调度算法本身的重写
- 购买链路逻辑改造

## 4. 已确认的用户决策

- “购买系统”重命名为“扫货系统”。
- 扫货系统顶部中，“选择配置/切换配置”左边增加“查询设置”入口。
- 查询设置是通用的、持久化的，不属于任意单个配置。
- 三种查询器各自独立配置：
  - 基础冷却时间
  - 随机冷却时间
  - 每日运行时间窗
- `fast_api` 最小基础冷却为 `0.2s`
- `new_api` 最小基础冷却为 `1.0s`
- `token` 推荐基础冷却为 `10.0s`
- `token` 小于 `10.0s` 不是硬拦截；保存时只提醒“封号风险极高”
- 时间窗通过独立开关控制，三种查询器彼此独立

## 5. 方案比较

### 方案 A：继续使用配置级 `mode_settings`

优点：

- 现有代码改动最少

缺点：

- 继续混淆配置层与运行层
- 无法表达“通用设置”
- 新 UI 仍被旧设计拖着走

### 方案 B：新增全局 `query settings`，运行时与新 UI 切换到全局设置

优点：

- 语义清晰，和用户需求完全一致
- 后续最小冷却校验、风险提示、独立设置页都有明确归属
- 可以保留旧结构做兼容，不必一次性拆光 legacy

缺点：

- 需要补新表、新仓储、新路由、新前端弹窗
- 运行时需要改为读取全局设置

### 方案 C：新增“全局默认值”，但运行时仍读配置设置

优点：

- 表面改动较少

缺点：

- 会出现“设置页改了但当前运行没生效”的错觉
- 仍然保留双源状态

## 6. 推荐方案

采用方案 B：

- 新增真正的全局 `query settings`
- 新 Web UI 与查询运行时统一读取这份全局设置
- 旧配置级 `mode_settings` 暂时保留，仅作兼容层

## 7. 数据模型

### 7.1 新领域模型

新增：

- `QuerySettings`
- `QuerySettingsMode`

`QuerySettingsMode` 字段：

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
- `created_at`
- `updated_at`

说明：

- 仍保留 `min/max` 区间表达，以兼容现有运行时 `ModeRunner._pick_delay`
- 单值冷却可通过 `min == max` 表达

### 7.2 新数据库表

新增表：

- `query_settings_modes`

主键建议：

- `mode_type`

每种模式一条记录：

- `new_api`
- `fast_api`
- `token`

### 7.3 默认值

首次初始化时，若库中不存在记录，则自动创建：

- `new_api`
  - `enabled = true`
  - `base_cooldown_min = 1.0`
  - `base_cooldown_max = 1.0`
- `fast_api`
  - `enabled = true`
  - `base_cooldown_min = 0.2`
  - `base_cooldown_max = 0.2`
- `token`
  - `enabled = true`
  - `base_cooldown_min = 10.0`
  - `base_cooldown_max = 10.0`

三者共同默认：

- `window_enabled = false`
- `start_hour = 0`
- `start_minute = 0`
- `end_hour = 0`
- `end_minute = 0`
- `random_delay_enabled = false`
- `random_delay_min = 0.0`
- `random_delay_max = 0.0`

## 8. API 设计

新增：

- `GET /query-settings`
- `PUT /query-settings`

`GET /query-settings` 返回：

- `modes: [QuerySettingsModeResponse]`

`PUT /query-settings` 请求体：

- `modes: [QuerySettingsModeUpdateRequest]`

说明：

- 一次性保存三种模式，避免前端多次提交造成部分成功、部分失败
- 返回值中允许携带 `warnings`

## 9. 校验规则

### 9.1 后端硬校验

- `new_api.base_cooldown_min >= 1.0`
- `fast_api.base_cooldown_min >= 0.2`
- `base_cooldown_max >= base_cooldown_min`
- 若开启随机冷却：
  - `random_delay_min >= 0`
  - `random_delay_max >= random_delay_min`
- 时间窗字段必须位于合法小时/分钟范围

### 9.2 后端非阻断 warning

若 `token.base_cooldown_min < 10.0` 或 `token.base_cooldown_max < 10.0`：

- 允许保存
- 返回 warning：`浏览器查询器基础冷却低于 10 秒，封号风险极高`

### 9.3 前端即时校验

前端在提交前同步校验上述硬规则，避免无效请求。

若命中 `token < 10s`：

- 弹出确认提示
- 用户确认后继续提交

## 10. 运行时接入

### 10.1 目标

查询运行时只读取全局 `query settings`，不再信任 `config.mode_settings` 作为真实运行策略来源。

### 10.2 具体策略

在 `QueryRuntimeService` 内增加设置仓储依赖。

当启动 runtime、构造等待快照或补齐模式快照时：

- 从 `query_settings_repository` 读取全局设置
- 按模式生成运行时使用的 `mode settings` 视图
- 将该视图附着到 runtime 使用的配置副本上

说明：

- 配置中的商品、分配、价格、磨损仍来自 `QueryConfig`
- 只有模式运行参数改为来自全局设置

## 11. 兼容策略

### 11.1 保留旧表

暂不删除：

- `query_mode_settings`

原因：

- 旧 PySide UI 仍可能读取它
- 当前测试中存在配置级模式设置假设

### 11.2 新旧职责边界

- 新 Web UI 不再读取或编辑配置级 `mode_settings`
- 新查询运行时不再依赖配置级 `mode_settings`
- 旧配置级 `mode_settings` 只作为 legacy 兼容保留

### 11.3 不做自动双写

本阶段不把全局设置反写回每个配置的 `mode_settings`。

原因：

- 双写会重新引入双源状态
- 容易让开发误以为配置级设置仍是权威数据

## 12. Web UI 设计

### 12.1 命名调整

- 侧边栏 `购买系统` 改名为 `扫货系统`

### 12.2 顶部入口

扫货系统顶部栏位：

- 左侧：`查询设置`
- 右侧：`选择配置 / 切换配置`
- 保留当前配置名、状态、累计购买

### 12.3 查询设置弹窗

采用中间 modal，三张模式卡：

- `new API`
- `fast API`
- `浏览器 token`

每张卡提供：

- 启用开关
- 基础冷却最小/最大
- 随机冷却开关与最小/最大
- 运行时间窗开关
- 起止时间

底部提供：

- `取消`
- `保存`

## 13. 测试策略

### 13.1 后端

- 仓储首次读取会生成默认全局设置
- 保存全局设置可持久化
- 最小冷却硬校验生效
- `token < 10s` 返回 warning 而非报错
- `QueryRuntimeService` 构建 runtime 时使用全局设置而不是配置设置

### 13.2 前端

- 侧边栏显示 `扫货系统`
- 扫货页顶部出现 `查询设置`
- 可以加载与保存查询设置
- `new_api < 1.0`、`fast_api < 0.2` 阻止提交
- `token < 10s` 会先提示，再允许提交

## 14. 验收标准

满足以下条件即可视为本轮闭环完成：

1. 新 Web UI 中 `购买系统` 已改名为 `扫货系统`
2. 扫货页可打开并保存全局查询设置
3. 查询设置重启后仍保留
4. 查询 runtime 使用的是全局设置
5. 配置管理页不再承担查询器冷却设置职责
6. `token < 10s` 只提示、不拦截
