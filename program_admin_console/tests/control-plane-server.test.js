const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const {createServer} = require("../src/server");

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "program-control-plane-server-"));
}

async function requestJson(ctx, method, route, body = null, headers = null) {
  const rawBody = body ? JSON.stringify(body) : "";
  const url = new URL(route, ctx.baseUrl);
  return new Promise((resolve, reject) => {
    const req = http.request(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(rawBody),
        ...(headers && typeof headers === "object" ? headers : {})
      }
    }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        const raw = Buffer.concat(chunks).toString("utf8");
        resolve({
          status: res.statusCode || 0,
          body: raw ? JSON.parse(raw) : {},
          text: raw
        });
      });
    });
    req.on("error", reject);
    if (rawBody) {
      req.write(rawBody);
    }
    req.end();
  });
}

function parseSseFrame(rawFrame = "") {
  const lines = String(rawFrame || "").split(/\r?\n/);
  const comments = [];
  const dataLines = [];
  let event = "";
  for (const line of lines) {
    if (!line) {
      continue;
    }
    if (line.startsWith(":")) {
      comments.push(line.slice(1).trim());
      continue;
    }
    const separatorIndex = line.indexOf(":");
    const field = separatorIndex >= 0 ? line.slice(0, separatorIndex).trim() : line.trim();
    const value = separatorIndex >= 0 ? line.slice(separatorIndex + 1).replace(/^ /, "") : "";
    if (field === "event") {
      event = value;
      continue;
    }
    if (field === "data") {
      dataLines.push(value);
    }
  }
  return {
    raw: rawFrame,
    event,
    comment: comments.join("\n"),
    dataText: dataLines.join("\n")
  };
}

function parseFrameJson(frame) {
  assert.ok(frame && frame.dataText, `expected json frame data, got: ${frame ? frame.raw : "<empty>"}`);
  return JSON.parse(frame.dataText);
}

function pushSseFrame(state, frame) {
  if (state.waiters.length) {
    const waiter = state.waiters.shift();
    clearTimeout(waiter.timer);
    waiter.resolve(frame);
    return;
  }
  state.frames.push(frame);
}

function flushSseFrames(state) {
  while (true) {
    const match = state.buffer.match(/\r?\n\r?\n/);
    if (!match) {
      return;
    }
    const separatorIndex = Number(match.index) || 0;
    const separatorLength = match[0].length;
    const rawFrame = state.buffer.slice(0, separatorIndex);
    state.buffer = state.buffer.slice(separatorIndex + separatorLength);
    if (!rawFrame.trim()) {
      continue;
    }
    pushSseFrame(state, parseSseFrame(rawFrame));
  }
}

function failPendingSseWaiters(state, error) {
  while (state.waiters.length) {
    const waiter = state.waiters.shift();
    clearTimeout(waiter.timer);
    waiter.reject(error);
  }
}

async function openRuntimeControlStream(ctx, {
  refreshToken,
  deviceId
}) {
  const url = new URL("/api/auth/runtime-control/stream", ctx.baseUrl);
  return new Promise((resolve, reject) => {
    const state = {
      buffer: "",
      frames: [],
      waiters: [],
      ended: false,
      endError: null,
      res: null,
      req: null
    };
    const req = http.request(url, {
      method: "GET",
      headers: {
        Accept: "text/event-stream",
        Authorization: `Bearer ${refreshToken}`,
        "X-C5-Device-Id": deviceId
      }
    }, (res) => {
      state.res = res;
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        state.buffer += chunk;
        flushSseFrames(state);
      });
      res.on("end", () => {
        state.ended = true;
        if (state.buffer.trim()) {
          pushSseFrame(state, parseSseFrame(state.buffer));
          state.buffer = "";
        }
        failPendingSseWaiters(state, state.endError || new Error("runtime-control stream ended"));
      });
      res.on("error", (error) => {
        state.endError = error;
        failPendingSseWaiters(state, error);
      });
      resolve({
        status: res.statusCode || 0,
        headers: res.headers,
        async readFrame({timeoutMs = 1000} = {}) {
          if (state.frames.length) {
            return state.frames.shift();
          }
          if (state.ended) {
            throw state.endError || new Error("runtime-control stream ended");
          }
          return new Promise((resolveFrame, rejectFrame) => {
            const waiter = {
              resolve: resolveFrame,
              reject: rejectFrame,
              timer: setTimeout(() => {
                const index = state.waiters.indexOf(waiter);
                if (index >= 0) {
                  state.waiters.splice(index, 1);
                }
                rejectFrame(new Error(`timed out waiting for runtime-control frame after ${timeoutMs}ms`));
              }, timeoutMs)
            };
            state.waiters.push(waiter);
          });
        },
        close() {
          req.destroy();
          if (state.res) {
            state.res.destroy();
          }
        }
      });
    });
    state.req = req;
    req.on("error", reject);
    req.end();
  });
}

async function readHelloFrame(stream) {
  const frame = await stream.readFrame({timeoutMs: 1000});
  assert.equal(frame.event, "hello");
  const payload = parseFrameJson(frame);
  assert.equal(Number.isNaN(Date.parse(payload.server_time)), false);
  assert.equal(Object.prototype.hasOwnProperty.call(payload, "stream_version"), true);
  return payload;
}

async function readHealthFrameWithoutRevoke(stream, {timeoutMs = 1000} = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const frame = await stream.readFrame({timeoutMs: Math.max(1, deadline - Date.now())});
    if (frame.event === "runtime.revoke") {
      const payload = parseFrameJson(frame);
      assert.fail(`expected keepalive/comment without runtime.revoke, got ${JSON.stringify(payload)}`);
    }
    if (frame.comment || frame.event === "keepalive") {
      return frame;
    }
  }
  assert.fail("expected keepalive/comment frame before timeout");
}

async function readRuntimeRevoke(stream, {timeoutMs = 1000} = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const frame = await stream.readFrame({timeoutMs: Math.max(1, deadline - Date.now())});
    if (frame.event !== "runtime.revoke") {
      continue;
    }
    const payload = parseFrameJson(frame);
    assert.equal(typeof payload.reason, "string");
    return payload;
  }
  assert.fail("expected runtime.revoke event before timeout");
}

async function startServer(options = {}) {
  const tempDir = makeTempDir();
  const sentMessages = [];
  const dbPath = path.join(tempDir, "control-plane.sqlite");
  const codes = ["123456", "654321", "777777", "888888", "112233", "445566", "778899"];
  const mailConfig = options.mailConfig || {
    configured: true,
    authCodeTtlMinutes: 5,
    refreshSessionDays: 30,
    adminSessionHours: 12
  };
  const serverOptions = {
    dbPath,
    now() {
      return new Date("2026-04-19T08:00:00.000Z");
    },
    codeGenerator() {
      return codes.shift() || "999999";
    },
    mailConfigFactory() {
      return mailConfig;
    },
    mailServiceFactory() {
      if (typeof options.mailServiceFactory === "function") {
        return options.mailServiceFactory({sentMessages});
      }
      return {
        async sendVerificationCode(payload) {
          sentMessages.push(payload);
          return {messageId: `msg_${sentMessages.length}`};
        }
      };
    }
  };
  if (Object.prototype.hasOwnProperty.call(options, "runtimeControlKeepaliveMs")) {
    serverOptions.runtimeControlKeepaliveMs = Number(options.runtimeControlKeepaliveMs) || 0;
  } else if (!options.useDefaultRuntimeControlKeepalive) {
    serverOptions.runtimeControlKeepaliveMs = 50;
  }
  const server = createServer(serverOptions);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  return {
    tempDir,
    sentMessages,
    server,
    baseUrl: `http://127.0.0.1:${address.port}`
  };
}

async function stopServer(ctx) {
  await new Promise((resolve) => ctx.server.close(resolve));
  fs.rmSync(ctx.tempDir, {recursive: true, force: true});
}

async function registerUserViaV3(ctx, {
  email,
  installId,
  username,
  password,
  deviceId
}) {
  const sendCode = await requestJson(ctx, "POST", "/api/auth/register/send-code", {
    email,
    install_id: installId
  });
  assert.equal(sendCode.status, 200);
  assert.equal(sendCode.body.ok, true);
  assert.equal(typeof sendCode.body.register_session_id, "string");

  const latestCode = ctx.sentMessages[ctx.sentMessages.length - 1].code;
  const verifyCode = await requestJson(ctx, "POST", "/api/auth/register/verify-code", {
    email,
    code: latestCode,
    register_session_id: sendCode.body.register_session_id,
    install_id: installId
  });
  assert.equal(verifyCode.status, 200);
  assert.equal(verifyCode.body.ok, true);
  assert.equal(typeof verifyCode.body.verification_ticket, "string");

  const complete = await requestJson(ctx, "POST", "/api/auth/register/complete", {
    email,
    verification_ticket: verifyCode.body.verification_ticket,
    username,
    password,
    install_id: installId,
    device_id: deviceId
  });
  assert.equal(complete.status, 200);
  assert.equal(complete.body.ok, true);
  return {
    sendCode,
    verifyCode,
    complete
  };
}

async function main() {
  const notConfiguredCtx = await startServer({
    mailConfig: {
      configured: false,
      authCodeTtlMinutes: 5,
      refreshSessionDays: 30,
      adminSessionHours: 12
    }
  });
  try {
    const legacySendCodeWithoutMail = await requestJson(notConfiguredCtx, "POST", "/api/auth/email/send-code", {
      email: "nomail@example.com"
    });
    assert.ok([404, 405].includes(legacySendCodeWithoutMail.status));

    const registerSendCodeWithoutMail = await requestJson(notConfiguredCtx, "POST", "/api/auth/register/send-code", {
      email: "nomail@example.com",
      install_id: "install_nomail"
    });
    assert.equal(registerSendCodeWithoutMail.status, 503);
    assert.equal(registerSendCodeWithoutMail.body.error_code, "REGISTER_SERVICE_UNAVAILABLE");

    const sendResetWithoutMail = await requestJson(notConfiguredCtx, "POST", "/api/auth/password/send-reset-code", {
      email: "nomail@example.com"
    });
    assert.equal(sendResetWithoutMail.status, 503);
    assert.equal(sendResetWithoutMail.body.reason, "mail_service_not_configured");
  } finally {
    await stopServer(notConfiguredCtx);
  }

  const failedMailCtx = await startServer({
    mailServiceFactory() {
      return {
        async sendVerificationCode() {
          throw new Error("smtp unavailable");
        }
      };
    }
  });
  try {
    const failedLegacySend = await requestJson(failedMailCtx, "POST", "/api/auth/email/send-code", {
      email: "failed@example.com"
    });
    assert.ok([404, 405].includes(failedLegacySend.status));

    const failedRegisterSend = await requestJson(failedMailCtx, "POST", "/api/auth/register/send-code", {
      email: "failed@example.com",
      install_id: "install_failed"
    });
    assert.equal(failedRegisterSend.status, 503);
    assert.equal(failedRegisterSend.body.error_code, "REGISTER_SERVICE_UNAVAILABLE");

    const registerAfterFailedSend = await requestJson(failedMailCtx, "POST", "/api/auth/register", {
      email: "failed@example.com",
      code: "123456",
      username: "failed_user",
      password: "Secret123!"
    });
    assert.ok([404, 405].includes(registerAfterFailedSend.status));
  } finally {
    await stopServer(failedMailCtx);
  }

  const defaultKeepaliveCtx = await startServer({useDefaultRuntimeControlKeepalive: true});
  try {
    const adminBootstrap = await requestJson(defaultKeepaliveCtx, "POST", "/api/admin/bootstrap", {
      username: "admin",
      password: "Root123!"
    });
    assert.equal(adminBootstrap.status, 200);
    assert.equal(adminBootstrap.body.ok, true);

    const adminLogin = await requestJson(defaultKeepaliveCtx, "POST", "/api/admin/login", {
      username: "admin",
      password: "Root123!"
    });
    assert.equal(adminLogin.status, 200);
    assert.equal(adminLogin.body.ok, true);
    const adminHeaders = {
      Authorization: `Bearer ${adminLogin.body.session_token}`
    };

    const registerKeepaliveUser = await registerUserViaV3(defaultKeepaliveCtx, {
      email: "keepalive@example.com",
      installId: "install_keepalive",
      username: "keepalive_user",
      password: "Secret123!",
      deviceId: "device_keepalive"
    });
    const keepaliveUserList = await requestJson(defaultKeepaliveCtx, "GET", "/api/admin/users", null, adminHeaders);
    assert.equal(keepaliveUserList.status, 200);
    const keepaliveUser = keepaliveUserList.body.items.find((item) => item.email === "keepalive@example.com");
    assert.ok(keepaliveUser);

    const upgradeKeepaliveUser = await requestJson(defaultKeepaliveCtx, "PATCH", `/api/admin/users/${keepaliveUser.id}`, {
      membership_plan: "member",
      permission_overrides: []
    }, adminHeaders);
    assert.equal(upgradeKeepaliveUser.status, 200);
    assert.equal(upgradeKeepaliveUser.body.ok, true);

    const refreshKeepaliveUser = await requestJson(defaultKeepaliveCtx, "POST", "/api/auth/refresh", {
      refresh_token: registerKeepaliveUser.complete.body.auth_session.refresh_token,
      device_id: "device_keepalive"
    });
    assert.equal(refreshKeepaliveUser.status, 200);
    assert.equal(refreshKeepaliveUser.body.ok, true);

    const defaultKeepaliveStream = await openRuntimeControlStream(defaultKeepaliveCtx, {
      refreshToken: refreshKeepaliveUser.body.refresh_token,
      deviceId: "device_keepalive"
    });
    try {
      assert.equal(defaultKeepaliveStream.status, 200);
      await readHelloFrame(defaultKeepaliveStream);
      const healthFrame = await readHealthFrameWithoutRevoke(defaultKeepaliveStream, {timeoutMs: 2200});
      assert.equal(Boolean(healthFrame.comment || healthFrame.event === "keepalive"), true);
    } finally {
      defaultKeepaliveStream.close();
    }
  } finally {
    await stopServer(defaultKeepaliveCtx);
  }

  const ctx = await startServer();
  try {
    const health = await requestJson(ctx, "GET", "/api/health");
    assert.equal(health.status, 200);
    assert.equal(health.body.ok, true);

    const publicKey = await requestJson(ctx, "GET", "/api/auth/public-key");
    assert.equal(publicKey.status, 200);
    assert.equal(publicKey.body.ok, true);
    assert.match(publicKey.body.kid, /^ed25519:/);
    assert.match(publicKey.body.public_key_pem, /BEGIN PUBLIC KEY/);
    const issuedKid = publicKey.body.kid;

    const registerCapability = await requestJson(ctx, "GET", "/api/auth/register/capability");
    assert.equal(registerCapability.status, 200);
    assert.equal(registerCapability.body.ok, true);
    assert.equal(registerCapability.body.registration_flow_version, 3);
    assert.deepEqual(registerCapability.body.registration_v3.endpoints, {
      send_code: "/api/auth/register/send-code",
      verify_code: "/api/auth/register/verify-code",
      complete: "/api/auth/register/complete"
    });
    assert.equal(Object.prototype.hasOwnProperty.call(registerCapability.body, "legacy"), false);

    assert.equal((await requestJson(ctx, "GET", "/api/admin/session")).body.needs_bootstrap, true);

    const adminBootstrap = await requestJson(ctx, "POST", "/api/admin/bootstrap", {
      username: "admin",
      password: "Root123!"
    });
    assert.equal(adminBootstrap.status, 200);
    assert.equal(adminBootstrap.body.ok, true);
    assert.equal(adminBootstrap.body.user.username, "admin");

    const adminLogin = await requestJson(ctx, "POST", "/api/admin/login", {
      username: "admin",
      password: "Root123!"
    });
    assert.equal(adminLogin.status, 200);
    assert.equal(adminLogin.body.ok, true);
    assert.equal(typeof adminLogin.body.session_token, "string");
    const adminHeaders = {
      Authorization: `Bearer ${adminLogin.body.session_token}`
    };

    const invalidAdminLogin = await requestJson(ctx, "POST", "/api/admin/login", {
      username: "admin",
      password: "wrong-password"
    });
    assert.equal(invalidAdminLogin.status, 401);
    assert.equal(invalidAdminLogin.body.reason, "invalid_credentials");
    assert.equal(invalidAdminLogin.body.message, "用户名或者密码错误");

    const adminSession = await requestJson(ctx, "GET", "/api/admin/session", null, adminHeaders);
    assert.equal(adminSession.status, 200);
    assert.equal(adminSession.body.authenticated, true);
    assert.equal(adminSession.body.user.username, "admin");

    const registerAlice = await registerUserViaV3(ctx, {
      email: "alice@example.com",
      installId: "install_alpha",
      username: "alice",
      password: "Secret123!",
      deviceId: "device_alpha"
    });
    assert.equal(ctx.sentMessages.length, 1);
    assert.equal(ctx.sentMessages[0].code, "123456");
    assert.equal(registerAlice.complete.body.account_summary.membership_plan, "inactive");
    assert.equal(registerAlice.complete.body.auth_session.access_bundle.snapshot.permissions.includes("program_access_enabled"), false);
    assert.equal(registerAlice.complete.body.auth_session.access_bundle.snapshot.feature_flags.program_access_enabled, false);
    assert.equal(registerAlice.complete.body.auth_session.access_bundle.kid, issuedKid);

    assert.ok([404, 405].includes((await requestJson(ctx, "POST", "/api/auth/register", {
      email: "alice@example.com",
      code: "654321",
      username: "alice",
      password: "Secret123!"
    })).status));

    const runtimePermitDenied = await requestJson(ctx, "POST", "/api/auth/runtime-permit", {
      refresh_token: registerAlice.complete.body.auth_session.refresh_token,
      device_id: "device_alpha",
      action: "runtime.start"
    });
    assert.equal(runtimePermitDenied.status, 403);
    assert.equal(runtimePermitDenied.body.reason, "runtime_permission_denied");

    const userList = await requestJson(ctx, "GET", "/api/admin/users", null, adminHeaders);
    assert.equal(userList.status, 200);
    assert.equal(userList.body.ok, true);
    assert.equal(userList.body.items.length, 1);
    assert.equal(userList.body.items[0].membership_plan, "inactive");
    assert.equal(userList.body.items[0].active_device_count, 1);
    assert.equal(userList.body.items[0].entitlements.membership_plan, "inactive");
    assert.equal(userList.body.items[0].entitlements.feature_flags.program_access_enabled, false);
    const aliceId = userList.body.items[0].id;

    const upgraded = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
      membership_plan: "member"
    }, adminHeaders);
    assert.equal(upgraded.status, 200);
    assert.equal(upgraded.body.ok, true);
    assert.equal(upgraded.body.user.membership_plan, "member");
    assert.equal(upgraded.body.entitlements.permissions.includes("program_access_enabled"), true);

    const browserQueryOverride = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
      permission_overrides: [
        {
          feature_code: "account.browser_query.enable",
          enabled: true
        }
      ]
    }, adminHeaders);
    assert.equal(browserQueryOverride.status, 200);
    assert.equal(browserQueryOverride.body.ok, true);
    assert.equal(browserQueryOverride.body.entitlements.permissions.includes("account.browser_query.enable"), true);

    const userListWithOverride = await requestJson(ctx, "GET", "/api/admin/users", null, adminHeaders);
    assert.equal(userListWithOverride.status, 200);
    assert.deepEqual(userListWithOverride.body.items[0].permission_overrides, [
      {
        feature_code: "account.browser_query.enable",
        enabled: true
      }
    ]);

    const refreshed = await requestJson(ctx, "POST", "/api/auth/refresh", {
      refresh_token: registerAlice.complete.body.auth_session.refresh_token,
      device_id: "device_alpha"
    });
    assert.equal(refreshed.status, 200);
    assert.equal(refreshed.body.ok, true);
    assert.notEqual(refreshed.body.refresh_token, registerAlice.complete.body.auth_session.refresh_token);
    assert.equal(refreshed.body.access_bundle.snapshot.permissions.includes("program_access_enabled"), true);

    const runtimeControlUserDisabledStream = await openRuntimeControlStream(ctx, {
      refreshToken: refreshed.body.refresh_token,
      deviceId: "device_alpha"
    });
    try {
      assert.equal(runtimeControlUserDisabledStream.status, 200);
      assert.match(String(runtimeControlUserDisabledStream.headers["content-type"] || ""), /text\/event-stream/i);
      await readHelloFrame(runtimeControlUserDisabledStream);

      const browserQueryDisabled = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
        permission_overrides: [
          {
            feature_code: "account.browser_query.enable",
            enabled: false
          }
        ]
      }, adminHeaders);
      assert.equal(browserQueryDisabled.status, 200);
      assert.equal(browserQueryDisabled.body.ok, true);
      const healthFrame = await readHealthFrameWithoutRevoke(runtimeControlUserDisabledStream, {timeoutMs: 1200});
      assert.equal(Boolean(healthFrame.comment || healthFrame.event === "keepalive"), true);

      const disabledUser = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
        status: "disabled"
      }, adminHeaders);
      assert.equal(disabledUser.status, 200);
      assert.equal(disabledUser.body.ok, true);
      const disabledRevoke = await readRuntimeRevoke(runtimeControlUserDisabledStream, {timeoutMs: 1200});
      assert.equal(disabledRevoke.reason, "user_disabled");
    } finally {
      runtimeControlUserDisabledStream.close();
    }

    const restoredAfterDisable = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
      status: "active",
      membership_plan: "member",
      permission_overrides: []
    }, adminHeaders);
    assert.equal(restoredAfterDisable.status, 200);
    assert.equal(restoredAfterDisable.body.ok, true);

    const runtimeControlMembershipStream = await openRuntimeControlStream(ctx, {
      refreshToken: refreshed.body.refresh_token,
      deviceId: "device_alpha"
    });
    try {
      assert.equal(runtimeControlMembershipStream.status, 200);
      await readHelloFrame(runtimeControlMembershipStream);

      const downgradedMembership = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
        membership_plan: "inactive"
      }, adminHeaders);
      assert.equal(downgradedMembership.status, 200);
      assert.equal(downgradedMembership.body.ok, true);
      const membershipRevoke = await readRuntimeRevoke(runtimeControlMembershipStream, {timeoutMs: 1200});
      assert.equal(membershipRevoke.reason, "membership_inactive");
    } finally {
      runtimeControlMembershipStream.close();
    }

    const restoredAfterInactive = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
      status: "active",
      membership_plan: "member",
      permission_overrides: []
    }, adminHeaders);
    assert.equal(restoredAfterInactive.status, 200);
    assert.equal(restoredAfterInactive.body.ok, true);

    const runtimeControlRuntimeStartStream = await openRuntimeControlStream(ctx, {
      refreshToken: refreshed.body.refresh_token,
      deviceId: "device_alpha"
    });
    try {
      assert.equal(runtimeControlRuntimeStartStream.status, 200);
      await readHelloFrame(runtimeControlRuntimeStartStream);

      const runtimeStartDisabled = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
        permission_overrides: [
          {
            feature_code: "runtime.start",
            enabled: false
          }
        ]
      }, adminHeaders);
      assert.equal(runtimeStartDisabled.status, 200);
      assert.equal(runtimeStartDisabled.body.ok, true);
      const runtimeStartRevoke = await readRuntimeRevoke(runtimeControlRuntimeStartStream, {timeoutMs: 1200});
      assert.equal(runtimeStartRevoke.reason, "runtime_start_disabled");
    } finally {
      runtimeControlRuntimeStartStream.close();
    }

    const restoredAfterRuntimeStartOverride = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
      status: "active",
      membership_plan: "member",
      permission_overrides: []
    }, adminHeaders);
    assert.equal(restoredAfterRuntimeStartOverride.status, 200);
    assert.equal(restoredAfterRuntimeStartOverride.body.ok, true);

    const runtimeControlProgramAccessStream = await openRuntimeControlStream(ctx, {
      refreshToken: refreshed.body.refresh_token,
      deviceId: "device_alpha"
    });
    try {
      assert.equal(runtimeControlProgramAccessStream.status, 200);
      await readHelloFrame(runtimeControlProgramAccessStream);

      const programAccessDisabled = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
        permission_overrides: [
          {
            feature_code: "program_access_enabled",
            enabled: false
          }
        ]
      }, adminHeaders);
      assert.equal(programAccessDisabled.status, 200);
      assert.equal(programAccessDisabled.body.ok, true);
      const programAccessRevoke = await readRuntimeRevoke(runtimeControlProgramAccessStream, {timeoutMs: 1200});
      assert.equal(programAccessRevoke.reason, "program_access_disabled");
    } finally {
      runtimeControlProgramAccessStream.close();
    }

    const runtimeControlDeniedOnConnectStream = await openRuntimeControlStream(ctx, {
      refreshToken: refreshed.body.refresh_token,
      deviceId: "device_alpha"
    });
    try {
      assert.equal(runtimeControlDeniedOnConnectStream.status, 200);
      await readHelloFrame(runtimeControlDeniedOnConnectStream);
      const deniedOnConnectRevoke = await readRuntimeRevoke(runtimeControlDeniedOnConnectStream, {timeoutMs: 1200});
      assert.equal(deniedOnConnectRevoke.reason, "program_access_disabled");
    } finally {
      runtimeControlDeniedOnConnectStream.close();
    }

    const restoredAfterProgramAccessOverride = await requestJson(ctx, "PATCH", `/api/admin/users/${aliceId}`, {
      status: "active",
      membership_plan: "member",
      permission_overrides: []
    }, adminHeaders);
    assert.equal(restoredAfterProgramAccessOverride.status, 200);
    assert.equal(restoredAfterProgramAccessOverride.body.ok, true);

    const runtimePermitAllowed = await requestJson(ctx, "POST", "/api/auth/runtime-permit", {
      refresh_token: refreshed.body.refresh_token,
      device_id: "device_alpha",
      action: "runtime.start"
    });
    assert.equal(runtimePermitAllowed.status, 200);
    assert.equal(runtimePermitAllowed.body.ok, true);
    assert.equal(runtimePermitAllowed.body.permit.snapshot.action, "runtime.start");

    const runtimePermitInvalidAction = await requestJson(ctx, "POST", "/api/auth/runtime-permit", {
      refresh_token: refreshed.body.refresh_token,
      device_id: "device_alpha",
      action: "runtime.stop"
    });
    assert.equal(runtimePermitInvalidAction.status, 400);
    assert.equal(runtimePermitInvalidAction.body.reason, "runtime_action_invalid");

    const refreshReuse = await requestJson(ctx, "POST", "/api/auth/refresh", {
      refresh_token: registerAlice.complete.body.auth_session.refresh_token,
      device_id: "device_alpha"
    });
    assert.equal(refreshReuse.status, 401);
    assert.ok(
      refreshReuse.body.reason === "refresh_token_replayed" || refreshReuse.body.reason === "refresh_token_not_found",
      `expected replayed or not_found, got: ${refreshReuse.body.reason}`
    );

    // Token family replay detection revoked all sessions in the family.
    // Re-login alice so subsequent device-management tests have an active session.
    const reLoginAlice = await requestJson(ctx, "POST", "/api/auth/login", {
      username: "alice",
      password: "Secret123!",
      device_id: "device_alpha"
    });
    assert.equal(reLoginAlice.status, 200);
    assert.equal(reLoginAlice.body.ok, true);
    // Use the new refreshed token for later tests
    const aliceRefreshToken = reLoginAlice.body.refresh_token;

    const registerBob = await registerUserViaV3(ctx, {
      email: "bob@example.com",
      installId: "install_beta",
      username: "bob",
      password: "Secret123!",
      deviceId: "device_beta"
    });
    assert.equal(ctx.sentMessages[1].code, "654321");

    const usersAfterBob = await requestJson(ctx, "GET", "/api/admin/users", null, adminHeaders);
    assert.equal(usersAfterBob.status, 200);
    assert.equal(usersAfterBob.body.ok, true);
    assert.equal(usersAfterBob.body.items.length, 2);
    const aliceAfterBob = usersAfterBob.body.items.find((item) => item.username === "alice");
    assert.equal(aliceAfterBob.active_device_count, 1);
    assert.equal(aliceAfterBob.entitlements.membership_plan, "member");
    assert.equal(aliceAfterBob.entitlements.feature_flags.program_access_enabled, true);
    const bobId = usersAfterBob.body.items.find((item) => item.username === "bob").id;
    const bobAfterCreate = usersAfterBob.body.items.find((item) => item.username === "bob");
    assert.equal(bobAfterCreate.active_device_count, 1);
    assert.equal(bobAfterCreate.entitlements.membership_plan, "inactive");
    assert.equal(bobAfterCreate.entitlements.feature_flags.program_access_enabled, false);

    const aliceDevices = await requestJson(ctx, "GET", `/api/admin/users/${aliceId}/devices`, null, adminHeaders);
    assert.equal(aliceDevices.status, 200);
    assert.equal(aliceDevices.body.ok, true);
    assert.equal(aliceDevices.body.items.length, 1);
    assert.equal(aliceDevices.body.items[0].device_id, "device_alpha");

    const bobDevices = await requestJson(ctx, "GET", `/api/admin/users/${bobId}/devices`, null, adminHeaders);
    assert.equal(bobDevices.status, 200);
    assert.equal(bobDevices.body.ok, true);
    assert.equal(bobDevices.body.items.length, 1);
    assert.equal(bobDevices.body.items[0].device_id, "device_beta");

    const crossUserRevoke = await requestJson(
      ctx,
      "POST",
      `/api/admin/users/${aliceId}/devices/${bobDevices.body.items[0].id}/revoke`,
      {},
      adminHeaders
    );
    assert.equal(crossUserRevoke.status, 404);
    assert.equal(crossUserRevoke.body.reason, "refresh_session_not_found");

    const bobDevicesAfterCrossAttempt = await requestJson(
      ctx,
      "GET",
      `/api/admin/users/${bobId}/devices`,
      null,
      adminHeaders
    );
    assert.equal(bobDevicesAfterCrossAttempt.status, 200);
    assert.equal(bobDevicesAfterCrossAttempt.body.ok, true);
    assert.equal(bobDevicesAfterCrossAttempt.body.items.length, 1);
    assert.equal(bobDevicesAfterCrossAttempt.body.items[0].id, bobDevices.body.items[0].id);

    const revokeBobDevice = await requestJson(
      ctx,
      "POST",
      `/api/admin/users/${bobId}/devices/${bobDevicesAfterCrossAttempt.body.items[0].id}/revoke`,
      {},
      adminHeaders
    );
    assert.equal(revokeBobDevice.status, 200);
    assert.equal(revokeBobDevice.body.ok, true);

    const bobRefreshAfterRevoke = await requestJson(ctx, "POST", "/api/auth/refresh", {
      refresh_token: registerBob.complete.body.auth_session.refresh_token,
      device_id: "device_beta"
    });
    assert.equal(bobRefreshAfterRevoke.status, 401);
    assert.ok(
      bobRefreshAfterRevoke.body.reason === "refresh_token_replayed" || bobRefreshAfterRevoke.body.reason === "refresh_token_not_found",
      `expected replayed or not_found, got: ${bobRefreshAfterRevoke.body.reason}`
    );

    const revokeDevice = await requestJson(
      ctx,
      "POST",
      `/api/admin/users/${aliceId}/devices/${aliceDevices.body.items[0].id}/revoke`,
      {},
      adminHeaders
    );
    assert.equal(revokeDevice.status, 200);
    assert.equal(revokeDevice.body.ok, true);

    const refreshAfterRevoke = await requestJson(ctx, "POST", "/api/auth/refresh", {
      refresh_token: aliceRefreshToken,
      device_id: "device_alpha"
    });
    assert.equal(refreshAfterRevoke.status, 401);
    assert.ok(
      refreshAfterRevoke.body.reason === "refresh_token_replayed" || refreshAfterRevoke.body.reason === "refresh_token_not_found",
      `expected replayed or not_found, got: ${refreshAfterRevoke.body.reason}`
    );

    const registerCarol = await registerUserViaV3(ctx, {
      email: "carol@example.com",
      installId: "install_gamma",
      username: "carol",
      password: "Secret123!",
      deviceId: "device_gamma"
    });
    assert.equal(ctx.sentMessages[2].code, "777777");

    const resetCarolCode = await requestJson(ctx, "POST", "/api/auth/password/send-reset-code", {
      email: "carol@example.com"
    });
    assert.equal(resetCarolCode.status, 200);
    assert.equal(resetCarolCode.body.ok, true);
    assert.equal(ctx.sentMessages[3].code, "888888");

    const resetCarolPassword = await requestJson(ctx, "POST", "/api/auth/password/reset", {
      email: "carol@example.com",
      code: "888888",
      new_password: "Secret456!"
    });
    assert.equal(resetCarolPassword.status, 200);
    assert.equal(resetCarolPassword.body.ok, true);

    const refreshCarolAfterReset = await requestJson(ctx, "POST", "/api/auth/refresh", {
      refresh_token: registerCarol.complete.body.auth_session.refresh_token,
      device_id: "device_gamma"
    });
    assert.equal(refreshCarolAfterReset.status, 401);
    assert.ok(
      refreshCarolAfterReset.body.reason === "refresh_token_replayed" || refreshCarolAfterReset.body.reason === "refresh_token_not_found",
      `expected replayed or not_found, got: ${refreshCarolAfterReset.body.reason}`
    );

    const loginCarolAfterReset = await requestJson(ctx, "POST", "/api/auth/login", {
      username: "carol",
      password: "Secret456!",
      device_id: "device_gamma"
    });
    assert.equal(loginCarolAfterReset.status, 200);
    assert.equal(loginCarolAfterReset.body.ok, true);

    const resetCode = await requestJson(ctx, "POST", "/api/auth/password/send-reset-code", {
      email: "alice@example.com"
    });
    assert.equal(resetCode.status, 200);
    assert.equal(resetCode.body.ok, true);
    assert.equal(ctx.sentMessages[4].code, "112233");

    const passwordReset = await requestJson(ctx, "POST", "/api/auth/password/reset", {
      email: "alice@example.com",
      code: "112233",
      new_password: "Secret456!"
    });
    assert.equal(passwordReset.status, 200);
    assert.equal(passwordReset.body.ok, true);

    const loginAfterReset = await requestJson(ctx, "POST", "/api/auth/login", {
      username: "alice",
      password: "Secret456!",
      device_id: "device_beta"
    });
    assert.equal(loginAfterReset.status, 200);
    assert.equal(loginAfterReset.body.ok, true);

    const authLogout = await requestJson(ctx, "POST", "/api/auth/logout", {
      refresh_token: loginAfterReset.body.refresh_token
    });
    assert.equal(authLogout.status, 200);
    assert.equal(authLogout.body.ok, true);

    const refreshAfterLogout = await requestJson(ctx, "POST", "/api/auth/refresh", {
      refresh_token: loginAfterReset.body.refresh_token,
      device_id: "device_beta"
    });
    assert.equal(refreshAfterLogout.status, 401);
    assert.ok(
      refreshAfterLogout.body.reason === "refresh_token_replayed" || refreshAfterLogout.body.reason === "refresh_token_not_found",
      `expected replayed or not_found, got: ${refreshAfterLogout.body.reason}`
    );

    const adminLogout = await requestJson(ctx, "POST", "/api/admin/logout", null, adminHeaders);
    assert.equal(adminLogout.status, 200);
    assert.equal(adminLogout.body.ok, true);

    const adminSessionAfterLogout = await requestJson(ctx, "GET", "/api/admin/session", null, adminHeaders);
    assert.equal(adminSessionAfterLogout.status, 401);
    assert.equal(adminSessionAfterLogout.body.reason, "admin_session_not_found");

    const sendRegisterCooldownSeed = await requestJson(ctx, "POST", "/api/auth/register/send-code", {
      email: "cooldown-a@example.com",
      install_id: "install_cooldown"
    });
    assert.equal(sendRegisterCooldownSeed.status, 200);
    assert.equal(sendRegisterCooldownSeed.body.ok, true);
    assert.equal(sendRegisterCooldownSeed.body.resend_after_seconds, 60);

    const sendRegisterCooldownBypass = await requestJson(ctx, "POST", "/api/auth/register/send-code", {
      email: "cooldown-b@example.com",
      install_id: "install_cooldown"
    });
    assert.equal(sendRegisterCooldownBypass.status, 429);
    assert.equal(sendRegisterCooldownBypass.body.error_code, "REGISTER_SEND_RETRY_LATER");
    assert.equal(sendRegisterCooldownBypass.body.retry_after_seconds, 60);

    const sendRegisterWithTypoDomain = await requestJson(ctx, "POST", "/api/auth/register/send-code", {
      email: "1822049852@qq.CO",
      install_id: "install_typo"
    });
    assert.equal(sendRegisterWithTypoDomain.status, 400);
    assert.equal(sendRegisterWithTypoDomain.body.error_code, "REGISTER_INPUT_INVALID");
  } finally {
    await stopServer(ctx);
  }

  console.log("control-plane-server tests passed");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
