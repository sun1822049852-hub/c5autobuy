# 会员鉴权与注册登录接口设计

日期：2026-04-06

## 1. 目标

为当前 `app_backend` 增加可产品化的用户与会员层，先完成以下最小闭环：

- 用户可通过邮箱验证码完成注册
- 用户可通过 `username + password` 登录
- 用户可重置密码
- 服务端可判断会员是否有效、套餐限制是否超额、功能是否可用
- 现有业务接口可在不推翻核心运行时逻辑的前提下接入会员闸门
- 后续新控制台只需要消费稳定的 `auth + membership + bootstrap` 契约

本次设计优先支持“远端 backend + Electron thin client”的产品形态。

## 2. 参考实现

本次注册机制明确参考：

- `C:\Users\18220\Desktop\cs2_alchemy\node_sidecar\src\controlPlaneAuthClient.js`
- `C:\Users\18220\Desktop\cs2_alchemy\node_sidecar\src\uiServer.js`
- `C:\Users\18220\Desktop\cs2_alchemy\node_sidecar\src\appAuthStore.js`

明确复用其思路：

- 注册不是裸 `username + password`
- 先发邮箱验证码，再提交注册
- 登录使用 `username + password`
- 密码哈希使用 `scrypt`
- 服务端能返回 `user + permissions + membership`

明确不直接照抄其实现：

- `cs2_alchemy` 的本地 sidecar / license runtime / cookie 注入链路
- 它的 Steam 业务上下文

当前项目仍以远端 FastAPI 为唯一可信后端。

## 3. 非目标

本次设计明确不覆盖以下内容：

- 控制台 UI 实现
- 支付接口
- 支付回调
- 多支付渠道并行接入
- 分销、优惠券、邀请返利
- 手机验证码、邮箱验证码以外的 SSO
- 多管理员后台权限系统
- 本地 license 离线授权

## 4. 现状与约束

当前项目已经具备：

- 后端主入口：`app_backend/main.py`
- 聚合快照：`GET /app/bootstrap`
- 运行时推送：`WS /ws/runtime`
- 账号、查询、购买、任务等完整业务接口

当前项目尚不具备：

- 产品用户注册体系
- 登录会话体系
- 密码重置体系
- 会员状态体系
- 统一鉴权中间件
- 按会员隔离的数据与运行时目录

因此本次设计不改业务核心语义，只在业务核心外层补一层：

`User/Auth -> Membership -> Existing Business APIs`

## 5. 方案选择

### 方案 A：只做登录，不做注册

特点：

- 用户必须由后台预创建
- 客户端只支持登录

优点：

- 实现最小

缺点：

- 产品化不足
- 与参考实现不一致

### 方案 B：邮箱验证码注册 + 用户名密码登录 + 服务端会员判定

特点：

- 注册分两步：`send-code -> register`
- 登录分离为 `username + password`
- 所有会员与套餐判断都在服务端完成
- 业务接口与 websocket 都走统一鉴权

优点：

- 与 `cs2_alchemy` 的产品用户认证方式一致
- 安全边界清晰
- 能先跑通用户体系，不被支付阻塞

缺点：

- 必须先做多租户隔离
- 当前阶段会员开通需要后台脚本或手工授予

### 方案 C：注册即自动送默认试用会员

特点：

- 注册后自动附带 `trial` 会员

优点：

- 用户上手快

缺点：

- 试用策略一旦写死，后续容易返工

### 结论

本次采用方案 B，并保留可选的 `AUTO_TRIAL_PLAN_CODE` 配置位：

- 默认：注册只创建用户，不自动开会员
- 若后续需要试用：通过配置给新用户挂一个默认试用套餐

## 6. 总体架构

整体链路如下：

1. 用户通过 `POST /auth/email/send-code` 请求注册验证码
2. 用户通过 `POST /auth/register` 完成注册
3. 用户通过 `POST /auth/login` 登录
4. 服务端返回 `access_token + refresh_token + viewer + membership + permissions`
5. 客户端后续请求通过 `Authorization: Bearer <access_token>` 访问业务接口
6. 服务端在每次业务调用前解析当前用户、当前会员与套餐限制
7. 客户端 token 即将过期或已过期时调用 `POST /auth/refresh`
8. 用户忘记密码时通过 `send-reset-code -> reset-password` 完成重置
9. 会员状态通过后台脚本、后台内部接口或初始化数据授予
10. `/me/membership` 与 `/app/bootstrap` 返回新的会员状态

说明：

- `cs2_alchemy` 参考实现内部使用 session/cookie 模式
- 当前项目为了适配 Electron 远端直连，保留 `access_token + refresh_token` 模式
- 注册与密码校验流程参考其控制面契约，不照搬其传输层细节

## 7. 域模型

### 7.1 User

字段：

- `user_id`
- `email`
- `username`
- `password_hash`
- `display_name`
- `status`
- `email_verified_at`
- `created_at`
- `updated_at`

状态建议：

- `active`
- `disabled`
- `locked`

### 7.2 AuthSession

字段：

- `session_id`
- `user_id`
- `refresh_token_hash`
- `device_id`
- `user_agent`
- `ip_address`
- `expires_at`
- `revoked_at`
- `created_at`

说明：

- access token 不入库
- refresh token 只存 hash，不存明文
- 一次登录创建一条 session

### 7.3 AuthEmailCode

字段：

- `challenge_id`
- `scene`
- `email`
- `code_hash`
- `expires_at`
- `used_at`
- `created_at`

`scene` 只支持：

- `register`
- `password_reset`

### 7.4 MembershipPlan

字段：

- `plan_code`
- `plan_name`
- `status`
- `duration_days`
- `account_limit`
- `query_concurrency_limit`
- `feature_flags_json`
- `created_at`
- `updated_at`

V1 推荐套餐能力：

- `account_limit`
- `query_concurrency_limit`
- `can_use_purchase_runtime`
- `can_use_open_api_binding`
- `can_use_balance_refresh`

### 7.5 Membership

字段：

- `membership_id`
- `user_id`
- `plan_code`
- `status`
- `starts_at`
- `expires_at`
- `grace_expires_at`
- `granted_by`
- `created_at`
- `updated_at`

状态建议：

- `inactive`
- `active`
- `expired`
- `grace`
- `cancelled`

## 8. 数据隔离要求

现有业务资源必须统一补 `owner_user_id`：

- `accounts`
- `query_configs`
- `query_products`
- `query_config_items`
- `query_mode_settings`
- `account_session_bundles`
- `account_inventory_snapshots`
- `purchase_ui_preferences`
- `runtime_settings`

此外，运行时目录必须改成：

```text
runtime-root/
  users/
    <user_id>/
      browser-profiles/
      browser-sessions/
      session-bundles/
      diagnostics/
```

任何 repository 默认都只能读写当前用户的数据，不允许显式跨会员访问。

## 9. 凭证与密码策略

### 9.1 Access Token

- 类型：JWT 或签名 token
- 传输：`Authorization: Bearer <token>`
- 生命周期：15 分钟
- 内容：
  - `sub=user_id`
  - `sid=session_id`
  - `role=user`
  - `exp`

### 9.2 Refresh Token

- 生命周期：30 天
- 只通过 `POST /auth/refresh` 使用
- 服务端只保存 hash
- 绑定 `session_id`

### 9.3 Password Hash

密码哈希明确参考 `cs2_alchemy/node_sidecar/src/appAuthStore.js`：

- 算法：`scrypt`
- 存储格式：`scrypt$<salt>$<digest>`
- 校验方式：`timingSafeEqual`

### 9.4 失效策略

以下情况强制要求重新登录：

- `user.status != active`
- `auth_session.revoked_at is not null`
- refresh token hash 不匹配
- refresh session 已过期

## 10. 接口设计

## 10.1 `POST /auth/email/send-code`

用途：

- 发送邮箱验证码
- 同时支持注册与密码重置场景

请求体：

```json
{
  "email": "demo@example.com",
  "scene": "register"
}
```

成功响应 `200`：

```json
{
  "ok": true,
  "scene": "register",
  "expires_in_seconds": 300
}
```

失败响应：

- `400 auth_email_required`
- `400 auth_scene_invalid`
- `429 auth_code_rate_limited`

## 10.2 `POST /auth/register`

用途：

- 通过邮箱验证码完成注册

请求体：

```json
{
  "email": "demo@example.com",
  "code": "123456",
  "username": "demo",
  "password": "plain-text-password"
}
```

成功响应 `201`：

```json
{
  "user_id": "u_123",
  "email": "demo@example.com",
  "username": "demo",
  "display_name": "demo",
  "status": "active",
  "membership": {
    "status": "inactive",
    "plan_code": null,
    "expires_at": null
  }
}
```

失败响应：

- `400 auth_code_invalid`
- `400 auth_code_expired`
- `409 auth_email_taken`
- `409 auth_username_taken`
- `422 auth_password_too_weak`

## 10.3 `POST /auth/login`

用途：

- 用户登录
- 创建新会话
- 返回首屏所需最小 viewer / membership / permissions 摘要

请求体：

```json
{
  "username": "demo",
  "password": "plain-text-password",
  "device_id": "DESKTOP-01",
  "client_version": "1.0.0"
}
```

成功响应 `200`：

```json
{
  "access_token": "[REDACTED]",
  "refresh_token": "[REDACTED]",
  "token_type": "Bearer",
  "expires_in": 900,
  "viewer": {
    "user_id": "u_123",
    "email": "demo@example.com",
    "username": "demo",
    "display_name": "demo"
  },
  "permissions": [
    "accounts.read",
    "inventory.read"
  ],
  "membership": {
    "plan_code": "pro",
    "status": "active",
    "starts_at": "2026-04-06T12:00:00",
    "expires_at": "2026-05-06T12:00:00"
  },
  "limits": {
    "account_limit": 50,
    "query_concurrency_limit": 5,
    "feature_flags": {
      "can_use_purchase_runtime": true,
      "can_use_open_api_binding": true,
      "can_use_balance_refresh": true
    }
  }
}
```

失败响应：

- `401 auth_invalid_credentials`
- `423 auth_user_locked`
- `403 auth_user_disabled`

## 10.4 `POST /auth/refresh`

用途：

- 刷新 access token
- 延长当前登录态

请求体：

```json
{
  "refresh_token": "[REDACTED]",
  "device_id": "DESKTOP-01"
}
```

成功响应 `200`：

```json
{
  "access_token": "[REDACTED]",
  "refresh_token": "[REDACTED]",
  "token_type": "Bearer",
  "expires_in": 900
}
```

失败响应：

- `401 auth_refresh_invalid`
- `401 auth_session_expired`
- `401 auth_session_revoked`

## 10.5 `POST /auth/logout`

用途：

- 撤销当前 session

请求头：

- `Authorization: Bearer <access_token>`

请求体：

```json
{
  "refresh_token": "[REDACTED]"
}
```

成功响应 `204`

## 10.6 `POST /auth/password/send-reset-code`

用途：

- 发送密码重置验证码

请求体：

```json
{
  "email": "demo@example.com"
}
```

成功响应 `200`：

```json
{
  "ok": true,
  "scene": "password_reset",
  "expires_in_seconds": 300
}
```

## 10.7 `POST /auth/password/reset`

用途：

- 用邮箱验证码重置密码

请求体：

```json
{
  "email": "demo@example.com",
  "code": "123456",
  "new_password": "new-plain-text-password"
}
```

成功响应 `200`：

```json
{
  "ok": true
}
```

失败响应：

- `400 auth_code_invalid`
- `400 auth_code_expired`
- `404 auth_email_not_found`
- `422 auth_password_too_weak`

## 10.8 `GET /me`

用途：

- 返回当前登录用户基本信息

成功响应 `200`：

```json
{
  "user_id": "u_123",
  "email": "demo@example.com",
  "username": "demo",
  "display_name": "demo",
  "status": "active"
}
```

## 10.9 `GET /me/membership`

用途：

- 返回当前会员态、权限与套餐限制摘要

成功响应 `200`：

```json
{
  "permissions": [
    "accounts.read",
    "inventory.read"
  ],
  "plan_code": "pro",
  "status": "active",
  "starts_at": "2026-04-06T12:00:00",
  "expires_at": "2026-05-06T12:00:00",
  "grace_expires_at": null,
  "limits": {
    "account_limit": 50,
    "query_concurrency_limit": 5,
    "feature_flags": {
      "can_use_purchase_runtime": true,
      "can_use_open_api_binding": true,
      "can_use_balance_refresh": true
    }
  }
}
```

## 10.10 `POST /internal/memberships/grant`

用途：

- 当前阶段由内部脚本或后台接口手工开通会员
- 不对普通客户端开放

请求体：

```json
{
  "user_id": "u_123",
  "plan_code": "pro",
  "starts_at": "2026-04-06T12:00:00",
  "expires_at": "2026-05-06T12:00:00"
}
```

成功响应 `200`：

```json
{
  "user_id": "u_123",
  "plan_code": "pro",
  "status": "active",
  "starts_at": "2026-04-06T12:00:00",
  "expires_at": "2026-05-06T12:00:00"
}
```

说明：

- 这一步也可以先用 CLI/seed script 实现，不一定要立即暴露 HTTP 接口

## 11. 业务接口与会员闸门

以下接口必须要求已登录：

- `GET /app/bootstrap`
- `/accounts/*`
- `/account-center/*`
- `/query-configs*`
- `/query-runtime/*`
- `/purchase-runtime/*`
- `/runtime-settings/*`
- `/tasks/*`
- `WS /ws/runtime`
- `WS /ws/accounts/updates`
- `WS /ws/tasks/{task_id}`

### 11.1 会员有效性规则

业务主流程可用条件：

- `membership.status in {active, grace}`
- `now < expires_at` 或 `now < grace_expires_at`

### 11.2 套餐限制规则

启动查询/购买前需要检查：

- 当前账号数量是否超出 `account_limit`
- 当前并发是否超出 `query_concurrency_limit`
- 功能是否被 `feature_flags` 禁止

### 11.3 错误码

统一业务错误建议：

- `auth_required`
- `membership_expired`
- `plan_limit_exceeded`
- `feature_not_enabled`

HTTP 建议：

- `401` 未登录或 token 无效
- `403` 已登录但会员无效或功能禁用
- `409` 已登录但资源状态冲突

## 12. `/app/bootstrap` 扩展

当前 `/app/bootstrap` 需要补以下字段：

```json
{
  "viewer": {
    "user_id": "u_123",
    "email": "demo@example.com",
    "username": "demo",
    "display_name": "demo"
  },
  "permissions": [
    "accounts.read",
    "inventory.read"
  ],
  "membership": {
    "plan_code": "pro",
    "status": "active",
    "expires_at": "2026-05-06T12:00:00"
  },
  "limits": {
    "account_limit": 50,
    "query_concurrency_limit": 5,
    "feature_flags": {
      "can_use_purchase_runtime": true
    }
  }
}
```

这样新控制台首屏只需：

- `GET /app/bootstrap`
- `WS /ws/runtime`

就能得到主业务态和会员态。

## 13. `WS /ws/runtime` 鉴权

V1 采用以下方式之一：

- 握手时带 `Authorization` header
- 或 query 参数 `?access_token=...`

推荐优先级：

1. header
2. query 参数作为 Electron 兼容 fallback

连接成功后：

- 服务端只推当前用户可见的运行时事件
- token 失效时主动断开并要求客户端 refresh / relogin

## 14. 会员开通来源

当前阶段不做支付接口，因此会员来源先限定为：

- 初始化 seed 数据
- 管理员脚本
- 内部 grant 接口
- 可选的注册即送试用套餐配置

这意味着第一阶段重点是：

- 把用户与会员边界做对
- 把注册/登录/重置密码做对
- 把业务接口闸门做对
- 把多租户隔离做对

而不是先做支付。

## 15. 迁移策略

### 15.1 数据库迁移

先新增：

- `users`
- `auth_sessions`
- `auth_email_codes`
- `membership_plans`
- `memberships`

再给现有业务表加：

- `owner_user_id`

### 15.2 初始数据

初始化至少插入：

- 一个管理员/测试用户
- 一个 `basic` 套餐
- 一个 `pro` 套餐

### 15.3 老数据归属

当前本地历史数据可先归到默认内部用户：

- `user_id = system_seed_user`

后续新注册用户全部走新隔离路径。

## 16. 测试要求

后端至少补这些测试：

- `test_auth_send_register_code_success`
- `test_auth_register_success`
- `test_auth_register_duplicate_username`
- `test_auth_login_success`
- `test_auth_login_invalid_password`
- `test_auth_refresh_success`
- `test_auth_logout_revokes_session`
- `test_auth_send_reset_code_success`
- `test_auth_reset_password_success`
- `test_membership_expired_blocks_query_runtime_start`
- `test_plan_limit_blocks_account_creation`
- `test_runtime_websocket_requires_auth`
- `test_bootstrap_returns_viewer_membership_and_limits`

## 17. 决策摘要

本次冻结以下决策：

- 会员与套餐判定全部放服务端
- V1 支持 `send-code -> register -> login -> refresh -> logout -> password reset`
- 注册机制参考 `cs2_alchemy` 的 control-plane 契约
- 密码哈希采用 `scrypt`
- V1 暂不做支付接口
- 当前阶段会员通过后台脚本、内部接口或初始化数据授予
- 所有现有业务资源统一挂 `owner_user_id`
- `/app/bootstrap` 与 `WS /ws/runtime` 同时承载会员上下文

这套接口设计的目的不是“再造一套平台”，而是给当前成熟业务核心补上产品化外壳，并保证最后接什么控制台 UI 都不会反向污染 backend 边界。
