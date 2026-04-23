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

function createRequestId() {
  return `req_${Math.random().toString(36).slice(2, 12)}${Date.now().toString(36).slice(-4)}`;
}

function writeRegisterV3Error(
  res,
  status,
  {
    errorCode = "REGISTER_SERVICE_UNAVAILABLE",
    message = "register service unavailable",
    requestId = "",
    retryAfterSeconds = null,
    retryAfterHeader = false
  } = {}
) {
  const payload = {
    ok: false,
    error_code: toText(errorCode) || "REGISTER_SERVICE_UNAVAILABLE",
    message: toText(message) || "register service unavailable",
    request_id: toText(requestId) || createRequestId()
  };
  if (Number.isFinite(Number(retryAfterSeconds)) && Number(retryAfterSeconds) >= 0) {
    payload.retry_after_seconds = Number(retryAfterSeconds);
  }
  const headers = {};
  if (retryAfterHeader && Number.isFinite(Number(retryAfterSeconds)) && Number(retryAfterSeconds) >= 0) {
    headers["Retry-After"] = String(Number(retryAfterSeconds));
  }
  const body = Buffer.from(JSON.stringify(payload), "utf8");
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": body.byteLength,
    ...headers
  });
  res.end(body);
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

function maskEmail(email = "") {
  const [localRaw = "", domainRaw = ""] = toText(email).toLowerCase().split("@");
  const local = toText(localRaw);
  const domain = toText(domainRaw);
  if (!local || !domain) {
    return "*@*";
  }
  if (local.length <= 2) {
    return `${local.slice(0, 1)}*@${domain}`;
  }
  return `${local.slice(0, 1)}***${local.slice(-1)}@${domain}`;
}

function isStrongPassword(value = "") {
  const text = toText(value);
  if (text.length < 8 || text.length > 64) {
    return false;
  }
  return /[A-Za-z]/.test(text) && /\d/.test(text);
}

function isValidUsername(value = "") {
  return /^[A-Za-z0-9_]{3,32}$/.test(toText(value));
}

function getSourceIp(req) {
  const xff = toText(req && req.headers && req.headers["x-forwarded-for"]);
  if (xff) {
    return toText(xff.split(",")[0]);
  }
  return toText(req && req.socket && req.socket.remoteAddress);
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
  const registerConfig = Object.freeze({
    codeLength: 6,
    codeExpiresInSeconds: 600,
    sessionTtlSeconds: 1800,
    resendAfterSeconds: 60,
    ticketExpiresInSeconds: 900,
    maxSessionSends: 5,
    maxVerifyAttempts: 5,
    idempotencyWindowSeconds: 2
  });

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

  function evaluateRegisterSendLimits({
    email = "",
    installId = "",
    sourceIp = "",
    deviceFingerprint = "",
    session = null
  } = {}) {
    const nowValue = now();
    const nowMs = Date.parse(nowValue.toISOString());
    if (session) {
      if ((Number(session.send_count) || 0) >= registerConfig.maxSessionSends) {
        store.invalidateRegisterSession({registerSessionId: session.id, now: nowValue});
        return {
          ok: false,
          status: 410,
          error_code: "REGISTER_SESSION_INVALID",
          message: "register session invalid"
        };
      }
      const resendAllowedMs = Date.parse(toText(session.resend_allowed_at));
      if (Number.isFinite(resendAllowedMs) && resendAllowedMs > nowMs) {
        const retryAfter = Math.max(1, Math.ceil((resendAllowedMs - nowMs) / 1000));
        return {
          ok: false,
          status: 429,
          error_code: "REGISTER_SEND_RETRY_LATER",
          message: "register send is cooling down",
          retry_after_seconds: retryAfter
        };
      }
    }
    const checks = [
      {field: "email", value: email, windowSeconds: 60, limit: 1},
      {field: "email", value: email, windowSeconds: 24 * 60 * 60, limit: 5},
      {field: "install_id", value: installId, windowSeconds: 10 * 60, limit: 3},
      {field: "install_id", value: installId, windowSeconds: 24 * 60 * 60, limit: 20},
      {field: "source_ip", value: sourceIp, windowSeconds: 10 * 60, limit: 10},
      {field: "source_ip", value: sourceIp, windowSeconds: 24 * 60 * 60, limit: 50},
      {field: "device_fingerprint", value: deviceFingerprint, windowSeconds: 10 * 60, limit: 3},
      {field: "device_fingerprint", value: deviceFingerprint, windowSeconds: 24 * 60 * 60, limit: 20}
    ];
    for (const check of checks) {
      if (!toText(check.value)) {
        continue;
      }
      const stat = store.countRegisterSendsByWindow({
        field: check.field,
        value: check.value,
        windowSeconds: check.windowSeconds,
        now: nowValue
      });
      if ((Number(stat.count) || 0) >= check.limit) {
        const retryAfter = stat.earliest_ms > 0
          ? Math.max(1, Math.ceil((stat.earliest_ms + check.windowSeconds * 1000 - nowMs) / 1000))
          : check.windowSeconds;
        return {
          ok: false,
          status: 429,
          error_code: "REGISTER_SEND_RETRY_LATER",
          message: "register send is rate limited",
          retry_after_seconds: retryAfter
        };
      }
    }
    return {ok: true};
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

      if (req.method === "GET" && pathname === "/api/auth/register/capability") {
        const ready = Boolean(config.configured);
        writeJson(res, 200, {
          ok: true,
          registration_flow_version: ready ? 3 : 2,
          registration_v3: {
            ready,
            endpoints: {
              send_code: "/api/auth/register/send-code",
              verify_code: "/api/auth/register/verify-code",
              complete: "/api/auth/register/complete"
            }
          },
          legacy: {
            send_code: "/api/auth/email/send-code",
            register: "/api/auth/register"
          }
        });
        return;
      }

      if (req.method === "GET" && pathname === "/api/auth/register/readiness") {
        const ready = Boolean(config.configured);
        writeJson(res, 200, {
          ok: true,
          ready,
          registration_flow_version: ready ? 3 : 2,
          mail_service_configured: ready
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

      if (req.method === "POST" && pathname === "/api/auth/register/send-code") {
        const requestId = createRequestId();
        const body = await readJsonBody(req);
        const email = toText(body && body.email).toLowerCase();
        const installId = toText(body && body.install_id) || "unknown_install";
        const registerSessionId = toText(body && body.register_session_id);
        const deviceFingerprint = toText(body && body.device_fingerprint);
        const sourceIp = getSourceIp(req);

        if (!isValidEmail(email)) {
          writeRegisterV3Error(res, 400, {
            errorCode: "REGISTER_INPUT_INVALID",
            message: "email is invalid",
            requestId
          });
          return;
        }
        if (store.getClientUserByEmail(email)) {
          writeRegisterV3Error(res, 403, {
            errorCode: "REGISTER_SEND_DENIED",
            message: "register send denied",
            requestId
          });
          return;
        }
        if (!config.configured) {
          writeRegisterV3Error(res, 503, {
            errorCode: "REGISTER_SERVICE_UNAVAILABLE",
            message: "mail service not configured",
            requestId
          });
          return;
        }

        store.purgeExpiredRegisterArtifacts({now: now()});
        let session = registerSessionId
          ? store.getRegisterSessionById(registerSessionId)
          : store.getLatestPendingRegisterSession({
            email,
            installId,
            now: now()
          });
        if (session && session.email !== email) {
          writeRegisterV3Error(res, 409, {
            errorCode: "REGISTER_SESSION_EMAIL_MISMATCH",
            message: "register session email mismatch",
            requestId
          });
          return;
        }
        if (session && session.install_id !== installId) {
          writeRegisterV3Error(res, 410, {
            errorCode: "REGISTER_SESSION_INVALID",
            message: "register session invalid",
            requestId
          });
          return;
        }
        const idempotencyKey = `${email}|${installId}|${session ? session.id : ""}`;
        const idempotentSession = store.getRegisterSendIdempotentHit({
          idempotencyKey,
          now: now()
        });
        if (idempotentSession) {
          const nowMs = Date.parse(now().toISOString());
          const resendMs = Date.parse(toText(idempotentSession.resend_allowed_at));
          const resendAfter = Number.isFinite(resendMs)
            ? Math.max(0, Math.ceil((resendMs - nowMs) / 1000))
            : registerConfig.resendAfterSeconds;
          writeJson(res, 200, {
            ok: true,
            register_session_id: idempotentSession.id,
            masked_email: maskEmail(email),
            code_length: registerConfig.codeLength,
            code_expires_in_seconds: registerConfig.codeExpiresInSeconds,
            resend_after_seconds: resendAfter
          });
          return;
        }
        if (!session) {
          session = store.beginRegisterSendSession({
            email,
            installId,
            deviceFingerprint,
            sessionTtlSeconds: registerConfig.sessionTtlSeconds,
            now: now()
          });
        }
        const limitResult = evaluateRegisterSendLimits({
          email,
          installId,
          sourceIp,
          deviceFingerprint,
          session
        });
        if (!limitResult.ok) {
          writeRegisterV3Error(res, Number(limitResult.status) || 429, {
            errorCode: limitResult.error_code || "REGISTER_SEND_RETRY_LATER",
            message: limitResult.message || "register send denied",
            requestId,
            retryAfterSeconds: Number(limitResult.retry_after_seconds) || undefined,
            retryAfterHeader: true
          });
          return;
        }
        const code = toText(nextCode());
        try {
          await mailService.sendVerificationCode({
            to: email,
            code,
            scene: "register_v3",
            ttlMinutes: Math.ceil(registerConfig.codeExpiresInSeconds / 60)
          });
        } catch (error) {
          writeRegisterV3Error(res, 503, {
            errorCode: "REGISTER_SERVICE_UNAVAILABLE",
            message: toText(error && error.message) || "verification email send failed",
            requestId
          });
          return;
        }
        const recorded = store.recordRegisterCodeDispatch({
          registerSessionId: session.id,
          code,
          codeExpiresInSeconds: registerConfig.codeExpiresInSeconds,
          resendAfterSeconds: registerConfig.resendAfterSeconds,
          sourceIp,
          now: now()
        });
        if (!recorded.ok || !recorded.session) {
          writeRegisterV3Error(res, 503, {
            errorCode: "REGISTER_SERVICE_UNAVAILABLE",
            message: "register send persistence failed",
            requestId
          });
          return;
        }
        store.rememberRegisterSendIdempotency({
          idempotencyKey,
          registerSessionId: recorded.session.id,
          windowSeconds: registerConfig.idempotencyWindowSeconds,
          now: now()
        });
        writeJson(res, 200, {
          ok: true,
          register_session_id: recorded.session.id,
          masked_email: maskEmail(email),
          code_length: registerConfig.codeLength,
          code_expires_in_seconds: registerConfig.codeExpiresInSeconds,
          resend_after_seconds: registerConfig.resendAfterSeconds
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/register/verify-code") {
        const requestId = createRequestId();
        const body = await readJsonBody(req);
        const email = toText(body && body.email).toLowerCase();
        const code = toText(body && body.code);
        const registerSessionId = toText(body && body.register_session_id);
        const installId = toText(body && body.install_id) || "unknown_install";
        if (!isValidEmail(email) || !code || !registerSessionId) {
          writeRegisterV3Error(res, 400, {
            errorCode: "REGISTER_INPUT_INVALID",
            message: "verify payload invalid",
            requestId
          });
          return;
        }
        const verified = store.verifyRegisterCode({
          email,
          code,
          registerSessionId,
          installId,
          ticketTtlSeconds: registerConfig.ticketExpiresInSeconds,
          maxVerifyAttempts: registerConfig.maxVerifyAttempts,
          now: now()
        });
        if (!verified.ok) {
          const reason = toText(verified.reason);
          if (reason === "register_session_email_mismatch") {
            writeRegisterV3Error(res, 409, {
              errorCode: "REGISTER_SESSION_EMAIL_MISMATCH",
              message: "register session email mismatch",
              requestId
            });
            return;
          }
          if (reason === "register_code_attempts_exceeded") {
            writeRegisterV3Error(res, 429, {
              errorCode: "REGISTER_CODE_ATTEMPTS_EXCEEDED",
              message: "register code attempts exceeded",
              requestId
            });
            return;
          }
          if (reason === "register_session_invalid") {
            writeRegisterV3Error(res, 410, {
              errorCode: "REGISTER_SESSION_INVALID",
              message: "register session invalid",
              requestId
            });
            return;
          }
          writeRegisterV3Error(res, 400, {
            errorCode: "REGISTER_CODE_INVALID_OR_EXPIRED",
            message: "register code invalid or expired",
            requestId
          });
          return;
        }
        writeJson(res, 200, {
          ok: true,
          verification_ticket: verified.verification_ticket,
          ticket_expires_in_seconds: registerConfig.ticketExpiresInSeconds
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/auth/register/complete") {
        const requestId = createRequestId();
        const body = await readJsonBody(req);
        const email = toText(body && body.email).toLowerCase();
        const username = toText(body && body.username);
        const password = toText(body && body.password);
        const verificationTicket = toText(body && body.verification_ticket);
        const installId = toText(body && body.install_id) || "unknown_install";
        const deviceId = toText(body && body.device_id) || `install:${installId}`;

        if (!isValidEmail(email) || !username || !password || !verificationTicket) {
          writeRegisterV3Error(res, 400, {
            errorCode: "REGISTER_INPUT_INVALID",
            message: "register complete payload invalid",
            requestId
          });
          return;
        }
        if (!isValidUsername(username)) {
          writeRegisterV3Error(res, 400, {
            errorCode: "REGISTER_USERNAME_INVALID",
            message: "username is invalid",
            requestId
          });
          return;
        }
        if (!isStrongPassword(password)) {
          writeRegisterV3Error(res, 400, {
            errorCode: "REGISTER_PASSWORD_WEAK",
            message: "password is weak",
            requestId
          });
          return;
        }
        const consumed = store.consumeVerificationTicket({
          verificationTicket,
          email,
          installId,
          now: now()
        });
        if (!consumed.ok) {
          writeRegisterV3Error(res, 410, {
            errorCode: "REGISTER_TICKET_INVALID_OR_EXPIRED",
            message: "verification ticket invalid or expired",
            requestId
          });
          return;
        }
        if (store.getClientUserByEmail(email)) {
          writeRegisterV3Error(res, 409, {
            errorCode: "REGISTER_EMAIL_UNAVAILABLE",
            message: "email is unavailable",
            requestId
          });
          return;
        }
        if (store.getClientUserByUsername(username)) {
          writeRegisterV3Error(res, 409, {
            errorCode: "REGISTER_USERNAME_TAKEN",
            message: "username already exists",
            requestId
          });
          return;
        }
        let user;
        try {
          user = store.createClientUser({
            email,
            username,
            password,
            membershipPlan: "inactive",
            now: now()
          });
        } catch (error) {
          writeRegisterV3Error(res, 503, {
            errorCode: "REGISTER_SERVICE_UNAVAILABLE",
            message: toText(error && error.message) || "register create user failed",
            requestId
          });
          return;
        }
        store.finalizeRegisterSession({
          registerSessionId: consumed.ticket.register_session_id,
          now: now()
        });
        const session = store.createRefreshSession({
          userId: user.id,
          deviceId,
          ttlDays: Number(config.refreshSessionDays) || 30,
          now: now()
        });
        writeJson(res, 200, {
          ok: true,
          account_summary: {
            id: user.id,
            email: user.email,
            username: user.username,
            membership_plan: user.membership_plan
          },
          auth_session: {
            refresh_token: session.refresh_token,
            access_bundle: buildUserBundle(user, deviceId),
            user
          }
        });
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
