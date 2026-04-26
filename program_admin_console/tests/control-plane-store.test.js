const assert = require("node:assert/strict");
const {spawnSync} = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {ControlPlaneStore} = require("../src/controlPlaneStore");
const {createEntitlementSigner} = require("../src/entitlementSigner");

function createTempDbPath() {
  const dirPath = fs.mkdtempSync(path.join(os.tmpdir(), "program-control-plane-"));
  return {
    dirPath,
    dbPath: path.join(dirPath, "control-plane.sqlite")
  };
}

function run() {
  const projectRoot = path.join(__dirname, "..");
  const packagePath = path.join(projectRoot, "package.json");
  const dockerfilePath = path.join(projectRoot, "Dockerfile");
  const dockerignorePath = path.join(projectRoot, ".dockerignore");
  const readmePath = path.join(projectRoot, "README.md");
  const adminInitScriptPath = path.join(projectRoot, "tools", "initProgramControlPlaneAdmin.js");

  assert.equal(fs.existsSync(packagePath), true);
  const packageJson = JSON.parse(fs.readFileSync(packagePath, "utf8"));
  assert.equal(packageJson.scripts["test:mail-config"], "node tests/mail_config.test.js");
  assert.equal(packageJson.scripts["test:mail-service"], "node tests/mail_service.test.js");
  assert.equal(packageJson.scripts["test:store"], "node tests/control-plane-store.test.js");
  assert.equal(packageJson.scripts["test:server"], "node tests/control-plane-server.test.js");
  assert.equal(packageJson.scripts["test:ui"], "node tests/control-plane-ui.test.js");
  assert.equal(packageJson.scripts["test:connect-script"], "node tests/connect-program-admin-console.test.js");
  assert.equal(
    packageJson.scripts.test,
    "npm run test:mail-config && npm run test:mail-service && npm run test:server-runtime && npm run test:store && npm run test:server && npm run test:ui && npm run test:connect-script"
  );
  assert.equal(packageJson.scripts.start, "node src/server.js");
  assert.equal(packageJson.scripts["admin:init"], "node tools/initProgramControlPlaneAdmin.js");
  assert.equal(packageJson.dependencies.nodemailer, "^6.10.0");

  assert.equal(fs.existsSync(dockerfilePath), true);
  const dockerfile = fs.readFileSync(dockerfilePath, "utf8");
  assert.match(dockerfile, /FROM\s+node:24-bookworm-slim/i);
  assert.match(dockerfile, /CMD\s+\["node",\s*"src\/server\.js"\]/);
  assert.doesNotMatch(dockerfile, /COPY\s+data\s+\.\/data/i);

  assert.equal(fs.existsSync(dockerignorePath), true);
  const dockerignore = fs.readFileSync(dockerignorePath, "utf8");
  assert.match(dockerignore, /node_modules/);
  assert.match(dockerignore, /^tmp\/?$/m);
  assert.match(dockerignore, /^data\/?$/m);
  assert.match(dockerignore, /^\*\.sqlite$/m);
  assert.match(dockerignore, /(coverage|test-results)/);

  assert.equal(fs.existsSync(readmePath), true);
  const readme = fs.readFileSync(readmePath, "utf8");
  assert.match(readme, /curl\s+http:\/\/127\.0\.0\.1:8787\/api\/health/);
  assert.match(readme, /curl\s+http:\/\/127\.0\.0\.1:8787\/api\/admin\/session/);
  assert.match(readme, /\/admin/);
  assert.match(readme, /docker build/i);
  assert.match(readme, /docker run/i);
  assert.match(readme, /ecs/i);
  assert.match(readme, /\$env:PROGRAM_ADMIN_HOST/i);
  assert.match(readme, /\$env:PROGRAM_ADMIN_PORT/i);
  assert.match(readme, /\-v\s+[^ \r\n]+:\/app\/data/i);
  assert.match(readme, /\/app\/data\/control-plane\.sqlite/i);
  assert.doesNotMatch(readme, /PROGRAM_ADMIN_HOST=127\.0\.0\.1\s+PROGRAM_ADMIN_PORT=8787\s+npm/i);
  assert.doesNotMatch(readme, /\\\s*\r?\n\s*-e\s+PROGRAM_ADMIN_HOST/i);

  assert.equal(fs.existsSync(adminInitScriptPath), true);

  const missingParentBase = fs.mkdtempSync(path.join(os.tmpdir(), "program-control-plane-missing-parent-"));
  const missingParentDbPath = path.join(missingParentBase, "nested", "db", "control-plane.sqlite");
  const missingParentStore = new ControlPlaneStore({dbPath: missingParentDbPath});
  try {
    assert.equal(fs.existsSync(path.dirname(missingParentDbPath)), true);
    assert.deepEqual(
      missingParentStore.listMembershipPlans().map((item) => item.code),
      ["inactive", "member"]
    );
  } finally {
    missingParentStore.close();
    fs.rmSync(missingParentBase, {recursive: true, force: true});
  }

  const {dirPath, dbPath} = createTempDbPath();
  const store = new ControlPlaneStore({dbPath});
  try {
    const missingPasswordResult = spawnSync(
      process.execPath,
      [adminInitScriptPath, "--username", "ops", "--db-path", dbPath],
      {encoding: "utf8"}
    );
    assert.notEqual(missingPasswordResult.status, 0);
    assert.match(
      `${missingPasswordResult.stdout}\n${missingPasswordResult.stderr}`,
      /Usage:\s*node\s+tools\/initProgramControlPlaneAdmin\.js/i
    );

    const bootstrapResult = spawnSync(
      process.execPath,
      [adminInitScriptPath, "--username", "ops", "--password", "Root123!", "--db-path", dbPath],
      {encoding: "utf8"}
    );
    assert.equal(bootstrapResult.status, 0, `${bootstrapResult.stdout}\n${bootstrapResult.stderr}`);
    assert.match(bootstrapResult.stdout, /control-plane admin ready:/i);

    const bootstrapResetResult = spawnSync(
      process.execPath,
      [adminInitScriptPath, "--username", "ops", "--password", "Root456!", "--db-path", dbPath],
      {encoding: "utf8"}
    );
    assert.equal(bootstrapResetResult.status, 0, `${bootstrapResetResult.stdout}\n${bootstrapResetResult.stderr}`);

    const adminAuthOldPassword = store.authenticateAdminUser({
      username: "ops",
      password: "Root123!"
    });
    assert.equal(adminAuthOldPassword.ok, false);
    assert.equal(adminAuthOldPassword.reason, "invalid_credentials");

    const adminAuthNewPassword = store.authenticateAdminUser({
      username: "ops",
      password: "Root456!"
    });
    assert.equal(adminAuthNewPassword.ok, true);
    assert.equal(adminAuthNewPassword.user.username, "ops");

    assert.deepEqual(
      store.listMembershipPlans().map((item) => item.code),
      ["inactive", "member"]
    );

    const alice = store.createClientUser({
      email: "alice@example.com",
      username: "alice",
      password: "Secret123!"
    });
    assert.equal(alice.membership_plan, "inactive");
    assert.equal(alice.status, "active");
    assert.equal(alice.membership_expires_at, "");

    const aliceEntitlements = store.resolveUserEntitlements({userId: alice.id});
    assert.equal(
      aliceEntitlements.permissions.includes("program_access_enabled"),
      false
    );
    assert.equal(aliceEntitlements.membership_plan, "inactive");

    const member = store.createClientUser({
      email: "member@example.com",
      username: "member",
      password: "Secret123!",
      membershipPlan: "member"
    });
    const memberEntitlements = store.resolveUserEntitlements({userId: member.id});
    assert.equal(
      memberEntitlements.permissions.includes("program_access_enabled"),
      true
    );

    const session = store.createRefreshSession({
      userId: alice.id,
      deviceId: "device-a",
      ttlDays: 10
    });
    const listedUsers = store.listUsersWithEntitlements();
    const listedAlice = listedUsers.find((item) => item.username === "alice");
    const listedMember = listedUsers.find((item) => item.username === "member");
    assert.equal(listedAlice.entitlements.membership_plan, "inactive");
    assert.equal(listedAlice.entitlements.feature_flags.program_access_enabled, false);
    assert.equal(listedAlice.active_device_count, 1);
    assert.equal(listedMember.entitlements.membership_plan, "member");
    assert.equal(listedMember.entitlements.feature_flags.program_access_enabled, true);
    assert.equal(listedMember.active_device_count, 0);
    const resolved = store.resolveRefreshSession({
      refreshToken: session.refresh_token,
      deviceId: "device-a"
    });
    assert.equal(resolved.ok, true);
    assert.equal(resolved.user.id, alice.id);

    const rotated = store.rotateRefreshSession({
      refreshToken: session.refresh_token,
      deviceId: "device-a",
      ttlDays: 10
    });
    assert.equal(rotated.ok, true);
    assert.notEqual(rotated.refresh_token, session.refresh_token);

    const oldSessionAfterRotate = store.resolveRefreshSession({
      refreshToken: session.refresh_token,
      deviceId: "device-a"
    });
    assert.equal(oldSessionAfterRotate.ok, false);
    assert.equal(oldSessionAfterRotate.reason, "refresh_token_not_found");

    const newSessionAfterRotate = store.resolveRefreshSession({
      refreshToken: rotated.refresh_token,
      deviceId: "device-a"
    });
    assert.equal(newSessionAfterRotate.ok, true);

    const failingRotationSession = store.createRefreshSession({
      userId: alice.id,
      deviceId: "device-a-rollback",
      ttlDays: 10
    });
    const originalCreateRefreshSession = store.createRefreshSession.bind(store);
    store.createRefreshSession = () => {
      throw new Error("injected_rotate_failure");
    };
    assert.throws(
      () => store.rotateRefreshSession({
        refreshToken: failingRotationSession.refresh_token,
        deviceId: "device-a-rollback",
        ttlDays: 10
      }),
      /injected_rotate_failure/
    );
    store.createRefreshSession = originalCreateRefreshSession;
    const failedRotationOldStillValid = store.resolveRefreshSession({
      refreshToken: failingRotationSession.refresh_token,
      deviceId: "device-a-rollback"
    });
    assert.equal(failedRotationOldStillValid.ok, true);

    const {privateKey} = crypto.generateKeyPairSync("ed25519");
    const signerKeyPath = path.join(dirPath, "entitlement-private.pem");
    fs.writeFileSync(signerKeyPath, privateKey.export({type: "pkcs8", format: "pem"}), "utf8");
    const signer = createEntitlementSigner({
      privateKeyFile: signerKeyPath,
      keyId: "test-kid",
      snapshotTtlMinutes: 10
    });
    const bundle = signer.issueBundle({
      user: member,
      deviceId: "device-a",
      permissions: memberEntitlements.permissions,
      featureFlags: {
        program_access_enabled: true
      }
    });
    assert.equal(bundle.kid, "test-kid");
    assert.equal(typeof bundle.signature, "string");
    assert.equal(bundle.signature.length > 10, true);
    assert.equal(bundle.snapshot.membership_plan, "member");
    assert.equal(Array.isArray(bundle.snapshot.permissions), true);
    assert.equal(typeof bundle.snapshot.feature_flags, "object");
    assert.equal(bundle.snapshot.feature_flags.program_access_enabled, true);
    assert.equal(typeof bundle.snapshot.exp, "string");
    assert.equal(Number.isNaN(Date.parse(bundle.snapshot.exp)), false);

    const runtimePermit = signer.issueRuntimePermit({
      user: member,
      deviceId: "device-a",
      action: "runtime.start",
      ttlSeconds: 120
    });
    assert.equal(runtimePermit.kid, "test-kid");
    assert.equal(typeof runtimePermit.signature, "string");
    assert.equal(runtimePermit.signature.length > 10, true);
    assert.equal(runtimePermit.snapshot.action, "runtime.start");
    assert.equal(typeof runtimePermit.snapshot.exp, "string");
    assert.equal(Number.isNaN(Date.parse(runtimePermit.snapshot.exp)), false);

    const defaultSigner = createEntitlementSigner();
    const defaultBundle = defaultSigner.issueBundle({
      user: member,
      deviceId: "device-default",
      permissions: memberEntitlements.permissions,
      featureFlags: {program_access_enabled: true}
    });
    assert.equal(typeof defaultBundle.signature, "string");
    assert.equal(defaultBundle.signature.length > 10, true);
    assert.equal(typeof defaultBundle.kid, "string");

    const {privateKey: signerKeyA} = crypto.generateKeyPairSync("ed25519");
    const keyAPath = path.join(dirPath, "entitlement-private-a.pem");
    fs.writeFileSync(keyAPath, signerKeyA.export({type: "pkcs8", format: "pem"}), "utf8");
    const {privateKey: signerKeyB} = crypto.generateKeyPairSync("ed25519");
    const keyBPath = path.join(dirPath, "entitlement-private-b.pem");
    fs.writeFileSync(keyBPath, signerKeyB.export({type: "pkcs8", format: "pem"}), "utf8");

    const signerWithoutKidA = createEntitlementSigner({privateKeyFile: keyAPath});
    const signerWithoutKidB = createEntitlementSigner({privateKeyFile: keyBPath});
    const bundleKidA = signerWithoutKidA.issueBundle({
      user: member,
      deviceId: "device-kid-a",
      permissions: memberEntitlements.permissions
    });
    const bundleKidB = signerWithoutKidB.issueBundle({
      user: member,
      deviceId: "device-kid-b",
      permissions: memberEntitlements.permissions
    });
    assert.notEqual(bundleKidA.kid, bundleKidB.kid);

    const explicitKidBundle = signer.issueBundle({
      user: member,
      deviceId: "device-explicit-kid",
      permissions: memberEntitlements.permissions,
      featureFlags: {}
    });
    assert.equal(explicitKidBundle.kid, "test-kid");
  } finally {
    store.close();
    fs.rmSync(dirPath, {recursive: true, force: true});
  }
}

run();
