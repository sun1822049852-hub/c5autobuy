const UNLOCKED_AUTH_STATES = new Set(["active", "grace", "refresh_due"]);

const MESSAGE_BY_CODE = Object.freeze({
  invalid_credentials: "账号或密码错误。",
  program_auth_not_ready: "会员服务暂未就绪",
  program_auth_required: "请先登录",
  program_device_conflict: "当前会员已在另一台设备登录",
  program_feature_not_enabled: "尚无会员",
  program_grace_limited: "当前处于宽限期，暂不允许新的关键动作",
  program_guard_bypassed_dev_only: "仅开发模式可用",
  program_membership_expired: "会员已过期",
  program_membership_service_unavailable: "服务器连接失败请检查网络设置。",
  program_permit_denied: "当前访问权限不足",
  program_remote_unavailable: "服务器连接失败请检查网络设置。",
  service_unavailable: "服务器连接失败请检查网络设置。",
});

export function resolveProgramAccessMessage({
  authState = "",
  code = "",
  guardEnabled = false,
  message = "",
  mode = "",
  username = "",
} = {}) {
  const normalizedCode = String(code || "").trim();
  const normalizedMessage = String(message || "").trim();
  const normalizedUsername = String(username || "").trim();
  const normalizedAuthState = String(authState || "").trim();

  if (normalizedCode && MESSAGE_BY_CODE[normalizedCode]) {
    if (normalizedCode === "program_auth_required" && normalizedUsername) {
      return "尚无会员";
    }
    return MESSAGE_BY_CODE[normalizedCode];
  }

  if (
    normalizedMessage === "invalid credentials"
    || normalizedMessage === "用户名或者密码错误"
    || normalizedMessage === "用户名或密码错误"
  ) {
    return "账号或密码错误。";
  }

  if (
    normalizedMessage === "请先登录程序会员"
    || normalizedMessage === "需要先登录程序会员"
  ) {
    return normalizedUsername ? "尚无会员" : "请先登录";
  }

  if (
    normalizedMessage === "账号已创建，但当前未开通会员"
    || normalizedMessage === "当前套餐暂未开放该功能"
  ) {
    return "尚无会员";
  }

  if (
    mode === "remote_entitlement"
    && guardEnabled
    && !UNLOCKED_AUTH_STATES.has(normalizedAuthState)
  ) {
    return normalizedUsername ? "尚无会员" : "请先登录";
  }

  return normalizedMessage;
}
