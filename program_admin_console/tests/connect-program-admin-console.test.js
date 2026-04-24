const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");
const {spawnSync} = require("node:child_process");

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "program-admin-connect-script-"));
}

function writeFile(filePath, content) {
  fs.mkdirSync(path.dirname(filePath), {recursive: true});
  fs.writeFileSync(filePath, content, "utf8");
}

function makeFakeSshScript(tempDir) {
  const scriptPath = path.join(tempDir, "fake-ssh.js");
  writeFile(scriptPath, `
const fs = require("node:fs");
const net = require("node:net");

const args = process.argv.slice(2);
const index = args.indexOf("-L");
if (index < 0 || index + 1 >= args.length) {
  throw new Error("missing -L spec");
}

const forwardSpec = args[index + 1];
const localPort = Number(String(forwardSpec).split(":")[0]);
if (!Number.isFinite(localPort)) {
  throw new Error("invalid local port");
}

if (process.env.FAKE_SSH_MARKER) {
  fs.writeFileSync(process.env.FAKE_SSH_MARKER, forwardSpec, "utf8");
}

const server = net.createServer((socket) => {
  socket.destroy();
});

server.listen(localPort, "127.0.0.1", () => {
  setInterval(() => {}, 1000);
});
`.trim());
  return scriptPath;
}

function makeFakeBrowserScript(tempDir) {
  const scriptPath = path.join(tempDir, "fake-browser.js");
  writeFile(scriptPath, `
const fs = require("node:fs");

const args = process.argv.slice(2);
let adminUrl = "";
for (let index = 0; index < args.length; index += 1) {
  if (args[index] === "-AdminUrl" && index + 1 < args.length) {
    adminUrl = args[index + 1];
    break;
  }
}

if (process.env.FAKE_BROWSER_MARKER) {
  fs.writeFileSync(process.env.FAKE_BROWSER_MARKER, adminUrl, "utf8");
}

const sleepMs = Number(process.env.FAKE_BROWSER_SLEEP_MS || "500");
const exitCode = Number(process.env.FAKE_BROWSER_EXIT_CODE || "0");

setTimeout(() => {
  process.exit(exitCode);
}, sleepMs);
`.trim());
  return scriptPath;
}

function getScriptPath() {
  return path.join(__dirname, "..", "tools", "connectProgramAdminConsole.ps1");
}

function runConnectScript(args = [], env = {}) {
  return spawnSync("powershell.exe", [
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    getScriptPath(),
    ...args
  ], {
    encoding: "utf8",
    env: {
      ...process.env,
      ...env
    }
  });
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({host: "127.0.0.1", port});
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("error", () => {
      resolve(false);
    });
  });
}

async function main() {
  const tempDir = makeTempDir();
  try {
    const fakeSsh = makeFakeSshScript(tempDir);
    const fakeBrowser = makeFakeBrowserScript(tempDir);
    const fakeSshMarker = path.join(tempDir, "fake-ssh-started.txt");
    const fakeBrowserMarker = path.join(tempDir, "fake-browser-started.txt");

    const dryRun = runConnectScript([
      "-DryRun",
      "-LocalPort", "19087",
      "-SshWrapperScript", fakeSsh,
      "-BrowserWrapperScript", fakeBrowser
    ]);
    assert.equal(dryRun.status, 0, dryRun.stderr || dryRun.stdout);
    assert.match(dryRun.stdout, /SSH_PATH=/);
    assert.match(dryRun.stdout, /BROWSER_PATH=/);
    assert.match(dryRun.stdout, /BROWSER_ARGS=/);
    assert.match(dryRun.stdout, /ADMIN_URL=http:\/\/127\.0\.0\.1:19087\/admin/);
    assert.doesNotMatch(dryRun.stdout, /^SSH tunnel launched in a new PowerShell window\./m);

    const successRun = runConnectScript([
      "-LocalPort", "19088",
      "-SshWrapperScript", fakeSsh,
      "-BrowserWrapperScript", fakeBrowser
    ], {
      FAKE_SSH_MARKER: fakeSshMarker,
      FAKE_BROWSER_MARKER: fakeBrowserMarker,
      FAKE_BROWSER_SLEEP_MS: "500",
      FAKE_BROWSER_EXIT_CODE: "0"
    });
    assert.equal(successRun.status, 0, successRun.stderr || successRun.stdout);
    assert.ok(fs.existsSync(fakeSshMarker), "expected fake ssh marker");
    assert.ok(fs.existsSync(fakeBrowserMarker), "expected fake browser marker");
    await wait(300);
    assert.equal(await isPortOpen(19088), false, "expected local port to be closed after browser exit");

    fs.rmSync(fakeSshMarker, {force: true});
    fs.rmSync(fakeBrowserMarker, {force: true});

    const failureRun = runConnectScript([
      "-LocalPort", "19089",
      "-SshWrapperScript", fakeSsh,
      "-BrowserWrapperScript", fakeBrowser
    ], {
      FAKE_SSH_MARKER: fakeSshMarker,
      FAKE_BROWSER_MARKER: fakeBrowserMarker,
      FAKE_BROWSER_SLEEP_MS: "200",
      FAKE_BROWSER_EXIT_CODE: "7"
    });
    assert.notEqual(failureRun.status, 0, "expected non-zero exit when browser wrapper fails");
    assert.ok(fs.existsSync(fakeSshMarker), "expected fake ssh marker for failure run");
    assert.ok(fs.existsSync(fakeBrowserMarker), "expected fake browser marker for failure run");
    await wait(300);
    assert.equal(await isPortOpen(19089), false, "expected local port to be closed after failed browser run");

    console.log("connect-program-admin-console tests passed");
  } finally {
    fs.rmSync(tempDir, {recursive: true, force: true});
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
