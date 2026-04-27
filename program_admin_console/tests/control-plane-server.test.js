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
  const server = createServer({
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
  });
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

    const refreshed = await requestJson(ctx, "POST", "/api/auth/refresh", {
      refresh_token: registerAlice.complete.body.auth_session.refresh_token,
      device_id: "device_alpha"
    });
    assert.equal(refreshed.status, 200);
    assert.equal(refreshed.body.ok, true);
    assert.notEqual(refreshed.body.refresh_token, registerAlice.complete.body.auth_session.refresh_token);
    assert.equal(refreshed.body.access_bundle.snapshot.permissions.includes("program_access_enabled"), true);

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
