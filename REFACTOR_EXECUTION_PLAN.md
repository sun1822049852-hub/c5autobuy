# C5 重构执行手册（跨对话）

更新时间：2026-03-15

## 1. 总目标
- 在不破坏现有功能的前提下，将 `autobuy.py` 逐步迁移到 `c5_layered`。
- 迁移期保持 GUI 与 CLI 可运行。
- 最终移除 `import autobuy` 直接依赖。

## 2. 当前完成度

### 已完成
- [x] 分层基础结构落地（domain/application/infrastructure/presentation）
- [x] 入口统一到 `ApplicationFacade`
- [x] 旧 `application/services.py` 与 `contracts.py` 已清理
- [x] GUI 支持：开始/停止、仅查询、白名单、日志状态
- [x] B1：查询生命周期从 scan runtime 抽离到 query pipeline
- [x] B2.1：账号接入逻辑（查询组+购买池注册）下沉到 query pipeline
- [x] B2.2-1：建立 `infrastructure/query`（bridge + canonical pipeline）
- [x] B2.2-2：新增 coordinator adapter
- [x] B2.2-3：QueryCoordinator 生命周期改由 adapter 管理
- [x] B2.2-4：新增 group runner
- [x] B2.2-5：group runner 直接构建 QueryGroup（new/fast/old）
- [x] B2.2-6：新增 scanner factory，group runner 不再写死 scanner 类名
- [x] B2.2-7：新增 query group policy，group 创建条件从 runner 抽离

### 未完成
- [ ] `QueryGroup/scanner` 的具体执行实现仍在 `autobuy.py`
- [ ] 购买调度、下单、支付仍在 `autobuy.py`
- [ ] 账号会话认证仍在 `autobuy.py`
- [ ] 尚未移除 `importlib.import_module("autobuy")`

## 3. 关键文件（当前）
- `run_app.py`
- `c5_layered/bootstrap.py`
- `c5_layered/infrastructure/query/query_group_policy.py`
- `c5_layered/infrastructure/query/scanner_factory.py`
- `c5_layered/infrastructure/query/group_runner.py`
- `c5_layered/infrastructure/query/coordinator_adapter.py`
- `c5_layered/infrastructure/query/legacy_bridge.py`
- `c5_layered/infrastructure/query/pipeline.py`
- `c5_layered/infrastructure/runtime/legacy_scan_runtime.py`
- `c5_layered/infrastructure/runtime/legacy_query_pipeline.py`（兼容 shim）

## 4. 分阶段计划

## 阶段 A：回归基线（进行中）
- 固化 smoke 场景：
  - GUI 启动
  - 扫描开始/停止
  - 仅查询模式
  - 白名单购买
- 关键指标：
  - `query_count`
  - `found_count`
  - `purchased_count`

## 阶段 B：查询链路迁移

状态：`B1 完成，B2.1 完成，B2.2 进行中`

### B2.2 下一步
- 抽离 scanner 执行适配层（逐步替换 legacy scanner 直接实现依赖）
- 目标：query 层对 legacy 的依赖进一步收敛到 bridge/factory 边界

验收：
- `LegacyScanRuntime` 无 query 组构建细节
- query 层不再出现 scanner 类名硬编码与组创建业务判断
- 指标偏差可控（建议 <5%）

## 阶段 C：购买资格迁移（待开始）
- 形成 `PurchaseEligibilityPolicy`
- 规则：非 query_only + 登录 + 白名单命中（或白名单为空）

## 阶段 D：下单支付迁移（待开始）
- 抽离 `OrderService/PaymentService/RetryPolicy/IdempotencyGuard`

## 阶段 E：会话认证迁移（待开始）
- 抽离 `AccountSessionManager/TokenRefreshService/CookieStore`

## 阶段 F：清退 legacy（待开始）
- 移除 `import autobuy` 依赖

## 5. 每次对话执行规范
1. 先读本文件，选一个最小可交付任务。
2. 避免跨阶段混改。
3. 完成后执行第 6 节验证命令。
4. 追加第 7 节执行日志。

## 6. 验证命令

```bash
python -m py_compile run_app.py
python -m py_compile c5_layered/infrastructure/runtime/legacy_scan_runtime.py
python -m py_compile c5_layered/infrastructure/query/query_group_policy.py
python -m py_compile c5_layered/infrastructure/query/scanner_factory.py
python -m py_compile c5_layered/infrastructure/query/group_runner.py
python -m py_compile c5_layered/infrastructure/query/coordinator_adapter.py
python -m py_compile c5_layered/infrastructure/query/legacy_bridge.py
python -m py_compile c5_layered/infrastructure/query/pipeline.py
python run_app.py --help
```

建议扩展：

```bash
python -m py_compile $(rg --files -g "*.py")
```

## 7. 执行日志

- 2026-03-15（记录1）
  - 完成：B1 查询生命周期抽离
  - 验证：`py_compile`、`run_app.py --help` 通过

- 2026-03-15（记录2）
  - 完成：B2.1 账号接入逻辑下沉到 query pipeline
  - 验证：`py_compile`、`run_app.py --help` 通过

- 2026-03-15（记录3）
  - 完成：B2.2 第一步，建立 `infrastructure/query`

- 2026-03-15（记录4）
  - 完成：B2.2 第二步，新增 coordinator adapter

- 2026-03-15（记录5）
  - 完成：B2.2 第三步，QueryCoordinator 生命周期适配

- 2026-03-15（记录6）
  - 完成：B2.2 第四步，抽离 QueryCoordinator 运行器

- 2026-03-15（记录7）
  - 完成：B2.2 第五步，group runner 直接构建 QueryGroup

- 2026-03-15（记录8）
  - 完成：B2.2 第六步，抽离 scanner 解析工厂

- 2026-03-15（记录9）
  - 完成：B2.2 第七步，抽离 query group policy
  - 变更：
    - 新增 `query/query_group_policy.py`
    - `group_runner` 改为通过 `LegacyQueryGroupPolicy` 决定是否创建 new/fast/old 组
    - `query/__init__.py` 导出 `LegacyQueryGroupPolicy` 与 `QueryGroupPlan`
  - 验证：
    - `py_compile` 通过
    - `run_app.py --help` 通过
    - `group_runner` 中无直接组创建策略判断逻辑
