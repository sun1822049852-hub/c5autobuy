import { useEffect, useState } from "react";

import { resolveProgramAccessMessage } from "./program_access_messages.js";
import { hasRemoteProgramSession } from "./program_access_readonly.js";


const LOGIN_FORM_TEMPLATE = Object.freeze({
  username: "",
  password: "",
});

const REGISTER_FORM_TEMPLATE = Object.freeze({
  email: "",
  code: "",
  username: "",
  password: "",
});

const RESET_FORM_TEMPLATE = Object.freeze({
  email: "",
  code: "",
  newPassword: "",
  confirmPassword: "",
});

const REGISTER_STEP_EMAIL = "register_email";
const REGISTER_STEP_CODE = "register_code";
const REGISTER_STEP_CREDENTIALS = "register_credentials";
const REGISTER_STEP_SUCCESS = "register_success";
const REGISTER_EMAIL_LOCAL_PATTERN = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$/;
const REGISTER_EMAIL_DOMAIN_LABEL_PATTERN = /^[A-Za-z0-9-]+$/;
const BLOCKED_REGISTER_EMAIL_DOMAIN_TYPOS = new Set([
  "qq.co",
]);


function resolveAuthStateLabel(authState) {
  if (authState === "active") {
    return "已生效";
  }
  if (authState === "grace") {
    return "宽限中";
  }
  if (authState === "refresh_due") {
    return "待续证";
  }
  if (authState === "revoked") {
    return "已停用";
  }
  return authState || "未登录";
}


function resolveRuntimeStateLabel(runtimeState) {
  if (runtimeState === "running") {
    return "运行中";
  }
  if (runtimeState === "paused") {
    return "已暂停";
  }
  if (runtimeState === "stopped") {
    return "未运行";
  }
  return runtimeState || "未运行";
}


function resolveProgramAuthError(access, lastProgramAuthError) {
  if (lastProgramAuthError?.code) {
    return {
      code: lastProgramAuthError.code,
      message: resolveProgramAccessMessage({
        authState: access?.authState,
        code: lastProgramAuthError.code,
        guardEnabled: access?.guardEnabled,
        message: lastProgramAuthError.message || "程序会员接口暂不可用",
        mode: access?.mode,
        username: access?.username,
      }),
    };
  }

  if (access?.lastErrorCode) {
    return {
      code: String(access.lastErrorCode),
      message: resolveProgramAccessMessage({
        authState: access?.authState,
        code: String(access.lastErrorCode),
        guardEnabled: access?.guardEnabled,
        message: String(access.message || "程序会员状态异常"),
        mode: access?.mode,
        username: access?.username,
      }),
    };
  }

  return null;
}


function resolveSidebarAccountLabel(access) {
  const username = String(access?.username || "").trim();
  return username || "未登录";
}


function resolveSidebarHint(access) {
  return hasRemoteProgramSession(access)
    ? "已授权，可编辑"
    : "无权限，仅只读";
}


async function noopAsync() {
  return null;
}


function resolveBusyLabel(action, idleText, busyText, busyAction) {
  return busyAction === action ? busyText : idleText;
}

function resolveDialogTitle({ isLocalPassThrough, hasRemoteSession, authMode }) {
  if (isLocalPassThrough) {
    return "本地调试模式";
  }
  if (hasRemoteSession) {
    return "账号状态";
  }
  if (authMode === "register") {
    return "注册";
  }
  if (authMode === "reset") {
    return "找回密码";
  }
  return "登录";
}


function tryParseJsonPayload(rawValue) {
  if (typeof rawValue !== "string" || !rawValue.trim()) {
    return null;
  }

  try {
    return JSON.parse(rawValue);
  } catch {
    return null;
  }
}


function extractProgramAuthActionErrorDetail(error) {
  const payload = tryParseJsonPayload(String(error?.responseText || error?.message || ""));
  if (!payload || typeof payload !== "object") {
    return null;
  }

  if (payload.detail && typeof payload.detail === "object" && typeof payload.detail.code === "string") {
    return {
      code: String(payload.detail.code),
      message: String(payload.detail.message || ""),
      retryAfterSeconds: Number.isFinite(Number(payload.detail.retry_after_seconds))
        ? Math.max(0, Number(payload.detail.retry_after_seconds))
        : null,
    };
  }

  if (typeof payload.error_code === "string") {
    return {
      code: String(payload.error_code),
      message: String(payload.message || ""),
      retryAfterSeconds: Number.isFinite(Number(payload.retry_after_seconds))
        ? Math.max(0, Number(payload.retry_after_seconds))
        : null,
    };
  }

  return null;
}


function hasValidRegisterEmail(email) {
  const normalized = String(email || "").trim().toLowerCase();
  if (!normalized || normalized.length > 254) {
    return false;
  }
  const parts = normalized.split("@");
  if (parts.length !== 2) {
    return false;
  }
  const [local = "", domain = ""] = parts;
  if (!local || !domain || local.length > 64) {
    return false;
  }
  if (
    local.startsWith(".")
    || local.endsWith(".")
    || local.includes("..")
    || !REGISTER_EMAIL_LOCAL_PATTERN.test(local)
  ) {
    return false;
  }
  if (BLOCKED_REGISTER_EMAIL_DOMAIN_TYPOS.has(domain)) {
    return false;
  }
  const labels = domain.split(".");
  if (labels.length < 2) {
    return false;
  }
  const topLevelDomain = labels[labels.length - 1] || "";
  if (!/^[a-z]{2,24}$/.test(topLevelDomain)) {
    return false;
  }
  return labels.every((label) => (
    label
    && !label.startsWith("-")
    && !label.endsWith("-")
    && REGISTER_EMAIL_DOMAIN_LABEL_PATTERN.test(label)
  ));
}


function resolveRegisterErrorMessage(code, fallbackMessage) {
  switch (String(code || "")) {
    case "program_remote_unavailable":
    case "program_membership_service_unavailable":
    case "service_unavailable":
      return "服务器连接失败请检查网络设置。";
    case "REGISTER_INPUT_INVALID":
      return "请输入有效邮箱地址。";
    case "REGISTER_SEND_RETRY_LATER":
    case "REGISTER_SERVICE_UNAVAILABLE":
      return "无法继续注册，请稍后再试。";
    case "REGISTER_SEND_DENIED":
      return "当前邮箱无法继续注册，请直接登录或找回密码。";
    case "REGISTER_CODE_INVALID_OR_EXPIRED":
    case "REGISTER_CODE_ATTEMPTS_EXCEEDED":
    case "REGISTER_SESSION_EMAIL_MISMATCH":
    case "REGISTER_SESSION_INVALID":
      return "验证码错误或已失效，请重新获取。";
    case "REGISTER_TICKET_INVALID_OR_EXPIRED":
      return "注册已失效，请重新验证邮箱。";
    case "REGISTER_USERNAME_INVALID":
      return "账号名格式不正确，请重新填写。";
    case "REGISTER_USERNAME_TAKEN":
      return "账号名已被使用。";
    case "REGISTER_PASSWORD_WEAK":
      return "密码至少 8 位且需同时包含字母和数字。";
    case "REGISTER_EMAIL_UNAVAILABLE":
      return "当前邮箱无法继续注册，请直接登录或找回密码。";
    default:
      return fallbackMessage;
  }
}


function resolveProgramAuthActionFailureMessage(detail, fallbackMessage) {
  if (detail?.code) {
    return resolveProgramAccessMessage({
      code: detail.code,
      message: detail.message || fallbackMessage,
    });
  }
  return fallbackMessage;
}


function resolveProgramAccessSummary(resultSummary, access) {
  if (!resultSummary || typeof resultSummary !== "object") {
    return access;
  }

  return {
    ...access,
    mode: String(resultSummary.mode || access?.mode || ""),
    guardEnabled: Boolean(resultSummary.guardEnabled ?? resultSummary.guard_enabled ?? access?.guardEnabled),
    authState: String(resultSummary.authState || resultSummary.auth_state || access?.authState || ""),
  };
}

function shouldSuppressProgramAuthError(error) {
  return String(error?.code || "") === "program_auth_required";
}


function resolveRegistrationFlowVersion(access) {
  return Number(access?.registrationFlowVersion ?? access?.registration_flow_version ?? 2);
}


export function ProgramAccessSidebarCard({
  access,
  guardError = null,
  lastProgramAuthError = null,
  refreshProgramAuthStatus = noopAsync,
  loginProgramAuth = noopAsync,
  logoutProgramAuth = noopAsync,
  sendRegisterCode = noopAsync,
  verifyRegisterCode = undefined,
  completeRegisterProgramAuth = undefined,
  sendResetPasswordCode = noopAsync,
  resetProgramAuthPassword = noopAsync,
}) {
  const [authMode, setAuthMode] = useState("login");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [loginForm, setLoginForm] = useState(LOGIN_FORM_TEMPLATE);
  const [registerForm, setRegisterForm] = useState(REGISTER_FORM_TEMPLATE);
  const [registerStep, setRegisterStep] = useState(REGISTER_STEP_EMAIL);
  const [registerSessionId, setRegisterSessionId] = useState("");
  const [registerSessionEmail, setRegisterSessionEmail] = useState("");
  const [maskedRegisterEmail, setMaskedRegisterEmail] = useState("");
  const [verificationTicket, setVerificationTicket] = useState("");
  const [isRegisterEditingEmail, setIsRegisterEditingEmail] = useState(false);
  const [registerResendCooldownSeconds, setRegisterResendCooldownSeconds] = useState(0);
  const [resetForm, setResetForm] = useState(RESET_FORM_TEMPLATE);
  const [isResetPasswordVisible, setIsResetPasswordVisible] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const [formError, setFormError] = useState("");
  const [formNotice, setFormNotice] = useState("");
  const isLocalPassThrough = access?.mode === "local_pass_through";
  const hasRemoteSession = !isLocalPassThrough && hasRemoteProgramSession(access);
  const registrationFlowVersion = resolveRegistrationFlowVersion(access);
  const hasRegisterV3Bridge = typeof verifyRegisterCode === "function"
    && typeof completeRegisterProgramAuth === "function";
  const sidebarAccountLabel = resolveSidebarAccountLabel(access);
  const sidebarHint = resolveSidebarHint(access);
  const programAuthError = !isLocalPassThrough
    ? resolveProgramAuthError(access, lastProgramAuthError)
    : null;
  const visibleProgramAuthError = shouldSuppressProgramAuthError(programAuthError) ? null : programAuthError;
  const dialogTitle = resolveDialogTitle({
    isLocalPassThrough,
    hasRemoteSession,
    authMode,
  });

  useEffect(() => {
    if (authMode !== "register" || registerResendCooldownSeconds <= 0) {
      return undefined;
    }

    const timer = globalThis.setTimeout(() => {
      setRegisterResendCooldownSeconds((current) => Math.max(0, current - 1));
    }, 1000);

    return () => {
      globalThis.clearTimeout(timer);
    };
  }, [authMode, registerStep, registerResendCooldownSeconds]);

  function clearLocalFeedback() {
    setFormError("");
    setFormNotice("");
  }

  function resetRegisterFlow({ preserveEmail = false, preserveCooldown = false } = {}) {
    setRegisterStep(REGISTER_STEP_EMAIL);
    setRegisterSessionId("");
    setRegisterSessionEmail("");
    setMaskedRegisterEmail("");
    setVerificationTicket("");
    setIsRegisterEditingEmail(false);
    setRegisterResendCooldownSeconds((current) => (preserveCooldown ? current : 0));
    setRegisterForm((current) => ({
      ...REGISTER_FORM_TEMPLATE,
      email: preserveEmail ? current.email : "",
    }));
  }

  function switchAuthMode(nextMode) {
    clearLocalFeedback();
    if (nextMode !== "reset") {
      setIsResetPasswordVisible(false);
    }
    if (authMode === "register" && nextMode !== "register" && registerStep === REGISTER_STEP_SUCCESS) {
      resetRegisterFlow({ preserveEmail: true });
    }
    setAuthMode(nextMode);
    if (
      nextMode === "register"
      && authMode !== "register"
      && !isLocalPassThrough
      && !hasRemoteSession
      && registrationFlowVersion !== 3
    ) {
      Promise.resolve(refreshProgramAuthStatus()).catch(() => {});
    }
  }

  function openDialog() {
    setIsDialogOpen(true);
  }

  function closeDialog() {
    clearLocalFeedback();
    setIsResetPasswordVisible(false);
    if (!(authMode === "register" && registerStep === REGISTER_STEP_CODE)) {
      if (authMode === "register") {
        resetRegisterFlow({ preserveEmail: true, preserveCooldown: true });
      }
      setAuthMode("login");
    }
    setIsDialogOpen(false);
  }

  async function runFormAction(action, invoke, { onSuccess = null } = {}) {
    clearLocalFeedback();
    setBusyAction(action);
    try {
      const result = await invoke();
      if (typeof onSuccess === "function") {
        onSuccess(result);
      }
      setFormNotice(String(result?.message || ""));
      return result;
    } catch (error) {
      if (!programAuthError) {
        setFormError("程序会员操作失败，请稍后再试。");
      }
      throw error;
    } finally {
      setBusyAction("");
    }
  }

  async function handleRemoteRefresh() {
    try {
      await runFormAction("refresh", () => refreshProgramAuthStatus(), {
        onSuccess() {
          setFormNotice("程序会员状态已刷新");
        },
      });
    } catch {
      setFormError("刷新程序会员状态失败，请稍后再试。");
    }
  }

  async function handleRemoteLogin() {
    const username = loginForm.username.trim();
    const password = loginForm.password;

    if (!username || !password) {
      setFormError("请先填写程序会员账号和密码。");
      return;
    }

    try {
      await runFormAction("login", () => loginProgramAuth({
        username,
        password,
      }), {
        onSuccess() {
          setLoginForm({
            ...LOGIN_FORM_TEMPLATE,
            username,
          });
        },
      });
    } catch (error) {
      const detail = extractProgramAuthActionErrorDetail(error);
      if (detail) {
        setFormError(resolveProgramAuthActionFailureMessage(detail, "程序会员登录失败"));
        return;
      }
      setFormError("程序会员登录暂不可用，请稍后再试。");
    }
  }

  async function handleRemoteLogout() {
    try {
      await runFormAction("logout", () => logoutProgramAuth(), {
        onSuccess() {
          setAuthMode("login");
          setLoginForm(LOGIN_FORM_TEMPLATE);
        },
      });
    } catch {
      setFormError("程序会员退出失败，请稍后再试。");
    }
  }

  async function handleSendRegisterCode() {
    const email = registerForm.email.trim();
    if (!hasValidRegisterEmail(email)) {
      setFormError("请输入有效邮箱地址。");
      return;
    }

    clearLocalFeedback();
    setBusyAction("send-register-code");
    try {
      const result = await sendRegisterCode({ email });
      setRegisterStep(REGISTER_STEP_CODE);
      setRegisterSessionId(String(result?.register_session_id || ""));
      setRegisterSessionEmail(email);
      setMaskedRegisterEmail(String(result?.masked_email || ""));
      setVerificationTicket("");
      setIsRegisterEditingEmail(false);
      setRegisterResendCooldownSeconds(Math.max(0, Number(result?.resend_after_seconds || 0)));
      setRegisterForm({
        ...REGISTER_FORM_TEMPLATE,
        email,
      });
      setFormNotice(String(result?.message || ""));
    } catch (error) {
      const detail = extractProgramAuthActionErrorDetail(error);
      if (detail?.retryAfterSeconds != null) {
        setRegisterResendCooldownSeconds(detail.retryAfterSeconds);
      }
      setFormError(resolveRegisterErrorMessage(detail?.code, "注册验证码发送失败，请稍后再试。"));
    } finally {
      setBusyAction("");
    }
  }

  async function handleVerifyRegisterCode() {
    if (typeof verifyRegisterCode !== "function") {
      setFormError("注册链路暂未就绪，请稍后再试。");
      return;
    }

    const email = registerSessionEmail || registerForm.email.trim();
    const code = registerForm.code.trim();

    if (!code) {
      setFormError("请先填写注册验证码。");
      return;
    }

    clearLocalFeedback();
    setBusyAction("verify-register-code");
    try {
      const result = await verifyRegisterCode({
        email,
        code,
        registerSessionId: registerSessionId || undefined,
      });
      setRegisterStep(REGISTER_STEP_CREDENTIALS);
      setVerificationTicket(String(result?.verification_ticket || ""));
      setRegisterForm((current) => ({
        ...current,
        code,
        username: "",
        password: "",
      }));
      setFormNotice(String(result?.message || ""));
    } catch (error) {
      const detail = extractProgramAuthActionErrorDetail(error);
      const errorCode = String(detail?.code || "");
      if (
        errorCode === "REGISTER_SESSION_INVALID"
        || errorCode === "REGISTER_SESSION_EMAIL_MISMATCH"
        || errorCode === "REGISTER_CODE_ATTEMPTS_EXCEEDED"
      ) {
        setRegisterSessionId("");
        setRegisterSessionEmail("");
        setVerificationTicket("");
      }
      setRegisterForm((current) => ({
        ...current,
        code: "",
      }));
      setFormError(resolveRegisterErrorMessage(detail?.code, "验证码验证失败，请稍后再试。"));
    } finally {
      setBusyAction("");
    }
  }

  async function handleResendRegisterCode() {
    if (registerResendCooldownSeconds > 0) {
      return;
    }
    await handleSendRegisterCode();
  }

  function handleReturnToRegisterEmailStep() {
    clearLocalFeedback();
    setIsRegisterEditingEmail(true);
    setRegisterStep(REGISTER_STEP_EMAIL);
    setRegisterForm((current) => ({
      ...current,
      email: registerSessionEmail || current.email,
    }));
  }

  function handleCancelRegisterEmailEdit() {
    clearLocalFeedback();
    setIsRegisterEditingEmail(false);
    setRegisterStep(REGISTER_STEP_CODE);
    setRegisterForm((current) => ({
      ...current,
      email: registerSessionEmail || current.email,
    }));
  }

  async function handleRegisterSubmit() {
    if (!hasRegisterV3Bridge) {
      setFormError("注册链路暂未就绪，请稍后再试。");
      return;
    }

    const email = registerSessionEmail || registerForm.email.trim();
    const username = registerForm.username.trim();
    const password = registerForm.password;

    if (!username || !password) {
      setFormError("请先填写完整的注册信息。");
      return;
    }

    clearLocalFeedback();
    setBusyAction("complete-register");
    try {
      const result = await completeRegisterProgramAuth({
        email,
        verificationTicket,
        username,
        password,
      });
      const nextAccess = resolveProgramAccessSummary(result?.summary, access);
      setVerificationTicket("");
      setRegisterForm((current) => ({
        ...current,
        email,
        username: "",
        password: "",
      }));
      setFormNotice(String(result?.message || ""));
      setLoginForm((current) => ({
        ...current,
        username,
      }));
      if (hasRemoteProgramSession(nextAccess)) {
        resetRegisterFlow();
        setAuthMode("login");
        setIsDialogOpen(false);
        return;
      }
      setRegisterStep(REGISTER_STEP_SUCCESS);
    } catch (error) {
      const detail = extractProgramAuthActionErrorDetail(error);
      if (String(detail?.code || "") === "REGISTER_TICKET_INVALID_OR_EXPIRED") {
        setVerificationTicket("");
        setRegisterStep(REGISTER_STEP_CODE);
        setRegisterForm((current) => ({
          ...current,
          username: "",
          password: "",
        }));
      }
      setFormError(resolveRegisterErrorMessage(detail?.code, "注册失败，请稍后再试。"));
    } finally {
      setBusyAction("");
    }
  }

  async function handleSendResetPasswordCode() {
    const email = resetForm.email.trim();
    if (!hasValidRegisterEmail(email)) {
      setFormError("请输入有效邮箱地址。");
      return;
    }

    try {
      await runFormAction("send-reset-password-code", () => sendResetPasswordCode({ email }));
    } catch (error) {
      const detail = extractProgramAuthActionErrorDetail(error);
      setFormError(resolveProgramAuthActionFailureMessage(detail, "找回密码验证码发送失败，请稍后再试。"));
    }
  }

  async function handleResetPasswordSubmit() {
    const payload = {
      email: resetForm.email.trim(),
      code: resetForm.code.trim(),
      newPassword: resetForm.newPassword,
    };
    const confirmPassword = resetForm.confirmPassword;

    if (!payload.email || !payload.code || !payload.newPassword || !confirmPassword) {
      setFormError("请先填写完整的找回密码信息。");
      return;
    }
    if (payload.newPassword !== confirmPassword) {
      setFormError("两次输入的新密码不一致。");
      return;
    }

    try {
      await runFormAction("reset-password", () => resetProgramAuthPassword(payload), {
        onSuccess() {
          setResetForm((current) => ({
            ...current,
            code: "",
            newPassword: "",
            confirmPassword: "",
          }));
          setIsResetPasswordVisible(false);
        },
      });
    } catch (error) {
      const detail = extractProgramAuthActionErrorDetail(error);
      setFormError(resolveProgramAuthActionFailureMessage(detail, "密码重置失败，请稍后再试。"));
    }
  }

  function renderDialogAlerts() {
    const visibleGuardError = shouldSuppressProgramAuthError(guardError) ? null : guardError;

    return (
      <>
        {visibleProgramAuthError ? (
          <div className="program-access-sidebar-card__guard-error" role="alert">
            <span>{visibleProgramAuthError.message}</span>
          </div>
        ) : null}
        {visibleGuardError ? (
          <div className="program-access-sidebar-card__guard-error" role="alert">
            <span>{visibleGuardError.message}</span>
          </div>
        ) : null}
      </>
    );
  }

  function renderDialogFeedback() {
    const feedbackText = formError || formNotice;
    if (!feedbackText) {
      return null;
    }

    const isError = Boolean(formError);
    return (
      <div
        aria-live={isError ? "assertive" : "polite"}
        className={`program-access-dialog__feedback-toast${isError ? " is-error" : " is-notice"}`}
        role={isError ? "alert" : "status"}
      >
        {feedbackText}
      </div>
    );
  }

  function renderLoggedInDialog() {
    return (
      <div className="program-access-dialog__stack">
        <div className="program-access-sidebar-card__summary">
          <div className="program-access-sidebar-card__summary-row">
            <span className="program-access-sidebar-card__summary-label">当前账号</span>
            <strong className="program-access-sidebar-card__summary-value">{sidebarAccountLabel}</strong>
          </div>
          <div className="program-access-sidebar-card__summary-row">
            <span className="program-access-sidebar-card__summary-label">当前账号状态</span>
            <strong className="program-access-sidebar-card__summary-value">
              {resolveAuthStateLabel(access?.authState)}
            </strong>
          </div>
          <div className="program-access-sidebar-card__summary-row">
            <span className="program-access-sidebar-card__summary-label">运行状态</span>
            <strong className="program-access-sidebar-card__summary-value">
              {resolveRuntimeStateLabel(access?.runtimeState)}
            </strong>
          </div>
          {access?.graceExpiresAt ? (
            <div className="program-access-sidebar-card__summary-row">
              <span className="program-access-sidebar-card__summary-label">宽限到</span>
              <strong className="program-access-sidebar-card__summary-value">{access.graceExpiresAt}</strong>
            </div>
          ) : null}
        </div>
        {renderDialogFeedback()}
        <div className="surface-actions program-access-dialog__actions">
          <button
            className="ghost-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
            type="button"
            disabled={Boolean(busyAction)}
            onClick={() => void handleRemoteLogout()}
          >
            {resolveBusyLabel("logout", "退出", "退出中...", busyAction)}
          </button>
        </div>
      </div>
    );
  }

  function renderLocalPassThroughDialog() {
    return (
      <div className="program-access-dialog__stack">
        <div className="program-access-sidebar-card__notice" role="status">本地调试模式</div>
      </div>
    );
  }

  function renderLoggedOutDialog() {
    const registerEmail = registerForm.email.trim();

    function renderRegisterV3Form() {
      const registerDisplayEmail = maskedRegisterEmail || registerSessionEmail || registerEmail;

      if (registerStep === REGISTER_STEP_CODE) {
        return (
          <div className="program-access-sidebar-card__form">
            <div className="program-access-sidebar-card__summary">
              <div className="program-access-sidebar-card__summary-row">
                <span className="program-access-sidebar-card__summary-label">注册邮箱</span>
                <strong className="program-access-sidebar-card__summary-value">
                  {registerDisplayEmail}
                </strong>
              </div>
            </div>
            <label className="program-access-sidebar-card__field">
              <span className="program-access-sidebar-card__field-label">注册验证码</span>
              <input
                aria-label="注册验证码"
                className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
                placeholder="请输入验证码"
                type="text"
                value={registerForm.code}
                onChange={(event) => {
                  setRegisterForm((current) => ({
                    ...current,
                    code: event.target.value,
                  }));
                }}
              />
            </label>
            <div className="surface-actions program-access-dialog__actions">
              <button
                className="accent-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                type="button"
                disabled={Boolean(busyAction) || !registerForm.code.trim()}
                onClick={() => void handleVerifyRegisterCode()}
              >
                {resolveBusyLabel("verify-register-code", "验证注册验证码", "验证中...", busyAction)}
              </button>
              <button
                className="ghost-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                type="button"
                disabled={Boolean(busyAction) || registerResendCooldownSeconds > 0}
                onClick={() => void handleResendRegisterCode()}
              >
                {busyAction === "send-register-code"
                  ? "发送中..."
                  : registerResendCooldownSeconds > 0
                    ? `重新发送验证码 (${registerResendCooldownSeconds}s)`
                    : "重新发送验证码"}
              </button>
              <button
                className="ghost-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                type="button"
                disabled={Boolean(busyAction)}
                onClick={handleReturnToRegisterEmailStep}
              >
                修改邮箱
              </button>
            </div>
          </div>
        );
      }

      if (registerStep === REGISTER_STEP_CREDENTIALS) {
        return (
          <div className="program-access-sidebar-card__form">
            <div className="program-access-sidebar-card__summary">
              <div className="program-access-sidebar-card__summary-row">
                <span className="program-access-sidebar-card__summary-label">已验证邮箱</span>
                <strong className="program-access-sidebar-card__summary-value">
                  {registerDisplayEmail}
                </strong>
              </div>
            </div>
            <label className="program-access-sidebar-card__field">
              <span className="program-access-sidebar-card__field-label">注册用户名</span>
              <input
                aria-label="注册用户名"
                className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
                placeholder="请输入注册用户名"
                type="text"
                value={registerForm.username}
                onChange={(event) => {
                  setRegisterForm((current) => ({
                    ...current,
                    username: event.target.value,
                  }));
                }}
              />
            </label>
            <label className="program-access-sidebar-card__field">
              <span className="program-access-sidebar-card__field-label">注册密码</span>
              <input
                aria-label="注册密码"
                className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
                placeholder="请输入注册密码"
                type="password"
                value={registerForm.password}
                onChange={(event) => {
                  setRegisterForm((current) => ({
                    ...current,
                    password: event.target.value,
                  }));
                }}
              />
            </label>
            <div className="surface-actions program-access-dialog__actions">
              <button
                className="accent-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                type="button"
                disabled={Boolean(busyAction) || !registerForm.username.trim() || !registerForm.password}
                onClick={() => void handleRegisterSubmit()}
              >
                {resolveBusyLabel("complete-register", "完成注册", "提交中...", busyAction)}
              </button>
              <button
                className="ghost-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                type="button"
                disabled={Boolean(busyAction)}
                onClick={() => {
                  clearLocalFeedback();
                  setVerificationTicket("");
                  setRegisterStep(REGISTER_STEP_CODE);
                  setRegisterForm((current) => ({
                    ...current,
                    username: "",
                    password: "",
                  }));
                }}
              >
                返回验证码
              </button>
            </div>
          </div>
        );
      }

      if (registerStep === REGISTER_STEP_SUCCESS) {
        return (
          <div className="program-access-dialog__stack">
            <div className="program-access-sidebar-card__notice" role="status">
              注册已完成，可返回登录或关闭窗口。
            </div>
            <div className="surface-actions program-access-dialog__actions">
              <button
                className="accent-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                type="button"
                disabled={Boolean(busyAction)}
                onClick={() => {
                  clearLocalFeedback();
                  resetRegisterFlow();
                  setAuthMode("login");
                }}
              >
                返回登录
              </button>
              <button
                className="ghost-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                type="button"
                disabled={Boolean(busyAction)}
                onClick={closeDialog}
              >
                关闭
              </button>
            </div>
          </div>
        );
      }

      return (
        <div className="program-access-sidebar-card__form">
          <label className="program-access-sidebar-card__field">
            <span className="program-access-sidebar-card__field-label">注册邮箱</span>
            <input
              aria-label="注册邮箱"
              className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
              placeholder="请输入注册邮箱"
              type="email"
              value={registerForm.email}
              onChange={(event) => {
                setRegisterForm((current) => ({
                  ...current,
                  email: event.target.value,
                }));
              }}
            />
          </label>
          <div className="surface-actions program-access-dialog__actions">
            <button
              className="accent-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
              type="button"
              disabled={Boolean(busyAction) || registerResendCooldownSeconds > 0}
              onClick={() => void handleSendRegisterCode()}
            >
              {busyAction === "send-register-code"
                ? "发送中..."
                : registerResendCooldownSeconds > 0
                  ? `发送注册验证码 (${registerResendCooldownSeconds}s)`
                  : "发送注册验证码"}
            </button>
            {isRegisterEditingEmail ? (
              <button
                className="ghost-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                type="button"
                disabled={Boolean(busyAction)}
                onClick={handleCancelRegisterEmailEdit}
              >
                取消
              </button>
            ) : null}
          </div>
        </div>
      );
    }

    return (
      <div className="program-access-dialog__stack">
        <div className="program-access-sidebar-card__auth">
          <div className="program-access-sidebar-card__tabs" aria-label="程序会员模式">
            {[
              { id: "login", label: "登录" },
              { id: "register", label: "注册" },
              { id: "reset", label: "找回密码" },
            ].map((item) => (
              <button
                key={item.id}
                aria-pressed={authMode === item.id}
                className={`program-access-sidebar-card__tab program-access-sidebar-card__tab--dense${authMode === item.id ? " is-active" : ""}`}
                type="button"
                onClick={() => switchAuthMode(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          {authMode === "login" ? (
            <div className="program-access-sidebar-card__form">
              <label className="program-access-sidebar-card__field">
                <span className="program-access-sidebar-card__field-label">登录账号</span>
                <input
                  aria-label="程序会员登录账号"
                  className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
                  placeholder="请输入账号"
                  type="text"
                  value={loginForm.username}
                  onChange={(event) => {
                    setLoginForm((current) => ({
                      ...current,
                      username: event.target.value,
                    }));
                  }}
                />
              </label>
              <label className="program-access-sidebar-card__field">
                <span className="program-access-sidebar-card__field-label">登录密码</span>
                <input
                  aria-label="程序会员登录密码"
                  className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
                  placeholder="请输入密码"
                  type="password"
                  value={loginForm.password}
                  onChange={(event) => {
                    setLoginForm((current) => ({
                      ...current,
                      password: event.target.value,
                    }));
                  }}
                />
              </label>
              <div className="surface-actions program-access-dialog__actions program-access-dialog__actions--submit-end">
                <button
                  className="accent-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                  type="button"
                  disabled={Boolean(busyAction)}
                  onClick={() => void handleRemoteLogin()}
                >
                  {resolveBusyLabel("login", "登录", "登录中...", busyAction)}
                </button>
              </div>
            </div>
          ) : null}

          {authMode === "register" ? (
            renderRegisterV3Form()
          ) : null}

          {authMode === "reset" ? (
            <div className="program-access-sidebar-card__form">
              <label className="program-access-sidebar-card__field">
                <span className="program-access-sidebar-card__field-label">找回密码邮箱</span>
                <input
                  aria-label="找回密码邮箱"
                  className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
                  placeholder="请输入找回邮箱"
                  type="email"
                  value={resetForm.email}
                  onChange={(event) => {
                    setResetForm((current) => ({
                      ...current,
                      email: event.target.value,
                    }));
                  }}
                />
              </label>
              <div className="program-access-sidebar-card__inline">
                <label className="program-access-sidebar-card__field">
                  <span className="program-access-sidebar-card__field-label">找回密码验证码</span>
                  <input
                    aria-label="找回密码验证码"
                    className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
                    placeholder="请输入验证码"
                    type="text"
                    value={resetForm.code}
                    onChange={(event) => {
                      setResetForm((current) => ({
                        ...current,
                        code: event.target.value,
                      }));
                    }}
                  />
                </label>
                <button
                  className="ghost-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                  type="button"
                  disabled={Boolean(busyAction)}
                  onClick={() => void handleSendResetPasswordCode()}
                >
                  {resolveBusyLabel("send-reset-password-code", "发送找回密码验证码", "发送中...", busyAction)}
                </button>
              </div>
              <div className="program-access-sidebar-card__inline program-access-sidebar-card__inline--password">
                <label className="program-access-sidebar-card__field program-access-sidebar-card__password-field">
                  <span className="program-access-sidebar-card__field-label">新密码</span>
                  <input
                    aria-label="新密码"
                    className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
                    placeholder="请输入新密码"
                    type={isResetPasswordVisible ? "text" : "password"}
                    value={resetForm.newPassword}
                    onChange={(event) => {
                      setResetForm((current) => ({
                        ...current,
                        newPassword: event.target.value,
                      }));
                    }}
                  />
                </label>
                <button
                  aria-label={isResetPasswordVisible ? "隐藏密码明文" : "显示密码明文"}
                  className="ghost-button program-access-sidebar-card__button program-access-sidebar-card__button--compact program-access-sidebar-card__password-toggle"
                  type="button"
                  disabled={Boolean(busyAction)}
                  onClick={() => setIsResetPasswordVisible((current) => !current)}
                >
                  {isResetPasswordVisible ? "隐藏密码明文" : "显示密码明文"}
                </button>
              </div>
              <label className="program-access-sidebar-card__field">
                <span className="program-access-sidebar-card__field-label">再次输入新密码</span>
                <input
                  aria-label="再次输入新密码"
                  className="program-access-sidebar-card__input program-access-sidebar-card__input--compact"
                  placeholder="请再次输入新密码"
                  type={isResetPasswordVisible ? "text" : "password"}
                  value={resetForm.confirmPassword}
                  onChange={(event) => {
                    setResetForm((current) => ({
                      ...current,
                      confirmPassword: event.target.value,
                    }));
                  }}
                />
              </label>
              <div className="surface-actions program-access-dialog__actions program-access-dialog__actions--submit-end">
                <button
                  className="accent-button program-access-sidebar-card__button program-access-sidebar-card__button--compact"
                  type="button"
                  disabled={Boolean(busyAction)}
                  onClick={() => void handleResetPasswordSubmit()}
                >
                  {resolveBusyLabel("reset-password", "提交新密码", "提交中...", busyAction)}
                </button>
              </div>
            </div>
          ) : null}
        </div>

        {renderDialogFeedback()}
      </div>
    );
  }

  return (
    <>
      <section className="program-access-sidebar-card" aria-label="程序会员区">
        <button
          aria-label="打开程序账号窗口"
          className="program-access-sidebar-card__entry"
          type="button"
          onClick={openDialog}
        >
          <span className="program-access-sidebar-card__eyebrow">登录状态：</span>
          <strong className="program-access-sidebar-card__entry-identity">{sidebarAccountLabel}</strong>
          <span className="program-access-sidebar-card__entry-hint">{sidebarHint}</span>
        </button>
      </section>

      {isDialogOpen ? (
        <div className="surface-backdrop" role="presentation">
          <section
            aria-label="程序账号"
            className="dialog-surface program-access-dialog program-access-dialog--fixed-size program-access-dialog--compact-shell program-access-dialog--dense-controls"
            data-dialog-size="fixed"
            role="dialog"
          >
            <div className="surface-header">
              <div>
                <div className="program-access-dialog__eyebrow">c5交易助手</div>
                <h2 className="surface-title">{dialogTitle}</h2>
              </div>
              <button
                aria-label="关闭"
                className="ghost-button program-access-dialog__close"
                type="button"
                onClick={closeDialog}
              >
                X
              </button>
            </div>

            {renderDialogAlerts()}

            {isLocalPassThrough
              ? renderLocalPassThroughDialog()
              : hasRemoteSession
                ? renderLoggedInDialog()
                : renderLoggedOutDialog()}
          </section>
        </div>
      ) : null}
    </>
  );
}
