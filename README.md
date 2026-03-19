# C5 桌面扫货系统

## 项目概况

这是当前仍在维护的 C5 桌面扫货项目。运行主线已经收口到新的前后端分层架构：

- 前端：`app_frontend/`
- 后端：`app_backend/`
- 默认启动入口：`run_app.py`

旧版 `autobuy.py` 已退出当前运行链路，后续维护不要再按单文件脚本思路理解项目。现在的 GUI 只负责输入、展示和调用后端接口，实际业务状态和运行时逻辑都在后端。

仓库中目前保留 `autobuy.py` 作为后续开发参考，但 `c5_layered/` 这套历史 UI/兼容层已经删除；默认启动与日常功能维护仍以 `app_frontend/` + `app_backend/` 为准。

## 快速开始

### 环境要求

- Python 3.11+

### 安装依赖

```bash
pip install -e .[dev]
```

### 启动整个程序

```bash
python run_app.py
```

启动后会：

1. 创建 Qt 应用
2. 在本地线程中拉起 FastAPI 后端
3. 打开工作区主窗口
4. 默认使用 SQLite 数据库 `data/app.db`

### 仅启动后端

```bash
python -m app_backend.main
```

这个入口主要用于接口调试或单独联调，日常使用还是以 `python run_app.py` 为准。

### 启动桌面化 Web 账号中心

```bash
node main_ui_account_center_desktop.js
```

这个入口会：

1. 使用 `app_desktop_web/` 下的 Electron 桌面壳启动独立账号中心
2. 自动拉起本地 Python/FastAPI 后端
3. 继续共用默认 SQLite 数据库 `data/app.db`
4. 加载新的桌面化 Web 账号中心界面

补充说明：

- 首次启动前需要先安装前端依赖：`npm --prefix app_desktop_web install`
- 如果 `app_desktop_web/dist/index.html` 不存在，启动器会先自动执行一次构建
- 如果改了 `app_desktop_web/src/` 里的前端代码，重新启动前建议先执行 `npm --prefix app_desktop_web run build`

## 入口与调用链

- `run_app.py`
  - 对外总入口
  - 只负责转到 `app_frontend.main.main()`
- `app_frontend/main.py`
  - 启动 Qt
  - 启动本地后端服务
  - 创建工作区主窗口
- `app_frontend/app/services/local_backend_server.py`
  - 在线程内启动本地 Uvicorn 服务
- `app_backend/main.py`
  - 组装 FastAPI 应用、仓储、运行时服务和任务管理器

## 目录说明

- `app_frontend/`
  - 桌面 GUI、窗口、ViewModel、前端服务
- `app_backend/`
  - API、用例、领域模型、仓储、查询运行时、购买运行时、Selenium 登录链路
- `app_desktop_web/`
  - Electron + React 桌面化 Web 前端
  - 负责新的账号中心界面和后续模块迁移骨架
- `tests/`
  - 当前行为的自动化测试，改动前后都应优先看这里
- `data/`
  - 默认数据库目录
- `docs/superpowers/`
  - 迁移过程中的 spec / plan / 记录
  - 这些文档很多仍会提到 `autobuy.py`、legacy、过渡层，属于历史材料，不代表当前运行依赖
- `REFACTOR_EXECUTION_PLAN.md`
  - 重构过程文档，适合了解迁移背景，不应替代源码和测试

仓库根目录里还保留了一些调试文件、历史目录和临时产物。接手时优先看上面这些主目录，不要被无关文件带偏。

## 当前必须保持的业务语义

下面这些约束是当前系统的有效语义，后续改动不要擅自改掉：

- 登录流程保留旧逻辑：用户扫码，浏览器抓取登录信息，用户手动关闭浏览器后登录任务结束
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

- 先从 `run_app.py`、`app_frontend/main.py`、`app_backend/main.py` 看启动链路
- 业务变更优先看 `tests/` 里是否已有对应约束
- 如果历史文档与当前代码冲突，以当前源码和测试为准
- 如果改动涉及登录、查询调度、购买分配、库存刷新，必须严格对照既有语义，不能凭印象改参数或流程
