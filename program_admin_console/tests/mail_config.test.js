const assert = require("node:assert/strict");

const {getMailConfig} = require("../src/mailConfig");

function run() {
  const defaultConfig = getMailConfig({});
  assert.equal(defaultConfig.configured, false);
  assert.equal(defaultConfig.smtpHost, "smtp.qq.com");
  assert.equal(defaultConfig.smtpPort, 465);
  assert.equal(defaultConfig.smtpSecure, true);
  assert.equal(defaultConfig.keyId, "");
  assert.equal(defaultConfig.fromName, "C5 交易助手");
  assert.equal(defaultConfig.fromAddress, "");

  const configured = getMailConfig({
    PROGRAM_ADMIN_HOST: "0.0.0.0",
    PROGRAM_ADMIN_PORT: "8787",
    PROGRAM_ADMIN_AUTH_CODE_TTL_MINUTES: "9",
    PROGRAM_ADMIN_REFRESH_SESSION_DAYS: "45",
    PROGRAM_ADMIN_ADMIN_SESSION_HOURS: "24",
    PROGRAM_ADMIN_SNAPSHOT_TTL_MINUTES: "18",
    PROGRAM_ADMIN_RUNTIME_PERMIT_TTL_SECONDS: "240",
    PROGRAM_ADMIN_SIGNING_KID: "smtp-kid",
    PROGRAM_ADMIN_PRIVATE_KEY_FILE: "/tmp/private.pem",
    MAIL_FROM: "bot@example.com",
    MAIL_FROM_NAME: "C5 交易助手",
    QQ_SMTP_HOST: "smtp.example.com",
    QQ_SMTP_PORT: "2525",
    QQ_SMTP_SECURE: "false",
    QQ_SMTP_USER: "smtp-user",
    QQ_SMTP_PASS: "smtp-pass"
  });

  assert.equal(configured.configured, true);
  assert.equal(configured.host, "0.0.0.0");
  assert.equal(configured.port, 8787);
  assert.equal(configured.authCodeTtlMinutes, 9);
  assert.equal(configured.refreshSessionDays, 45);
  assert.equal(configured.adminSessionHours, 24);
  assert.equal(configured.snapshotTtlMinutes, 18);
  assert.equal(configured.runtimePermitTtlSeconds, 240);
  assert.equal(configured.keyId, "smtp-kid");
  assert.equal(configured.privateKeyFile, "/tmp/private.pem");
  assert.equal(configured.fromName, "C5 交易助手");
  assert.equal(configured.fromAddress, "bot@example.com");
  assert.equal(configured.smtpHost, "smtp.example.com");
  assert.equal(configured.smtpPort, 2525);
  assert.equal(configured.smtpSecure, false);
  assert.equal(configured.smtpUser, "smtp-user");
  assert.equal(configured.smtpPass, "smtp-pass");

  console.log("mail-config tests passed");
}

run();
