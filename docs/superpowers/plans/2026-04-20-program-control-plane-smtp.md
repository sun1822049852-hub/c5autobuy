# Program Control Plane SMTP Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `program_admin_console` 的邮件验证码从 stub 切到 alchemy 同款 SMTP，实现真实注册/找回密码邮件发送。

**Architecture:** 复用 alchemy 已验证的 `mailConfig + mailService` 结构，但保持当前控制面的业务配置项不变。服务端发码接口统一走“配置校验 -> 写验证码 -> 发信 -> 失败回滚”的链路，不新增后台配置 UI。

**Tech Stack:** Node.js CommonJS, `nodemailer`, 现有 `program_admin_console` 自带集成测试

---

## Chunk 1: SMTP Config And Delivery

### Task 1: Add red tests for SMTP config and failure handling

**Files:**
- Create: `program_admin_console/tests/mail_config.test.js`
- Create: `program_admin_console/tests/mail_service.test.js`
- Modify: `program_admin_console/tests/control-plane-server.test.js`

- [ ] **Step 1: Write the failing config test**

```js
const assert = require("node:assert/strict");
const {getMailConfig} = require("../src/mailConfig");

const config = getMailConfig({
  MAIL_FROM: "bot@example.com",
  QQ_SMTP_USER: "bot@example.com",
  QQ_SMTP_PASS: "secret"
});

assert.equal(config.configured, true);
assert.equal(config.smtpHost, "smtp.qq.com");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node program_admin_console/tests/mail_config.test.js`  
Expected: FAIL because current `mailConfig` does not expose SMTP fields or `configured` truthfully.

- [ ] **Step 3: Write the failing mail service test**

```js
const transport = { sendMail: async (payload) => payload };
const service = createMailService({config, transport});
const result = await service.sendVerificationCode({to: "a@example.com", code: "123456", scene: "register"});
assert.equal(result.subject.includes("注册验证码"), true);
```

- [ ] **Step 4: Run test to verify it fails**

Run: `node program_admin_console/tests/mail_service.test.js`  
Expected: FAIL because current mail service is stub and does not build SMTP mail payloads.

- [ ] **Step 5: Extend the server red test for rollback**

```js
const sendCode = await requestJson(ctx, "POST", "/api/auth/email/send-code", {email: "alice@example.com"});
assert.equal(sendCode.status, 503);
assert.equal(sendCode.body.reason, "mail_service_not_configured");
```

```js
const failedSend = await requestJson(ctx, "POST", "/api/auth/email/send-code", {email: "alice@example.com"});
assert.equal(failedSend.status, 502);
assert.equal(failedSend.body.reason, "mail_send_failed");
```

- [ ] **Step 6: Run server test to verify it fails**

Run: `node program_admin_console/tests/control-plane-server.test.js`  
Expected: FAIL because current server always treats mail as configured and does not rollback on send failure.

### Task 2: Implement SMTP config, service, and route guards

**Files:**
- Modify: `program_admin_console/src/mailConfig.js`
- Modify: `program_admin_console/src/mailService.js`
- Modify: `program_admin_console/src/server.js`
- Modify: `program_admin_console/package.json`

- [ ] **Step 1: Implement `mailConfig` using alchemy env names**

```js
const config = {
  fromName: ...,
  fromAddress: ...,
  smtpHost: ...,
  smtpPort: ...,
  smtpSecure: ...,
  smtpUser: ...,
  smtpPass: ...
};
```

- [ ] **Step 2: Implement `mailService` with `nodemailer` transport**

```js
const nodemailer = require("nodemailer");
return nodemailer.createTransport({...});
```

- [ ] **Step 3: Add route-level mail configuration checks and rollback**

```js
if (!config.configured) {
  writeError(res, 503, "mail_service_not_configured", "mail service not configured");
  return;
}
```

```js
const row = store.createEmailCode(...);
try {
  await mailService.sendVerificationCode(...);
} catch (error) {
  store.deleteEmailCode(row.id);
  writeError(res, 502, "mail_send_failed", ...);
  return;
}
```

- [ ] **Step 4: Add runtime dependency**

```json
"dependencies": {
  "nodemailer": "^6.10.0"
}
```

- [ ] **Step 5: Run targeted tests to verify green**

Run: `node program_admin_console/tests/mail_config.test.js`  
Expected: PASS

Run: `node program_admin_console/tests/mail_service.test.js`  
Expected: PASS

Run: `node program_admin_console/tests/control-plane-server.test.js`  
Expected: PASS

### Task 3: Update operator docs and run full affected verification

**Files:**
- Modify: `program_admin_console/README.md`
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if new stable rule emerges)

- [ ] **Step 1: Update README SMTP instructions**

Document the real env vars and remove stub wording.

- [ ] **Step 2: Update session log**

Record SMTP landing, verification status, and deployment follow-up.

- [ ] **Step 3: Run affected verification**

Run: `npm --prefix program_admin_console test`  
Expected: all control-plane tests pass

- [ ] **Step 4: Run dependency lockfile refresh if `package-lock.json` changes**

Run: `npm --prefix program_admin_console install`  
Expected: `package-lock.json` updated with `nodemailer`

- [ ] **Step 5: Re-run affected verification after lockfile refresh**

Run: `npm --prefix program_admin_console test`  
Expected: all control-plane tests pass
