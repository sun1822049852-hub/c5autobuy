export const PROGRAM_ACCESS_LOGIN_PLACEHOLDER = "程序会员登录后续接入";


export const EMPTY_PROGRAM_ACCESS = Object.freeze({
  mode: "",
  stage: "",
  guardEnabled: false,
  message: "",
  username: "",
  authState: "",
  runtimeState: "",
  graceExpiresAt: "",
  lastErrorCode: null,
  loginPlaceholderLabel: PROGRAM_ACCESS_LOGIN_PLACEHOLDER,
});


export function resolveProgramAccessPayload(payload) {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }

  if (payload.programAccess && typeof payload.programAccess === "object") {
    return payload.programAccess;
  }

  if (payload.program_access && typeof payload.program_access === "object") {
    return payload.program_access;
  }

  return undefined;
}


export function normalizeProgramAccess(payload) {
  if (!payload || typeof payload !== "object") {
    return EMPTY_PROGRAM_ACCESS;
  }

  return {
    mode: String(payload.mode || ""),
    stage: String(payload.stage || ""),
    guardEnabled: Boolean(payload.guardEnabled ?? payload.guard_enabled),
    message: String(payload.message || ""),
    username: String(payload.username || ""),
    authState: String(payload.authState || payload.auth_state || ""),
    runtimeState: String(payload.runtimeState || payload.runtime_state || ""),
    graceExpiresAt: String(payload.graceExpiresAt || payload.grace_expires_at || ""),
    lastErrorCode: payload.lastErrorCode ?? payload.last_error_code ?? null,
    loginPlaceholderLabel: String(
      payload.loginPlaceholderLabel
      || payload.login_placeholder_label
      || PROGRAM_ACCESS_LOGIN_PLACEHOLDER
    ),
  };
}
