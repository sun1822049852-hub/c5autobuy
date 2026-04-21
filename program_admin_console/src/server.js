const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const {DEFAULTS, RUNTIME_PERMIT_ACTIONS} = require("./constants");
const {ControlPlaneStore} = require("./controlPlaneStore");
const {createEntitlementSigner} = require("./entitlementSigner");
const {getMailConfig} = require("./mailConfig");
const {createMailService} = require("./mailService");

function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

function isValidEmail(value = "") {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(toText(value));
}

function writeJson(res, status, payload) {
  const body = Buffer.from(JSON.stringify(payload), "utf8");
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": body.byteLength
  });
  res.end(body);
}

function writeError(res, status, reason, message) {
  writeJson(res, status, {
    ok: false,
    reason: toText(reason),
    message: toText(message)
  });
}

function writeFile(res, status, filePath, contentType) {
  const body = fs.readFileSync(filePath);
  res.writeHead(status, {
    "Content-Type": `${contentType}; charset=utf-8`,
    "Content-Length": body.byteLength
  });
  res.end(body);
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8").trim();
      if (!raw) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

function readBearerToken(req) {
  const authorization = toText(req && req.headers && req.headers.authorization);
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  return match ? toText(match[1]) : "";
}

function isAllowedRuntimePermitAction(action = "") {
  return RUNTIME_PERMIT_ACTIONS.includes(toText(action));
}

function createServer({
  dbPath = "",
  storeFactory = null,
  mailConfigFactory = null,
  mailServiceFactory = null,
  codeGenerator = null,
  now = () => new Date()
} = {}) {
  const uiDir = path.resolve(__dirname, "../ui");
  const store = typeof storeFactory === "function"
    ? storeFactory({dbPath})
    : new ControlPlaneStore({dbPath});
  const config = typeof mailConfigFactory === "function"
    ? mailConfigFactory()
    : getMailConfig();
  const mailService = typeof mailServiceFactory === "function"
    ? mailServiceFactory(config)
    : createMailService({config});
  const signer = createEntitlementSigner({
    privateKeyFile: config.privateKeyFile,
    keyId: config.keyId,
    now,
    snapshotTtlMinutes: Number(config.snapshotTtlMinutes) || DEFAULTS.SNAPSHOT_TTL_MINUTES,
    runtimePermitTtlSeconds: Number(config.runtimePermitTtlSeconds) || DEFAULTS.RUNTIME_PERMIT_TTL_SECONDS
  });
  const nextCode = typeof codeGenerator === "function"
    ? codeGenerator
    : () => String(Math.floor(100000 + Math.random() * 900000));

  async function sendEmailCode({email = "", scene = ""} = {}) {
    if (!config.configured) {
      return {
        ok: false,
        status: 503,
        reason: "mail_service_not_configured",
        message: "mail service not configured"
      };
    }
    const code = toText(nextCode());
    const row = store.createEmailCode({
      email,
      scene,
      code,
      ttlMs: (Number(config.authCodeTtlMinutes) || 5) * 60 * 1000,
      now: now()
    });
    try {
      await mailService.sendVerificationCode({
        to: email,
        code,
        scene,
        ttlMinutes: Number(config.authCodeTtlMinutes) || 5
      });
    } catch (error) {
      store.deleteEmailCode(row.id);
      return {
        ok: false,
        status: 502,
        reason: "mail_send_failed",
        message: toText(error && error.message) || "verification email send failed"
      };
    }
    return {
      ok: true,
      expires_in_seconds: (Number(config.authCodeTtlMinutes) || 5) * 60
    };
  }

  function buildUserBundle(user, deviceId) {
    const entitlements = store.resolveUserEntitlements({userId: user.id, now: now()}) || {
      membership_plan: "inactive",
      permissions: [],
      feature_flags: {
        program_access_enabled: false
      }
    };
    return signer.issueBundle({
      user: {
        ...user,
        membership_plan: entitlements.membership_plan
      },
      deviceId,
      permissions: entitlements.permissions,
      featureFlags: entitlements.feature_flags
    });
  }

  function resolveAdminRequest(req) {
    const sessionToken = readBearerToken(req);
    if (!sessionToken) {
      return {ok: false, reason: "admin_auth_required"};
    }
    return store.resolveAdminSession({
      sessionToken,
      now: now()
    });
  }

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);
    const pathname = url.pathname;
    try {
      if (req.method === "GET") {
        if (pathname === "/admin" || pathname === "/admin/") {
          writeFile(res, 200, path.join(uiDir, "index.html"), "text/html");
          return;
        }

        if (pathname === "/admin/app.js") {
          writeFile(res, 200, path.join(uiDir, "app.js"), "text/javascript");
          return;
        }

        if (pathname === "/admin/styles.css") {
          writeFile(res, 200, path.join(uiDir, "styles.css"), "text/css");
          return;
        }
      }

      if (req.method === "GET" && pathname === "/api/health") {
        writeJson(res, 200, {ok: true});
        return;
      }

      if (req.method === "GET" && pathname === "/api/auth/public-key") {
        writeJson(res, 200, {
          ok: true,
          kid: signer.keyId,
          public_key_pem: signer.publicKeyPem
        });
        return;
      }

      if (req.method === "GET" && pathname === "/api/admin/bootstrap/state") {
        writeJson(res, 200, {
          ok: true,
          needs_bootstrap: store.needsAdminBootstrap()
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/admin/bootstrap") {
        if (!store.needsAdminBootstrap()) {
          writeError(res, 409, "admin_already_exists", "admin bootstrap already completed");
          return;
        }
        const body = await readJsonBody(req);
        const password = toText(body && body.password);
        if (!password) {
          writeError(res, 400, "password_required", "password is required");
          return;
        }
        const user = store.createOrUpdateAdminUser({
          username: toText(body && body.username) || "admin",
          password,
          isSuperAdmin: true,
          now: now()
        });
        writeJson(res, 200, {
          ok: true,
          user
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/admin/login") {
        const body = await readJsonBody(req);
        const auth = store.authenticateAdminUser({
          username: toText(body && body.username) || "admin",
          password: toText(body && body.password)
        });
        if (!auth.ok) {
          writeError(res, 401, auth.reason, "invalid admin credentials");
          return;
        }
        const session = store.createAdminSession({
          adminUserId: auth.user.id,
          ttlHours: Number(config.adminSessionHours) || 12,
          now: now()
        });
        writeJson(res, 200, {
          ok: true,
          user: auth.user,
          session_token: session.session_token,
          expires_at: session.expires_at
        });
        return;
      }

      if (req.method === "GET" && pathname === "/api/admin/session") {
        const sessionToken = readBearerToken(req);
        if (!sessionToken) {
          writeJson(res, 200, {
            ok: true,
            authenticated: false,
            needs_bootstrap: store.needsAdminBootstrap()
          });
          return;
        }
        const resolved = store.resolveAdminSession({
          sessionToken,
          now: now()
        });
        if (!resolved.ok) {
          writeError(res, 401, resolved.reason, "admin session invalid");
          return;
        }
        writeJson(res, 200, {
          ok: true,
          authenticated: true,
          user: resolved.user,
          expires_at: resolved.session.expires_at
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/admin/logout") {
        const sessionToken = readBearerToken(req);
        if (!sessionToken) {
          writeJson(res, 200, {ok: true});
          return;
        }
        const revoked = store.revokeAdminSession({
          sessionToken,
          now: now()
        });
        if (!revoked.ok) {
          writeError(res, 401, revoked.reason, "admin session invalid");
          return;
        }
        writeJson(res, 200, {ok: true});
        return;
      }

      if (pathname.startsWith("/api/admin/")) {
        const admin = resolveAdminRequest(req);
        if (!admin.ok) {
          writeError(res, 401, admin.reason, "admin auth required");
          return;
        }

        if (req.method === "GET" && pathname === "/api/admin/users") {
          writeJson(res, 200, {
            ok: true,
            items: store.listClientUsers().map((user) => ({
              ...user,
              entitlements: store.resolveUserEntitlements({userId: user.id, now: now()}),
              active_device_count: store.listUserDeviceSessions({userId: user.id}).length
            }))
          });
          return;
        }

        const patchUserMatch = pathname.match(/^\/api\/admin\/users\/(\d+)$/);
        if (req.method === "PATCH" && patchUserMatch) {
          const body = await readJsonBody(req);
          const result = store.updateClientUserControl({
            userId: Number(patchUserMatch[1]) || 0,
            status: toText(body && body.status),
            membershipPlan: toText(body && body.membership_plan),
            membershipExpiresAt: body && Object.prototype.hasOwnProperty.call(body, "membership_expires_at")
              ? toText(body.membership_expires_at)
              : undefined,
            permissionOverrides: Array.isArray(body && body.permission_overrides) ? body.permission_overrides : null,
            now: now()
          });
          if (!result.ok) {
            writeError(res, result.reason === "user_not_found" ? 404 : 400, result.reason, "user update failed");
            return;
          }
          writeJson(res, 200, result);
          return;
        }

        const userDevicesMatch = pathname.match(/^\/api\/admin\/users\/(\d+)\/devices$/);
        if (req.method === "GET" && userDevicesMatch) {
          const userId = Number(userDevicesMatch[1]) || 0;
          const user = store.getClientUserById(userId);
          if (!user) {
            writeError(res, 404, "user_not_found", "user not found");
            return;
          }
          writeJson(res, 200, {
            ok: true,
            user,
            items: store.listUserDeviceSessions({userId})
          });
          return;
        }

        const revokeDeviceMatch = pathname.match(/^\/api\/admin\/users\/(\d+)\/devices\/(\d+)\/revoke$/);
        if (req.method === "POST" && revokeDeviceMatch) {
          const userId = Number(revokeDeviceMatch[1]) || 0;
          const sessionId = Number(revokeDeviceMatch[2]) || 0;
          const user = store.getClientUserById(userId);
          if (!user) {
            writeError(res, 404, "user_not_found", "user not found");
            return;
          }
          const revoked = store.revokeRefreshSessionForUserById({
            userId,
            sessionId,
            now: now()
          });
          if (!revoked.ok) {
            writeError(res, 404, revoked.reason, "device session not found");
            return;
          }
          writeJson(res, 200, {ok: true});
          return;
        }

        writeError(res, 404, "not_found", "route not found");
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/email/send-code") {
        const body = await readJsonBody(req);
        const email = toText(body && body.email).toLowerCase();
        if (!isValidEmail(email)) {
          writeError(res, 400, "email_invalid", "email is invalid");
          return;
        }
        const sent = await sendEmailCode({
          email,
          scene: "register"
        });
        if (!sent.ok) {
          writeError(res, sent.status, sent.reason, sent.message);
          return;
        }
        writeJson(res, 200, {ok: true, expires_in_seconds: sent.expires_in_seconds});
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/register") {
        const body = await readJsonBody(req);
        const email = toText(body && body.email).toLowerCase();
        const code = toText(body && body.code);
        const username = toText(body && body.username);
        const password = toText(body && body.password);
        if (!isValidEmail(email) || !code || !username || !password) {
          writeError(res, 400, "register_payload_invalid", "register payload invalid");
          return;
        }
        const verified = store.verifyEmailCode({
          email,
          scene: "register",
          code,
          now: now()
        });
        if (!verified.ok) {
          writeError(res, 400, verified.reason, "email code invalid");
          return;
        }
        if (store.getClientUserByEmail(email) || store.getClientUserByUsername(username)) {
          writeError(res, 409, "user_already_exists", "user already exists");
          return;
        }
        const user = store.createClientUser({
          email,
          username,
          password,
          membershipPlan: "inactive",
          now: now()
        });
        writeJson(res, 200, {
          ok: true,
          user
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/login") {
        const body = await readJsonBody(req);
        const username = toText(body && body.username);
        const password = toText(body && body.password);
        const deviceId = toText(body && body.device_id);
        if (!username || !password || !deviceId) {
          writeError(res, 400, "login_payload_invalid", "username, password and device_id are required");
          return;
        }
        const auth = store.authenticateClientUser({username, password});
        if (!auth.ok) {
          writeError(res, 401, auth.reason, "invalid credentials");
          return;
        }
        const session = store.createRefreshSession({
          userId: auth.user.id,
          deviceId,
          ttlDays: Number(config.refreshSessionDays) || 30,
          now: now()
        });
        writeJson(res, 200, {
          ok: true,
          refresh_token: session.refresh_token,
          access_bundle: buildUserBundle(auth.user, deviceId),
          user: auth.user
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/refresh") {
        const body = await readJsonBody(req);
        const refreshToken = toText(body && body.refresh_token);
        const deviceId = toText(body && body.device_id);
        if (!refreshToken || !deviceId) {
          writeError(res, 400, "refresh_payload_invalid", "refresh_token and device_id are required");
          return;
        }
        const rotated = store.rotateRefreshSession({
          refreshToken,
          deviceId,
          ttlDays: Number(config.refreshSessionDays) || 30,
          now: now()
        });
        if (!rotated.ok) {
          writeError(res, rotated.reason === "device_mismatch" ? 409 : 401, rotated.reason, "refresh denied");
          return;
        }
        writeJson(res, 200, {
          ok: true,
          refresh_token: rotated.refresh_token,
          access_bundle: buildUserBundle(rotated.user, deviceId),
          user: rotated.user
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/logout") {
        const body = await readJsonBody(req);
        const refreshToken = toText(body && body.refresh_token);
        if (!refreshToken) {
          writeJson(res, 200, {ok: true});
          return;
        }
        const revoked = store.revokeRefreshSession({
          refreshToken,
          now: now()
        });
        if (!revoked.ok) {
          writeError(res, 401, revoked.reason, "refresh token invalid");
          return;
        }
        writeJson(res, 200, {ok: true});
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/password/send-reset-code") {
        const body = await readJsonBody(req);
        const email = toText(body && body.email).toLowerCase();
        if (!isValidEmail(email)) {
          writeError(res, 400, "email_invalid", "email is invalid");
          return;
        }
        if (!config.configured) {
          writeError(res, 503, "mail_service_not_configured", "mail service not configured");
          return;
        }
        if (!store.getClientUserByEmail(email)) {
          writeError(res, 404, "user_not_found", "user not found");
          return;
        }
        const sent = await sendEmailCode({
          email,
          scene: "reset_password"
        });
        if (!sent.ok) {
          writeError(res, sent.status, sent.reason, sent.message);
          return;
        }
        writeJson(res, 200, {ok: true, expires_in_seconds: sent.expires_in_seconds});
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/password/reset") {
        const body = await readJsonBody(req);
        const email = toText(body && body.email).toLowerCase();
        const code = toText(body && body.code);
        const newPassword = toText(body && body.new_password);
        if (!isValidEmail(email) || !code || !newPassword) {
          writeError(res, 400, "reset_payload_invalid", "reset payload invalid");
          return;
        }
        const verified = store.verifyEmailCode({
          email,
          scene: "reset_password",
          code,
          now: now()
        });
        if (!verified.ok) {
          writeError(res, 400, verified.reason, "email code invalid");
          return;
        }
        const updated = store.updateClientPassword({
          email,
          newPassword,
          now: now()
        });
        if (!updated.ok) {
          writeError(res, 404, updated.reason, "user not found");
          return;
        }
        writeJson(res, 200, {ok: true});
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/runtime-permit") {
        const body = await readJsonBody(req);
        const refreshToken = toText(body && body.refresh_token);
        const deviceId = toText(body && body.device_id);
        const action = toText(body && body.action) || "runtime.start";
        if (!refreshToken || !deviceId) {
          writeError(res, 400, "runtime_permit_payload_invalid", "refresh_token and device_id are required");
          return;
        }
        if (!isAllowedRuntimePermitAction(action)) {
          writeError(res, 400, "runtime_action_invalid", "runtime action is invalid");
          return;
        }
        const resolved = store.resolveRefreshSession({
          refreshToken,
          deviceId,
          now: now()
        });
        if (!resolved.ok) {
          writeError(res, resolved.reason === "device_mismatch" ? 409 : 401, resolved.reason, "runtime permit denied");
          return;
        }
        const entitlements = store.resolveUserEntitlements({
          userId: resolved.user.id,
          now: now()
        });
        if (!entitlements || !entitlements.permissions.includes("runtime.start")) {
          writeError(res, 403, "runtime_permission_denied", "runtime permission denied");
          return;
        }
        writeJson(res, 200, {
          ok: true,
          permit: signer.issueRuntimePermit({
            user: {
              ...resolved.user,
              membership_plan: entitlements.membership_plan
            },
            deviceId,
            action
          })
        });
        return;
      }

      writeError(res, 404, "not_found", "route not found");
    } catch (error) {
      writeError(res, 500, "internal_error", error && error.message ? error.message : "internal error");
    }
  });

  server.on("close", () => {
    store.close();
  });

  return server;
}

async function main() {
  const config = getMailConfig();
  const server = createServer({
    mailConfigFactory: () => config
  });
  await new Promise((resolve) => server.listen(config.port, config.host, resolve));
  console.log(`[program_admin_console] listening on http://${config.host}:${config.port}`);
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}

module.exports = {
  createServer
};
