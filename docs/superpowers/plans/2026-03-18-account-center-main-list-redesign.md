# Account Center Main List Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把账号中心改成以主列表为核心的四列账号管理界面，支持单元格直改、购买配置、表头添加账号和右键删除账号。

**Architecture:** 后端新增账号中心专用读模型和购买配置写接口，统一提供 `购买状态` 与当前仓库信息；前端把账号中心窗口改成“列表主操作区 + 轻量弹框”的交互模型，不再依赖右侧详情栏。实现时保持现有 Python 登录、查询、购买链路不变，只重构账号中心的聚合数据与 UI 编排。

**Tech Stack:** Python, FastAPI, PySide6, pytest, httpx

---

## 文件结构

- Create: `app_backend/api/routes/account_center.py`
- Create: `app_backend/api/schemas/account_center.py`
- Create: `app_backend/application/use_cases/list_account_center_accounts.py`
- Create: `app_backend/application/use_cases/update_account_purchase_config.py`
- Modify: `app_backend/main.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/repositories/account_inventory_snapshot_repository.py`
- Modify: `app_frontend/app/services/backend_client.py`
- Modify: `app_frontend/app/viewmodels/account_center_vm.py`
- Modify: `app_frontend/app/widgets/account_table.py`
- Modify: `app_frontend/app/controllers/account_center_controller.py`
- Modify: `app_frontend/app/windows/account_center_window.py`
- Create: `app_frontend/app/dialogs/remark_edit_dialog.py`
- Create: `app_frontend/app/dialogs/api_key_dialog.py`
- Create: `app_frontend/app/dialogs/purchase_config_dialog.py`
- Modify: `app_frontend/app/dialogs/login_proxy_dialog.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`
- Create: `tests/backend/test_account_center_routes.py`
- Modify: `tests/frontend/test_backend_client.py`
- Modify: `tests/frontend/test_account_center_vm.py`
- Modify: `tests/frontend/test_account_center_controller.py`
- Modify: `tests/frontend/test_account_center_window_status.py`

注：

- 按当前仓库规则，本计划不包含 git 提交、分支或 worktree 操作。
- 实现阶段按 `@superpowers/test-driven-development` 先写失败测试，再写最小实现。

## Chunk 1: 后端账号中心读模型与购买配置写接口

### Task 1: 先把后端接口测试写红

**Files:**
- Create: `tests/backend/test_account_center_routes.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`

- [ ] 为账号中心读模型新增路由测试，覆盖 `未登录 / 禁用 / 库存已满 / 当前仓库内容` 四种显示
- [ ] 为账号中心读模型新增测试，覆盖运行时优先、快照回退的 `selected_steam_id`
- [ ] 为购买配置新增路由测试，覆盖更新 `disabled` 和 `selected_steam_id`
- [ ] 为购买配置新增校验测试，覆盖“未登录不可切仓”“满仓不可选”
- [ ] 运行定向后端测试，确认因为缺少新路由和写接口而失败

Run:

```powershell
pytest "tests/backend/test_account_center_routes.py" "tests/backend/test_purchase_runtime_routes.py" -q
```

Expected:

- 新增账号中心路由测试失败
- 失败原因指向缺少 `/account-center/accounts` 或缺少购买配置写接口

### Task 2: 最小实现后端读写接口

**Files:**
- Create: `app_backend/api/routes/account_center.py`
- Create: `app_backend/api/schemas/account_center.py`
- Create: `app_backend/application/use_cases/list_account_center_accounts.py`
- Create: `app_backend/application/use_cases/update_account_purchase_config.py`
- Modify: `app_backend/main.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/infrastructure/repositories/account_inventory_snapshot_repository.py`

- [ ] 在 `purchase_runtime_service.py` 增加账号中心列表聚合方法，统一产出 `purchase_status_code / purchase_status_text / selected_steam_id`
- [ ] 在 `purchase_runtime_service.py` 增加购买配置更新方法，负责校验、写入快照和同步运行时状态
- [ ] 在 `account_inventory_snapshot_repository.py` 增加只更新 `selected_steam_id` 的辅助入口，避免前端切仓时重写无关字段
- [ ] 新增账号中心 schema、use case 和路由，并在 `main.py` 注册
- [ ] 复跑定向后端测试，确认新接口通过

Run:

```powershell
pytest "tests/backend/test_account_center_routes.py" "tests/backend/test_purchase_runtime_routes.py" -q
```

Expected:

- 账号中心读模型和购买配置写接口测试通过
- 现有购买运行时接口测试继续通过

## Chunk 2: 前端数据访问与列表行模型

### Task 3: 先把前端数据层和 view model 测试写红

**Files:**
- Modify: `tests/frontend/test_backend_client.py`
- Modify: `tests/frontend/test_account_center_vm.py`

- [ ] 为 `BackendClient` 增加账号中心列表读取测试
- [ ] 为 `BackendClient` 增加购买配置写入测试
- [ ] 为 `AccountCenterViewModel` 增加四列行模型测试
- [ ] 为 `AccountCenterViewModel` 增加 `购买状态` 优先级测试
- [ ] 运行定向前端测试，确认因为缺少 client 方法和新行模型而失败

Run:

```powershell
pytest "tests/frontend/test_backend_client.py" "tests/frontend/test_account_center_vm.py" -q
```

Expected:

- 新增测试失败
- 失败原因指向缺少 `BackendClient` 新方法或 `AccountCenterViewModel` 旧字段结构

### Task 4: 最小实现数据访问与列表行模型

**Files:**
- Modify: `app_frontend/app/services/backend_client.py`
- Modify: `app_frontend/app/viewmodels/account_center_vm.py`

- [ ] 在 `BackendClient` 增加 `list_account_center_accounts()` 和 `update_account_purchase_config()`
- [ ] 让 `AccountCenterViewModel` 改为保存账号中心专用行数据，不再输出旧的五列表结构
- [ ] 让 `AccountCenterViewModel` 提供按 `account_id` 获取行数据的能力，供单元格点击和右键菜单使用
- [ ] 复跑数据层和 view model 定向测试，确认转绿

Run:

```powershell
pytest "tests/frontend/test_backend_client.py" "tests/frontend/test_account_center_vm.py" -q
```

Expected:

- `BackendClient` 与 `AccountCenterViewModel` 新测试通过
- 旧的账号中心 view model 测试同步更新后通过

## Chunk 3: 主列表组件与账号中心窗口重构

### Task 5: 先把窗口与表格交互测试写红

**Files:**
- Modify: `tests/frontend/test_account_center_window_status.py`
- Modify: `tests/frontend/test_account_center_controller.py`

- [ ] 为窗口新增“表头右上角添加账号”测试
- [ ] 为窗口新增“点击 `C5昵称` / `API Key` / `代理` / `购买状态` 触发对应动作”测试
- [ ] 为窗口新增“右键账号行弹出删除菜单并二次确认”测试
- [ ] 为控制器新增“加载账号中心读模型而不是旧 `/accounts` 列表”的测试
- [ ] 运行窗口和控制器定向测试，确认因为旧布局和旧事件模型而失败

Run:

```powershell
pytest "tests/frontend/test_account_center_window_status.py" "tests/frontend/test_account_center_controller.py" -q
```

Expected:

- 新增窗口交互测试失败
- 失败原因指向旧布局仍依赖详情栏或控制器仍在使用旧加载路径

### Task 6: 最小实现主列表与窗口结构

**Files:**
- Modify: `app_frontend/app/widgets/account_table.py`
- Modify: `app_frontend/app/controllers/account_center_controller.py`
- Modify: `app_frontend/app/windows/account_center_window.py`

- [ ] 把 `AccountTableWidget` 改成四列表结构，并增加单元格点击与行右键菜单信号
- [ ] 在窗口中移除右侧详情栏依赖，改成“状态区 + 表头动作区 + 主表格”
- [ ] 把 `添加账号` 放到列表头部动作区，并保留刷新入口作为次级动作
- [ ] 让控制器改为加载账号中心读模型，并增加按账号 ID 执行删除和购买配置更新的入口
- [ ] 复跑窗口和控制器定向测试，确认主交互链路通过

Run:

```powershell
pytest "tests/frontend/test_account_center_window_status.py" "tests/frontend/test_account_center_controller.py" -q
```

Expected:

- 新增窗口交互测试通过
- 旧的“查看详情”相关测试删除或重写后不再失败

## Chunk 4: 轻量弹框与购买配置编排

### Task 7: 先把弹框和控制器行为测试写红

**Files:**
- Modify: `tests/frontend/test_account_center_controller.py`
- Modify: `tests/frontend/test_account_center_window_status.py`

- [ ] 为备注编辑增加“保存后只改 `remark_name`”测试
- [ ] 为 API Key 编辑增加“不强制重新登录”测试
- [ ] 为代理编辑增加“代理变化时先更新再重登，未变化不重登”测试
- [ ] 为购买配置增加“禁用购买”“切换仓库”“未登录时点击状态直接拉起登录”测试
- [ ] 运行定向测试，确认因为缺少弹框和控制器分发逻辑而失败

Run:

```powershell
pytest "tests/frontend/test_account_center_controller.py" "tests/frontend/test_account_center_window_status.py" -q
```

Expected:

- 新增弹框与购买配置测试失败
- 失败原因指向缺少新弹框或控制器编排入口

### Task 8: 最小实现轻量弹框与购买配置流

**Files:**
- Create: `app_frontend/app/dialogs/remark_edit_dialog.py`
- Create: `app_frontend/app/dialogs/api_key_dialog.py`
- Create: `app_frontend/app/dialogs/purchase_config_dialog.py`
- Modify: `app_frontend/app/dialogs/login_proxy_dialog.py`
- Modify: `app_frontend/app/controllers/account_center_controller.py`
- Modify: `app_frontend/app/windows/account_center_window.py`

- [ ] 新增备注弹框，返回 `remark_name` payload
- [ ] 新增 API Key 弹框，返回 `api_key` payload
- [ ] 复用现有代理输入逻辑，把 `LoginProxyDialog` 用作代理编辑弹框
- [ ] 新增购买配置弹框，展示当前仓库、可选仓库和 `参与购买` 开关
- [ ] 在控制器中把四列点击分发到对应更新动作，并在需要时刷新列表或拉起登录
- [ ] 复跑窗口与控制器定向测试，确认四列编辑路径通过

Run:

```powershell
pytest "tests/frontend/test_account_center_controller.py" "tests/frontend/test_account_center_window_status.py" -q
```

Expected:

- 四列点击行为测试通过
- 删除、代理重登、购买配置三条主链路通过

## Chunk 5: 集成验证

### Task 9: 跑账号中心相关回归测试

**Files:**
- Modify: `tests/frontend/test_account_center_vm.py`
- Modify: `tests/frontend/test_account_center_controller.py`
- Modify: `tests/frontend/test_account_center_window_status.py`
- Modify: `tests/frontend/test_backend_client.py`
- Create: `tests/backend/test_account_center_routes.py`
- Modify: `tests/backend/test_purchase_runtime_routes.py`

- [ ] 运行账号中心后端接口测试
- [ ] 运行账号中心前端数据层与窗口测试
- [ ] 检查是否有与登录代理流程、购买运行时库存详情相关的回归
- [ ] 汇总仍未覆盖的风险点

Run:

```powershell
pytest "tests/backend/test_account_center_routes.py" "tests/backend/test_purchase_runtime_routes.py" "tests/frontend/test_backend_client.py" "tests/frontend/test_account_center_vm.py" "tests/frontend/test_account_center_controller.py" "tests/frontend/test_account_center_window_status.py" -q
```

Expected:

- 账号中心相关测试通过
- 若有残余失败，集中在与本次重构直接相关的测试，不应出现无关模块大面积回归

### Task 10: 手工验证账号中心主交互

**Files:**
- Modify: `run_app.py`（仅在确有必要时）

- [ ] 启动桌面应用并打开账号中心
- [ ] 验证 `添加账号` 位于列表表头区域右上角
- [ ] 验证四列点击路径、右键删除确认和代理改动后重登
- [ ] 记录无法自动化覆盖的 UI 风险

Run:

```powershell
py run_app.py
```

Expected:

- 账号中心可以正常打开
- 列表主交互按设计工作
- 如果手工验证受限，明确记录阻塞点
