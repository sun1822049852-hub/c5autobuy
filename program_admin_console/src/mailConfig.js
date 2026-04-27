function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

function toNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function toBoolean(value, fallback = false) {
  const text = toText(value).toLowerCase();
  if (!text) {
    return fallback;
  }
  if (["1", "true", "yes", "on"].includes(text)) {
    return true;
  }
  if (["0", "false", "no", "off"].includes(text)) {
    return false;
  }
  return fallback;
}

function getMailConfig(env = process.env) {
  const fromAddress = toText(env.MAIL_FROM);
  const smtpUser = toText(env.QQ_SMTP_USER);
  const smtpPass = toText(env.QQ_SMTP_PASS);
  return {
    host: toText(env.PROGRAM_ADMIN_HOST) || "127.0.0.1",
    port: toNumber(env.PROGRAM_ADMIN_PORT, 3030),
    configured: !!(fromAddress && smtpUser && smtpPass),
    authCodeTtlMinutes: toNumber(env.PROGRAM_ADMIN_AUTH_CODE_TTL_MINUTES, 5),
    refreshSessionDays: toNumber(env.PROGRAM_ADMIN_REFRESH_SESSION_DAYS, 30),
    adminSessionHours: toNumber(env.PROGRAM_ADMIN_ADMIN_SESSION_HOURS, 12),
    snapshotTtlMinutes: toNumber(env.PROGRAM_ADMIN_SNAPSHOT_TTL_MINUTES, 30),
    runtimePermitTtlSeconds: toNumber(env.PROGRAM_ADMIN_RUNTIME_PERMIT_TTL_SECONDS, 120),
    keyId: toText(env.PROGRAM_ADMIN_SIGNING_KID),
    privateKeyFile: toText(env.PROGRAM_ADMIN_PRIVATE_KEY_FILE),
    provider: "qq",
    fromName: toText(env.MAIL_FROM_NAME) || "C5 交易助手",
    fromAddress,
    smtpHost: toText(env.QQ_SMTP_HOST) || "smtp.qq.com",
    smtpPort: toNumber(env.QQ_SMTP_PORT, 465),
    smtpSecure: toBoolean(env.QQ_SMTP_SECURE, true),
    smtpUser,
    smtpPass
  };
}

module.exports = {
  getMailConfig
};
