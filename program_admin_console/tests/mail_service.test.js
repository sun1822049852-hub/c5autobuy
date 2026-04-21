const assert = require("node:assert/strict");

const {createMailService} = require("../src/mailService");

async function run() {
  const sent = [];
  const service = createMailService({
    config: {
      configured: true,
      provider: "qq",
      fromName: "C5 交易助手",
      fromAddress: "bot@example.com",
      smtpHost: "smtp.qq.com",
      smtpPort: 465,
      smtpSecure: true,
      smtpUser: "smtp-user",
      smtpPass: "smtp-pass",
      authCodeTtlMinutes: 5
    },
    transport: {
      async sendMail(payload) {
        sent.push(payload);
        return payload;
      }
    }
  });

  const register = await service.sendVerificationCode({
    to: "alice@example.com",
    code: "123456",
    scene: "register",
    ttlMinutes: 5
  });
  assert.equal(register.to, "alice@example.com");
  assert.equal(register.from, "C5 交易助手 <bot@example.com>");
  assert.equal(register.subject, "C5 交易助手 注册验证码");
  assert.match(register.text, /123456/);
  assert.match(register.text, /完成注册/);

  const reset = await service.sendVerificationCode({
    to: "alice@example.com",
    code: "654321",
    scene: "reset_password",
    ttlMinutes: 10
  });
  assert.equal(reset.to, "alice@example.com");
  assert.equal(reset.subject, "C5 交易助手 密码重置验证码");
  assert.match(reset.text, /654321/);
  assert.match(reset.text, /重置密码/);

  const capabilities = service.getCapabilities();
  assert.equal(capabilities.configured, true);
  assert.equal(capabilities.provider, "qq");
  assert.equal(capabilities.fromAddress, "bot@example.com");
  assert.equal(sent.length, 2);

  console.log("mail-service tests passed");
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
