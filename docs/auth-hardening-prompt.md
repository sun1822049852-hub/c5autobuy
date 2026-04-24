# C5autobug 认证加固 — 执行指令

> 你的任务是：按以下清单逐项修改代码并验证。不要生成新文档，不要重新分析，直接改代码。

---

## 你的角色

你是安全工程 AI。对 C5autobug（C5 交易助手）的认证体系执行加固。所有修改必须向后兼容，不破坏现有用户登录状态和数据。

---

## 项目结构

三层架构：

- **控制面**（`program_admin_console/`）：Node.js 原生 http + SQLite，部署在远端服务器
- **Python 后端**（`app_backend/`）：FastAPI，本地运行，代理认证请求到控制面
- **桌面端**（`app_desktop_web/`）：Electron + React

### 关键文件

```
program_admin_console/src/server.js           — HTTP 路由、所有 auth 端点、限流逻辑
program_admin_console/src/controlPlaneStore.js — SQLite 数据层、session/密码/验证码 CRUD
program_admin_console/src/entitlementSigner.js — Ed25519 签名、snapshot/permit 签发
program_admin_console/src/constants.js         — 权限定义、路径常量
program_admin_console/src/mailService.js       — 验证码邮件发送
program_admin_console/tests/                   — 测试套件

app_backend/api/routes/program_auth.py                              — 认证路由（代理层）
app_backend/api/program_access_guard.py                             — 请求级权限守卫
app_backend/infrastructure/program_access/remote_control_plane_client.py — 控制面 HTTP 客户端
app_backend/infrastructure/program_access/remote_entitlement_gateway.py — 认证网关
app_backend/infrastructure/program_access/secret_store.py           — Secret Store 工厂
app_backend/infrastructure/program_access/windows_dpapi_secret_store.py — DPAPI 加密
app_backend/infrastructure/program_access/file_program_credential_store.py — 凭据持久化
```

### 技术栈

- 控制面：Node.js（原生 `node:http`），SQLite（`node:sqlite` 的 `DatabaseSync`），nodemailer，Ed25519
- 后端：Python 3，FastAPI，httpx
- 前端：React，Vite，Electron
- 密码哈希：scrypt（`controlPlaneStore.js:20-28`）
- Token 哈希：SHA-256（`controlPlaneStore.js:40-42`）
- 密码比较：`crypto.timingSafeEqual`（`controlPlaneStore.js:37`）
- Refresh Token：`crypto.randomBytes(24).toString("base64url")`

### 现有安全模式（复用这些，不要发明新模式）

**滑动窗口限流**（`server.js:265-331` — `evaluateRegisterSendLimits`）：
```js
// 已有模式：按维度（email/install_id/source_ip/device_fingerprint）查 ledger 表计数
const checks = [
  {field: "email", value: email, windowSeconds: 60, limit: 1},
  {field: "source_ip", value: sourceIp, windowSeconds: 600, limit: 10}
];
for (const check of checks) {
  const stat = store.countRegisterSendsByWindow({field, value, windowSeconds, now});
  if (stat.count >= check.limit) { /* 返回 429 */ }
}
```

**Session 创建/解析**（`controlPlaneStore.js:620-670`）：
```js
// token = createOpaqueToken(24)，存 hashToken(token)，返回明文 token
// 解析时 hashToken(input) 查表匹配
```

---

## 缺陷清单与修改步骤

### 缺陷 1：登录无暴力破解防护 [Critical]

**位置**：`server.js:456-477`（admin login）、`server.js` 约第 991 行（client login）
**问题**：无失败计数、无锁定、无延迟。攻击者可无限次尝试密码。

**步骤**：

1. 打开 `controlPlaneStore.js`，在 `ensureSchema()` 的 SQL 末尾追加：

```sql
CREATE TABLE IF NOT EXISTS login_attempt (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  realm TEXT NOT NULL,
  username TEXT NOT NULL,
  success INTEGER NOT NULL DEFAULT 0,
  source_ip TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_attempt_realm_username_created
  ON login_attempt(realm, username, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempt_realm_ip_created
  ON login_attempt(realm, source_ip, created_at);
```

2. 在 `ControlPlaneStore` 类中新增三个方法：

```javascript
recordLoginAttempt({realm = "client", username = "", success = false, sourceIp = "", now = new Date()} = {}) {
  this.db.prepare(`
    INSERT INTO login_attempt(realm, username, success, source_ip, created_at)
    VALUES(?, ?, ?, ?, ?)
  `).run(toText(realm), toText(username), success ? 1 : 0, toText(sourceIp), nowIso(now));
}

getRecentFailedAttempts({realm = "client", username = "", windowMs = 15 * 60 * 1000, now = new Date()} = {}) {
  const cutoff = new Date(parseMs(nowIso(now)) - windowMs).toISOString();
  const row = this.db.prepare(`
    SELECT COUNT(*) AS cnt FROM login_attempt
    WHERE realm = ? AND username = ? AND success = 0 AND created_at >= ?
  `).get(toText(realm), toText(username), cutoff);
  return Number(row && row.cnt) || 0;
}

isLoginLocked({realm = "client", username = "", maxAttempts = 5, windowMs = 15 * 60 * 1000, now = new Date()} = {}) {
  return this.getRecentFailedAttempts({realm, username, windowMs, now}) >= maxAttempts;
}
```

3. 修改 `server.js` 的 `/api/admin/login`（第 456 行附近），在 `authenticateAdminUser` 调用前插入：

```javascript
const sourceIp = getSourceIp(req);
if (store.isLoginLocked({realm: "admin", username: toText(body && body.username) || "admin", now: now()})) {
  writeError(res, 429, "login_locked", "登录失败次数过多，请15分钟后再试");
  return;
}
```

在 `authenticateAdminUser` 调用后、无论成功失败都记录：

```javascript
store.recordLoginAttempt({
  realm: "admin",
  username: toText(body && body.username) || "admin",
  success: auth.ok,
  sourceIp,
  now: now()
});
```

4. 对 `/api/auth/login`（client login）做同样处理，`realm` 改为 `"client"`。

---

### 缺陷 2：密码/用户名校验不统一 [High]

**位置**：`server.js:167-177`（`isStrongPassword`、`isValidUsername` 已存在但未统一应用）
**问题**：v2 旧注册路由 `/api/auth/register` 不校验密码强度；密码重置不校验新密码强度。

**步骤**：

1. 新建 `program_admin_console/src/validation.js`：

```javascript
function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

function validatePassword(password) {
  const text = toText(password);
  if (!text) return {ok: false, reason: "password_required", message: "密码不能为空"};
  if (text.length < 8) return {ok: false, reason: "password_too_short", message: "密码至少需要8个字符"};
  if (text.length > 128) return {ok: false, reason: "password_too_long", message: "密码不能超过128个字符"};
  if (!/[a-zA-Z]/.test(text)) return {ok: false, reason: "password_missing_letter", message: "密码至少需要包含1个字母"};
  if (!/[0-9]/.test(text)) return {ok: false, reason: "password_missing_digit", message: "密码至少需要包含1个数字"};
  return {ok: true};
}

function validateUsername(username) {
  const text = toText(username);
  if (!text) return {ok: false, reason: "username_required", message: "用户名不能为空"};
  if (text.length < 3) return {ok: false, reason: "username_too_short", message: "用户名至少需要3个字符"};
  if (text.length > 32) return {ok: false, reason: "username_too_long", message: "用户名不能超过32个字符"};
  if (!/^[a-zA-Z0-9_]+$/.test(text)) return {ok: false, reason: "username_invalid_chars", message: "用户名只能包含字母、数字和下划线"};
  return {ok: true};
}

module.exports = {validatePassword, validateUsername};
```

2. 在 `server.js` 顶部引入：`const {validatePassword, validateUsername} = require("./validation");`

3. 在以下路由中，在写库前插入校验：
   - `/api/auth/register`（v2，约第 957 行）— 校验 username + password
   - `/api/auth/register/complete`（v3）— 替换现有 `isStrongPassword` 调用，增加 `validateUsername`
   - `/api/auth/password/reset`（约第 1098 行）— 校验 new_password
   - `/api/admin/bootstrap`（约第 438 行）— 校验 password

校验失败返回 400：
```javascript
const pwCheck = validatePassword(password);
if (!pwCheck.ok) {
  writeError(res, 400, pwCheck.reason, pwCheck.message);
  return;
}
```

---

### 缺陷 3：验证码猜测无限制 [High]

**位置**：`controlPlaneStore.js` — `verifyEmailCode()` 方法
**问题**：密码重置验证码验证无尝试次数限制。v3 注册流程有 `maxVerifyAttempts: 5`，但旧版 email_code 没有。

**步骤**：

1. 在 `email_code` 表增加 `attempt_count` 列（通过 `ensureSchema` 中 `CREATE TABLE IF NOT EXISTS` 已有表不受影响，需用 ALTER TABLE 或在 verifyEmailCode 中用应用层计数）。

2. 推荐方案：在 `verifyEmailCode` 方法中增加应用层计数——查询同一 email+scene 在 5 分钟内的失败验证次数，超过 5 次拒绝。复用 `login_attempt` 表的模式，或新增 `code_verify_attempt` 表。

---

### 缺陷 4：请求体无大小限制 [Medium]

**位置**：`server.js:124-142`（`readJsonBody`）
**问题**：无 body size 限制，可被用于 DoS。

**步骤**：

1. 修改 `readJsonBody` 函数，增加 `maxBytes` 参数：

```javascript
function readJsonBody(req, maxBytes = 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let totalSize = 0;
    req.on("data", (chunk) => {
      totalSize += chunk.length;
      if (totalSize > maxBytes) {
        req.destroy();
        reject(new Error("request_body_too_large"));
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8").trim();
      if (!raw) { resolve({}); return; }
      try { resolve(JSON.parse(raw)); }
      catch (error) { reject(error); }
    });
    req.on("error", reject);
  });
}
```

2. 在 `server.js` 的 `catch` 块中增加对 `request_body_too_large` 的处理：

```javascript
} catch (error) {
  if (error && error.message === "request_body_too_large") {
    writeError(res, 413, "request_body_too_large", "request body too large");
    return;
  }
  writeError(res, 500, "internal_error", error && error.message ? error.message : "internal error");
}
```

---

### 缺陷 5：验证码使用 Math.random() [Medium]

**位置**：`server.js:214`
**问题**：`Math.random()` 非 CSPRNG，验证码可预测。

**步骤**：

1. 将第 214 行：
```javascript
: () => String(Math.floor(100000 + Math.random() * 900000));
```
改为：
```javascript
: () => String(crypto.randomInt(100000, 1000000));
```

2. 确认 `server.js` 顶部已有 `const crypto = require("node:crypto");`（`controlPlaneStore.js` 有，`server.js` 需确认，若无则添加）。

---

### 缺陷 6：Refresh Token 无 Family 检测 [Medium]

**位置**：`controlPlaneStore.js:739-764`（`rotateRefreshSession`）
**问题**：旧 token 被标记为 `rotated` 后若被重放，仅返回 `not_found`，不会吊销整个 token 家族。

**步骤**：

1. 在 `ensureSchema()` 中追加：
```sql
ALTER TABLE refresh_session ADD COLUMN family_id TEXT NOT NULL DEFAULT '';
```
注意：SQLite 的 `ALTER TABLE ADD COLUMN` 对已有表是幂等安全的（列已存在会报错），需包裹在 try-catch 中：
```javascript
try { this.db.exec("ALTER TABLE refresh_session ADD COLUMN family_id TEXT NOT NULL DEFAULT ''"); } catch {}
try { this.db.exec("CREATE INDEX IF NOT EXISTS idx_refresh_session_family ON refresh_session(family_id, status)"); } catch {}
```

2. 修改 `createRefreshSession`：生成 `family_id = createId("fam")`，写入新行。

3. 修改 `rotateRefreshSession`：新 session 继承旧 session 的 `family_id`。

4. 修改 `resolveRefreshSession`：若查到的 token 状态为 `rotated`，说明被重放——吊销该 `family_id` 下所有 active session：
```javascript
if (toText(row.status) === "rotated") {
  const familyId = toText(row.family_id);
  if (familyId) {
    this.db.prepare(`
      UPDATE refresh_session SET status = 'revoked', revoked_at = ?, updated_at = ?
      WHERE family_id = ? AND status IN ('active', 'rotated')
    `).run(stamp, stamp, familyId);
  }
  return {ok: false, reason: "refresh_token_reuse_detected"};
}
```

---

### 缺陷 7：Admin Session 无 IP 绑定 [Medium]

**位置**：`controlPlaneStore.js:620-650`（admin_session 表）
**问题**：token 泄露可从任意 IP 使用。

**步骤**：

1. 在 `ensureSchema()` 中追加（同样 try-catch 包裹）：
```javascript
try { this.db.exec("ALTER TABLE admin_session ADD COLUMN source_ip TEXT NOT NULL DEFAULT ''"); } catch {}
try { this.db.exec("ALTER TABLE admin_session ADD COLUMN user_agent TEXT NOT NULL DEFAULT ''"); } catch {}
```

2. 修改 `createAdminSession` 方法签名，增加 `sourceIp`、`userAgent` 参数，写入新列。

3. 修改 `server.js` 的 `/api/admin/login` 路由，传入 `sourceIp: getSourceIp(req)` 和 `userAgent: toText(req.headers["user-agent"])`。

---

### 缺陷 8：Entitlement Snapshot 无 iss/aud [Low]

**位置**：`entitlementSigner.js:84-93`
**问题**：跨环境 snapshot 可能被误用。

**步骤**：

1. 在 `issueBundle` 的 snapshot 对象中增加：
```javascript
iss: "c5-control-plane",
aud: "c5-desktop-client",
```

2. 在 `issueRuntimePermit` 的 snapshot 中同样增加。

3. 在 `app_backend/infrastructure/program_access/entitlement_verifier.py` 中增加 iss/aud 校验（可选，因为签名已保证完整性）。

---

### 缺陷 9：X-Forwarded-For 可伪造 [Medium]

**位置**：`server.js:179-185`（`getSourceIp`）
**问题**：直接信任 XFF 首段，攻击者可伪造 IP 绕过限流。

**步骤**：

1. 增加环境变量 `TRUST_PROXY`（默认 `false`）。
2. 修改 `getSourceIp`：
```javascript
function getSourceIp(req) {
  if (config.trustProxy) {
    const xff = toText(req && req.headers && req.headers["x-forwarded-for"]);
    if (xff) return toText(xff.split(",")[0]);
  }
  return toText(req && req.socket && req.socket.remoteAddress);
}
```

---

### 缺陷 10：HTTPS 部署 [Critical — 需服务器操作]

**问题**：控制面裸 HTTP 传输，密码和 refresh token 明文过网。

**步骤**（需要在服务器上操作）：

1. 申请域名，DNS 解析到服务器 IP
2. 安装 nginx + certbot：`apt install nginx certbot python3-certbot-nginx`
3. 配置 nginx 反向代理：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location /api/ {
        proxy_pass http://127.0.0.1:18787;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /admin {
        proxy_pass http://127.0.0.1:18787;
    }
}
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}
```

4. `certbot --nginx -d your-domain.com`
5. 修改 Python 后端 `remote_control_plane_client.py` 中的 base_url 为 `https://your-domain.com`
6. 部署后将 `TRUST_PROXY` 设为 `true`（因为 nginx 是可信代理）

---

### 缺陷 11：Bootstrap 无防护 [Low]

**位置**：`server.js:432-454`
**问题**：数据库被清空后攻击者可抢先创建管理员。

**步骤**：

1. 在 `/api/admin/bootstrap` 路由中增加 IP 检查：
```javascript
const bootstrapIp = getSourceIp(req);
if (bootstrapIp !== "127.0.0.1" && bootstrapIp !== "::1" && bootstrapIp !== "::ffff:127.0.0.1") {
  writeError(res, 403, "bootstrap_forbidden", "bootstrap only allowed from localhost");
  return;
}
```

---

### 缺陷 12：桌面端 API Key 明文显示 [Low]

**位置**：`app_desktop_web/src/` 编辑对话框
**问题**：API Key 以 `type="text"` 显示。

**步骤**：找到 API Key 的 input 元素，改为 `type="password"`，旁边加一个切换可见的按钮。

---

### 缺陷 13：Dev Plaintext Secret Store 泄露风险 [Medium]

**位置**：`app_backend/infrastructure/program_access/secret_store.py:34-37`
**问题**：`stage == "local_dev"` 时明文存储 refresh token。

**步骤**：在打包构建脚本中确认 `stage` 硬编码为 `"packaged_release"`，不从环境变量读取。

---

## 实施顺序

| 优先级 | 缺陷 | 难度 | 说明 |
|--------|------|------|------|
| P0 | 缺陷 1：登录暴力破解 | 中 | 最紧急，直接影响账号安全 |
| P0 | 缺陷 10：HTTPS | 低（配置） | 需服务器操作，可并行 |
| P1 | 缺陷 2：密码校验统一 | 低 | 基础防线 |
| P1 | 缺陷 4：请求体限制 | 低 | 一个函数改动 |
| P1 | 缺陷 5：验证码 CSPRNG | 低 | 一行改动 |
| P2 | 缺陷 3：验证码猜测限制 | 中 | 需新增计数逻辑 |
| P2 | 缺陷 6：Token Family | 高 | 涉及 schema 变更和多方法修改 |
| P2 | 缺陷 9：XFF 信任 | 低 | 配置项 + 函数改动 |
| P3 | 缺陷 7：Admin Session IP | 低 | schema + 方法签名 |
| P3 | 缺陷 8：iss/aud | 低 | 两处 snapshot 加字段 |
| P3 | 缺陷 11：Bootstrap IP | 低 | 几行代码 |
| P3 | 缺陷 12：API Key 显示 | 低 | 前端改动 |
| P3 | 缺陷 13：Stage 硬编码 | 低 | 构建配置 |

---

## 验证检查清单

### 登录防护
- [ ] Client 连续 5 次错误密码 → 第 6 次返回 429 `login_locked`
- [ ] Admin 连续 5 次错误密码 → 第 6 次返回 429 `login_locked`
- [ ] 锁定期间正确密码也返回 429
- [ ] 15 分钟后解锁，可正常登录

### 密码校验
- [ ] v2 注册：密码 "123" 被拒（400）
- [ ] v2 注册：用户名 "ab" 被拒（400）
- [ ] v3 注册 complete：同上校验生效
- [ ] 密码重置：新密码 "weak" 被拒（400）
- [ ] Admin bootstrap：弱密码被拒（400）

### 请求体
- [ ] 超大请求体（>1MB）返回 413

### 验证码
- [ ] 验证码改用 `crypto.randomInt`，输出仍为 6 位数字
- [ ] 密码重置验证码连续猜错 5 次后被锁定

### Token Family
- [ ] Refresh token rotation 后旧 token 重放 → 整个 family 被吊销
- [ ] 正常 rotation 流程不受影响

### Admin Session
- [ ] admin_session 表包含 source_ip 和 user_agent
- [ ] 登录成功后旧 session 可选 revoke（单点登录）

### Snapshot
- [ ] Entitlement snapshot 包含 iss 和 aud 字段

### 网络
- [ ] HTTPS 部署后密码不再明文传输
- [ ] `getSourceIp` 在 `TRUST_PROXY=false` 时忽略 XFF

### 回归
- [ ] Admin bootstrap → login → session → logout 全链路正常
- [ ] Client register V3 三步流程正常
- [ ] Client login → refresh → runtime-permit 全链路正常
- [ ] 现有测试全部通过：`npm --prefix program_admin_console test`
- [ ] 密码重置流程正常用户不受限流误伤

---

## 注意事项

1. **向后兼容**：SQLite schema 变更用 `ALTER TABLE ... ADD COLUMN` 包裹在 try-catch 中，新表用 `CREATE TABLE IF NOT EXISTS`
2. **不引入新依赖**：所有修改使用 Node.js 标准库（`node:crypto`、`node:http` 等）
3. **保留现有 v3 流程**：v3 三步注册已运行良好，只补充校验
4. **Python 后端是代理层**：核心校验在控制面完成，Python 端可选增加前置校验
5. **测试**：`program_admin_console/tests/` 下有测试套件，新增功能需补充对应测试
6. **不要修改现有密码哈希方式**：scrypt 已足够安全
7. **不要修改现有 token 生成方式**：`createOpaqueToken(24)` 已足够安全
