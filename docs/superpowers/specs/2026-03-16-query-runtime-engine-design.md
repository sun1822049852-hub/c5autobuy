# 查询执行器设计

## 1. 目标

在现有查询系统前后端分离架构上，把“运行时空壳”补成“真实可执行的三模式查询引擎”，同时保持以下边界不变：

- 一个查询任务只绑定一个查询配置
- 同一时间只允许一个查询任务运行
- UI 只做输入、展示、控制，不直接接触 legacy 查询对象
- 本阶段只做查询，不接购买链路

完成后，点击“启动查询”应能真实驱动三种查询模式：

- `new_api`
- `fast_api`
- `token`

并且每种模式都按自己的时间窗、基础冷却、随机延迟独立运行。

## 2. 当前问题

当前重构版查询模块已经具备：

- 查询配置管理
- 三模式参数配置
- 商品管理
- 启停接口
- 运行态基本展示

但运行时仍然只是一个最小壳子：

- `QueryRuntimeService` 只会启动一个内存对象
- `QueryTaskRuntime` 只会返回静态 snapshot
- `ModeRunner` 只做资格统计，不发请求
- 时间窗调度器 `WindowScheduler` 没有真正挂进执行循环

因此当前“启动查询”不等于“真实开始查询”。

## 3. 设计原则

### 3.1 复用旧 scanner，不复用旧 runtime

本阶段采用“新壳包旧芯”的桥接方案：

- 继续复用 legacy 的三种 scanner 协议细节
- 不直接复用 legacy 的整体扫描运行时
- 在新后端里重建任务生命周期、模式调度、事件和状态汇总

原因：

- 最大限度保留旧查询细节
- 降低 `token / x-sign / device_id` 这类协议回归风险
- 保持新架构分层边界清晰，便于后续逐步替换 legacy scanner

### 3.2 模式级调度，不再沿用旧逻辑的时间窗限制

旧代码里：

- `new_api` / `fast_api` 默认不受时间窗限制
- `token` 才受时间窗限制

新需求已经明确变更为：

- 三种模式都有各自独立时间窗
- 三种模式都有各自基础冷却与随机延迟

因此新的运行时必须以“模式”为调度核心，而不是照搬旧的“查询组类型特判”。

### 3.3 能力与偏好分离

账号是否参与某模式，由两层条件共同决定：

- 账号中心偏好开关
- 真实运行能力

真实能力定义如下：

- `new_api`: 账号开启 `new_api_enabled` 且存在 `api_key`
- `fast_api`: 账号开启 `fast_api_enabled` 且存在 `api_key`
- `token`: 账号开启 `token_enabled` 且存在 `cookie / access token / device_id`

模式运行时只消费这些结论，不在 UI 中重复决策。

## 4. 运行时架构

### 4.1 QueryRuntimeService

职责：

- 启动查询任务
- 停止查询任务
- 返回当前任务状态

约束：

- 全局只允许一个运行中的查询任务
- 不直接感知 scanner 细节

### 4.2 QueryTaskRuntime

职责：

- 一个任务只绑定一个 `QueryConfig`
- 创建并持有三个模式执行器
- 聚合模式级状态、计数、日志和事件
- 统一处理任务启动、停止、snapshot 输出

输出：

- 任务级状态
- 模式级状态
- 最近事件 / 日志

### 4.3 ModeExecutionRunner

职责：

- 只负责一种模式
- 读取自身模式配置：
  - `window_enabled`
  - `start_hour/start_minute`
  - `end_hour/end_minute`
  - `base_cooldown_min/base_cooldown_max`
  - `random_delay_enabled/random_delay_min/random_delay_max`
- 维护本模式的账号活跃池
- 调度本模式下所有账号 worker

关键行为：

- 不在时间窗内时休眠到下一个窗口开始
- 在时间窗内时按配置节奏执行查询轮次
- 单账号失败不拖垮整个模式

### 4.4 AccountQueryWorker

职责：

- 负责“一个账号 + 一个模式”的实际查询执行
- 将账号、商品、模式映射为 legacy scanner 所需对象
- 返回查询结果、错误、延迟、禁用原因

它不负责：

- UI 更新
- 全局任务管理
- 模式时间调度

### 4.5 LegacyScannerAdapter

职责：

- 统一桥接三类 legacy scanner
- 隐藏 legacy `AccountManager` 风格接口
- 向运行时暴露统一的执行协议

它要兼容三种模式：

- `new_api` -> `C5MarketAPIScanner`
- `fast_api` -> `C5MarketAPIFastScanner`
- `token` -> `ProductQueryScanner`

## 5. 数据流

### 5.1 启动流程

1. `QueryRuntimeService.start(config_id)` 读取查询配置与全部账号
2. 构建 `QueryTaskRuntime`
3. `QueryTaskRuntime` 为每个模式创建 `ModeExecutionRunner`
4. 每个 mode runner 筛选符合条件的账号
5. 为每个账号创建对应的 `AccountQueryWorker`
6. 启动模式调度循环

### 5.2 单轮查询流程

1. `ModeExecutionRunner` 检查是否在时间窗内
2. 若不在窗口内，计算下次启动时间并等待
3. 若在窗口内，生成本轮等待时长：
   - 基础冷却
   - 随机延迟
4. 唤起本模式下每个活跃账号的 worker
5. worker 用 legacy scanner 查询当前配置中的全部商品
6. 查询结果汇总为事件并更新模式统计
7. `QueryTaskRuntime` 聚合到任务级 snapshot

### 5.3 查询结果去向

本阶段结果只进入运行时：

- 事件日志
- 模式计数
- 任务计数
- UI 展示数据

明确不做：

- 购买链路联动
- 购买池写入
- 库存分配变更

## 6. 状态模型

### 6.1 任务级状态

- `running`
- `config_id`
- `config_name`
- `message`
- `started_at`
- `stopped_at`
- `account_count`
- `total_query_count`
- `total_found_count`

### 6.2 模式级状态

- `mode_type`
- `enabled`
- `window_enabled`
- `in_window`
- `next_window_start`
- `next_window_end`
- `eligible_account_count`
- `active_account_count`
- `query_count`
- `found_count`
- `last_error`

### 6.3 账号级运行态

- `account_id`
- `display_name`
- `eligible`
- `active`
- `disabled_reason`
- `last_query_at`
- `last_success_at`
- `last_error`

### 6.4 事件模型

- `timestamp`
- `level`
- `mode_type`
- `account_id`
- `query_item_id`
- `message`
- `match_count`
- `latency_ms`
- `error`

## 7. 错误处理

### 7.1 商品级错误

- 某商品失败，不影响同账号同模式的其他商品
- 记录事件
- 继续后续商品

### 7.2 账号级错误

- 403: 该账号在该模式下禁用
- `Not login`: 该账号在 `token` 模式下禁用
- 429: 该账号在该模式下退避冷却，不停任务
- 普通超时 / 网络异常：记错误，下一轮继续

### 7.3 模式级错误

- 没有符合条件账号时，模式状态为可见但空转
- 模式状态写入 `last_error` 或 `message`
- 不连带终止其他模式

### 7.4 任务级错误

- 只有任务调度主循环崩溃，才终止整个查询任务
- 停机时要保证所有模式 runner 和 worker 都能退出

## 8. 停机语义

点击“停止查询”后：

1. 任务进入 stopping
2. 模式 runner 不再开始新一轮查询
3. 正在进行中的请求等待完成或超时
4. 适配器清理 scanner / session 资源
5. 任务状态变为 stopped

如果模式正处于窗口外等待：

- 收到停止信号后立即退出，不等待窗口开始

## 9. 接口与前端影响

### 9.1 后端接口

保留现有接口：

- `GET /query-runtime/status`
- `POST /query-runtime/start`
- `POST /query-runtime/stop`

但 `status` 返回体要增强，至少补：

- 模式级时间窗状态
- 模式级运行计数
- 最近错误 / 消息
- 可选的最近事件摘要

### 9.2 前端

前端不改控制链路，只增强展示：

- 运行状态面板增加模式细节
- 保持 `QuerySystemController` 调用方式不变
- 所有查询业务判断仍然在后端

## 10. 测试策略

### 10.1 后端优先

先补后端测试覆盖：

- 三模式独立时间窗
- 模式账号筛选
- 启动 / 停止
- 403 / 429 / 未登录处理
- 事件与统计聚合

### 10.2 接口回归

验证 `/query-runtime/*` 的返回体能稳定驱动前端

### 10.3 前端回归

前端只验证：

- 面板能显示增强后的状态字段
- 启停按钮和现有交互不回归

## 11. 非目标

本阶段明确不做：

- 购买链路接入
- 购买池状态联动
- 查询结果持久化入库
- 实时流式日志通道（WebSocket / SSE）
- 完全移除 legacy scanner

## 12. 后续演进

本设计完成后，后续可以安全做两件事：

1. 逐个替换 legacy scanner，先从 `new_api / fast_api` 开始
2. 在运行时稳定后再接入购买链路，而不是反过来

注：本次仅写设计文档，未执行 `git commit`，遵循当前会话“非用户明确要求不做 git 提交”的约束。
