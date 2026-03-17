# 查询执行路由器重命名与旧壳收缩设计

## 1. 目标

把查询运行时里残留的旧职责名 `LegacyScannerAdapter` 清理掉，改成符合当前真实职责的命名，同时保持运行时行为完全不变。

本次目标：

- 新增真实职责名 `QueryExecutorRouter`
- 把查询模式分发的主入口从 `LegacyScannerAdapter` 切到 `QueryExecutorRouter`
- 保留一个超薄兼容层，避免一次性硬切引发漏改
- 不改查询执行器请求参数
- 不改 `RuntimeAccountAdapter`
- 不改调度逻辑、事件结构和结果结构

本次不是“实质迁移”，只是“表面清理 + 主入口正名”。

## 2. 当前现状

当前查询运行时已经不再直接依赖 `autobuy.py`，但命名上还残留旧阶段痕迹：

- `LegacyScannerAdapter` 实际已经不调用旧模块
- 它现在只是按 `mode_type` 分发到：
  - `NewApiQueryExecutor`
  - `FastApiQueryExecutor`
  - `TokenQueryExecutor`
- 同时负责把账号包装成 `RuntimeAccountAdapter`
- 并把异常收敛成 `QueryExecutionResult`

也就是说，当前这个类并不“legacy”，也不“scanner”，而是一个查询执行分发器。

## 3. 方案比较

### 方案 A：新增 `QueryExecutorRouter`，旧类保留为薄兼容层

做法：

- 新增 `query_executor_router.py`
- 新主类命名为 `QueryExecutorRouter`
- 主引用切到新类
- `legacy_scanner_adapter.py` 仅保留兼容转发

优点：

- 风险最低
- 主职责名立即正确
- 不需要一次性删光旧引用
- 为后续彻底删除兼容层留出缓冲

缺点：

- 短期内仓库里会同时存在新旧两个名字

### 方案 B：一次性硬切并删除旧文件

做法：

- 直接删除 `legacy_scanner_adapter.py`
- 所有引用和测试一次性切到新文件

优点：

- 最干净

缺点：

- 漏掉一个引用就会直接打炸查询运行时
- 风险高于这次“表面清理”的目标

### 方案 C：只改类名，不改文件名

做法：

- 文件仍保留 `legacy_scanner_adapter.py`
- 类名改成 `QueryExecutorRouter`

优点：

- 改动最少

缺点：

- 文件名和职责继续不一致
- 清理不彻底

## 4. 结论

采用方案 A。

原因：

- 这一步的目标是稳妥地把主职责名纠正过来
- 不是做一次高风险的大清洗
- 兼容层能把风险限制在“引用接线”这一层

## 5. 设计

### 5.1 新主类

新增文件：

- `app_backend/infrastructure/query/runtime/query_executor_router.py`

新增类：

- `QueryExecutorRouter`

职责保持与当前运行时一致，仅负责：

1. 接收 `mode_type`
2. 把账号统一包装成 `RuntimeAccountAdapter`
3. 路由到 3 个查询执行器
4. 把异常兜底转成 `QueryExecutionResult`

明确不负责：

- 构建查询请求体细节
- 调度器决策
- 时间窗口判断
- 事件发射

### 5.2 旧兼容层

保留：

- `app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py`

但它只保留为超薄兼容层：

- 内部直接转发到 `QueryExecutorRouter`
- 不再承载主逻辑
- 不再保留任何“legacy”语义实现

这样做的目的只是避免一次性硬切导致隐藏引用炸掉。

### 5.3 Worker 接线

`AccountQueryWorker` 默认依赖从：

- `LegacyScannerAdapter`

改为：

- `QueryExecutorRouter`

但行为不变：

- 仍然调用统一的 `execute_query(...)`
- 仍然拿到 `QueryExecutionResult`
- 仍然保留原有错误处理和统计逻辑

### 5.4 导出和引用

`app_backend/infrastructure/query/runtime/__init__.py` 需要导出：

- `QueryExecutorRouter`

旧的 `LegacyScannerAdapter` 仍可保留导出一个过渡周期，但不再作为主入口使用。

测试和其他运行时引用应优先切到新名字。

## 6. 测试策略

### 6.1 主测试迁到新名字

主行为测试应该直接覆盖 `QueryExecutorRouter`：

- `new_api` 正确分发
- `fast_api` 正确分发
- `token` 正确分发
- 非法 `mode_type` 返回 unsupported
- 异常会被转成失败的 `QueryExecutionResult`

### 6.2 兼容测试缩小

`LegacyScannerAdapter` 不再承担主行为测试，只保留很小一组兼容测试，证明：

- 它确实转发到了 `QueryExecutorRouter`
- 它没有引入额外行为分叉

### 6.3 Worker 回归

`AccountQueryWorker` 的测试需要补一条：

- 默认依赖已经变成 `QueryExecutorRouter`

其余行为测试不变。

## 7. 风险控制

本次不改这些内容：

- 3 个查询执行器的接口参数和请求体
- `RuntimeAccountAdapter` 的方法名和行为
- 运行时调度器结构
- 命中事件结构
- `QueryExecutionResult` 结构

因此风险主要集中在：

- 导入路径是否全部切对
- 兼容层是否正确转发
- 测试是否同步迁移

## 8. 完成标准

满足以下条件才算完成：

1. 查询运行时主职责名变成 `QueryExecutorRouter`
2. `AccountQueryWorker` 默认依赖新名字
3. `LegacyScannerAdapter` 只剩兼容转发
4. 查询运行时行为没有变化
5. 全量测试仍然通过

## 9. 非目标

本次不做：

- 删除 `RuntimeAccountAdapter`
- 把执行器改成直接吃新账号能力对象
- 修改查询执行器内部实现
- 改造购买、库存刷新、详情抓取的账号适配层
- 彻底删除兼容层

## 10. 结论

这一步的核心不是“改功能”，而是把当前已经迁完的查询执行分发层正名：

- 主入口变成 `QueryExecutorRouter`
- 旧名退化成兼容壳

这样仓库表面语义会更干净，后面再做更深层的账号适配迁移时，边界也更清楚。

注：当前会话按用户要求不执行 git 提交；spec 仅落盘供确认与后续实现使用。
