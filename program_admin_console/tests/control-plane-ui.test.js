const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const vm = require("node:vm");

const {createServer} = require("../src/server");

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "program-control-plane-ui-"));
}

function readUiFile(relativePath) {
  const filePath = path.join(__dirname, "..", "ui", relativePath);
  assert.ok(fs.existsSync(filePath), `missing UI resource: ${relativePath}`);
  return fs.readFileSync(filePath, "utf8");
}

function createFakeElement() {
  return {
    hidden: false,
    textContent: "",
    className: "",
    innerHTML: "",
    value: "",
    disabled: false,
    listeners: {},
    addEventListener(type, handler) {
      this.listeners[type] = handler;
    }
  };
}

function createUiHarness() {
  const selectors = [
    "#authPanel",
    "#authTitle",
    "#authHint",
    "#authMessage",
    "#workspaceMessage",
    "#bootstrapForm",
    "#bootstrapUsername",
    "#bootstrapPassword",
    "#loginForm",
    "#loginUsername",
    "#loginPassword",
    "#workspace",
    "#sessionSummary",
    "#logoutButton",
    "#usersList",
    "#detailHint",
    "#userForm",
    "#detailUsername",
    "#detailEmail",
    "#userPlan",
    "#userExpiryDate",
    "#userExpiryTime",
    "#membershipMeta",
    "#deviceList"
  ];
  const elements = Object.fromEntries(selectors.map((selector) => [selector, createFakeElement()]));
  elements["#bootstrapUsername"].value = "admin";
  elements["#loginUsername"].value = "admin";
  elements["#userPlan"].value = "inactive";
  elements["#userExpiryTime"].value = "23:59";

  const responses = {
    "/api/admin/bootstrap/state": {ok: true, needs_bootstrap: false},
    "/api/admin/session": {
      ok: true,
      authenticated: true,
      user: {username: "root"}
    },
    "/api/admin/users": {
      ok: true,
      items: [
        {
          id: 7,
          username: "<img src=x onerror=alert(1)>",
          email: "<svg/onload=alert(2)>@mail.test",
          membership_plan: "member",
          membership_expires_at: "2026-05-01T12:30:00.000Z"
        }
      ]
    },
    "/api/admin/users/7/devices": {
      ok: true,
      items: [
        {
          id: 13,
          device_id: "<script>alert(3)</script>",
          created_at: "2026-04-20T08:00:00.000Z",
          last_used_at: "2026-04-20T08:30:00.000Z",
          expires_at: "2026-05-20T08:30:00.000Z"
        }
      ]
    }
  };

  const context = {
    console,
    setTimeout,
    clearTimeout,
    fetch: async (route) => {
      const payload = responses[route];
      if (!payload) {
        throw new Error(`Unexpected fetch route: ${route}`);
      }
      return {
        ok: true,
        headers: {
          get(name) {
            return String(name).toLowerCase() === "content-type" ? "application/json; charset=utf-8" : "";
          }
        },
        async json() {
          return payload;
        }
      };
    },
    window: {
      localStorage: {
        getItem() {
          return "session-token";
        },
        setItem() {},
        removeItem() {}
      },
      confirm() {
        return true;
      }
    },
    document: {
      querySelector(selector) {
        return elements[selector] || null;
      }
    }
  };

  return {context, elements};
}

async function flushPromises(count = 6) {
  for (let index = 0; index < count; index += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

async function executeUiApp() {
  const code = readUiFile("app.js");
  const harness = createUiHarness();
  vm.runInNewContext(code, harness.context, {
    filename: "program_admin_console/ui/app.js"
  });
  await flushPromises();
  return harness;
}

async function request(ctx, route) {
  const url = new URL(route, ctx.baseUrl);
  return new Promise((resolve, reject) => {
    const req = http.request(url, {method: "GET"}, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        resolve({
          status: res.statusCode || 0,
          text: Buffer.concat(chunks).toString("utf8"),
          headers: res.headers
        });
      });
    });
    req.on("error", reject);
    req.end();
  });
}

async function startServer() {
  const tempDir = makeTempDir();
  const dbPath = path.join(tempDir, "control-plane.sqlite");
  const server = createServer({
    dbPath,
    now() {
      return new Date("2026-04-20T08:00:00.000Z");
    },
    mailConfigFactory() {
      return {
        configured: true,
        authCodeTtlMinutes: 5,
        refreshSessionDays: 30,
        adminSessionHours: 12,
        keyId: "ed25519-2026-04"
      };
    },
    mailServiceFactory() {
      return {
        async sendVerificationCode() {
          return {messageId: "noop"};
        }
      };
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  return {
    tempDir,
    server,
    baseUrl: `http://127.0.0.1:${address.port}`
  };
}

async function stopServer(ctx) {
  await new Promise((resolve) => ctx.server.close(resolve));
  fs.rmSync(ctx.tempDir, {recursive: true, force: true});
}

async function main() {
  const html = readUiFile("index.html");
  readUiFile("app.js");
  readUiFile("styles.css");

  assert.match(html, /初始化超级管理员/);
  assert.match(html, /用户列表/);
  assert.match(html, /inactive/);
  assert.match(html, /workspaceMessage/);
  assert.doesNotMatch(html, /trial/);
  assert.doesNotMatch(html, /standard/);
  assert.doesNotMatch(html, /Steam binding/i);
  assert.doesNotMatch(html, /craft\./);

  const uiHarness = await executeUiApp();
  const {context, elements} = uiHarness;
  assert.match(elements["#usersList"].innerHTML, /member/);
  assert.doesNotMatch(elements["#usersList"].innerHTML, /<img/i);
  assert.doesNotMatch(elements["#usersList"].innerHTML, /<svg/i);
  assert.doesNotMatch(elements["#deviceList"].innerHTML, /<script/i);

  context.setMessage("保存失败", true);
  assert.equal(elements["#workspace"].hidden, false);
  assert.equal(elements["#workspaceMessage"].hidden, false);
  assert.equal(elements["#workspaceMessage"].textContent, "保存失败");
  assert.equal(elements["#authMessage"].hidden, true);

  const ctx = await startServer();
  try {
    const adminPage = await request(ctx, "/admin");
    assert.equal(adminPage.status, 200);
    assert.match(adminPage.headers["content-type"] || "", /text\/html/);
    assert.match(adminPage.text, /初始化超级管理员/);

    const script = await request(ctx, "/admin/app.js");
    assert.equal(script.status, 200);
    assert.match(script.headers["content-type"] || "", /javascript/);

    const stylesheet = await request(ctx, "/admin/styles.css");
    assert.equal(stylesheet.status, 200);
    assert.match(stylesheet.headers["content-type"] || "", /text\/css/);
  } finally {
    await stopServer(ctx);
  }

  console.log("control-plane-ui tests passed");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
