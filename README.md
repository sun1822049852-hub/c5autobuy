# C5 分层重构说明

## 当前目标
- 保持现有功能可运行，逐步迁移 `autobuy.py` 核心逻辑到分层架构。
- GUI 为主入口，CLI 为迁移期兼容入口。

## 目录结构（当前）

```text
c5_layered/
  domain/                           # 领域模型
  application/
    dto/                            # DTO
    ports/                          # 仓储/运行时抽象
    use_cases/                      # 应用用例
    facade.py                       # ApplicationFacade
  infrastructure/
    repositories/                   # JSON/SQLite 适配器
    query/
      query_group_policy.py         # 查询组创建策略
      scanner_factory.py            # scanner 解析工厂
      group_runner.py               # QueryGroup 运行器
      coordinator_adapter.py        # 协调器适配器
      legacy_bridge.py              # legacy 查询桥接
      pipeline.py                   # 查询链路编排（canonical）
    runtime/
      legacy_cli_runtime.py         # 旧版 CLI 适配
      legacy_scan_runtime.py        # 扫描流程编排
      legacy_query_pipeline.py      # 兼容 shim
  presentation/gui/                 # Tk GUI
  bootstrap.py                      # 依赖装配
run_app.py                          # 统一入口
autobuy.py                          # legacy 引擎（迁移中）
```

## 标准调用链
- `run_app.py` -> `build_container(...)`
- `AppContainer.app` -> `ApplicationFacade`
- `ApplicationFacade.dashboard` -> `DashboardQueryUseCase`
- `ApplicationFacade.scan` -> `ScanControlUseCase`

## 已完成能力
- Dashboard 查询（账号/配置/商品快照）
- GUI 扫描控制（开始/停止）
- 仅查询模式（查询结果不进入购买调度）
- 购买账号白名单
- 实时状态与日志
- 启动 legacy CLI

## 当前重构进度（2026-03-17）
- 查询运行时已显式拆成 3 个独立调度器：`new_api`、`fast_api`、`token`
- `new_api` 查询执行已从 `autobuy.py` legacy scanner 中剥离，迁移到新模块 `app_backend/infrastructure/query/runtime/new_api_query_executor.py`
- `fast_api` 查询执行已从 `autobuy.py` legacy scanner 中剥离，迁移到新模块 `app_backend/infrastructure/query/runtime/fast_api_query_executor.py`
- `token` 查询执行已从 `autobuy.py` legacy scanner 中剥离，迁移到新模块 `app_backend/infrastructure/query/runtime/token_query_executor.py`
- 购买执行链路已从 `autobuy.py` 中剥离，迁移到新模块 `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`
- 库存刷新链路已从 `autobuy.py` 中剥离，迁移到新模块 `app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py`
- 登录执行链路已从 `autobuy.py` 中剥离，迁移到新模块 `app_backend/infrastructure/selenium/selenium_login_runner.py`
- `PurchaseRuntimeService` 默认已接入新购买执行网关和新库存刷新网关，`AccountPurchaseWorker` 和库存状态机保持原有行为
- 购买模块运行时已不再依赖 legacy `autobuy.py`
- 账号中心后端登录运行时已不再依赖 legacy `SeleniumLoginManager`
- 对外合同保持不变：
  - 前端配置项不变
  - 后端 API 字段不变
  - `QueryExecutionResult` 结构不变
  - 查询命中转购买链路不变
- 查询链路已不再依赖 `autobuy.py`

## 阶段 B 进展（查询链路）
- B1 已完成：查询生命周期从 `LegacyScanRuntime` 抽离到 query pipeline
- B2.1 已完成：账号接入（查询组+购买池注册）下沉到 query pipeline
- B2.2 进行中：
  - 建立 `infrastructure/query` canonical 层
  - `coordinator_adapter` 接管协调器方法适配
  - `group_runner` 直接构建和运行 `QueryGroup`
  - `scanner_factory` 提供 scanner 类解析
  - `query_group_policy` 抽离查询组创建条件决策

## 运行方式

### GUI（默认）

```bash
python run_app.py
```

### CLI（兼容模式）

```bash
python run_app.py --mode cli
```
