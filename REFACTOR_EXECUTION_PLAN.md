# C5 重构执行手册（完成态）

更新时间：2026-03-18

## 1. 当前状态
- `autobuy.py` 已退出默认运行链路，但源码当前仍保留在仓库中作为参考。
- `c5_layered` 兼容 UI 层已从仓库删除。
- 当前运行入口为 `run_app.py -> app_frontend.main.main() -> LocalBackendServer -> app_backend.main.create_app()`。
- 查询、购买、库存刷新、登录运行时都已收口到 `app_backend`。

## 2. 当前代码边界

### 前端
- `app_frontend/main.py`
- `app_frontend/app/windows/workspace_window.py`
- `app_frontend/app/windows/account_center_window.py`
- `app_frontend/app/windows/query_system_window.py`
- `app_frontend/app/windows/purchase_runtime_window.py`

### 后端
- `app_backend/main.py`
- `app_backend/infrastructure/query/runtime/`
- `app_backend/infrastructure/purchase/runtime/`
- `app_backend/infrastructure/selenium/`
- `app_backend/api/routes/`

## 3. 已完成迁移
- 三种查询模式 `new_api / fast_api / token` 已迁出旧实现
- 查询运行时三模式独立调度、时间窗、账号模式开关已落地
- 查询命中到购买运行时的联动已落地
- 无可用购买账号时，查询停机并清空 backlog；账号恢复后自动恢复查询
- 购买执行、库存刷新、登录链路都已迁入新模块
- 默认运行链路已不再依赖旧版 CLI 入口、`c5_layered` 过渡层与 `autobuy.py`

## 4. 当前约束
- 新增默认行为不要重新依赖 `autobuy.py`、`c5_layered` 或任何 `legacy_*` 兼容壳
- UI 只通过 `app_frontend` 调后端接口，不直接持有后端运行时对象
- 新增行为必须继续对照旧语义，但实现只能落在当前前后端分层内
- `autobuy.py` 当前保留为历史单文件参考；`c5_layered` 已删除，不代表默认运行链路仍依赖旧 UI 层

## 5. 建议验证命令

```bash
python -m pytest tests/backend/test_no_legacy_runtime_dependency.py -q
python -m pytest -q
```

## 6. 维护说明
- 如果后续继续做差异审计，基准对象应改为“历史设计语义”而不是仓库内旧实现文件
- 如果要补当前里程碑说明，优先更新 `README.md` 与本文件
- 如果要排查旧 `autobuy.py` 与新 backend 的实现级差异，先看 `docs/superpowers/references/2026-03-19-autobuy-backend-semantic-drift-reference.md`
- `docs/superpowers/specs/`、`docs/superpowers/plans/` 保留为迁移过程档案，不作为当前运行结构说明
