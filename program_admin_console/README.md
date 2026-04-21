# program_admin_console

`program_admin_console` 提供控制面 API 与后台页面（`/admin`），用于管理员初始化、用户权限管理和会话管控。

## Smoke Note（先验失败/连通性检查）

```powershell
curl http://127.0.0.1:8787/api/health
curl http://127.0.0.1:8787/api/admin/bootstrap/state
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

仅当 `MAIL_FROM + QQ_SMTP_USER + QQ_SMTP_PASS` 都已配置时，注册验证码与找回密码验证码才会真正发信；否则 `/api/auth/email/send-code` 与 `/api/auth/password/send-reset-code` 会返回 `mail_service_not_configured`。

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
curl http://<ECS_PUBLIC_IP>:<CONTROL_PLANE_PORT>/api/admin/bootstrap/state
```

4. 浏览器访问 `http://<ECS_PUBLIC_IP>:<CONTROL_PLANE_PORT>/admin`。

## 当前发行联调示例

当前项目预留的桌面端 release 配置文件为：

- `app_desktop_web/build/client_config.release.json`

示例控制面地址：

- `http://8.138.39.139:18787`

若 ECS 上使用该端口部署容器，可按下列命令联调：

```powershell
docker build -t c5-program-admin ./program_admin_console
docker volume create c5_program_admin_data
docker run -d --name c5-program-admin `
  -p 18787:8787 `
  -e PROGRAM_ADMIN_HOST=0.0.0.0 `
  -e PROGRAM_ADMIN_PORT=8787 `
  -e MAIL_FROM=bot@example.com `
  -e MAIL_FROM_NAME="C5 交易助手" `
  -e QQ_SMTP_USER=bot@example.com `
  -e QQ_SMTP_PASS=<SMTP_AUTH_CODE> `
  -v c5_program_admin_data:/app/data `
  c5-program-admin

curl http://8.138.39.139:18787/api/health
curl http://8.138.39.139:18787/api/admin/bootstrap/state
```

浏览器后台入口：

- `http://8.138.39.139:18787/admin`
