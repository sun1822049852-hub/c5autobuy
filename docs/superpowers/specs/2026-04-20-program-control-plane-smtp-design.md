# Program Control Plane SMTP Design

## 背景

当前 `program_admin_console` 的邮件发送仍是 stub：

- `mailConfig` 直接返回 `configured: true`
- `mailService` 不走真实 SMTP
- 注册/找回密码虽然已有接口，但邮件验证码并未真正发送

用户已明确要求直接沿用 `cs2_alchemy` 的 SMTP 方案，并保持最小改动范围。

## 不可改变项

- 不修改现有会员语义与控制面接口路径。
- 不增加新的后台配置 UI。
- 不扩展为新的邮件供应商体系，先直接复用 alchemy 的 QQ SMTP 配置命名。
- 不改变现有管理员、公钥签名、注册、登录、刷新、找回密码的业务边界。

## 方案

在 `program_admin_console` 内直接搬运 `cs2_alchemy/admin_console` 的最小 SMTP 能力：

1. `mailConfig`
   - 支持读取 alchemy 同款环境变量：
     - `MAIL_FROM`
     - `MAIL_FROM_NAME`
     - `QQ_SMTP_HOST`
     - `QQ_SMTP_PORT`
     - `QQ_SMTP_SECURE`
     - `QQ_SMTP_USER`
     - `QQ_SMTP_PASS`
   - 同时保留当前控制面已有的业务配置项：
     - `PROGRAM_ADMIN_HOST`
     - `PROGRAM_ADMIN_PORT`
     - `PROGRAM_ADMIN_AUTH_CODE_TTL_MINUTES`
     - `PROGRAM_ADMIN_REFRESH_SESSION_DAYS`
     - `PROGRAM_ADMIN_ADMIN_SESSION_HOURS`
     - `PROGRAM_ADMIN_SNAPSHOT_TTL_MINUTES`
     - `PROGRAM_ADMIN_RUNTIME_PERMIT_TTL_SECONDS`
     - `PROGRAM_ADMIN_SIGNING_KID`
     - `PROGRAM_ADMIN_PRIVATE_KEY_FILE`
   - 仅当发件地址、SMTP 用户名、SMTP 密码齐备时才标记 `configured: true`

2. `mailService`
   - 使用 `nodemailer` 建立 SMTP transport
   - 复用 alchemy 的验证码邮件文案结构
   - 支持注册验证码与重置密码验证码两类场景

3. `server`
   - 发码前检查 `config.configured`
   - 发码失败时返回明确错误，并删除本次新建验证码，避免“邮件没发出去但验证码已写库”
   - 找回密码发码沿用同一套校验/回滚逻辑

4. `README`
   - 删除“当前仓库 mail service stub”表述
   - 改成真实 SMTP 配置说明
   - 明确部署时需补充 SMTP 环境变量

## 验证

- 新增/补充最小自动化回归：
  - `mailConfig` 配置解析
  - `mailService` 邮件主题/正文/transport 调用
  - `server` 在邮件未配置与发送失败时的接口行为和验证码回滚
- 跑通 `program_admin_console` 受影响测试集

## 风险与边界

- 这次只补“真实 SMTP 发信能力”，不补后台邮件配置页面。
- 这次不直接把服务器 SMTP 密码写入仓库；部署时仍通过环境变量注入。
- 远端容器是否真正能发信，取决于后续是否补齐 SMTP 环境变量与外网连通性。
