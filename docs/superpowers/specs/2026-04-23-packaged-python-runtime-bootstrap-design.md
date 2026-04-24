# Packaged Python Runtime Bootstrap Design

**Goal:** 降低 `C5 交易助手` Windows 发行包体积：发行包不再内置完整 `.venv`，改为首次启动时从 Python 官方下载固定版本 Windows embeddable runtime，并在下载成功后再启动本地 Python backend。

**Scope:** 只修改 packaged release 的 Python runtime 获取与启动链路、打包资源清单、相关自动化验证；保留开发态 `.venv` 启动方式，不改前端页面设计、不改本地 backend 业务能力、不改程序会员控制面协议。

## 背景与根因

- 当前 `app_desktop_web/electron-builder.config.cjs` 把仓库根目录 `.venv` 整包打入 `resources/.venv`。
- 当前 `.venv` 实测约 `727.69MB`，其中当前运行代码已不再引用的 `PySide6 + shiboken6` 约 `623.35MB`。
- 当前打包后的 `win-unpacked` 约 `1.02GB`，其中 `resources` 约 `727.50MB`；真实前端与 Electron app 代码壳 `app.asar` 仅约 `21.07MB`。
- 因此包体膨胀主要来自“开发环境整包发行”，不是前端设计代码本身。

## 已确认产品决策

- 接受首次启动联网下载 Python runtime。
- 下载源首刀使用 Python 官方 Windows embeddable package。
- 首次启动网络不可用、下载失败、校验失败或解压失败时，阻止进入主程序，并显示错误与重试入口。
- 不采用“要求用户自行安装 Python”方案。
- 不采用“继续内置最小 `.venv`”作为首刀方案。

## 不可改变项

- 不改 `查询 -> 命中 -> 购买` 主链。
- 不改登录成功链路、白名单 / open-api 打开与复用链路。
- 不改程序账号登录、注册、找回密码协议。
- 不改 `main_ui_node_desktop.js` 作为正式桌面入口的地位。
- 不破坏开发态：源码运行继续允许使用仓库或上级目录中的 `.venv/Scripts/python.exe`。
- 不把辅助下载动作反向绑死已经可用的已安装 runtime：若本机已有完整且校验通过的托管 runtime，应直接复用，不重新下载。

## 方案

### 1. 发行包不再内置 `.venv`

- `electron-builder` 的 `extraResources` 移除 `.venv` 整包资源。
- 发行包仍保留：
  - 前端构建产物 `dist/**/*`；
  - Electron 主进程与 preload；
  - `app_backend/` 源码；
  - `xsign.py`；
  - release client config。
- 打包测试新增断言：builder config 不再包含 `.venv` 资源项，避免后续回归。

### 2. packaged release 使用托管 Python runtime

- 新增 runtime resolver / bootstrap 层，专门负责 packaged release 下的 Python runtime：
  - 运行目录放在应用私有数据目录下，例如 `<userData>/python-runtime/<version>/`；
  - 以 manifest 标记已安装版本、下载来源、SHA256、安装完成时间；
  - 解析成功后返回 `python.exe` 绝对路径给现有 backend 启动链。
- 开发态仍保留当前 `.venv` 解析逻辑，不要求开发者走下载链。
- packaged release 不再默认查找发行包 `resources/.venv/Scripts/python.exe`。

### 3. 首启下载固定官方版本

- 固定 Python 版本与 embeddable zip URL，不使用 `latest`。
- 下载完成后必须校验 SHA256；校验失败删除临时文件并阻断启动。
- 解压采用临时目录 staging，全部完成后再原子切换为正式 runtime 目录，避免半安装目录被误判为可用。
- 写入 manifest 前必须确认 `python.exe` 存在。
- 若 manifest 与实际文件不一致，视为损坏，重新下载或提示重试。

### 4. 下载失败阻断进入主程序

- packaged release 启动顺序：
  1. 显示 loading / bootstrap 状态。
  2. 检查托管 Python runtime。
  3. runtime 不存在或损坏时下载、校验、解压。
  4. 成功后启动 Python backend。
  5. backend health check 通过后进入主窗口。
- 任一 bootstrap 步骤失败：
  - 不进入主程序；
  - 展示明确错误：网络失败、校验失败、解压失败、backend 启动失败；
  - 提供重试入口。
- 失败状态不修改业务数据，不删除现有可用 runtime。

### 5. Python 依赖安装边界

- Python embeddable runtime 只提供解释器，不等同于当前 `.venv` 的 site-packages。
- 首刀实现需要同时解决后端依赖来源，推荐采用随 app 打包一个最小 wheels / vendor 依赖包，或在 runtime bootstrap 完成后用固定 requirements 从官方 PyPI 拉取依赖。
- 为了避免把“下载 Python”做成新的不稳定链路，本设计首选：
  - 发行包不带完整 `.venv`；
  - 发行包可带最小 `python_deps` 资源目录，仅包含当前 `pyproject.toml` runtime dependencies 需要的 wheels 或已解包 vendor；
  - 不包含 `PySide6`、pytest、pip/setuptools 的开发残留。
- 具体依赖投递方式在 implementation plan 中按现有启动代码和测试成本细化；不允许回到“整包复制开发 `.venv`”。

## 数据流

```text
Electron packaged main
  -> resolve packaged app data paths
  -> ensure managed Python runtime
      -> read manifest
      -> if missing/corrupt: download official embeddable zip
      -> verify SHA256
      -> extract staging
      -> install runtime manifest
  -> resolve python.exe
  -> start Python backend with existing dbPath / C5_APP_PRIVATE_DIR / program access env
  -> wait /health
  -> show main window
```

## 错误处理

- 网络失败：显示“运行环境下载失败，请检查网络后重试”。
- SHA256 不匹配：显示“运行环境校验失败，请联系作者”，并删除本次下载文件。
- 解压失败：显示“运行环境安装失败，请联系作者”，并删除 staging。
- runtime manifest 缺失但文件存在：重新校验，不直接信任目录。
- backend health timeout：沿用现有 backend 启动错误链路，但错误归类为“后端启动失败”，不是下载失败。

## 安全与可复现

- 固定官方 URL 与 SHA256。
- 不执行下载包中的任意脚本；只解压官方 embeddable zip 并运行 `python.exe`。
- 下载文件先落临时目录，校验通过后才解压。
- manifest 写入必须在所有文件完成后执行。
- 不使用“最新版本”自动漂移，避免同一安装包在不同日期下载到不同 runtime。

## 验证

- Electron unit tests：
  - builder config 不再包含 `.venv` extraResources。
  - packaged release 缺 runtime 时会调用 bootstrap，并在成功后把托管 `python.exe` 传给 backend 启动。
  - bootstrap 失败时不调用 backend 启动，并返回可展示的阻断错误。
  - 开发态仍按 `.venv/Scripts/python.exe` 解析。
- Bootstrap unit tests：
  - manifest + `python.exe` 完整时直接复用，不下载。
  - 缺失 runtime 时下载、校验、解压、写 manifest。
  - SHA256 不匹配时失败并清理临时文件。
  - 解压失败时失败并清理 staging。
- Packaging verification：
  - `npm --prefix app_desktop_web run pack:win` 成功。
  - 新 `win-unpacked` 不包含 `resources/.venv`。
  - 记录 `win-unpacked` 与 installer 新体积。
- Manual smoke：
  - 清空托管 Python runtime 后启动 packaged app，观察 loading -> 下载 -> backend ready -> 主窗口。
  - 断网启动 packaged app，确认阻断错误与重试入口。

## 回退策略

- 若首启下载方案在验证中阻塞，可以临时恢复 `.venv` extraResources 回到旧发行方式。
- 回退不应改动业务代码；只回退 packaged runtime resolver 与 builder config。
- 若已安装用户本地存在托管 runtime，回退不应删除用户数据目录中的 runtime 或业务数据。
