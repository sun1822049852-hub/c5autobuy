function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

function buildFrom(config = {}) {
  const fromAddress = toText(config.fromAddress);
  const fromName = toText(config.fromName);
  if (!fromName) {
    return fromAddress;
  }
  return `${fromName} <${fromAddress}>`;
}

function resolveBrandName(config = {}) {
  return toText(config.fromName) || "C5 交易助手";
}

function buildVerificationMessage({brandName = "", scene = "", code = "", ttlMinutes = 5} = {}) {
  const sceneText = toText(scene);
  const title = sceneText === "reset_password" ? "密码重置验证码" : "注册验证码";
  const action = sceneText === "reset_password" ? "重置密码" : "完成注册";
  const brandText = toText(brandName) || "C5 交易助手";
  return {
    subject: `${brandText} ${title}`,
    text:
      `你的${title}为：${toText(code)}\n`
      + `有效期：${Number(ttlMinutes) || 5} 分钟\n`
      + `用途：${action}\n`
      + "若非本人操作，请忽略此邮件。"
  };
}

function createMailService({config = {}, transport = null, transportFactory = null} = {}) {
  const resolvedConfig = config && typeof config === "object" ? config : {};
  const resolvedTransport = transport
    || (typeof transportFactory === "function" ? transportFactory(resolvedConfig) : null)
    || (() => {
      const nodemailer = require("nodemailer");
      return nodemailer.createTransport({
        host: resolvedConfig.smtpHost,
        port: resolvedConfig.smtpPort,
        secure: !!resolvedConfig.smtpSecure,
        auth: {
          user: resolvedConfig.smtpUser,
          pass: resolvedConfig.smtpPass
        }
      });
    })();

  return {
    getCapabilities() {
      return {
        configured: !!resolvedConfig.configured,
        provider: toText(resolvedConfig.provider) || "qq",
        fromAddress: toText(resolvedConfig.fromAddress)
      };
    },
    async sendVerificationCode({to = "", code = "", scene = "", ttlMinutes = resolvedConfig.authCodeTtlMinutes} = {}) {
      const message = buildVerificationMessage({
        brandName: resolveBrandName(resolvedConfig),
        scene,
        code,
        ttlMinutes
      });
      return resolvedTransport.sendMail({
        from: buildFrom(resolvedConfig),
        to: toText(to),
        subject: message.subject,
        text: message.text
      });
    }
  };
}

module.exports = {
  createMailService
};
