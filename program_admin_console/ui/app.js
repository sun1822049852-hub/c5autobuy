const LEGACY_TOKEN_STORAGE_KEY = "program_admin_console_token";

const state = {
  token: "",
  session: null,
  bootstrapNeeded: false,
  users: [],
  selectedUserId: 0,
  devices: []
};

const refs = {
  authPanel: document.querySelector("#authPanel"),
  authTitle: document.querySelector("#authTitle"),
  authHint: document.querySelector("#authHint"),
  authMessage: document.querySelector("#authMessage"),
  workspaceMessage: document.querySelector("#workspaceMessage"),
  bootstrapForm: document.querySelector("#bootstrapForm"),
  bootstrapUsername: document.querySelector("#bootstrapUsername"),
  bootstrapPassword: document.querySelector("#bootstrapPassword"),
  loginForm: document.querySelector("#loginForm"),
  loginUsername: document.querySelector("#loginUsername"),
  loginPassword: document.querySelector("#loginPassword"),
  workspace: document.querySelector("#workspace"),
  sessionSummary: document.querySelector("#sessionSummary"),
  logoutButton: document.querySelector("#logoutButton"),
  usersList: document.querySelector("#usersList"),
  detailHint: document.querySelector("#detailHint"),
  userForm: document.querySelector("#userForm"),
  detailUsername: document.querySelector("#detailUsername"),
  detailEmail: document.querySelector("#detailEmail"),
  userPlan: document.querySelector("#userPlan"),
  userExpiryDate: document.querySelector("#userExpiryDate"),
  userExpiryTime: document.querySelector("#userExpiryTime"),
  membershipMeta: document.querySelector("#membershipMeta"),
  deviceList: document.querySelector("#deviceList"),
  sidebarCopy: document.querySelector("#sidebarCopy"),
  pageHeader: document.querySelector("#pageHeader")
};

const DEFAULT_EXPIRY_TIME = "23:59";

function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

function escapeHtml(value = "") {
  return toText(value).replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case "\"":
        return "&quot;";
      case "'":
        return "&#39;";
      default:
        return char;
    }
  });
}

function getHeaders(extra = {}) {
  return {
    "Content-Type": "application/json",
    ...(state.token ? {Authorization: `Bearer ${state.token}`} : {}),
    ...extra
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: getHeaders(options.headers || {})
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.message || "请求失败");
  }
  return payload;
}

function setMessage(message = "", isError = false) {
  const target = state.session ? refs.workspaceMessage : refs.authMessage;
  const inactiveTarget = state.session ? refs.authMessage : refs.workspaceMessage;

  if (inactiveTarget) {
    inactiveTarget.hidden = true;
    inactiveTarget.textContent = "";
    inactiveTarget.className = "notice";
  }

  if (!target) {
    return;
  }

  target.hidden = !message;
  target.textContent = message;
  target.className = `notice ${isError ? "is-error" : ""}`.trim();
}

function clearLegacyPersistedToken() {
  try {
    window.localStorage.removeItem(LEGACY_TOKEN_STORAGE_KEY);
  } catch (_) {
  }
}

function saveToken(token = "") {
  state.token = token;
  if (!token) {
    clearLegacyPersistedToken();
  }
}

function selectedUser() {
  return state.users.find((user) => user.id === state.selectedUserId) || null;
}

function normalizeTimeValue(value = "") {
  const match = toText(value).match(/^(\d{1,2}):(\d{2})$/);
  if (!match) {
    return "";
  }
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
    return "";
  }
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function splitExpiryParts(value = "") {
  const text = toText(value);
  if (!text) {
    return {
      dateValue: "",
      timeValue: DEFAULT_EXPIRY_TIME
    };
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return {
      dateValue: "",
      timeValue: DEFAULT_EXPIRY_TIME
    };
  }
  const pad = (number) => String(number).padStart(2, "0");
  return {
    dateValue: [
      date.getFullYear(),
      pad(date.getMonth() + 1),
      pad(date.getDate())
    ].join("-"),
    timeValue: `${pad(date.getHours())}:${pad(date.getMinutes())}`
  };
}

function expiryToIso(dateValue = "", timeValue = "") {
  const dateText = toText(dateValue);
  if (!dateText) {
    return "";
  }
  const normalizedTime = normalizeTimeValue(timeValue) || DEFAULT_EXPIRY_TIME;
  const date = new Date(`${dateText}T${normalizedTime}`);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

function formatDateTime(value = "") {
  const text = toText(value);
  if (!text) {
    return "未设置";
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  const pad = (number) => String(number).padStart(2, "0");
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate())
  ].join("-") + ` ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function renderAuth() {
  const loggedIn = Boolean(state.session);
  refs.bootstrapForm.hidden = !state.bootstrapNeeded;
  refs.loginForm.hidden = state.bootstrapNeeded;
  refs.authTitle.textContent = state.bootstrapNeeded ? "初始化超级管理员" : "管理员登录";
  refs.authHint.textContent = state.bootstrapNeeded
    ? "当前控制台尚未初始化，请先创建第一个管理员账号。"
    : "使用管理员账号进入控制台。";
  refs.authPanel.hidden = loggedIn;
  refs.workspace.hidden = !loggedIn;
  refs.logoutButton.hidden = !loggedIn;
  refs.sessionSummary.textContent = loggedIn
    ? `当前管理员：${state.session.user.username}`
    : "尚未登录";

  if (refs.sidebarCopy) {
    if (loggedIn) {
      refs.sidebarCopy.innerHTML =
        "<h1>管理控制台</h1><p>用户列表、成员资格与设备会话控制。</p>";
    } else if (state.bootstrapNeeded) {
      refs.sidebarCopy.innerHTML =
        "<h1>初始化管理员</h1><p>请创建第一个管理员账号以启用控制台。</p>";
    } else {
      refs.sidebarCopy.innerHTML =
        "<h1>管理控制台</h1><p>请登录以继续。</p>";
    }
  }

  if (refs.pageHeader) {
    if (loggedIn) {
      refs.pageHeader.innerHTML = [
        '<p class="eyebrow">Control Plane</p>',
        "<h2>用户列表与成员资格控制</h2>",
        '<p>计划只允许 <span class="token">inactive</span> 与 <span class="token">member</span>。</p>'
      ].join("");
    } else {
      refs.pageHeader.innerHTML = [
        '<p class="eyebrow">管理控制台</p>',
        "<h2>请登录</h2>",
        "<p></p>"
      ].join("");
    }
  }
}

function renderUsers() {
  if (!state.users.length) {
    refs.usersList.innerHTML = '<div class="empty-state">当前没有终端用户。</div>';
    return;
  }
  refs.usersList.innerHTML = state.users.map((user) => {
    const membershipPlan = toText(user.membership_plan) || "inactive";
    const userId = Number(user.id) || 0;
    return `
      <button class="user-row ${userId === state.selectedUserId ? "is-selected" : ""}" type="button" data-user-id="${userId}">
        <span class="user-row-main">
          <strong>${escapeHtml(user.username)}</strong>
          <span>${escapeHtml(user.email)}</span>
        </span>
        <span class="user-row-side">
          <span class="token">${escapeHtml(membershipPlan)}</span>
          <span>${escapeHtml(formatDateTime(user.membership_expires_at))}</span>
        </span>
      </button>
    `;
  }).join("");
}

function renderMembershipMeta(user) {
  const plan = refs.userPlan.value;
  if (plan === "inactive") {
    refs.userExpiryDate.disabled = true;
    refs.userExpiryTime.disabled = true;
    refs.membershipMeta.textContent = "inactive 不发放程序访问权限，保存后会清空到期时间。";
    return;
  }
  refs.userExpiryDate.disabled = false;
  refs.userExpiryTime.disabled = false;
  const preview = expiryToIso(refs.userExpiryDate.value, refs.userExpiryTime.value);
  refs.membershipMeta.textContent = preview
    ? `member 将保留程序访问权限。当前选择的到期时间：${formatDateTime(preview)}。`
    : `member 将保留程序访问权限。当前用户原始到期时间：${formatDateTime(user && user.membership_expires_at)}。`;
}

function renderDevices() {
  const user = selectedUser();
  if (!user) {
    refs.deviceList.innerHTML = '<div class="empty-state">尚未选择用户。</div>';
    return;
  }
  if (!state.devices.length) {
    refs.deviceList.innerHTML = '<div class="empty-state">当前没有活跃设备。</div>';
    return;
  }
  refs.deviceList.innerHTML = state.devices.map((device) => `
    <article class="device-card">
      <strong>${escapeHtml(device.device_id)}</strong>
      <p>最后使用：${escapeHtml(formatDateTime(device.last_used_at || device.created_at))}</p>
      <p>过期时间：${escapeHtml(formatDateTime(device.expires_at))}</p>
      <button type="button" data-session-id="${Number(device.id) || 0}">吊销设备</button>
    </article>
  `).join("");
}

function renderUserDetail() {
  const user = selectedUser();
  if (!user) {
    refs.userForm.hidden = true;
    refs.detailHint.textContent = "选择左侧用户后即可编辑。";
    renderDevices();
    return;
  }
  refs.userForm.hidden = false;
  refs.detailHint.textContent = `正在编辑 ${user.username}。`;
  refs.detailUsername.textContent = user.username;
  refs.detailEmail.textContent = user.email;
  refs.userPlan.value = toText(user.membership_plan) === "member" ? "member" : "inactive";
  const expiry = splitExpiryParts(user.membership_expires_at);
  refs.userExpiryDate.value = expiry.dateValue;
  refs.userExpiryTime.value = expiry.timeValue;
  renderMembershipMeta(user);
  renderDevices();
}

async function loadSession() {
  if (!state.token) {
    state.session = null;
    try {
      const sessionInfo = await api("/api/admin/session", {method: "GET"});
      state.bootstrapNeeded = Boolean(sessionInfo.needs_bootstrap);
    } catch (_) {
      state.bootstrapNeeded = false;
    }
    renderAuth();
    return;
  }
  try {
    const session = await api("/api/admin/session", {method: "GET"});
    state.session = session.authenticated ? session : null;
    state.bootstrapNeeded = false;
  } catch (_) {
    saveToken("");
    state.session = null;
    state.bootstrapNeeded = false;
  }
  renderAuth();
}

async function loadDashboard() {
  if (!state.session) {
    return;
  }
  const previousSelectedId = state.selectedUserId;
  const usersPromise = api("/api/admin/users", {method: "GET"});
  // Capture the result immediately so stale-user failures do not escape if selection changes mid-refresh.
  const devicesPromise = previousSelectedId
    ? api(`/api/admin/users/${previousSelectedId}/devices`, {method: "GET"})
      .then((response) => ({ok: true, response}))
      .catch((error) => ({ok: false, error}))
    : null;

  const users = await usersPromise;
  state.users = Array.isArray(users.items) ? users.items : [];
  if (!state.users.find((user) => user.id === state.selectedUserId)) {
    state.selectedUserId = state.users[0] ? state.users[0].id : 0;
  }
  renderUsers();

  // If selected user changed (or had none), fetch devices for the new selection
  if (devicesPromise && state.selectedUserId === previousSelectedId) {
    const deviceResult = await devicesPromise;
    if (!deviceResult.ok) {
      throw deviceResult.error;
    }
    state.devices = Array.isArray(deviceResult.response.items) ? deviceResult.response.items : [];
    renderUserDetail();
  } else {
    await loadDevices();
  }
}

async function loadDevices() {
  const user = selectedUser();
  if (!user || !state.session) {
    state.devices = [];
    renderUserDetail();
    return;
  }
  const response = await api(`/api/admin/users/${user.id}/devices`, {method: "GET"});
  state.devices = Array.isArray(response.items) ? response.items : [];
  renderUserDetail();
}

async function handleBootstrap(event) {
  event.preventDefault();
  try {
    await api("/api/admin/bootstrap", {
      method: "POST",
      body: JSON.stringify({
        username: toText(refs.bootstrapUsername.value) || "admin",
        password: toText(refs.bootstrapPassword.value)
      })
    });
    refs.bootstrapPassword.value = "";
    state.bootstrapNeeded = false;
    setMessage("超级管理员已初始化，请直接登录。");
    renderAuth();
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function handleLogin(event) {
  event.preventDefault();
  try {
    const response = await api("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({
        username: toText(refs.loginUsername.value) || "admin",
        password: toText(refs.loginPassword.value)
      })
    });
    saveToken(response.session_token || "");
    refs.loginPassword.value = "";
    setMessage("");
    await loadSession();
    await loadDashboard();
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function handleLogout() {
  try {
    await api("/api/admin/logout", {
      method: "POST",
      body: JSON.stringify({})
    });
  } catch (_) {
  }
  saveToken("");
  state.session = null;
  state.users = [];
  state.selectedUserId = 0;
  state.devices = [];
  renderAuth();
  renderUsers();
  renderUserDetail();
  await loadSession();
}

async function handleUserSubmit(event) {
  event.preventDefault();
  const user = selectedUser();
  if (!user) {
    return;
  }
  const membershipPlan = refs.userPlan.value === "member" ? "member" : "inactive";
  try {
    await api(`/api/admin/users/${user.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        membership_plan: membershipPlan,
        membership_expires_at: membershipPlan === "inactive"
          ? ""
          : expiryToIso(refs.userExpiryDate.value, refs.userExpiryTime.value)
      })
    });
    await loadDashboard();
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function handleUsersClick(event) {
  const row = event.target.closest("[data-user-id]");
  if (!row) {
    return;
  }
  state.selectedUserId = Number(row.getAttribute("data-user-id")) || 0;
  renderUsers();
  await loadDevices();
}

async function handleDevicesClick(event) {
  const button = event.target.closest("[data-session-id]");
  if (!button) {
    return;
  }
  const user = selectedUser();
  if (!user) {
    return;
  }
  await api(`/api/admin/users/${user.id}/devices/${button.getAttribute("data-session-id")}/revoke`, {
    method: "POST",
    body: JSON.stringify({})
  });
  await loadDashboard();
}

function bindEvents() {
  refs.bootstrapForm.addEventListener("submit", handleBootstrap);
  refs.loginForm.addEventListener("submit", handleLogin);
  refs.logoutButton.addEventListener("click", handleLogout);
  refs.userForm.addEventListener("submit", handleUserSubmit);
  refs.userPlan.addEventListener("change", () => {
    const user = selectedUser();
    if (refs.userPlan.value === "inactive") {
      refs.userExpiryDate.value = "";
      refs.userExpiryTime.value = DEFAULT_EXPIRY_TIME;
    } else {
      refs.userExpiryTime.value = normalizeTimeValue(refs.userExpiryTime.value) || DEFAULT_EXPIRY_TIME;
    }
    renderMembershipMeta(user);
  });
  refs.userExpiryDate.addEventListener("input", () => renderMembershipMeta(selectedUser()));
  refs.userExpiryTime.addEventListener("change", () => {
    refs.userExpiryTime.value = normalizeTimeValue(refs.userExpiryTime.value) || DEFAULT_EXPIRY_TIME;
    renderMembershipMeta(selectedUser());
  });
  refs.usersList.addEventListener("click", (event) => {
    handleUsersClick(event).catch((error) => setMessage(error.message, true));
  });
  refs.deviceList.addEventListener("click", (event) => {
    handleDevicesClick(event).catch((error) => setMessage(error.message, true));
  });
}

async function init() {
  clearLegacyPersistedToken();
  bindEvents();
  renderUsers();
  renderUserDetail();
  await loadSession();
  if (state.session) {
    await loadDashboard();
  }
}

init().catch((error) => {
  setMessage(error.message || "控制台加载失败", true);
});
