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
}

module.exports = {
  ControlPlaneStore
};
