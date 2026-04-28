# program_admin_console

`program_admin_console` 提供控制面 API 与后台页面（`/admin`），用于管理员初始化、用户权限管理和会话管控。

## 当前现网口径（2026-04-26）

当前远端开发机 `8.138.39.139` 上的控制台默认仍保持“不直接对公网开放”的姿势。现网访问方式固定为：

- 宿主机端口绑定：`127.0.0.1:18787 -> 容器 8787`
- 外部访问路径：`本机 SSH 隧道 -> 服务器 127.0.0.1:18787 -> /admin`
- 当前推荐后台入口：`http://127.0.0.1:18787/admin`（在 SSH 隧道建立后访问）

这意味着：

- `http://8.138.39.139:18787/admin` 不应作为日常访问入口
- 下文保留的公网 IP / `0.0.0.0` 示例主要用于历史 rollout 或一般性部署说明，不代表当前现网推荐姿势
- 后续若要让桌面端程序会员链路直连远端 API，必须先单独提供新的公网 API 入口（域名 / 反向代理 / 新配置迁移），不能再靠“临时重新开放 `18787` 公网监听”硬顶

## 给不懂代码的说明

如果你主要让 AI 维护，不自己碰代码或服务器，只需要记住这几件事：

- 这个后台真正跑在远端服务器容器里，本地改完代码不等于远端已经生效。
- AI 每次改 `program_admin_console`，都应该同时做三件事：同步远端源码、重建远端 `c5-program-admin` 容器、跑 smoke 验证。
- 如果 AI 只说“本地代码改好了”，但没有给出远端 `health`、`public-key`、`/admin` 或静态资源的验证结果，就不算真正完成。
- 你不需要自己 SSH 上服务器；默认由 AI 完成。
- 你真正需要关心的是“远端现在是否健康、程序会员注册/登录是否正常”，不是代码文件名。

## 远端部署脚本

当前仓库已提供一个给 AI 复用的远端部署入口：

- `program_admin_console/tools/deployProgramAdminRemote.ps1`

它的职责是把“同步源码 -> 基于远端源码重建镜像 -> 按现网容器口径替换 -> 跑基础 smoke”这套动作固定下来，减少以后手工敲命令时漏挂密钥、漏配环境变量或忘记验收的风险。

这个脚本有两个关键特点：

- 不在仓库里硬编码 SMTP 密码或其他远端 secret；它会复用当前远端容器已有的环境变量口径。
- 会先读取远端私钥，再自动派生正确的 `PROGRAM_ADMIN_SIGNING_KID`，避免再次出现“注册完成后 `program_snapshot_invalid`”这种签名漂移问题。

只看计划、不真正修改远端：

```powershell
powershell -ExecutionPolicy Bypass -File program_admin_console/tools/deployProgramAdminRemote.ps1 -DryRun
```

真正执行远端更新：

```powershell
powershell -ExecutionPolicy Bypass -File program_admin_console/tools/deployProgramAdminRemote.ps1
```

默认成功收口时，脚本至少应输出这些关键信息：

- `REMOTE_CONTAINER=...`
- `DEPLOYED_IMAGE=...`
- `DERIVED_SIGNING_KID=...`

如果这轮改动命中注册、签名、公钥链路，AI 还应额外确认：

- `GET /api/auth/public-key` 返回的 `kid` 与脚本输出的 `DERIVED_SIGNING_KID` 一致
- 额外开放公网 `HTTPS` smoke 时，必须显式验证 `/admin` 与 `/api/admin/*` 仍不可公网访问
- 脚本输出需要明确区分 `LOOPBACK_SMOKE=passed` 与 `PUBLIC_HTTPS_SMOKE=passed|disabled`
- 必要时再做一次 `register/complete` 深 smoke，而不是只看 `health`

## 桌面端安全公网接入口径

若目标是“用户端可直连 program access 服务，同时不把后台管理面暴露出去”，推荐口径固定为：

- `c5-program-admin` 容器继续只绑定宿主机 `127.0.0.1:18787`
- 单独提供一个 `HTTPS` 公网入口（推荐独立域名或子域名）
- 公网入口只转发 `GET /api/health` 与 `/api/auth/*`
- 公网入口必须显式拒绝 `/admin` 与 `/api/admin/*`
- 桌面端 `controlPlaneBaseUrl` 最终切到这个 `HTTPS` 入口，不再继续使用裸 `http://8.138.39.139:18787`

仓库内已提供示例反代配置：

- `program_admin_console/deploy/nginx-program-access-auth-gateway.example.conf`
- `program_admin_console/deploy/nginx-program-access-auth-gateway-ip.example.conf`

如果 control plane 运行在反向代理之后，记得同时设置：

- `PROGRAM_ADMIN_TRUST_PROXY=true`

否则注册风控与登录来源识别拿到的只会是代理层 IP，而不是用户真实来源。

### 无域名时的推荐走法

如果暂时没有域名，但又需要让桌面端安全直连服务器，推荐走：

1. 服务器继续保持 `c5-program-admin` 为 `127.0.0.1:18787 -> 8787`
2. 在服务器本机额外部署一个 `443` 反向代理，只放行 `/api/health` 与 `/api/auth/*`
3. 使用带 `IP SAN` 的自签 / 私有 CA 证书给这个 `443` 入口做 TLS
4. 把客户端信任的 CA 证书放到：
   - `app_desktop_web/build/control_plane_ca.pem`
5. 把桌面端 release 配置改成类似：

```json
{
  "controlPlaneBaseUrl": "https://8.138.39.139",
  "controlPlaneCaCertPath": "control_plane_ca.pem"
}
```

说明：

- `controlPlaneCaCertPath` 支持相对 `client_config.release.json` 的路径；打包时若 `app_desktop_web/build/control_plane_ca.pem` 存在，会自动随包带入 resources 根目录
- 这条链只影响桌面端 program access 认证入口，不会把 `/admin` 与 `/api/admin/*` 暴露给公网
- 因为用户只使用桌面程序，不直接在浏览器打开这个接口，所以使用“私有 CA + 客户端 pin 证书”是可接受的

## 远端对齐纪律

`program_admin_console/tools/connectProgramAdminConsole.{ps1,cmd}` 打开的始终是远端运行中的 `c5-program-admin` 容器，不是本地工作树页面。

这意味着：

- 只改本地 `program_admin_console/src/` 或 `program_admin_console/ui/`，不会自动反映到 `connectProgramAdminConsole` 入口
- 只要控制台本地代码有用户可见或接口行为改动，就必须在同一轮把远端源码与远端运行容器一起对齐
- 不能只热补容器不回写远端源码，也不能只改远端源码不刷新容器；两边任何一边落后，`connectProgramAdminConsole` 都可能继续看到旧版

当前推荐的最小对齐闭环：

1. 本地先跑 focused 验证：

```powershell
node program_admin_console/tests/control-plane-ui.test.js
node program_admin_console/tests/control-plane-server.test.js
node program_admin_console/tests/control-plane-store.test.js
```

2. 把本地控制台源码同步到远端源码目录：

- `/home/admin/c5-program-admin-src/src/`
- `/home/admin/c5-program-admin-src/ui/`

注意：不是只同步“肉眼看到改过的文件”，而是要保证新代码依赖到的文件也在远端源码树里。例如 `server.js` 新增 `require("./validation")` 时，`src/validation.js` 也必须同步过去，否则远端重建会直接启动失败。

3. 基于远端源码重建并替换现网容器 `c5-program-admin`。

4. 发布后至少验四类结果：

```powershell
# 远端宿主机本机健康
curl http://127.0.0.1:18787/api/health
curl http://127.0.0.1:18787/api/admin/session

# connect 入口对应的静态资源
curl http://127.0.0.1:18787/admin
curl http://127.0.0.1:18787/admin/app.js
curl http://127.0.0.1:18787/admin/styles.css
```

若本轮改动涉及静态页面或前端交互，建议额外比较本地与远端的静态文件哈希，确认 `/admin`、`/admin/app.js`、`/admin/styles.css` 已与本地工作树对齐后，再宣称“connect 入口已生效”。

## Smoke Note（先验失败/连通性检查）

```powershell
curl http://127.0.0.1:8787/api/health
curl http://127.0.0.1:8787/api/admin/session
```

## 本地启动

```powershell
npm --prefix program_admin_console install
$env:PROGRAM_ADMIN_HOST = "127.0.0.1"
$env:PROGRAM_ADMIN_PORT = "8787"
npm --prefix program_admin_console start
```

浏览器打开：

- `http://127.0.0.1:8787/admin`

## 环境变量

控制面现在已支持真实 SMTP 发信；邮件配置直接沿用 `cs2_alchemy` 同款变量命名。

- `PROGRAM_ADMIN_HOST`（默认 `127.0.0.1`）
- `PROGRAM_ADMIN_PORT`（默认 `3030`）
- `PROGRAM_ADMIN_TRUST_PROXY`（默认 `false`；仅在可信反向代理后置为 `true`）
- `PROGRAM_ADMIN_AUTH_CODE_TTL_MINUTES`
- `PROGRAM_ADMIN_REFRESH_SESSION_DAYS`
- `PROGRAM_ADMIN_ADMIN_SESSION_HOURS`
- `PROGRAM_ADMIN_SNAPSHOT_TTL_MINUTES`
- `PROGRAM_ADMIN_RUNTIME_PERMIT_TTL_SECONDS`
- `PROGRAM_ADMIN_SIGNING_KID`
- `PROGRAM_ADMIN_PRIVATE_KEY_FILE`
- `MAIL_FROM`
- `MAIL_FROM_NAME`（默认 `C5 交易助手`）
- `QQ_SMTP_HOST`（默认 `smtp.qq.com`）
- `QQ_SMTP_PORT`（默认 `465`）
- `QQ_SMTP_SECURE`（默认 `true`）
- `QQ_SMTP_USER`
- `QQ_SMTP_PASS`

仅当 `MAIL_FROM + QQ_SMTP_USER + QQ_SMTP_PASS` 都已配置时，注册验证码与找回密码验证码才会真正发信；否则 `/api/auth/register/send-code` 与 `/api/auth/password/send-reset-code` 会分别返回注册链/找回密码链对应的“邮件服务不可用”错误。

## 初始化或重置管理员密码（CLI）

```powershell
npm --prefix program_admin_console run admin:init -- --username admin --password "Root123!" --db-path "$PWD\program_admin_console\tmp\control-plane.sqlite"
```

重复执行会覆盖同名管理员密码。

## 测试

```powershell
npm --prefix program_admin_console test
```

## Docker

构建镜像：

```powershell
docker build -t program-admin-console:local ./program_admin_console
```

启动容器：

```powershell
docker volume create program_admin_console_data
docker run --rm -p 8787:8787 --name program-admin-console `
  -e PROGRAM_ADMIN_HOST=0.0.0.0 `
  -e PROGRAM_ADMIN_PORT=8787 `
  -e MAIL_FROM=bot@example.com `
  -e MAIL_FROM_NAME="C5 交易助手" `
  -e QQ_SMTP_USER=bot@example.com `
  -e QQ_SMTP_PASS=<SMTP_AUTH_CODE> `
  -v program_admin_console_data:/app/data `
  program-admin-console:local
```

容器内数据库默认路径：`/app/data/control-plane.sqlite`。  
不要把本地 `program_admin_console/data/*.sqlite` 烘进镜像，管理员初始化请针对运行态 DB 执行（本机或容器挂载卷）。

容器卷内初始化管理员（可重复执行重置密码）：

```powershell
docker run --rm `
  -v program_admin_console_data:/app/data `
  program-admin-console:local `
  node tools/initProgramControlPlaneAdmin.js --username admin --password "Root123!" --db-path "/app/data/control-plane.sqlite"
```

## ECS Smoke（端口占位符）

1. 在 ECS 安全组放通 `<CONTROL_PLANE_PORT>`（示例 8787）。
2. 在 ECS 上启动服务并绑定 `PROGRAM_ADMIN_HOST=0.0.0.0`、`PROGRAM_ADMIN_PORT=<CONTROL_PLANE_PORT>`。
3. 远端验证：

```powershell
curl http://<ECS_PUBLIC_IP>:<CONTROL_PLANE_PORT>/api/health
curl http://<ECS_PUBLIC_IP>:<CONTROL_PLANE_PORT>/api/admin/session
```

4. 浏览器访问 `http://<ECS_PUBLIC_IP>:<CONTROL_PLANE_PORT>/admin`。

## 当前发行联调示例

当前项目预留的桌面端 release 配置文件为：

- `app_desktop_web/build/client_config.release.json`

示例控制面地址：

- `https://8.138.39.139`

配套 CA 证书文件：

- `app_desktop_web/build/control_plane_ca.pem`

注意：上面的公网地址是桌面端 release 配置所指向的认证入口，不等于后台 `/admin` 页面必须重新暴露给公网。当前自用后台访问仍应优先遵循本 README 顶部的“当前现网口径”。

当前更推荐的发行联调方式，是保持源站容器仅监听宿主机 `127.0.0.1:18787`，再由 `443` auth gateway 对外暴露：

```powershell
docker build -t c5-program-admin ./program_admin_console
docker volume create c5_program_admin_data
docker run -d --name c5-program-admin `
  -p 127.0.0.1:18787:8787 `
  -e PROGRAM_ADMIN_HOST=0.0.0.0 `
  -e PROGRAM_ADMIN_PORT=8787 `
  -e PROGRAM_ADMIN_TRUST_PROXY=true `
  -e MAIL_FROM=bot@example.com `
  -e MAIL_FROM_NAME="C5 交易助手" `
  -e QQ_SMTP_USER=bot@example.com `
  -e QQ_SMTP_PASS=<SMTP_AUTH_CODE> `
  -v c5_program_admin_data:/app/data `
  c5-program-admin

curl --cacert app_desktop_web/build/control_plane_ca.pem https://8.138.39.139/api/health
curl --cacert app_desktop_web/build/control_plane_ca.pem https://8.138.39.139/api/auth/register/readiness
```

后台 `/admin` 入口不应再经公网暴露，继续只走：

- `http://127.0.0.1:18787/admin` + SSH 隧道

## 自用后台的更安全访问方式

如果这个后台只给你自己使用，不推荐长期把 `18787` 直接暴露到公网。更稳的做法是：

1. 宿主机只绑定本机端口：

```powershell
docker run -d --name c5-program-admin `
  -p 127.0.0.1:18787:8787 `
  -e PROGRAM_ADMIN_HOST=0.0.0.0 `
  -e PROGRAM_ADMIN_PORT=8787 `
  -e MAIL_FROM=bot@example.com `
  -e MAIL_FROM_NAME="C5 交易助手" `
  -e QQ_SMTP_USER=bot@example.com `
  -e QQ_SMTP_PASS=<SMTP_AUTH_CODE> `
  -v /home/admin/c5-program-admin-runtime/keys:/app/keys:ro `
  -v c5_program_admin_data:/app/data `
  c5-program-admin
```

2. 本机先建立 SSH 隧道，再访问后台：

```powershell
ssh -i C:/Users/18220/.ssh/c5_ecs_deploy_temp `
  -L 18787:127.0.0.1:18787 `
  admin@8.138.39.139
```

3. 浏览器打开：

- `http://127.0.0.1:18787/admin`

这样不需要固定家庭公网 IP，也不需要先买域名；后台不会直接暴露给公网，传输链路走 SSH 加密。

### 本机连接脚本

如果你不想每次手敲 SSH 命令，可以直接使用仓库内脚本：

- PowerShell 脚本：`program_admin_console/tools/connectProgramAdminConsole.ps1`
- 双击包装：`program_admin_console/tools/connectProgramAdminConsole.cmd`

默认行为：

- 拉起 `127.0.0.1:18787 -> 8.138.39.139:18787` 的 SSH 隧道
- 启动一个专用浏览器窗口打开 `http://127.0.0.1:18787/admin`
- 关闭这个专用浏览器窗口后，自动断开本次 SSH 隧道

直接运行：

```powershell
powershell -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1
```

或直接双击：

- `program_admin_console/tools/connectProgramAdminConsole.cmd`

常用参数：

```powershell
# 只打印将要执行的 SSH 命令，不真正连接
powershell -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1 -DryRun

# 如果本机 18787 已被占用，可换本地端口
powershell -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1 -LocalPort 28787

# 只拉隧道，不自动打开浏览器
powershell -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1 -NoBrowser

# 如果要显式指定浏览器可执行文件
powershell -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1 -BrowserPath "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
```
