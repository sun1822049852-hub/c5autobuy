# Program Access Registration V3 Rollout Design

## 背景

截至 `2026-04-23`，本地仓库里的注册 v3 实现已经落地并通过自动化验证，但真人从 `main_ui_node_desktop.js` 打开的正式桌面入口仍回落到旧注册页：

- 注册弹窗仍同屏显示“注册验证码 / 注册用户名 / 注册密码”；
- 首次发码直接报“注册验证码发送失败，请稍后再试”；
- 本地 backend 与远端控制面联调时，`/api/auth/register/readiness` 仍返回 `404 route not found`。

这说明问题不在 renderer 源码，而在远端控制面 `http://8.138.39.139:18787` 仍运行旧版镜像，尚未部署注册 v3 路由。

## 不可改变项

- 不修改登录成功链路。
- 不修改找回密码入口与整体能力边界。
- 不修改 `查询 -> 命中 -> 购买` 主链与任何性能路径。
- 不修改桌面端 release 配置地址；仍保持 `app_desktop_web/build/client_config.release.json -> http://8.138.39.139:18787`。
- 不把前端强行切到 v3；只有远端 readiness 真正就绪后，桌面端才允许显示三步注册 UI。

## 目标

只完成注册 v3 的远端 rollout，使正式桌面入口在不改现有启动方式的前提下满足以下结果：

1. 远端控制面提供：
   - `GET /api/auth/register/readiness`
   - `POST /api/auth/register/send-code`
   - `POST /api/auth/register/verify-code`
   - `POST /api/auth/register/complete`
2. 远端 readiness 不再 `404`，并能返回 `registration_flow_version=3`。
3. 正式桌面 backend 的 `/app/bootstrap` 在 release 语义下切到 `registration_flow_version=3`。
4. 注册弹窗首屏只显示“注册邮箱”，验证码通过前不得出现“注册用户名 / 注册密码”。

## 方案

### 1. 先确认现网根因

- 继续以“远端 readiness / send-code 是否 404”为单一判据。
- 若 readiness 仍是 `404`，则视为远端镜像未升级，不再怀疑前端状态机。

### 2. 最小部署单元只取 `program_admin_console`

- 本次 rollout 仅重新部署 `program_admin_console`。
- 不连带发布 `app_backend`、`app_desktop_web`、Electron 安装包或其它模块。
- 发布包只包含控制面运行所需文件：`src/`、`ui/`、`tools/`、`package*.json`、`Dockerfile`、`.dockerignore`、`README.md`。

### 3. 采用“先备份、后构建、再切换”的远端容器更新

- 在远端保留旧源码目录备份与旧镜像 tag，形成可回退点。
- 先在远端完成新镜像构建。
- 镜像构建成功后再短暂停机替换 `c5-program-admin` 容器。
- 保留既有：
  - 端口映射 `18787 -> 8787`
  - `c5_program_admin_data` volume
  - `/home/admin/c5-program-admin-runtime/keys:/app/keys:ro`
  - 现有 SMTP env file 与签名 key 配置

### 4. 用三段证据验证 rollout

1. 远端 HTTP：
   - `GET /api/auth/register/readiness` 不再 404
   - `POST /api/auth/register/send-code` 不再 404
2. 本地桌面 backend：
   - `GET http://127.0.0.1:<main_port>/app/bootstrap` 返回 `registration_flow_version=3`
3. 真人 UI：
   - 注册首屏仅邮箱
   - 验码前无账号名/密码字段

## 风险与边界

- 这次修改命中“程序账号注册/登录控制面”关键行为，因此必须保留回退点并做远端 + 本地双验证后才能宣称上线。
- 若远端容器更新成功但 readiness 仍不为 `3`，优先检查运行时 SMTP / key / env 注入，而不是重新改前端。
- 若本地 `main_ui_node_desktop.js` 指向的不是 `8.138.39.139:18787`，则桌面验证结论无效，必须先核对 release 配置。
