const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const vm = require("node:vm");
const zlib = require("node:zlib");

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

function createTrackedStorage(initialValue = "") {
  let storedValue = initialValue;
  const calls = {
    getItem: [],
    setItem: [],
    removeItem: []
  };
  return {
    calls,
    storage: {
      getItem(key) {
        calls.getItem.push(key);
        return storedValue || "";
      },
      setItem(key, value) {
        calls.setItem.push([key, value]);
        storedValue = String(value);
      },
      removeItem(key) {
        calls.removeItem.push(key);
        storedValue = "";
      }
    }
  };
}

function createJsonResponse(payload) {
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
}

function createUiHarness(options = {}) {
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
    "#userStatus",
    "#userPlan",
    "#userExpiryDate",
    "#userExpiryTime",
    "#membershipMeta",
    "#effectivePermissions",
    "#permissionOverrideProgramAccessEnabled",
    "#permissionOverrideRuntimeStart",
    "#permissionOverrideAccountBrowserQueryEnable",
    "#deviceList",
    "#sidebarCopy",
    "#pageHeader"
  ];
  const elements = Object.fromEntries(selectors.map((selector) => [selector, createFakeElement()]));
  const persistedToken = typeof options.persistedToken === "string" ? options.persistedToken : "session-token";
  const trackedStorage = createTrackedStorage(persistedToken);
  elements["#bootstrapUsername"].value = "admin";
  elements["#loginUsername"].value = "admin";
  elements["#userPlan"].value = "inactive";
  elements["#userExpiryTime"].value = "23:59";

  const responses = {
    "/api/admin/users": {
      ok: true,
      items: [
        {
          id: 7,
          username: "<img src=x onerror=alert(1)>",
          email: "<svg/onload=alert(2)>@mail.test",
          status: "disabled",
          membership_plan: "member",
          membership_expires_at: "2026-05-01T12:30:00.000Z",
          permission_overrides: [
            {
              feature_code: "account.browser_query.enable",
              enabled: true
            }
          ],
          entitlements: {
            membership_plan: "inactive",
            assigned_membership_plan: "member",
            membership_expires_at: "2026-05-01T12:30:00.000Z",
            membership_active: false,
            permissions: ["account.browser_query.enable"],
            feature_flags: {
              program_access_enabled: false
            }
          }
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
    fetch: async (route, requestOptions = {}) => {
      const authHeader = requestOptions && requestOptions.headers
        ? requestOptions.headers.Authorization || requestOptions.headers.authorization || ""
        : "";
      const payload = route === "/api/admin/session"
        ? (authHeader === `Bearer ${persistedToken}` && persistedToken
          ? {
            ok: true,
            authenticated: true,
            user: {username: "root"}
          }
          : {
            ok: true,
            authenticated: false,
            needs_bootstrap: false
          })
        : responses[route];
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
      localStorage: trackedStorage.storage,
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

  return {
    context,
    elements,
    localStorageCalls: trackedStorage.calls
  };
}

async function flushPromises(count = 6) {
  for (let index = 0; index < count; index += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

async function executeUiApp(options = {}) {
  const code = readUiFile("app.js");
  const harness = createUiHarness(options);
  vm.runInNewContext(code, harness.context, {
    filename: "program_admin_console/ui/app.js"
  });
  await flushPromises();
  return harness;
}

async function request(ctx, route, headers = null) {
  const url = new URL(route, ctx.baseUrl);
  return new Promise((resolve, reject) => {
    const req = http.request(url, {
      method: "GET",
      headers: headers && typeof headers === "object" ? headers : {}
    }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        const buffer = Buffer.concat(chunks);
        resolve({
          status: res.statusCode || 0,
          buffer,
          text: buffer.toString("utf8"),
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
        adminSessionHours: 12
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

  assert.match(html, /管理控制台/);
  assert.match(html, /用户列表/);
  assert.match(html, /inactive/);
  assert.match(html, /账号状态/);
  assert.match(html, /权限覆盖/);
  assert.match(html, /实际权限/);
  assert.match(html, /workspaceMessage/);
  assert.doesNotMatch(html, /trial/);
  assert.doesNotMatch(html, /standard/);
  assert.doesNotMatch(html, /Steam binding/i);
  assert.doesNotMatch(html, /craft\./);

  const uiHarness = await executeUiApp();
  const {context, elements} = uiHarness;
  context.saveToken("session-token");
  await context.loadSession();
  await context.loadDashboard();
  assert.match(elements["#usersList"].innerHTML, /member/);
  assert.doesNotMatch(elements["#usersList"].innerHTML, /<img/i);
  assert.doesNotMatch(elements["#usersList"].innerHTML, /<svg/i);
  assert.doesNotMatch(elements["#deviceList"].innerHTML, /<script/i);
  assert.equal(elements["#userStatus"].value, "disabled");
  assert.equal(elements["#permissionOverrideProgramAccessEnabled"].value, "inherit");
  assert.equal(elements["#permissionOverrideRuntimeStart"].value, "inherit");
  assert.equal(elements["#permissionOverrideAccountBrowserQueryEnable"].value, "force_on");
  assert.match(elements["#effectivePermissions"].innerHTML, /account\.browser_query\.enable/);

  context.setMessage("保存失败", true);
  assert.equal(elements["#workspace"].hidden, false);
  assert.equal(elements["#workspaceMessage"].hidden, false);
  assert.equal(elements["#workspaceMessage"].textContent, "保存失败");
  assert.equal(elements["#authMessage"].hidden, true);

  const submitHarness = await executeUiApp();
  const submittedBodies = [];
  const mutableUser = {
    id: 7,
    username: "alice",
    email: "alice@example.com",
    status: "active",
    membership_plan: "member",
    membership_expires_at: "2026-05-01T12:30:00.000Z",
    permission_overrides: [],
    entitlements: {
      membership_plan: "member",
      assigned_membership_plan: "member",
      membership_expires_at: "2026-05-01T12:30:00.000Z",
      membership_active: true,
      permissions: ["program_access_enabled", "runtime.start"],
      feature_flags: {
        program_access_enabled: true
      }
    }
  };
  submitHarness.context.fetch = async (route, requestOptions = {}) => {
    const method = String(requestOptions.method || "GET").toUpperCase();
    if (route === "/api/admin/session") {
      return createJsonResponse({
        ok: true,
        authenticated: true,
        user: {username: "root"}
      });
    }
    if (route === "/api/admin/users" && method === "GET") {
      return createJsonResponse({
        ok: true,
        items: [mutableUser]
      });
    }
    if (route === "/api/admin/users/7/devices" && method === "GET") {
      return createJsonResponse({
        ok: true,
        items: []
      });
    }
    if (route === "/api/admin/users/7" && method === "PATCH") {
      const payload = JSON.parse(String(requestOptions.body || "{}"));
      submittedBodies.push(payload);
      mutableUser.status = payload.status;
      mutableUser.membership_plan = payload.membership_plan;
      mutableUser.membership_expires_at = payload.membership_expires_at;
      mutableUser.permission_overrides = payload.permission_overrides;
      mutableUser.entitlements = {
        membership_plan: payload.status === "disabled" ? "inactive" : payload.membership_plan,
        assigned_membership_plan: payload.membership_plan,
        membership_expires_at: payload.membership_expires_at,
        membership_active: payload.status === "active",
        permissions: ["program_access_enabled"],
        feature_flags: {
          program_access_enabled: true
        }
      };
      return createJsonResponse({
        ok: true,
        user: mutableUser,
        entitlements: mutableUser.entitlements
      });
    }
    throw new Error(`Unexpected fetch route: ${route}`);
  };
  submitHarness.context.saveToken("session-token");
  await submitHarness.context.loadSession();
  await submitHarness.context.loadDashboard();
  submitHarness.elements["#userStatus"].value = "disabled";
  submitHarness.elements["#permissionOverrideProgramAccessEnabled"].value = "force_on";
  submitHarness.elements["#permissionOverrideRuntimeStart"].value = "force_off";
  submitHarness.elements["#permissionOverrideAccountBrowserQueryEnable"].value = "inherit";
  await submitHarness.context.handleUserSubmit({
    preventDefault() {}
  });
  assert.deepEqual(submittedBodies, [
    {
      status: "disabled",
      membership_plan: "member",
      membership_expires_at: "2026-05-01T12:30:00.000Z",
      permission_overrides: [
        {
          feature_code: "program_access_enabled",
          enabled: true
        },
        {
          feature_code: "runtime.start",
          enabled: false
        }
      ]
    }
  ]);

  const staleSelectionHarness = await executeUiApp();
  const staleRejections = [];
  const onUnhandledRejection = (reason) => {
    staleRejections.push(reason);
  };
  process.on("unhandledRejection", onUnhandledRejection);
  try {
    staleSelectionHarness.context.saveToken("session-token");
    await staleSelectionHarness.context.loadSession();
    await staleSelectionHarness.context.loadDashboard();
    staleSelectionHarness.context.fetch = async (route) => {
      if (route === "/api/admin/users") {
        return createJsonResponse({
          ok: true,
          items: [
            {
              id: 8,
              username: "bob",
              email: "bob@example.com",
              membership_plan: "inactive",
              membership_expires_at: ""
            }
          ]
        });
      }
      if (route === "/api/admin/users/7/devices") {
        throw new Error("stale selected user");
      }
      if (route === "/api/admin/users/8/devices") {
        return createJsonResponse({
          ok: true,
          items: [
            {
              id: 21,
              device_id: "device-b",
              created_at: "2026-04-20T09:00:00.000Z",
              last_used_at: "2026-04-20T09:05:00.000Z",
              expires_at: "2026-05-20T09:05:00.000Z"
            }
          ]
        });
      }
      throw new Error(`Unexpected fetch route: ${route}`);
    };
    await staleSelectionHarness.context.loadDashboard();
    await flushPromises(12);
    assert.equal(staleSelectionHarness.elements["#detailUsername"].textContent, "bob");
    assert.equal(staleSelectionHarness.elements["#deviceList"].innerHTML.includes("device-b"), true);
    assert.deepEqual(staleRejections, []);
  } finally {
    process.removeListener("unhandledRejection", onUnhandledRejection);
  }

  const persistedTokenHarness = await executeUiApp({persistedToken: "legacy-admin-token"});
  assert.equal(persistedTokenHarness.elements["#authPanel"].hidden, false);
  assert.equal(persistedTokenHarness.elements["#workspace"].hidden, true);
  assert.equal(persistedTokenHarness.elements["#sessionSummary"].textContent, "尚未登录");
  assert.deepEqual(persistedTokenHarness.localStorageCalls.getItem, []);
  assert.deepEqual(persistedTokenHarness.localStorageCalls.setItem, []);
  assert.deepEqual(persistedTokenHarness.localStorageCalls.removeItem, ["program_admin_console_token"]);
  persistedTokenHarness.context.saveToken("fresh-admin-token");
  assert.deepEqual(persistedTokenHarness.localStorageCalls.setItem, []);

  const ctx = await startServer();
  try {
    const adminPage = await request(ctx, "/admin");
    assert.equal(adminPage.status, 200);
    assert.match(adminPage.headers["content-type"] || "", /text\/html/);
    assert.match(adminPage.text, /管理控制台/);

    const script = await request(ctx, "/admin/app.js");
    assert.equal(script.status, 200);
    assert.match(script.headers["content-type"] || "", /javascript/);

    const gzippedScript = await request(ctx, "/admin/app.js", {
      "Accept-Encoding": "gzip"
    });
    assert.equal(gzippedScript.status, 200);
    assert.equal(gzippedScript.headers["content-encoding"], "gzip");
    assert.equal(gzippedScript.headers.vary, "Accept-Encoding");
    assert.match(zlib.gunzipSync(gzippedScript.buffer).toString("utf8"), /LEGACY_TOKEN_STORAGE_KEY/);

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
