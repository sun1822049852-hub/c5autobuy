const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {spawnSync} = require("node:child_process");

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "program-admin-deploy-script-"));
}

function writeFile(filePath, content) {
  fs.mkdirSync(path.dirname(filePath), {recursive: true});
  fs.writeFileSync(filePath, content, "utf8");
}

function getScriptPath() {
  return path.join(__dirname, "..", "tools", "deployProgramAdminRemote.ps1");
}

function deriveKeyId(privateKey) {
  const publicDer = crypto.createPublicKey(privateKey).export({type: "spki", format: "der"});
  const fingerprint = crypto.createHash("sha256").update(publicDer).digest("base64url");
  return `ed25519:${fingerprint.slice(0, 32)}`;
}

function makeFakeSshScript(tempDir) {
  const scriptPath = path.join(tempDir, "fake-ssh.js");
  writeFile(scriptPath, `
const args = process.argv.slice(2);
const joined = args.join(" ");
if (joined.includes("docker inspect")) {
  process.stdout.write(process.env.FAKE_REMOTE_INSPECT || "");
  process.exit(0);
}
if (joined.includes("cat /remote/entitlement-private.pem")) {
  process.stderr.write("remote private key must not be copied to deploy machine");
  process.exit(31);
}
if (joined.includes("python3") && joined.includes("/remote/entitlement-private.pem")) {
  process.stdout.write(process.env.FAKE_REMOTE_DERIVED_KID || "");
  process.exit(0);
}
if (joined.includes("bash /home/admin/deploy_program_admin_remote_")) {
  process.stderr.write("stop after remote deploy script upload");
  process.exit(23);
}
process.stderr.write(\`unexpected ssh command: \${joined}\`);
process.exit(9);
`.trim());
  return scriptPath;
}

function makeFakeScpScript(tempDir) {
  const scriptPath = path.join(tempDir, "fake-scp.js");
  writeFile(scriptPath, `
process.exit(0);
`.trim());
  return scriptPath;
}

function main() {
  const tempDir = makeTempDir();
  try {
    const scriptPath = getScriptPath();
    const scriptSource = fs.readFileSync(scriptPath, "utf8");
    const fakeSsh = makeFakeSshScript(tempDir);
    const fakeScp = makeFakeScpScript(tempDir);
    const identityFile = path.join(tempDir, "id_ed25519");
    writeFile(identityFile, "fake-key");
    const localProjectDir = path.join(tempDir, "program_admin_console");
    writeFile(path.join(localProjectDir, "src", "server.js"), "console.log('stub');\n");
    const runtimeDir = path.join(tempDir, "runtime");

    const {privateKey} = crypto.generateKeyPairSync("ed25519");
    const derivedKid = deriveKeyId(privateKey);
    const fakeInspect = JSON.stringify({
      binds: ["/keys:/app/keys:ro", "c5_program_admin_data:/app/data"],
      env: [
        "PROGRAM_ADMIN_PRIVATE_KEY_FILE=/app/keys/entitlement-private.pem",
        "PROGRAM_ADMIN_SIGNING_KID=ed25519-2026-04",
        "PROGRAM_ADMIN_PORT=8787",
        "MAIL_FROM=bot@example.com",
        "QQ_SMTP_USER=bot@example.com",
        "QQ_SMTP_PASS=secret",
      ],
      portBindings: {"8787/tcp": [{HostIp: "127.0.0.1", HostPort: "18787"}]},
      image: "c5-program-admin:current",
    });

    const result = spawnSync("powershell.exe", [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      scriptPath,
      "-DryRun",
      "-IdentityFile", identityFile,
      "-SshWrapperScript", fakeSsh,
      "-RemotePrivateKeyPath", "/remote/entitlement-private.pem",
    ], {
      encoding: "utf8",
      env: {
        ...process.env,
        FAKE_REMOTE_INSPECT: fakeInspect,
        FAKE_REMOTE_DERIVED_KID: derivedKid,
      }
    });

    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.match(result.stdout, /REMOTE_CONTAINER=c5-program-admin/);
    assert.match(result.stdout, new RegExp(`DERIVED_SIGNING_KID=${derivedKid}`));
    assert.match(result.stdout, /CURRENT_SIGNING_KID=ed25519-2026-04/);
    assert.match(result.stdout, /REMOTE_SOURCE_DIR=\/home\/admin\/c5-program-admin-src/);
    assert.match(result.stdout, /PUBLIC_HTTPS_SMOKE=enabled/);

    const runtimeResult = spawnSync("powershell.exe", [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      scriptPath,
      "-IdentityFile", identityFile,
      "-SshWrapperScript", fakeSsh,
      "-ScpWrapperScript", fakeScp,
      "-RemotePrivateKeyPath", "/remote/entitlement-private.pem",
      "-LocalProjectDir", localProjectDir,
      "-RuntimeDir", runtimeDir,
      "-SkipHttpsSmoke",
    ], {
      encoding: "utf8",
      env: {
        ...process.env,
        FAKE_REMOTE_INSPECT: fakeInspect,
        FAKE_REMOTE_DERIVED_KID: derivedKid,
      }
    });

    assert.notEqual(runtimeResult.status, 0, "expected fake remote deploy stop to abort the script");
    assert.match(runtimeResult.stderr || runtimeResult.stdout, /stop after remote deploy script upload/);
    assert.match(scriptSource, /base_url \+ "\/api\/admin\/session"/);
    assert.match(scriptSource, /PUBLIC_HTTPS_SMOKE=disabled/);

    const generatedScripts = fs.readdirSync(runtimeDir)
      .filter((entry) => /^deploy_program_admin_remote_.*\.sh$/.test(entry))
      .map((entry) => path.join(runtimeDir, entry));
    assert.equal(generatedScripts.length, 1);
    const remoteDeployScript = fs.readFileSync(generatedScripts[0], "utf8");
    assert.match(remoteDeployScript, /rm -rf \$TMPDIR/);
    assert.match(remoteDeployScript, /mkdir -p \$TMPDIR/);
    assert.match(remoteDeployScript, /tar -xzf \$TARBALL -C \$TMPDIR/);
    assert.match(remoteDeployScript, /if \[ -d \$SOURCE_DIR \]; then/);
    assert.match(remoteDeployScript, /mv \$TMPDIR \$SOURCE_DIR/);
  } finally {
    fs.rmSync(tempDir, {recursive: true, force: true});
  }
}

main();
