# C5 桌面扫货系统

## 项目概况

这是当前仍在维护的 C5 桌面扫货项目。运行主线已经收口到新的前后端分层架构：

- 前端：`app_desktop_web/`
- 后端：`app_backend/`
- 桌面启动入口：`main_ui_account_center_desktop.js`

旧版 `autobuy.py` 已退出当前运行链路，后续维护不要再按单文件脚本思路理解项目。当前 UI 只负责输入、展示和调用后端接口，实际业务状态和运行时逻辑都在后端。

仓库中目前保留 `autobuy.py` 作为后续开发参考；`c5_layered/` 与旧 `PySide6` 的 `app_frontend/` 都已移除。当前默认运行与日常功能维护以 `app_desktop_web/` + `app_backend/` 为准。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js

### 安装依赖

```bash
pip install -e .[dev]
npm --prefix app_desktop_web install
```

### 启动整个程序

```bash
node main_ui_account_center_desktop.js
```

启动后会：

1. 启动 Electron 桌面壳
2. 自动拉起本地 Python/FastAPI 后端
3. 加载新的桌面化 Web 前端
4. 默认使用 SQLite 数据库 `data/app.db`

登录补充说明：

- 通过桌面入口 `node main_ui_account_center_desktop.js` 启动时，Python backend 会收到 `C5_APP_PRIVATE_DIR`，默认落到仓库根目录 `.runtime/app-private`
- 如果单独执行 `python -m app_backend.main` 且未显式设置 `C5_APP_PRIVATE_DIR`，fallback 才会落到 `data/app-private`
- Python backend 会把账号相关运行时数据落到 `app-private/`，包括账号独立 profile、临时 browser session 和 session bundle
- 登录成功不再只看扫码跳转，后端会强制 refresh `https://www.c5game.com/user/user/` 做二次验真
- 登录成功后会为账号写入加密 session bundle；当前仍保留 `cookie_raw` 字段，旧账号与旧运行链可继续兼容
- 直连账号会优先复用账号独立 profile，并在需要时附着真实 Microsoft Edge 会话；自定义代理账号继续走隔离临时浏览器链

### Python 包装入口

```bash
python run_app.py
```

这个入口现在只是一个轻量包装：内部会调用 `node main_ui_account_center_desktop.js`。适合保留旧使用习惯，但仍然要求本机已安装 Node.js。

### 仅启动后端

```bash
python -m app_backend.main
```

这个入口主要用于接口调试或单独联调，日常使用还是以 `python run_app.py` 为准。

补充说明：

- 如果 `app_desktop_web/dist/index.html` 不存在，启动器会先自动执行一次构建
- 如果改了 `app_desktop_web/src/` 里的前端代码，重新启动前建议先执行 `npm --prefix app_desktop_web run build`

### 初始化受管 browser-runtime

如果你想让项目优先使用自己的浏览器 runtime，而不是每次去找系统 Edge，可以先把本机现有 Edge 安装导入到 `browser-runtime`：

```powershell
.\.venv\Scripts\python.exe -m app_backend.debug.init_managed_browser_runtime `
  --source-path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --app-private-dir ".runtime\app-private" `
  --force
```

补充说明：

- `--source-path` 可以传 `msedge.exe`，也可以传包含它的 `Application` 目录
- 导入完成后会在 `app-private/browser-runtime/.managed-runtime.json` 写入 manifest
- 登录启动器查找浏览器的优先级现在是：`C5_EDGE_RUNTIME_EXECUTABLE` → `app-private/browser-runtime/` → 系统 Edge
- 这样后续封装程序时，可以直接把 `browser-runtime/` 一起带走，减少对用户本机环境的依赖

如果你不想依赖本机已有 Edge 安装，也可以直接让程序从 Microsoft Edge Enterprise releases API 下载最新 Windows runtime：

```powershell
.\.venv\Scripts\python.exe -m app_backend.debug.init_managed_browser_runtime `
  --download-latest `
  --channel Stable `
  --app-private-dir ".runtime\app-private" `
  --force
```

补充说明：

- 下载源使用官方 `https://edgeupdates.microsoft.com/api/products?view=enterprise`
- 当前默认按本机架构选择 `x64` 或 `arm64`
- 下载后会做 SHA256 校验，再解包导入到 `browser-runtime`
- 如果设置环境变量 `C5_EDGE_AUTO_DOWNLOAD=1`，在程序找不到本地 runtime 且也找不到系统 Edge 时，会自动触发这条下载链

### 当前浏览器环境说明

当前项目已经移除旧的浏览器环境调试链。

现在保留的只有：

- `browser-runtime`
- 账号独立 `browser-profiles`
- 运行时克隆出来的临时 `browser-sessions`

登录与 API 信息同步均直接走：

- 真 Edge 进程启动
- 账号 Profile 复用
- CDP 读取登录态 / Cookie / API 页面状态

## 入口与调用链

- `run_app.py`
  - Python 包装入口
  - 只负责调用 `node main_ui_account_center_desktop.js`
- `main_ui_account_center_desktop.js`
  - 桌面对外总入口
  - 校验 Electron 运行时与前端构建产物
  - 启动 `app_desktop_web/` 桌面壳
- `app_backend/main.py`
  - 组装 FastAPI 应用、仓储、运行时服务和任务管理器

## 目录说明

- `app_backend/`
  - API、用例、领域模型、仓储、查询运行时、购买运行时、浏览器登录与 CDP 会话链路
- `app_desktop_web/`
  - Electron + React 桌面化 Web 前端
  - 负责新的账号中心界面和后续模块迁移骨架
- `tests/`
  - 当前行为的自动化测试，改动前后都应优先看这里
- `data/`
  - 默认数据库目录
- `docs/superpowers/`
  - 迁移过程中的 spec / plan / 记录
  - 登录、查询、购买与 legacy `autobuy.py` 的语义对账参考也放在这里
  - 这些文档很多仍会提到 `autobuy.py`、legacy、过渡层，属于历史材料，不代表当前运行依赖
- `REFACTOR_EXECUTION_PLAN.md`
  - 重构过程文档，适合了解迁移背景，不应替代源码和测试

仓库根目录里还保留了一些调试文件、历史目录和临时产物。接手时优先看上面这些主目录，不要被无关文件带偏。

## Agent 协作记录（持续维护）

### 2026-04-14 会话进度纪要

- 已完成：在项目 `AGENTS.md` 增加 agent 模型限定（仅 `gpt-5.2` / `gpt-5.3-codex` / `gpt-5.4`，禁用 `gpt-5.1*`）。
- 已完成：将“子 agent 仅 5.2~5.4（禁用 5.1）”标记为特殊硬约束，优先级高于一般调度偏好。
- 已完成：在项目 `AGENTS.md` 增加两条可选流程模块（可独立启用，不要求同时具备）：
  - `README` 同步维护模块。
  - 压缩前会话纪要模块。
- 已完成：新增“会话日志 + 记忆文件”可选模块，并落地文件：
  - `docs/agent/session-log.md`
  - `docs/agent/memory.md`
- 已完成：将“会话日志 + 记忆文件”升级为持续开启机制（默认强制），并增加防遗漏检查（改动后写日志、稳定约束写记忆）。
- 已完成：上述规则已同步到全局 `~/.codex/AGENTS.md`。
- 已完成：检索并筛选 GitHub 可参考的现成 agent 规范样例（用于后续对照迭代）。

## 当前必须保持的业务语义

注意：

- 下面列的是当前实现需要维持的行为约束
- 它们不等同于 legacy `autobuy.py` 的全部历史语义
- 如需排查两者之间的漂移与回归风险，先看 `docs/superpowers/references/2026-03-19-autobuy-backend-semantic-drift-reference.md`

下面这些约束是当前系统的有效语义，后续改动不要擅自改掉：

- 登录流程区分两条主链：直连账号复用账号独立 profile，并在需要时附着真实 Edge 会话；自定义代理账号使用隔离临时浏览器链
- 登录任务成功标准包含 refresh 验真；只有 refresh 后仍在线、且关键 cookie 仍存在时，任务才算真正成功
- 登录成功后除了回写 `cookie_raw`，还会为账号保存独立 session bundle；重新登录只覆盖当前账号自己的 bundle，不应污染其他账号
- 查询和购买必须联动，不能只开查询不跑购买
- 事件是全局共享的，不挂到账户上
- `new_api`、`fast_api`、`token` 是三套独立调度器
- 每种查询模式只处理自己的查询组，并且各自有全局生效的时间窗口
- 所有账号都可以参与查询，但是否允许参与某种查询模式，由账号中心里的模式开关决定
- 备注名优先显示，但账号详情页仍要能看到完整账户信息
- 覆盖已有账号时，按“删除旧账号并新增账号”的语义处理，不做就地覆盖
- 账户的 token/cookie 更新走登录任务链路：重新扫码成功后回写到账户；当前没有单独的手工更新 token 入口
- 如果没有任何可用购买账号，查询要直接停机并清空积压任务；购买账号恢复可用后，查询再重新启动

## 测试与验证

全量回归命令：

```bash
python -m pytest -q
```

提交任何影响运行时语义的改动前，至少应跑相关模块测试；准备收口时跑一次全量测试。

## 接手建议

- 先从 `run_app.py`、`main_ui_account_center_desktop.js`、`app_backend/main.py` 看启动链路
- 业务变更优先看 `tests/` 里是否已有对应约束
- 如果历史文档与当前代码冲突，以当前源码和测试为准
- 如果要排查旧 `autobuy.py` 与新 backend 的实现差异，先看 `docs/superpowers/references/2026-03-19-autobuy-backend-semantic-drift-reference.md`
- 如果改动涉及登录、查询调度、购买分配、库存刷新，必须严格对照既有语义，不能凭印象改参数或流程
