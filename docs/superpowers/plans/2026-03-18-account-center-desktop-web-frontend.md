# Account Center Desktop Web Frontend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个独立的 `Electron + React` 桌面化 Web 账号中心程序，自动拉起现有 Python 后端，首版覆盖账号中心首页、四列主列表、基础编辑、购买配置和登录任务状态展示。

**Architecture:** 新建一个独立 `app_desktop_web/` 前端工程，Electron 主进程负责窗口和 Python 子进程生命周期，React 渲染层通过现有 FastAPI 接口读取和写入账号数据。业务数据继续共用当前 SQLite 与 Python service，新的桌面程序只单独维护 UI 状态缓存，并通过左侧导航为后续迁移 `查询系统 / 购买系统` 预留入口。

**Tech Stack:** Electron, React, Vite, JavaScript, Vitest, Testing Library, Python, FastAPI, pytest, httpx

---

## 文件结构

- Create: `main_ui_account_center_desktop.js`
- Create: `app_desktop_web/package.json`
- Create: `app_desktop_web/vite.config.js`
- Create: `app_desktop_web/index.html`
- Create: `app_desktop_web/electron-main.js`
- Create: `app_desktop_web/electron-preload.js`
- Create: `app_desktop_web/python_backend.js`
- Create: `app_desktop_web/window_state.js`
- Create: `app_desktop_web/src/main.jsx`
- Create: `app_desktop_web/src/App.jsx`
- Create: `app_desktop_web/src/styles/app.css`
- Create: `app_desktop_web/src/desktop/bridge.js`
- Create: `app_desktop_web/src/api/http.js`
- Create: `app_desktop_web/src/api/account_center_client.js`
- Create: `app_desktop_web/src/features/shell/app_shell.jsx`
- Create: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Create: `app_desktop_web/src/features/account-center/components/overview_cards.jsx`
- Create: `app_desktop_web/src/features/account-center/components/account_table.jsx`
- Create: `app_desktop_web/src/features/account-center/components/status_strip.jsx`
- Create: `app_desktop_web/src/features/account-center/components/account_context_menu.jsx`
- Create: `app_desktop_web/src/features/account-center/dialogs/account_create_dialog.jsx`
- Create: `app_desktop_web/src/features/account-center/dialogs/account_remark_dialog.jsx`
- Create: `app_desktop_web/src/features/account-center/dialogs/account_api_key_dialog.jsx`
- Create: `app_desktop_web/src/features/account-center/dialogs/account_proxy_dialog.jsx`
- Create: `app_desktop_web/src/features/account-center/drawers/login_drawer.jsx`
- Create: `app_desktop_web/src/features/account-center/drawers/purchase_config_drawer.jsx`
- Create: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Create: `app_desktop_web/src/features/account-center/hooks/use_login_task_stream.js`
- Create: `app_desktop_web/src/features/account-center/state/ui_state_store.js`
- Create: `app_desktop_web/tests/electron/python_backend.test.js`
- Create: `app_desktop_web/tests/electron/window_state.test.js`
- Create: `app_desktop_web/tests/renderer/account_center_client.test.js`
- Create: `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- Create: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`
- Create: `app_desktop_web/tests/renderer/login_drawer.test.jsx`
- Create: `tests/backend/test_desktop_web_backend_bootstrap.py`
- Modify: `app_backend/main.py`
- Modify: `README.md`

注：

- 按当前仓库规则，本计划不包含 git 提交、分支或 worktree 操作。
- 现有 `PySide6` 程序保留；本计划只新增独立 Electron 桌面程序。
- 实现过程按 `@superpowers/test-driven-development` 先写失败测试，再写最小实现。

## Chunk 1: Python 后端自启动接线

### Task 1: 先写后端启动与跨源访问的失败测试

**Files:**
- Create: `tests/backend/test_desktop_web_backend_bootstrap.py`
- Modify: `app_backend/main.py`

- [ ] 为 `/health` 增加桌面 Web 场景测试，验证 `Origin: http://localhost:5173` 时返回允许的 CORS 头
- [ ] 为 `/health` 增加测试，验证 `Origin: null` 时也允许 Electron `file://` 页面访问
- [ ] 为后端启动参数接线写测试，锁定 `create_app()` 保持现有依赖装配，同时允许 Electron 健康检查使用
- [ ] 运行定向后端测试，确认因为缺少 CORS 中间件和桌面 Web 启动接线而失败

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_desktop_web_backend_bootstrap.py" -q
```

Expected:

- 新测试失败
- 失败原因指向缺少 CORS 响应头或后端启动接线不满足桌面 Web 访问

### Task 2: 最小实现后端启动与跨源访问

**Files:**
- Modify: `app_backend/main.py`

- [ ] 在 `app_backend/main.py` 为本地桌面 Web 前端增加允许的 CORS 配置
- [ ] 允许 `http://localhost:*`、`http://127.0.0.1:*` 和 `Origin: null` 访问当前 FastAPI
- [ ] 保持现有 `/health` 路由不变，避免破坏 `PySide6` 现有调用方式
- [ ] 复跑定向后端测试，确认桌面 Web 启动基础接线通过

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_desktop_web_backend_bootstrap.py" -q
```

Expected:

- 后端桌面 Web 启动相关测试通过
- 不影响现有 FastAPI 路由装配

## Chunk 2: Electron 壳与 Python 子进程管理

### Task 3: 先写 Electron 启动器和后端管理的失败测试

**Files:**
- Create: `app_desktop_web/tests/electron/python_backend.test.js`
- Create: `app_desktop_web/tests/electron/window_state.test.js`

- [ ] 为 Python 子进程管理器写失败测试，覆盖“选择端口、启动 Python、轮询 `/health` 成功后返回 base URL”
- [ ] 为 Python 子进程管理器写失败测试，覆盖“健康检查超时后抛出启动失败”
- [ ] 为窗口状态存储写失败测试，覆盖“读取默认尺寸”“保存并恢复窗口位置”
- [ ] 运行定向 Node 测试，确认因为缺少 Electron 壳文件和后端管理器而失败

Run:

```powershell
npm --prefix "app_desktop_web" test -- python_backend.test.js window_state.test.js
```

Expected:

- 测试失败
- 失败原因指向缺少 `python_backend.js` 或 `window_state.js`

### Task 4: 最小实现 Electron 壳、启动器和 Python 管理器

**Files:**
- Create: `main_ui_account_center_desktop.js`
- Create: `app_desktop_web/package.json`
- Create: `app_desktop_web/vite.config.js`
- Create: `app_desktop_web/electron-main.js`
- Create: `app_desktop_web/electron-preload.js`
- Create: `app_desktop_web/python_backend.js`
- Create: `app_desktop_web/window_state.js`

- [ ] 新建 `app_desktop_web/package.json`，加入 `electron`、`react`、`vite`、`vitest`、`@testing-library/react`
- [ ] 新建根级 `main_ui_account_center_desktop.js`，仿照参考项目风格，用 Node 启动 Electron 主入口
- [ ] 在 `python_backend.js` 中实现：
  - 选择空闲端口
  - 使用 `.venv/Scripts/python.exe` 启动当前项目 Python 后端
  - 轮询 `/health`
  - 向主进程返回 `baseUrl`
- [ ] 在 `window_state.js` 中实现窗口尺寸与位置缓存
- [ ] 在 `electron-main.js` 中实现：
  - 程序启动
  - Python 后端拉起
  - 创建 BrowserWindow
  - 把 `apiBaseUrl` 暴露给 preload
- [ ] 在 `electron-preload.js` 中只暴露最小桌面桥接，不把 Node 能力整个泄露给页面
- [ ] 安装 Node 依赖
- [ ] 复跑定向 Electron 单测，确认主进程辅助模块转绿

Run:

```powershell
npm --prefix "app_desktop_web" install
npm --prefix "app_desktop_web" test -- python_backend.test.js window_state.test.js
```

Expected:

- Electron 启动辅助模块测试通过
- 依赖安装成功，生成 `app_desktop_web/node_modules`

## Chunk 3: React Shell 与只读账号中心首页

### Task 5: 先写首页只读态失败测试

**Files:**
- Create: `app_desktop_web/tests/renderer/account_center_client.test.js`
- Create: `app_desktop_web/tests/renderer/account_center_page.test.jsx`

- [ ] 为 HTTP 客户端写失败测试，覆盖读取 `window.desktopApp.getBootstrapConfig()` 并请求 `/account-center/accounts`
- [ ] 为首页写失败测试，覆盖左侧导航显示 `账号中心 / 查询系统 / 购买系统`
- [ ] 为首页写失败测试，覆盖四张概览卡片：总账号、未登录、无 API Key、可购买
- [ ] 为首页写失败测试，覆盖四列主列表：`C5昵称 / API Key / 购买状态 / 代理`
- [ ] 为首页写失败测试，覆盖下方状态带的三个区域占位：最近登录任务、最近错误、最近修改
- [ ] 运行定向前端测试，确认因为缺少 React Shell 和页面组件而失败

Run:

```powershell
npm --prefix "app_desktop_web" test -- account_center_client.test.js account_center_page.test.jsx
```

Expected:

- 测试失败
- 失败原因指向缺少 `src/main.jsx`、`App.jsx` 或账号中心首页组件

### Task 6: 最小实现 React Shell 和只读首页

**Files:**
- Create: `app_desktop_web/index.html`
- Create: `app_desktop_web/src/main.jsx`
- Create: `app_desktop_web/src/App.jsx`
- Create: `app_desktop_web/src/styles/app.css`
- Create: `app_desktop_web/src/desktop/bridge.js`
- Create: `app_desktop_web/src/api/http.js`
- Create: `app_desktop_web/src/api/account_center_client.js`
- Create: `app_desktop_web/src/features/shell/app_shell.jsx`
- Create: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Create: `app_desktop_web/src/features/account-center/components/overview_cards.jsx`
- Create: `app_desktop_web/src/features/account-center/components/account_table.jsx`
- Create: `app_desktop_web/src/features/account-center/components/status_strip.jsx`
- Create: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- Create: `app_desktop_web/src/features/account-center/state/ui_state_store.js`

- [ ] 用 Vite 初始化 React 渲染入口
- [ ] 在 `bridge.js` 中读取 preload 提供的 `apiBaseUrl`
- [ ] 在 `account_center_client.js` 中实现首页所需的只读接口：
  - `listAccountCenterAccounts`
  - `getPurchaseRuntimeInventoryDetail`
  - `getTask`
- [ ] 在 `AppShell` 中实现左侧导航与桌面控制台骨架
- [ ] 在 `AccountCenterPage` 中实现：
  - 紧凑页头
  - 四张概览卡片
  - 搜索框
  - 四列主列表
  - 列表下方状态带占位
- [ ] 概览卡片点击后过滤当前列表
- [ ] 复跑只读态前端测试，确认首页骨架转绿

Run:

```powershell
npm --prefix "app_desktop_web" test -- account_center_client.test.js account_center_page.test.jsx
```

Expected:

- 首页和客户端只读态测试通过
- 页面已经能在 Electron 中加载真实账号中心列表

## Chunk 4: 基础编辑弹窗与购买配置抽屉

### Task 7: 先写编辑与配置的失败测试

**Files:**
- Create: `app_desktop_web/tests/renderer/account_center_editing.test.jsx`

- [ ] 为“添加账号”写失败测试，覆盖弹窗提交后刷新列表
- [ ] 为“修改备注”写失败测试，覆盖点击昵称打开小弹窗并调用 `PATCH /accounts/{id}`
- [ ] 为“修改 API Key”写失败测试，覆盖点击 API Key 打开小弹窗并且不触发登录
- [ ] 为“修改代理”写失败测试，覆盖代理变化时保存成功后把登录抽屉拉起
- [ ] 为“购买状态”写失败测试，覆盖：
  - 未登录时打开登录抽屉
  - 其他状态打开购买配置抽屉
- [ ] 为右键删除写失败测试，覆盖二次确认后调用删除接口
- [ ] 运行定向前端测试，确认因为缺少弹窗、抽屉和写接口编排而失败

Run:

```powershell
npm --prefix "app_desktop_web" test -- account_center_editing.test.jsx
```

Expected:

- 编辑与配置测试失败
- 失败原因指向缺少弹窗/抽屉组件或缺少写接口编排

### Task 8: 最小实现基础编辑与购买配置

**Files:**
- Create: `app_desktop_web/src/features/account-center/components/account_context_menu.jsx`
- Create: `app_desktop_web/src/features/account-center/dialogs/account_create_dialog.jsx`
- Create: `app_desktop_web/src/features/account-center/dialogs/account_remark_dialog.jsx`
- Create: `app_desktop_web/src/features/account-center/dialogs/account_api_key_dialog.jsx`
- Create: `app_desktop_web/src/features/account-center/dialogs/account_proxy_dialog.jsx`
- Create: `app_desktop_web/src/features/account-center/drawers/purchase_config_drawer.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Modify: `app_desktop_web/src/features/account-center/components/account_table.jsx`
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`

- [ ] 在客户端补齐写接口：
  - `createAccount`
  - `updateAccount`
  - `updateAccountPurchaseConfig`
  - `deleteAccount`
- [ ] 实现添加账号弹窗
- [ ] 实现备注、API Key、代理编辑弹窗
- [ ] 实现购买配置抽屉：
  - 读取库存详情
  - 展示当前仓库
  - 禁用满仓仓库
  - 保存 `disabled` 与 `selected_steam_id`
- [ ] 在列表组件中增加右键菜单和删除确认
- [ ] 列表上的昵称/API Key/代理/购买状态点击全部接到对应编辑动作
- [ ] 状态带记录最近修改与最近错误
- [ ] 复跑编辑与配置测试，确认这一层转绿

Run:

```powershell
npm --prefix "app_desktop_web" test -- account_center_editing.test.jsx
```

Expected:

- 基础编辑与购买配置相关测试通过
- 购买状态和右键删除可用

## Chunk 5: 登录抽屉与任务状态展示

### Task 9: 先写登录流程失败测试

**Files:**
- Create: `app_desktop_web/tests/renderer/login_drawer.test.jsx`

- [ ] 为登录抽屉写失败测试，覆盖点击“未登录”或代理变化后打开抽屉
- [ ] 为登录抽屉写失败测试，覆盖点击“发起登录”后调用 `POST /accounts/{id}/login`
- [ ] 为任务状态写失败测试，覆盖优先走 WebSocket，失败后回退轮询
- [ ] 为状态带写失败测试，覆盖最近登录任务会随着任务状态更新
- [ ] 运行定向前端测试，确认因为缺少任务流 hook 和登录抽屉而失败

Run:

```powershell
npm --prefix "app_desktop_web" test -- login_drawer.test.jsx
```

Expected:

- 登录流程测试失败
- 失败原因指向缺少登录抽屉、任务轮询或状态带绑定

### Task 10: 最小实现登录抽屉与任务流

**Files:**
- Create: `app_desktop_web/src/features/account-center/drawers/login_drawer.jsx`
- Create: `app_desktop_web/src/features/account-center/hooks/use_login_task_stream.js`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/features/account-center/account_center_page.jsx`
- Modify: `app_desktop_web/src/features/account-center/components/status_strip.jsx`
- Modify: `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`

- [ ] 在客户端补齐登录相关能力：
  - `startLogin`
  - `watchTask`（优先 WebSocket，失败回退轮询）
- [ ] 实现登录抽屉，展示当前账号、代理信息、任务状态时间线
- [ ] 在状态带中实时展示最近登录任务
- [ ] 当登录任务结束时刷新账号列表
- [ ] 第一版明确不实现冲突处理，只在任务流中展示“冲突处理暂未迁移”
- [ ] 复跑登录相关测试，确认发起登录和状态展示转绿

Run:

```powershell
npm --prefix "app_desktop_web" test -- login_drawer.test.jsx
```

Expected:

- 登录抽屉和任务状态展示测试通过
- 冲突态不会中断程序，但不会在第一版里进入处理分支

## Chunk 6: 集成验证与文档

### Task 11: 跑跨栈回归测试

**Files:**
- Modify: `README.md`

- [ ] 运行后端桌面 Web 启动相关 pytest
- [ ] 运行 Electron/React 前端全部 Vitest
- [ ] 运行构建命令，确认 Vite 构建与 Electron 打包入口无语法错误
- [ ] 在 `README.md` 增加新桌面 Web 账号中心的启动说明

Run:

```powershell
& ".venv/Scripts/python.exe" -m pytest "tests/backend/test_desktop_web_backend_bootstrap.py" -q
npm --prefix "app_desktop_web" test
npm --prefix "app_desktop_web" run build
```

Expected:

- Python 与前端测试通过
- 构建成功
- README 包含新程序运行方式

### Task 12: 手工启动新桌面程序做验收

**Files:**
- Create: `main_ui_account_center_desktop.js`

- [ ] 用根级启动器启动新 Electron 程序
- [ ] 验证 Electron 会自动拉起 Python 后端
- [ ] 验证左侧导航、首页概览卡、四列列表都能正常显示
- [ ] 验证备注/API Key/代理/购买配置/登录任务状态展示
- [ ] 记录仍未实现的已知限制：登录冲突处理尚未迁移

Run:

```powershell
node "main_ui_account_center_desktop.js"
```

Expected:

- 新账号中心桌面 Web 程序可独立打开
- 无需手动启动 Python 后端
- 第一版目标范围内功能可实际操作

## 风险与补充说明

- Electron 渲染层如果直接用 `file://` 访问本地接口，必须保证后端 CORS 正确配置，否则列表会空白。
- 现有 Python 后端是新前端和旧 PySide 前端的共同真相来源，任何前端状态都不能自己推导业务真相。
- 第一版严格不做登录冲突处理，否则实现范围会明显膨胀。
- 若后续要迁移 `查询系统 / 购买系统`，优先复用当前 `Shell`、HTTP 客户端和 Electron 主进程，而不是再起一套新壳。
