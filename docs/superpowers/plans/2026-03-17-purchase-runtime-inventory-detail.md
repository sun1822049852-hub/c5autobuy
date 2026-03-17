# Purchase Runtime Inventory Detail Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为购买运行页补齐“目标仓库 + 容量摘要”展示，并提供按账号打开的库存详情弹窗，且不改变现有购买核心逻辑。

**Architecture:** 后端继续保持购买运行状态接口轻量化，只在 `accounts[]` 中补目标仓库摘要字段；全部小仓库明细通过新的只读详情接口按需获取。前端主页面只渲染摘要，双击账号行时调用独立接口并打开只读弹窗展示库存快照。

**Tech Stack:** Python, FastAPI, PySide6, httpx, pytest

---

## 文件结构

- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/api/schemas/purchase_runtime.py`
- Modify: `app_backend/api/routes/purchase_runtime.py`
- Create: `app_backend/application/use_cases/get_purchase_runtime_inventory_detail.py`
- Modify: `app_frontend/app/services/backend_client.py`
- Modify: `app_frontend/app/viewmodels/purchase_runtime_vm.py`
- Modify: `app_frontend/app/widgets/purchase_runtime_panel.py`
- Modify: `app_frontend/app/controllers/purchase_runtime_controller.py`
- Modify: `app_frontend/app/windows/purchase_runtime_window.py`
- Create: `app_frontend/app/dialogs/purchase_inventory_detail_dialog.py`
- Modify: `tests/backend/test_purchase_runtime_service.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Modify: `tests/frontend/test_backend_client.py`
- Modify: `tests/frontend/test_purchase_runtime_vm.py`
- Modify: `tests/frontend/test_purchase_runtime_panel.py`
- Modify: `tests/frontend/test_purchase_runtime_controller.py`
- Modify: `tests/frontend/test_purchase_runtime_window.py`
- Create: `tests/frontend/test_purchase_inventory_detail_dialog.py`

注：本计划不包含 git 提交，因用户明确要求不主动执行 git。

## Chunk 1: 后端库存摘要与详情接口

### Task 1: 先写后端失败测试

- [ ] 在 `tests/backend/test_purchase_runtime_service.py` 为 `get_status()` 增加目标仓库摘要断言
- [ ] 在 `tests/backend/test_purchase_runtime_service.py` 增加“详情优先读运行时内存快照”的失败测试
- [ ] 在 `tests/backend/test_purchase_runtime_service.py` 增加“详情回退持久化快照”的失败测试
- [ ] 在 `tests/backend/test_purchase_runtime_routes.py` 增加详情路由返回库存明细的失败测试
- [ ] 运行定向测试，确认因字段或接口不存在而失败

Run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; $PSDefaultParameterValues['*:Encoding'] = 'utf8'; .\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py -q
```

Expected:
- `FAIL`
- 失败原因应是缺少库存摘要字段、缺少详情方法或缺少详情路由，而不是测试本身写错

### Task 2: 最小实现后端库存摘要

- [ ] 在 `purchase_runtime_service.py` 的运行状态 `accounts[]` 中补：
  - `selected_inventory_remaining_capacity`
  - `selected_inventory_max`
- [ ] 从当前 `selected_steam_id` 对应的小仓库快照中提取剩余容量与总容量
- [ ] 无目标仓库时返回空值，不抛异常
- [ ] 复跑后端状态摘要相关测试

Run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; $PSDefaultParameterValues['*:Encoding'] = 'utf8'; .\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py -q
```

Expected:
- 与库存摘要相关的测试 `PASS`

### Task 3: 最小实现库存详情接口

- [ ] 在 `purchase_runtime_service.py` 新增只读详情查询方法
- [ ] 详情数据优先从运行时内存状态读取
- [ ] 当前运行时取不到账号时，回退到库存快照仓库
- [ ] 为详情响应中每个小仓库补 `is_selected` 和 `is_available`
- [ ] 在 `app_backend/api/schemas/purchase_runtime.py` 增加详情响应 schema
- [ ] 新建 `app_backend/application/use_cases/get_purchase_runtime_inventory_detail.py`
- [ ] 在 `app_backend/api/routes/purchase_runtime.py` 增加 `GET /purchase-runtime/accounts/{account_id}/inventory`
- [ ] 复跑后端定向测试

Run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; $PSDefaultParameterValues['*:Encoding'] = 'utf8'; .\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py -q
```

Expected:
- `PASS`
- 路由返回详情快照
- 详情接口不触发远端刷新、不写回状态

## Chunk 2: 前端摘要渲染与详情弹窗

### Task 4: 先写前端失败测试

- [ ] 在 `tests/frontend/test_purchase_runtime_vm.py` 增加容量摘要格式化断言
- [ ] 在 `tests/frontend/test_purchase_runtime_panel.py` 增加主表显示“目标仓库/容量”的失败测试
- [ ] 在 `tests/frontend/test_backend_client.py` 增加新详情接口 client 方法失败测试
- [ ] 在 `tests/frontend/test_purchase_runtime_controller.py` 增加加载库存详情的失败测试
- [ ] 在 `tests/frontend/test_purchase_runtime_window.py` 增加“双击账号行打开详情”的失败测试
- [ ] 新建 `tests/frontend/test_purchase_inventory_detail_dialog.py`，覆盖弹窗加载成功、空快照、错误状态
- [ ] 运行前端定向测试，确认因 client / dialog / 双击交互缺失而失败

Run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; $PSDefaultParameterValues['*:Encoding'] = 'utf8'; .\.venv\Scripts\python.exe -m pytest tests/frontend/test_backend_client.py tests/frontend/test_purchase_runtime_vm.py tests/frontend/test_purchase_runtime_panel.py tests/frontend/test_purchase_runtime_controller.py tests/frontend/test_purchase_runtime_window.py tests/frontend/test_purchase_inventory_detail_dialog.py -q
```

Expected:
- `FAIL`
- 失败原因集中在新字段未渲染、详情 dialog 不存在、controller/client 缺少新方法

### Task 5: 最小实现前端库存摘要

- [ ] 在 `app_frontend/app/viewmodels/purchase_runtime_vm.py` 增加：
  - `selected_steam_id` 展示值
  - `capacity_text` 展示值
- [ ] 容量格式统一为 `remaining/max`
- [ ] 无目标仓库或无摘要字段时统一显示 `-`
- [ ] 在 `app_frontend/app/widgets/purchase_runtime_panel.py` 调整账号表为 7 列并渲染 `目标仓库`、`容量`
- [ ] 复跑 VM 和 panel 定向测试

Run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; $PSDefaultParameterValues['*:Encoding'] = 'utf8'; .\.venv\Scripts\python.exe -m pytest tests/frontend/test_purchase_runtime_vm.py tests/frontend/test_purchase_runtime_panel.py -q
```

Expected:
- `PASS`
- 主表可显示目标仓库与容量摘要

### Task 6: 最小实现详情 client / controller / dialog / window

- [ ] 在 `app_frontend/app/services/backend_client.py` 增加购买库存详情接口方法
- [ ] 在 `app_frontend/app/controllers/purchase_runtime_controller.py` 增加加载详情的方法和错误回调入口
- [ ] 新建 `app_frontend/app/dialogs/purchase_inventory_detail_dialog.py`
- [ ] 弹窗顶部展示账号名、目标仓库、最近快照时间、最近错误
- [ ] 弹窗表格展示全部小仓库：仓库ID、当前数量、容量上限、剩余容量、是否当前目标、是否可用
- [ ] 在 `app_frontend/app/windows/purchase_runtime_window.py` 接入账号表双击事件
- [ ] 双击时读取当前选中账号 ID，请求详情接口并打开只读弹窗
- [ ] 接口失败时只在弹窗层或窗口状态层提示，不影响主表刷新
- [ ] 复跑前端定向测试

Run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; $PSDefaultParameterValues['*:Encoding'] = 'utf8'; .\.venv\Scripts\python.exe -m pytest tests/frontend/test_backend_client.py tests/frontend/test_purchase_runtime_controller.py tests/frontend/test_purchase_runtime_window.py tests/frontend/test_purchase_inventory_detail_dialog.py -q
```

Expected:
- `PASS`
- 双击账号行会打开详情弹窗
- 弹窗只读，不自动刷新

## Chunk 3: 联调验证

### Task 7: 跑购买运行相关回归测试

- [ ] 运行购买运行相关后端测试
- [ ] 运行购买运行相关前端测试
- [ ] 确认没有把现有查询桥接、库存恢复、购买成功回写逻辑打坏

Run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; $PSDefaultParameterValues['*:Encoding'] = 'utf8'; .\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py tests/backend/test_query_purchase_bridge.py tests/frontend/test_backend_client.py tests/frontend/test_purchase_runtime_vm.py tests/frontend/test_purchase_runtime_panel.py tests/frontend/test_purchase_runtime_controller.py tests/frontend/test_purchase_runtime_window.py tests/frontend/test_purchase_inventory_detail_dialog.py -q
```

Expected:
- `PASS`

### Task 8: 跑全量测试做最终验证

- [ ] 运行全量测试
- [ ] 记录 warnings 和非本次改动问题
- [ ] 基于实际输出汇报结果，不做无证据结论

Run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; $PSDefaultParameterValues['*:Encoding'] = 'utf8'; .\.venv\Scripts\python.exe -m pytest -q
```

Expected:
- 全量 `PASS`
- 若仍有历史 warnings，单独说明来源，不把 warnings 说成失败

## 备注

- 当前环境没有可用的 plan reviewer 子代理，本计划采用人工自检后交由用户确认
- 执行阶段继续遵守 TDD：先写失败测试，再做最小实现
- 实现时不得把全部小仓库明细塞回主状态轮询接口
