import { useState } from "react";

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
});


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
      message: lastProgramAuthError.message || "程序会员接口暂不可用",
    };
  }

  if (access?.lastErrorCode) {
    return {
      code: String(access.lastErrorCode),
      message: String(access.message || "程序会员状态异常"),
    };
  }

  return null;
}


function resolveSidebarAccountLabel(access) {
  const username = String(access?.username || "").trim();
  return username || "未登录";
}


function resolveSidebarHint(access) {
  if (hasRemoteProgramSession(access)) {
    return "点击查看当前账号状态";
  }
  return "点击登录或管理程序账号";
}


async function noopAsync() {
  return null;
}


function resolveBusyLabel(action, idleText, busyText, busyAction) {
  return busyAction === action ? busyText : idleText;
}


export function ProgramAccessSidebarCard({
  access,
  guardError = null,
  lastProgramAuthError = null,
  refreshProgramAuthStatus = noopAsync,
  loginProgramAuth = noopAsync,
  logoutProgramAuth = noopAsync,
  sendRegisterCode = noopAsync,
  registerProgramAuth = noopAsync,
  sendResetPasswordCode = noopAsync,
  resetProgramAuthPassword = noopAsync,
}) {
  const [authMode, setAuthMode] = useState("login");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [loginForm, setLoginForm] = useState(LOGIN_FORM_TEMPLATE);
  const [registerForm, setRegisterForm] = useState(REGISTER_FORM_TEMPLATE);
  const [resetForm, setResetForm] = useState(RESET_FORM_TEMPLATE);
  const [busyAction, setBusyAction] = useState("");
  const [formError, setFormError] = useState("");
  const [formNotice, setFormNotice] = useState("");
  const isLocalPassThrough = access?.mode === "local_pass_through";
  const hasRemoteSession = !isLocalPassThrough && hasRemoteProgramSession(access);
  const sidebarAccountLabel = resolveSidebarAccountLabel(access);
  const sidebarHint = resolveSidebarHint(access);
  const programAuthError = !isLocalPassThrough
    ? resolveProgramAuthError(access, lastProgramAuthError)
    : null;

  function clearLocalFeedback() {
    setFormError("");
    setFormNotice("");
  }

  function switchAuthMode(nextMode) {
    clearLocalFeedback();
    setAuthMode(nextMode);
  }

  function openDialog() {
    setIsDialogOpen(true);
  }

  function closeDialog() {
    clearLocalFeedback();
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
    } catch {
      if (!programAuthError) {
        setFormError("程序会员操作失败，请稍后再试。");
      }
      throw new Error("program access action failed");
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
    } catch {
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
    if (!email) {
      setFormError("请先填写注册邮箱。");
      return;
    }

    try {
      await runFormAction("send-register-code", () => sendRegisterCode({ email }));
    } catch {
      setFormError("注册验证码发送失败，请稍后再试。");
    }
  }

  async function handleRegisterSubmit() {
    const payload = {
      email: registerForm.email.trim(),
      code: registerForm.code.trim(),
      username: registerForm.username.trim(),
      password: registerForm.password,
    };

    if (!payload.email || !payload.code || !payload.username || !payload.password) {
      setFormError("请先填写完整的注册信息。");
      return;
    }

    try {
      await runFormAction("register", () => registerProgramAuth(payload), {
        onSuccess() {
          setRegisterForm((current) => ({
            ...current,
            code: "",
            password: "",
          }));
        },
      });
    } catch {
      setFormError("注册失败，请稍后再试。");
    }
  }

  async function handleSendResetPasswordCode() {
    const email = resetForm.email.trim();
    if (!email) {
      setFormError("请先填写找回密码邮箱。");
      return;
    }

    try {
      await runFormAction("send-reset-password-code", () => sendResetPasswordCode({ email }));
    } catch {
      setFormError("找回密码验证码发送失败，请稍后再试。");
    }
  }

  async function handleResetPasswordSubmit() {
    const payload = {
      email: resetForm.email.trim(),
      code: resetForm.code.trim(),
      newPassword: resetForm.newPassword,
    };

    if (!payload.email || !payload.code || !payload.newPassword) {
      setFormError("请先填写完整的找回密码信息。");
      return;
    }

    try {
      await runFormAction("reset-password", () => resetProgramAuthPassword(payload), {
        onSuccess() {
          setResetForm((current) => ({
            ...current,
            code: "",
            newPassword: "",
          }));
        },
      });
    } catch {
      setFormError("密码重置失败，请稍后再试。");
    }
  }

  function renderDialogAlerts() {
    return (
      <>
        {programAuthError ? (
          <div className="program-access-sidebar-card__guard-error" role="alert">
            <span className="program-access-sidebar-card__guard-code">{programAuthError.code}</span>
            <span>{programAuthError.message}</span>
          </div>
        ) : null}
        {guardError ? (
          <div className="program-access-sidebar-card__guard-error" role="alert">
            <span className="program-access-sidebar-card__guard-code">{guardError.code}</span>
            <span>{guardError.message}</span>
          </div>
        ) : null}
      </>
    );
  }

  function renderDialogFeedback() {
    return (
      <>
        {formNotice ? (
          <div className="program-access-sidebar-card__notice" role="status">
            {formNotice}
          </div>
        ) : null}
        {formError ? (
          <div className="program-access-sidebar-card__error" role="alert">
            {formError}
          </div>
        ) : null}
      </>
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
            className="ghost-button"
            type="button"
            disabled={Boolean(busyAction)}
            onClick={() => void handleRemoteRefresh()}
          >
            {resolveBusyLabel("refresh", "刷新状态", "刷新中...", busyAction)}
          </button>
          <button
            className="ghost-button"
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
                className={`program-access-sidebar-card__tab${authMode === item.id ? " is-active" : ""}`}
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
                  className="program-access-sidebar-card__input"
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
                  className="program-access-sidebar-card__input"
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
              <button
                className="accent-button program-access-sidebar-card__button"
                type="button"
                disabled={Boolean(busyAction)}
                onClick={() => void handleRemoteLogin()}
              >
                {resolveBusyLabel("login", "登录程序会员", "登录中...", busyAction)}
              </button>
              <button
                className="ghost-button program-access-sidebar-card__button"
                type="button"
                disabled={Boolean(busyAction)}
                onClick={() => void handleRemoteRefresh()}
              >
                {resolveBusyLabel("refresh", "刷新状态", "刷新中...", busyAction)}
              </button>
            </div>
          ) : null}

          {authMode === "register" ? (
            <div className="program-access-sidebar-card__form">
              <label className="program-access-sidebar-card__field">
                <span className="program-access-sidebar-card__field-label">注册邮箱</span>
                <input
                  aria-label="注册邮箱"
                  className="program-access-sidebar-card__input"
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
              <div className="program-access-sidebar-card__inline">
                <label className="program-access-sidebar-card__field">
                  <span className="program-access-sidebar-card__field-label">注册验证码</span>
                  <input
                    aria-label="注册验证码"
                    className="program-access-sidebar-card__input"
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
                <button
                  className="ghost-button program-access-sidebar-card__button"
                  type="button"
                  disabled={Boolean(busyAction)}
                  onClick={() => void handleSendRegisterCode()}
                >
                  {resolveBusyLabel("send-register-code", "发送注册验证码", "发送中...", busyAction)}
                </button>
              </div>
              <label className="program-access-sidebar-card__field">
                <span className="program-access-sidebar-card__field-label">注册用户名</span>
                <input
                  aria-label="注册用户名"
                  className="program-access-sidebar-card__input"
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
                  className="program-access-sidebar-card__input"
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
              <button
                className="accent-button program-access-sidebar-card__button"
                type="button"
                disabled={Boolean(busyAction)}
                onClick={() => void handleRegisterSubmit()}
              >
                {resolveBusyLabel("register", "提交注册", "提交中...", busyAction)}
              </button>
            </div>
          ) : null}

          {authMode === "reset" ? (
            <div className="program-access-sidebar-card__form">
              <label className="program-access-sidebar-card__field">
                <span className="program-access-sidebar-card__field-label">找回密码邮箱</span>
                <input
                  aria-label="找回密码邮箱"
                  className="program-access-sidebar-card__input"
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
                    className="program-access-sidebar-card__input"
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
                  className="ghost-button program-access-sidebar-card__button"
                  type="button"
                  disabled={Boolean(busyAction)}
                  onClick={() => void handleSendResetPasswordCode()}
                >
                  {resolveBusyLabel("send-reset-password-code", "发送找回密码验证码", "发送中...", busyAction)}
                </button>
              </div>
              <label className="program-access-sidebar-card__field">
                <span className="program-access-sidebar-card__field-label">新密码</span>
                <input
                  aria-label="新密码"
                  className="program-access-sidebar-card__input"
                  type="password"
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
                className="accent-button program-access-sidebar-card__button"
                type="button"
                disabled={Boolean(busyAction)}
                onClick={() => void handleResetPasswordSubmit()}
              >
                {resolveBusyLabel("reset-password", "提交新密码", "提交中...", busyAction)}
              </button>
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
          <span className="program-access-sidebar-card__eyebrow">PROGRAM ACCESS</span>
          <span className="program-access-sidebar-card__entry-title">账号登录</span>
          <strong className="program-access-sidebar-card__entry-identity">{sidebarAccountLabel}</strong>
          <span className="program-access-sidebar-card__entry-hint">{sidebarHint}</span>
        </button>
      </section>

      {isDialogOpen ? (
        <div
          className="surface-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeDialog();
            }
          }}
        >
          <section aria-label="程序账号" className="dialog-surface program-access-dialog" role="dialog">
            <div className="surface-header">
              <div>
                <div className="program-access-dialog__eyebrow">PROGRAM ACCESS</div>
                <h2 className="surface-title">程序账号</h2>
              </div>
              <button className="ghost-button program-access-dialog__close" type="button" onClick={closeDialog}>
                关闭
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
