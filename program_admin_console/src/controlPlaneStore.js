const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const {DatabaseSync} = require("node:sqlite");
const {MEMBERSHIP_PLANS, PATHS} = require("./constants");

function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

function nowIso(now = new Date()) {
  return now instanceof Date ? now.toISOString() : new Date(now).toISOString();
}

function parseMs(value = "") {
  const ms = Date.parse(toText(value));
  return Number.isFinite(ms) ? ms : 0;
}

function hashPassword(password = "") {
  const text = toText(password);
  if (!text) {
    throw new Error("password is required");
  }
  const salt = crypto.randomBytes(16).toString("hex");
  const digest = crypto.scryptSync(text, salt, 64).toString("hex");
  return `scrypt$${salt}$${digest}`;
}

function verifyPassword(passwordHash = "", password = "") {
  const text = toText(password);
  const [scheme, salt, digest] = toText(passwordHash).split("$");
  if (scheme !== "scrypt" || !salt || !digest || !text) {
    return false;
  }
  const actual = crypto.scryptSync(text, salt, 64).toString("hex");
  return crypto.timingSafeEqual(Buffer.from(actual, "hex"), Buffer.from(digest, "hex"));
}

function hashToken(token = "") {
  return crypto.createHash("sha256").update(toText(token)).digest("hex");
}

function createOpaqueToken(bytes = 24) {
  return crypto.randomBytes(bytes).toString("base64url");
}

function createId(prefix = "id") {
  return `${toText(prefix) || "id"}_${createOpaqueToken(12)}`;
}

function normalizePlan(code = "") {
  return toText(code).toLowerCase() === "member" ? "member" : "inactive";
}

function parsePermissions(raw = "[]") {
  try {
    const value = JSON.parse(raw);
    if (!Array.isArray(value)) {
      return [];
    }
    return [...new Set(value.map((item) => toText(item)).filter(Boolean))].sort();
  } catch {
    return [];
  }
}

function mapClientUser(row) {
  if (!row) {
    return null;
  }
  return {
    id: Number(row.id) || 0,
    email: toText(row.email),
    username: toText(row.username),
    status: toText(row.status) || "active",
    membership_plan: normalizePlan(row.membership_plan),
    membership_expires_at: toText(row.membership_expires_at),
    created_at: toText(row.created_at),
    updated_at: toText(row.updated_at)
  };
}

function mapAdminUser(row) {
  if (!row) {
    return null;
  }
  return {
    id: Number(row.id) || 0,
    username: toText(row.username),
    status: toText(row.status) || "active",
    is_super_admin: Number(row.is_super_admin) === 1,
    created_at: toText(row.created_at),
    updated_at: toText(row.updated_at)
  };
}

class ControlPlaneStore {
  constructor({dbPath = PATHS.DEFAULT_DB_FILE} = {}) {
    const resolvedDbPath = path.resolve(toText(dbPath) || PATHS.DEFAULT_DB_FILE);
    fs.mkdirSync(path.dirname(resolvedDbPath), {recursive: true});
    this.db = new DatabaseSync(resolvedDbPath);
    this.db.exec("PRAGMA foreign_keys = ON");
    this.ensureSchema();
    this.seedMembershipPlans();
  }

  close() {
    if (this.db) {
      this.db.close();
    }
  }

  runInTransaction(fn) {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = fn();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  ensureSchema() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS email_code (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        scene TEXT NOT NULL,
        code_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        consumed_at TEXT NOT NULL DEFAULT ''
      );

      CREATE TABLE IF NOT EXISTS client_user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        membership_plan TEXT NOT NULL DEFAULT 'inactive',
        membership_expires_at TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS admin_user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        is_super_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS admin_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT NOT NULL UNIQUE,
        admin_user_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked_at TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (admin_user_id) REFERENCES admin_user(id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS membership_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        permissions_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS client_user_feature_override (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        feature_code TEXT NOT NULL,
        enabled INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user_id, feature_code),
        FOREIGN KEY (user_id) REFERENCES client_user(id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS refresh_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        device_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_used_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked_at TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (user_id) REFERENCES client_user(id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS register_session (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        install_id TEXT NOT NULL,
        device_fingerprint TEXT NOT NULL DEFAULT '',
        session_state TEXT NOT NULL DEFAULT 'pending',
        code_hash TEXT NOT NULL DEFAULT '',
        code_expires_at TEXT NOT NULL DEFAULT '',
        session_expires_at TEXT NOT NULL,
        resend_allowed_at TEXT NOT NULL DEFAULT '',
        send_count INTEGER NOT NULL DEFAULT 0,
        verify_attempt_count INTEGER NOT NULL DEFAULT 0,
        last_sent_at TEXT NOT NULL DEFAULT '',
        verified_at TEXT NOT NULL DEFAULT '',
        completed_at TEXT NOT NULL DEFAULT '',
        invalidated_at TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_register_session_email_install
      ON register_session(email, install_id, session_state, session_expires_at);

      CREATE TABLE IF NOT EXISTS register_send_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        install_id TEXT NOT NULL,
        source_ip TEXT NOT NULL DEFAULT '',
        device_fingerprint TEXT NOT NULL DEFAULT '',
        register_session_id TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_register_send_ledger_email_created
      ON register_send_ledger(email, created_at);
      CREATE INDEX IF NOT EXISTS idx_register_send_ledger_install_created
      ON register_send_ledger(install_id, created_at);
      CREATE INDEX IF NOT EXISTS idx_register_send_ledger_source_ip_created
      ON register_send_ledger(source_ip, created_at);
      CREATE INDEX IF NOT EXISTS idx_register_send_ledger_device_created
      ON register_send_ledger(device_fingerprint, created_at);

      CREATE TABLE IF NOT EXISTS register_send_idempotency (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idempotency_key TEXT NOT NULL UNIQUE,
        register_session_id TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_register_send_idempotency_expires
      ON register_send_idempotency(expires_at);

      CREATE TABLE IF NOT EXISTS register_verification_ticket (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_hash TEXT NOT NULL UNIQUE,
        register_session_id TEXT NOT NULL,
        email TEXT NOT NULL,
        install_id TEXT NOT NULL,
        device_fingerprint TEXT NOT NULL DEFAULT '',
        expires_at TEXT NOT NULL,
        consumed_at TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_register_ticket_lookup
      ON register_verification_ticket(register_session_id, email, install_id, consumed_at, expires_at);
    `);
  }

  seedMembershipPlans() {
    const stamp = nowIso();
    const expectedCodes = new Set(MEMBERSHIP_PLANS.map((item) => item.code));
    const existing = this.db.prepare("SELECT code FROM membership_plan").all();
    for (const row of existing) {
      const code = toText(row.code);
      if (!expectedCodes.has(code)) {
        this.db.prepare("DELETE FROM membership_plan WHERE code = ?").run(code);
      }
    }
    for (const plan of MEMBERSHIP_PLANS) {
      const row = this.db.prepare("SELECT id FROM membership_plan WHERE code = ?").get(plan.code);
      const permissionsJson = JSON.stringify(plan.permissions);
      if (row) {
        this.db.prepare(`
          UPDATE membership_plan
          SET permissions_json = ?, updated_at = ?
          WHERE code = ?
        `).run(permissionsJson, stamp, plan.code);
      } else {
        this.db.prepare(`
          INSERT INTO membership_plan(code, permissions_json, created_at, updated_at)
          VALUES(?, ?, ?, ?)
        `).run(plan.code, permissionsJson, stamp, stamp);
      }
    }
  }

  listMembershipPlans() {
    const rows = this.db.prepare("SELECT * FROM membership_plan ORDER BY code ASC").all();
    return rows.map((row) => ({
      id: Number(row.id) || 0,
      code: toText(row.code),
      permissions: parsePermissions(row.permissions_json),
      created_at: toText(row.created_at),
      updated_at: toText(row.updated_at)
    }));
  }

  getMembershipPlanByCode(code = "") {
    const row = this.db.prepare("SELECT * FROM membership_plan WHERE code = ?").get(normalizePlan(code));
    if (!row) {
      return null;
    }
    return {
      id: Number(row.id) || 0,
      code: toText(row.code),
      permissions: parsePermissions(row.permissions_json)
    };
  }

  getClientUserById(userId = 0) {
    return mapClientUser(this.db.prepare("SELECT * FROM client_user WHERE id = ?").get(Number(userId) || 0));
  }

  getClientUserByEmail(email = "") {
    return mapClientUser(this.db.prepare("SELECT * FROM client_user WHERE email = ?").get(toText(email).toLowerCase()));
  }

  getClientUserByUsername(username = "") {
    return mapClientUser(this.db.prepare("SELECT * FROM client_user WHERE username = ?").get(toText(username)));
  }

  listClientUsers() {
    const rows = this.db.prepare("SELECT * FROM client_user ORDER BY id ASC").all();
    return rows.map((row) => mapClientUser(row));
  }

  createClientUser({
    email = "",
    username = "",
    password = "",
    membershipPlan = "inactive",
    membershipExpiresAt = "",
    now = new Date()
  } = {}) {
    const emailText = toText(email).toLowerCase();
    const usernameText = toText(username);
    if (!emailText || !usernameText) {
      throw new Error("email and username are required");
    }
    const stamp = nowIso(now);
    const result = this.db.prepare(`
      INSERT INTO client_user(
        email, username, password_hash, status, membership_plan, membership_expires_at, created_at, updated_at
      ) VALUES(?, ?, ?, 'active', ?, ?, ?, ?)
    `).run(
      emailText,
      usernameText,
      hashPassword(password),
      normalizePlan(membershipPlan),
      toText(membershipExpiresAt),
      stamp,
      stamp
    );
    return this.getClientUserById(result.lastInsertRowid);
  }

  authenticateClientUser({username = "", password = ""} = {}) {
    const row = this.db.prepare("SELECT * FROM client_user WHERE username = ?").get(toText(username));
    if (!row || !verifyPassword(row.password_hash, password)) {
      return {ok: false, reason: "invalid_credentials"};
    }
    if (toText(row.status) !== "active") {
      return {ok: false, reason: "user_disabled"};
    }
    return {
      ok: true,
      user: mapClientUser(row)
    };
  }

  updateClientPassword({email = "", newPassword = "", now = new Date()} = {}) {
    const user = this.getClientUserByEmail(email);
    if (!user) {
      return {ok: false, reason: "user_not_found"};
    }
    const stamp = nowIso(now);
    this.runInTransaction(() => {
      this.db.prepare(`
        UPDATE client_user
        SET password_hash = ?, updated_at = ?
        WHERE id = ?
      `).run(hashPassword(newPassword), stamp, user.id);
      this.revokeActiveRefreshSessionsForUser({
        userId: user.id,
        now
      });
    });
    return {
      ok: true,
      user: this.getClientUserById(user.id)
    };
  }

  resolveUserEntitlements({userId = 0, now = new Date()} = {}) {
    const user = this.getClientUserById(userId);
    if (!user) {
      return null;
    }
    const plan = this.getMembershipPlanByCode(user.membership_plan) || this.getMembershipPlanByCode("inactive");
    const active = this.isMembershipActive(user, now);
    const effectivePlan = active ? plan : this.getMembershipPlanByCode("inactive");
    const permissions = new Set(effectivePlan ? effectivePlan.permissions : []);
    const overrides = this.db.prepare(`
      SELECT feature_code, enabled
      FROM client_user_feature_override
      WHERE user_id = ?
      ORDER BY feature_code ASC
    `).all(user.id);
    for (const item of overrides) {
      const code = toText(item.feature_code);
      if (!code) {
        continue;
      }
      if (Number(item.enabled) === 1) {
        permissions.add(code);
      } else {
        permissions.delete(code);
      }
    }
    const resolvedPermissions = [...permissions].sort();
    return {
      membership_plan: effectivePlan ? effectivePlan.code : "inactive",
      assigned_membership_plan: user.membership_plan,
      membership_expires_at: user.membership_expires_at,
      membership_active: active,
      permissions: resolvedPermissions,
      feature_flags: {
        program_access_enabled: resolvedPermissions.includes("program_access_enabled")
      }
    };
  }

  isMembershipActive(user, now = new Date()) {
    if (!user || toText(user.status) !== "active") {
      return false;
    }
    if (normalizePlan(user.membership_plan) === "inactive") {
      return false;
    }
    const expiresAt = toText(user.membership_expires_at);
    if (!expiresAt) {
      return true;
    }
    return parseMs(expiresAt) > parseMs(nowIso(now));
  }

  updateClientUserControl({
    userId = 0,
    status = "",
    membershipPlan = "",
    membershipExpiresAt = "",
    permissionOverrides = null,
    now = new Date()
  } = {}) {
    const user = this.getClientUserById(userId);
    if (!user) {
      return {ok: false, reason: "user_not_found"};
    }
    const nextStatus = toText(status) || user.status;
    if (!["active", "disabled"].includes(nextStatus)) {
      return {ok: false, reason: "status_invalid"};
    }
    const nextPlan = toText(membershipPlan) ? normalizePlan(membershipPlan) : user.membership_plan;
    const nextExpiresAt = membershipExpiresAt === undefined ? user.membership_expires_at : toText(membershipExpiresAt);
    const stamp = nowIso(now);
    return this.runInTransaction(() => {
      this.db.prepare(`
        UPDATE client_user
        SET status = ?, membership_plan = ?, membership_expires_at = ?, updated_at = ?
        WHERE id = ?
      `).run(nextStatus, nextPlan, nextExpiresAt, stamp, user.id);
      if (Array.isArray(permissionOverrides)) {
        this.db.prepare("DELETE FROM client_user_feature_override WHERE user_id = ?").run(user.id);
        const insert = this.db.prepare(`
          INSERT INTO client_user_feature_override(user_id, feature_code, enabled, created_at, updated_at)
          VALUES(?, ?, ?, ?, ?)
        `);
        for (const item of permissionOverrides) {
          const featureCode = toText(item && item.feature_code);
          if (!featureCode) {
            continue;
          }
          insert.run(user.id, featureCode, Number(item && item.enabled ? 1 : 0), stamp, stamp);
        }
      }
      const updatedUser = this.getClientUserById(user.id);
      return {
        ok: true,
        user: updatedUser,
        entitlements: this.resolveUserEntitlements({userId: user.id, now})
      };
    });
  }

  createEmailCode({email = "", scene = "", code = "", ttlMs = 5 * 60 * 1000, now = new Date()} = {}) {
    const stamp = nowIso(now);
    const expiresAt = new Date(parseMs(stamp) + Math.max(1, Number(ttlMs) || 1)).toISOString();
    const emailText = toText(email).toLowerCase();
    const sceneText = toText(scene);
    const result = this.runInTransaction(() => {
      this.db.prepare(`
        UPDATE email_code
        SET consumed_at = ?
        WHERE email = ? AND scene = ? AND consumed_at = ''
      `).run(stamp, emailText, sceneText);
      return this.db.prepare(`
        INSERT INTO email_code(email, scene, code_hash, expires_at, created_at, consumed_at)
        VALUES(?, ?, ?, ?, ?, '')
      `).run(
        emailText,
        sceneText,
        hashToken(code),
        expiresAt,
        stamp
      );
    });
    return {
      id: Number(result.lastInsertRowid) || 0,
      email: emailText,
      scene: sceneText,
      expires_at: expiresAt
    };
  }

  deleteEmailCode(codeId = 0) {
    this.db.prepare("DELETE FROM email_code WHERE id = ?").run(Number(codeId) || 0);
  }

  verifyEmailCode({email = "", scene = "", code = "", now = new Date()} = {}) {
    const row = this.db.prepare(`
      SELECT *
      FROM email_code
      WHERE email = ? AND scene = ? AND code_hash = ? AND consumed_at = ''
      ORDER BY id DESC
      LIMIT 1
    `).get(
      toText(email).toLowerCase(),
      toText(scene),
      hashToken(code)
    );
    if (!row) {
      return {ok: false, reason: "email_code_invalid"};
    }
    if (parseMs(row.expires_at) <= parseMs(nowIso(now))) {
      return {ok: false, reason: "email_code_expired"};
    }
    this.db.prepare("UPDATE email_code SET consumed_at = ? WHERE id = ?").run(nowIso(now), Number(row.id) || 0);
    return {ok: true, code_id: Number(row.id) || 0};
  }

  needsAdminBootstrap() {
    const row = this.db.prepare("SELECT COUNT(1) AS total FROM admin_user").get();
    return (Number(row && row.total) || 0) === 0;
  }

  createOrUpdateAdminUser({username = "admin", password = "", isSuperAdmin = false, now = new Date()} = {}) {
    const stamp = nowIso(now);
    const usernameText = toText(username) || "admin";
    const existing = this.db.prepare("SELECT * FROM admin_user WHERE username = ?").get(usernameText);
    if (existing) {
      this.db.prepare(`
        UPDATE admin_user
        SET password_hash = ?, status = 'active', is_super_admin = ?, updated_at = ?
        WHERE id = ?
      `).run(hashPassword(password), Number(isSuperAdmin ? 1 : 0), stamp, Number(existing.id) || 0);
      return mapAdminUser(this.db.prepare("SELECT * FROM admin_user WHERE id = ?").get(Number(existing.id) || 0));
    }
    const result = this.db.prepare(`
      INSERT INTO admin_user(username, password_hash, status, is_super_admin, created_at, updated_at)
      VALUES(?, ?, 'active', ?, ?, ?)
    `).run(usernameText, hashPassword(password), Number(isSuperAdmin ? 1 : 0), stamp, stamp);
    return mapAdminUser(this.db.prepare("SELECT * FROM admin_user WHERE id = ?").get(Number(result.lastInsertRowid) || 0));
  }

  authenticateAdminUser({username = "admin", password = ""} = {}) {
    const row = this.db.prepare("SELECT * FROM admin_user WHERE username = ?").get(toText(username) || "admin");
    if (!row || !verifyPassword(row.password_hash, password)) {
      return {ok: false, reason: "invalid_credentials"};
    }
    if (toText(row.status) !== "active") {
      return {ok: false, reason: "admin_user_disabled"};
    }
    return {
      ok: true,
      user: mapAdminUser(row)
    };
  }

  createAdminSession({adminUserId = 0, ttlHours = 12, now = new Date()} = {}) {
    const user = mapAdminUser(this.db.prepare("SELECT * FROM admin_user WHERE id = ?").get(Number(adminUserId) || 0));
    if (!user) {
      throw new Error("admin user not found");
    }
    const sessionToken = createOpaqueToken(24);
    const stamp = nowIso(now);
    const expiresAt = new Date(parseMs(stamp) + Math.max(1, Number(ttlHours) || 1) * 60 * 60 * 1000).toISOString();
    this.db.prepare(`
      INSERT INTO admin_session(token_hash, admin_user_id, status, created_at, updated_at, expires_at, revoked_at)
      VALUES(?, ?, 'active', ?, ?, ?, '')
    `).run(hashToken(sessionToken), user.id, stamp, stamp, expiresAt);
    return {
      session_token: sessionToken,
      expires_at: expiresAt
    };
  }

  resolveAdminSession({sessionToken = "", now = new Date()} = {}) {
    const row = this.db.prepare(`
      SELECT s.*, u.username, u.status AS user_status, u.is_super_admin
      FROM admin_session s
      JOIN admin_user u ON u.id = s.admin_user_id
      WHERE s.token_hash = ?
      LIMIT 1
    `).get(hashToken(sessionToken));
    if (!row || toText(row.status) !== "active" || toText(row.revoked_at)) {
      return {ok: false, reason: "admin_session_not_found"};
    }
    if (parseMs(row.expires_at) <= parseMs(nowIso(now))) {
      return {ok: false, reason: "admin_session_expired"};
    }
    if (toText(row.user_status) !== "active") {
      return {ok: false, reason: "admin_user_disabled"};
    }
    return {
      ok: true,
      user: {
        id: Number(row.admin_user_id) || 0,
        username: toText(row.username),
        status: toText(row.user_status) || "active",
        is_super_admin: Number(row.is_super_admin) === 1
      },
      session: {
        id: Number(row.id) || 0,
        expires_at: toText(row.expires_at)
      }
    };
  }

  revokeAdminSession({sessionToken = "", now = new Date()} = {}) {
    const tokenHash = hashToken(sessionToken);
    const row = this.db.prepare(`
      SELECT id
      FROM admin_session
      WHERE token_hash = ? AND status = 'active' AND revoked_at = ''
      LIMIT 1
    `).get(tokenHash);
    if (!row) {
      return {ok: false, reason: "admin_session_not_found"};
    }
    const stamp = nowIso(now);
    this.db.prepare(`
      UPDATE admin_session
      SET status = 'revoked', revoked_at = ?, updated_at = ?
      WHERE id = ?
    `).run(stamp, stamp, Number(row.id) || 0);
    return {ok: true};
  }

  createRefreshSession({userId = 0, deviceId = "", ttlDays = 30, now = new Date()} = {}) {
    const user = this.getClientUserById(userId);
    if (!user) {
      throw new Error("user not found");
    }
    const deviceText = toText(deviceId);
    if (!deviceText) {
      throw new Error("device_id is required");
    }
    const refreshToken = createOpaqueToken(24);
    const stamp = nowIso(now);
    const expiresAt = new Date(parseMs(stamp) + Math.max(1, Number(ttlDays) || 1) * 24 * 60 * 60 * 1000).toISOString();
    const result = this.db.prepare(`
      INSERT INTO refresh_session(
        token_hash, user_id, device_id, status, created_at, updated_at, last_used_at, expires_at, revoked_at
      ) VALUES(?, ?, ?, 'active', ?, ?, ?, ?, '')
    `).run(hashToken(refreshToken), user.id, deviceText, stamp, stamp, stamp, expiresAt);
    return {
      id: Number(result.lastInsertRowid) || 0,
      refresh_token: refreshToken,
      expires_at: expiresAt
    };
  }

  resolveRefreshSession({refreshToken = "", deviceId = "", now = new Date()} = {}) {
    const row = this.db.prepare(`
      SELECT rs.*, cu.email, cu.username, cu.status AS user_status, cu.membership_plan, cu.membership_expires_at
      FROM refresh_session rs
      JOIN client_user cu ON cu.id = rs.user_id
      WHERE rs.token_hash = ?
      LIMIT 1
    `).get(hashToken(refreshToken));
    if (!row || toText(row.status) !== "active" || toText(row.revoked_at)) {
      return {ok: false, reason: "refresh_token_not_found"};
    }
    if (toText(deviceId) !== toText(row.device_id)) {
      return {ok: false, reason: "device_mismatch"};
    }
    if (parseMs(row.expires_at) <= parseMs(nowIso(now))) {
      return {ok: false, reason: "refresh_token_expired"};
    }
    if (toText(row.user_status) !== "active") {
      return {ok: false, reason: "user_disabled"};
    }
    const stamp = nowIso(now);
    this.db.prepare("UPDATE refresh_session SET last_used_at = ?, updated_at = ? WHERE id = ?")
      .run(stamp, stamp, Number(row.id) || 0);
    return {
      ok: true,
      session: {
        id: Number(row.id) || 0,
        user_id: Number(row.user_id) || 0,
        device_id: toText(row.device_id),
        status: toText(row.status),
        expires_at: toText(row.expires_at)
      },
      user: {
        id: Number(row.user_id) || 0,
        email: toText(row.email),
        username: toText(row.username),
        status: toText(row.user_status) || "active",
        membership_plan: normalizePlan(row.membership_plan),
        membership_expires_at: toText(row.membership_expires_at)
      }
    };
  }

  rotateRefreshSession({refreshToken = "", deviceId = "", ttlDays = 30, now = new Date()} = {}) {
    const resolved = this.resolveRefreshSession({refreshToken, deviceId, now});
    if (!resolved.ok) {
      return resolved;
    }
    const next = this.runInTransaction(() => {
      const stamp = nowIso(now);
      this.db.prepare(`
        UPDATE refresh_session
        SET status = 'rotated', revoked_at = ?, updated_at = ?
        WHERE id = ?
      `).run(stamp, stamp, resolved.session.id);
      return this.createRefreshSession({
        userId: resolved.user.id,
        deviceId,
        ttlDays,
        now
      });
    });
    return {
      ok: true,
      user: resolved.user,
      refresh_token: next.refresh_token,
      expires_at: next.expires_at
    };
  }

  listUserDeviceSessions({userId = 0} = {}) {
    const rows = this.db.prepare(`
      SELECT *
      FROM refresh_session
      WHERE user_id = ? AND status = 'active' AND revoked_at = ''
      ORDER BY id ASC
    `).all(Number(userId) || 0);
    return rows.map((row) => ({
      id: Number(row.id) || 0,
      user_id: Number(row.user_id) || 0,
      device_id: toText(row.device_id),
      status: toText(row.status),
      created_at: toText(row.created_at),
      updated_at: toText(row.updated_at),
      last_used_at: toText(row.last_used_at),
      expires_at: toText(row.expires_at)
    }));
  }

  revokeActiveRefreshSessionsForUser({userId = 0, now = new Date()} = {}) {
    const stamp = nowIso(now);
    const result = this.db.prepare(`
      UPDATE refresh_session
      SET status = 'revoked', revoked_at = ?, updated_at = ?
      WHERE user_id = ? AND status = 'active' AND revoked_at = ''
    `).run(stamp, stamp, Number(userId) || 0);
    return {
      ok: true,
      revoked_count: Number(result.changes) || 0
    };
  }

  revokeRefreshSessionById({sessionId = 0, now = new Date()} = {}) {
    const row = this.db.prepare(`
      SELECT id
      FROM refresh_session
      WHERE id = ? AND status = 'active' AND revoked_at = ''
      LIMIT 1
    `).get(Number(sessionId) || 0);
    if (!row) {
      return {ok: false, reason: "refresh_session_not_found"};
    }
    const stamp = nowIso(now);
    this.db.prepare(`
      UPDATE refresh_session
      SET status = 'revoked', revoked_at = ?, updated_at = ?
      WHERE id = ?
    `).run(stamp, stamp, Number(row.id) || 0);
    return {ok: true};
  }

  revokeRefreshSessionForUserById({userId = 0, sessionId = 0, now = new Date()} = {}) {
    const row = this.db.prepare(`
      SELECT id
      FROM refresh_session
      WHERE id = ? AND user_id = ? AND status = 'active' AND revoked_at = ''
      LIMIT 1
    `).get(Number(sessionId) || 0, Number(userId) || 0);
    if (!row) {
      return {ok: false, reason: "refresh_session_not_found"};
    }
    return this.revokeRefreshSessionById({
      sessionId: Number(row.id) || 0,
      now
    });
  }

  revokeRefreshSession({refreshToken = "", now = new Date()} = {}) {
    const row = this.db.prepare(`
      SELECT id
      FROM refresh_session
      WHERE token_hash = ? AND status = 'active' AND revoked_at = ''
      LIMIT 1
    `).get(hashToken(refreshToken));
    if (!row) {
      return {ok: false, reason: "refresh_token_not_found"};
    }
    return this.revokeRefreshSessionById({
      sessionId: Number(row.id) || 0,
      now
    });
  }

  purgeExpiredRegisterArtifacts({now = new Date()} = {}) {
    const stamp = nowIso(now);
    this.db.prepare(`
      DELETE FROM register_send_idempotency
      WHERE expires_at <= ?
    `).run(stamp);
    this.db.prepare(`
      DELETE FROM register_verification_ticket
      WHERE consumed_at != '' OR expires_at <= ?
    `).run(stamp);
    this.db.prepare(`
      DELETE FROM register_session
      WHERE session_expires_at <= ? OR session_state IN ('completed', 'invalidated')
    `).run(stamp);
  }

  getRegisterSessionById(registerSessionId = "") {
    const row = this.db.prepare(`
      SELECT *
      FROM register_session
      WHERE id = ?
      LIMIT 1
    `).get(toText(registerSessionId));
    if (!row) {
      return null;
    }
    return {
      id: toText(row.id),
      email: toText(row.email),
      install_id: toText(row.install_id),
      device_fingerprint: toText(row.device_fingerprint),
      session_state: toText(row.session_state) || "pending",
      code_hash: toText(row.code_hash),
      code_expires_at: toText(row.code_expires_at),
      session_expires_at: toText(row.session_expires_at),
      resend_allowed_at: toText(row.resend_allowed_at),
      send_count: Number(row.send_count) || 0,
      verify_attempt_count: Number(row.verify_attempt_count) || 0,
      last_sent_at: toText(row.last_sent_at),
      verified_at: toText(row.verified_at),
      completed_at: toText(row.completed_at),
      invalidated_at: toText(row.invalidated_at),
      created_at: toText(row.created_at),
      updated_at: toText(row.updated_at)
    };
  }

  getLatestPendingRegisterSession({email = "", installId = "", now = new Date()} = {}) {
    const row = this.db.prepare(`
      SELECT *
      FROM register_session
      WHERE email = ? AND install_id = ? AND session_state = 'pending' AND session_expires_at > ?
      ORDER BY created_at DESC
      LIMIT 1
    `).get(toText(email).toLowerCase(), toText(installId), nowIso(now));
    return row ? this.getRegisterSessionById(row.id) : null;
  }

  getRegisterSendIdempotentHit({idempotencyKey = "", now = new Date()} = {}) {
    const row = this.db.prepare(`
      SELECT register_session_id
      FROM register_send_idempotency
      WHERE idempotency_key = ? AND expires_at > ?
      LIMIT 1
    `).get(toText(idempotencyKey), nowIso(now));
    if (!row) {
      return null;
    }
    return this.getRegisterSessionById(row.register_session_id);
  }

  rememberRegisterSendIdempotency({
    idempotencyKey = "",
    registerSessionId = "",
    windowSeconds = 2,
    now = new Date()
  } = {}) {
    const stamp = nowIso(now);
    const expiresAt = new Date(parseMs(stamp) + Math.max(1, Number(windowSeconds) || 1) * 1000).toISOString();
    this.db.prepare(`
      INSERT INTO register_send_idempotency(idempotency_key, register_session_id, observed_at, expires_at)
      VALUES(?, ?, ?, ?)
      ON CONFLICT(idempotency_key) DO UPDATE SET
        register_session_id = excluded.register_session_id,
        observed_at = excluded.observed_at,
        expires_at = excluded.expires_at
    `).run(toText(idempotencyKey), toText(registerSessionId), stamp, expiresAt);
  }

  countRegisterSendsByWindow({
    field = "",
    value = "",
    windowSeconds = 60,
    now = new Date()
  } = {}) {
    const name = toText(field);
    const allowedFields = new Set(["email", "install_id", "source_ip", "device_fingerprint"]);
    if (!allowedFields.has(name)) {
      return {count: 0, earliest_ms: 0};
    }
    const valueText = toText(value);
    if (!valueText) {
      return {count: 0, earliest_ms: 0};
    }
    const stamp = nowIso(now);
    const since = new Date(parseMs(stamp) - Math.max(1, Number(windowSeconds) || 1) * 1000).toISOString();
    const row = this.db.prepare(`
      SELECT COUNT(1) AS total, MIN(created_at) AS earliest_at
      FROM register_send_ledger
      WHERE ${name} = ? AND created_at >= ?
    `).get(valueText, since);
    return {
      count: Number(row && row.total) || 0,
      earliest_ms: parseMs(row && row.earliest_at ? row.earliest_at : "")
    };
  }

  beginRegisterSendSession({
    email = "",
    installId = "",
    deviceFingerprint = "",
    sessionTtlSeconds = 1800,
    now = new Date()
  } = {}) {
    const stamp = nowIso(now);
    const sessionId = createId("regsess");
    const expiresAt = new Date(
      parseMs(stamp) + Math.max(1, Number(sessionTtlSeconds) || 1) * 1000
    ).toISOString();
    this.db.prepare(`
      INSERT INTO register_session(
        id,
        email,
        install_id,
        device_fingerprint,
        session_state,
        code_hash,
        code_expires_at,
        session_expires_at,
        resend_allowed_at,
        send_count,
        verify_attempt_count,
        last_sent_at,
        verified_at,
        completed_at,
        invalidated_at,
        created_at,
        updated_at
      ) VALUES(?, ?, ?, ?, 'pending', '', '', ?, '', 0, 0, '', '', '', '', ?, ?)
    `).run(
      sessionId,
      toText(email).toLowerCase(),
      toText(installId),
      toText(deviceFingerprint),
      expiresAt,
      stamp,
      stamp
    );
    return this.getRegisterSessionById(sessionId);
  }

  recordRegisterCodeDispatch({
    registerSessionId = "",
    code = "",
    codeExpiresInSeconds = 600,
    resendAfterSeconds = 60,
    sourceIp = "",
    now = new Date()
  } = {}) {
    const session = this.getRegisterSessionById(registerSessionId);
    if (!session || session.session_state !== "pending") {
      return {ok: false, reason: "register_session_invalid"};
    }
    const stamp = nowIso(now);
    if (parseMs(session.session_expires_at) <= parseMs(stamp)) {
      this.db.prepare(`
        UPDATE register_session
        SET session_state = 'invalidated', invalidated_at = ?, updated_at = ?
        WHERE id = ?
      `).run(stamp, stamp, session.id);
      return {ok: false, reason: "register_session_invalid"};
    }
    const codeExpiresAt = new Date(
      parseMs(stamp) + Math.max(1, Number(codeExpiresInSeconds) || 1) * 1000
    ).toISOString();
    const resendAllowedAt = new Date(
      parseMs(stamp) + Math.max(1, Number(resendAfterSeconds) || 1) * 1000
    ).toISOString();
    this.runInTransaction(() => {
      this.db.prepare(`
        UPDATE register_session
        SET code_hash = ?,
            code_expires_at = ?,
            resend_allowed_at = ?,
            send_count = send_count + 1,
            verify_attempt_count = 0,
            last_sent_at = ?,
            updated_at = ?
        WHERE id = ?
      `).run(hashToken(code), codeExpiresAt, resendAllowedAt, stamp, stamp, session.id);
      this.db.prepare(`
        INSERT INTO register_send_ledger(
          email,
          install_id,
          source_ip,
          device_fingerprint,
          register_session_id,
          created_at
        ) VALUES(?, ?, ?, ?, ?, ?)
      `).run(
        session.email,
        session.install_id,
        toText(sourceIp),
        session.device_fingerprint,
        session.id,
        stamp
      );
    });
    return {
      ok: true,
      session: this.getRegisterSessionById(session.id)
    };
  }

  invalidateRegisterSession({registerSessionId = "", now = new Date()} = {}) {
    const stamp = nowIso(now);
    this.db.prepare(`
      UPDATE register_session
      SET session_state = 'invalidated', invalidated_at = ?, updated_at = ?
      WHERE id = ? AND session_state != 'completed'
    `).run(stamp, stamp, toText(registerSessionId));
  }

  verifyRegisterCode({
    email = "",
    code = "",
    registerSessionId = "",
    installId = "",
    ticketTtlSeconds = 900,
    maxVerifyAttempts = 5,
    now = new Date()
  } = {}) {
    const session = this.getRegisterSessionById(registerSessionId);
    const stamp = nowIso(now);
    if (!session || session.session_state !== "pending" || parseMs(session.session_expires_at) <= parseMs(stamp)) {
      return {ok: false, reason: "register_session_invalid"};
    }
    if (toText(installId) && toText(installId) !== session.install_id) {
      return {ok: false, reason: "register_session_invalid"};
    }
    if (toText(email).toLowerCase() !== session.email) {
      return {ok: false, reason: "register_session_email_mismatch"};
    }
    if (session.verify_attempt_count >= Math.max(1, Number(maxVerifyAttempts) || 1)) {
      this.invalidateRegisterSession({registerSessionId: session.id, now});
      return {ok: false, reason: "register_code_attempts_exceeded"};
    }
    const incomingHash = hashToken(code);
    const codeExpired = parseMs(session.code_expires_at) <= parseMs(stamp);
    if (!session.code_hash || incomingHash !== session.code_hash || codeExpired) {
      const nextAttempts = session.verify_attempt_count + 1;
      this.db.prepare(`
        UPDATE register_session
        SET verify_attempt_count = ?, updated_at = ?
        WHERE id = ?
      `).run(nextAttempts, stamp, session.id);
      if (nextAttempts >= Math.max(1, Number(maxVerifyAttempts) || 1)) {
        this.invalidateRegisterSession({registerSessionId: session.id, now});
        return {ok: false, reason: "register_code_attempts_exceeded"};
      }
      return {ok: false, reason: "register_code_invalid_or_expired"};
    }
    const verificationTicket = createId("regticket");
    const ticketExpiresAt = new Date(
      parseMs(stamp) + Math.max(1, Number(ticketTtlSeconds) || 1) * 1000
    ).toISOString();
    this.runInTransaction(() => {
      this.db.prepare(`
        UPDATE register_session
        SET session_state = 'verified',
            verify_attempt_count = ?,
            code_hash = '',
            code_expires_at = '',
            verified_at = ?,
            updated_at = ?
        WHERE id = ?
      `).run(session.verify_attempt_count + 1, stamp, stamp, session.id);
      this.db.prepare(`
        UPDATE register_verification_ticket
        SET consumed_at = ?, updated_at = ?
        WHERE register_session_id = ? AND consumed_at = ''
      `).run(stamp, stamp, session.id);
      this.db.prepare(`
        INSERT INTO register_verification_ticket(
          ticket_hash,
          register_session_id,
          email,
          install_id,
          device_fingerprint,
          expires_at,
          consumed_at,
          created_at,
          updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, '', ?, ?)
      `).run(
        hashToken(verificationTicket),
        session.id,
        session.email,
        session.install_id,
        session.device_fingerprint,
        ticketExpiresAt,
        stamp,
        stamp
      );
    });
    return {
      ok: true,
      verification_ticket: verificationTicket,
      ticket_expires_in_seconds: Math.max(1, Number(ticketTtlSeconds) || 1),
      register_session_id: session.id
    };
  }

  consumeVerificationTicket({
    verificationTicket = "",
    email = "",
    installId = "",
    now = new Date()
  } = {}) {
    const ticketHash = hashToken(verificationTicket);
    const row = this.db.prepare(`
      SELECT *
      FROM register_verification_ticket
      WHERE ticket_hash = ? AND consumed_at = ''
      LIMIT 1
    `).get(ticketHash);
    if (!row) {
      return {ok: false, reason: "register_ticket_invalid_or_expired"};
    }
    const stamp = nowIso(now);
    if (parseMs(row.expires_at) <= parseMs(stamp)) {
      return {ok: false, reason: "register_ticket_invalid_or_expired"};
    }
    if (toText(email).toLowerCase() !== toText(row.email)) {
      return {ok: false, reason: "register_ticket_invalid_or_expired"};
    }
    if (toText(installId) && toText(installId) !== toText(row.install_id)) {
      return {ok: false, reason: "register_ticket_invalid_or_expired"};
    }
    const consumed = this.db.prepare(`
      UPDATE register_verification_ticket
      SET consumed_at = ?, updated_at = ?
      WHERE id = ? AND consumed_at = ''
    `).run(stamp, stamp, Number(row.id) || 0);
    if ((Number(consumed.changes) || 0) <= 0) {
      return {ok: false, reason: "register_ticket_invalid_or_expired"};
    }
    const session = this.getRegisterSessionById(toText(row.register_session_id));
    if (!session || session.session_state !== "verified") {
      return {ok: false, reason: "register_ticket_invalid_or_expired"};
    }
    return {
      ok: true,
      ticket: {
        register_session_id: toText(row.register_session_id),
        email: toText(row.email),
        install_id: toText(row.install_id),
        device_fingerprint: toText(row.device_fingerprint)
      }
    };
  }

  finalizeRegisterSession({
    registerSessionId = "",
    now = new Date()
  } = {}) {
    const stamp = nowIso(now);
    this.db.prepare(`
      UPDATE register_session
      SET session_state = 'completed', completed_at = ?, updated_at = ?
      WHERE id = ?
    `).run(stamp, stamp, toText(registerSessionId));
  }
}

module.exports = {
  ControlPlaneStore
};
